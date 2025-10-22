# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class FuelCardBalanceReportWizard(models.TransientModel):
    _name = 'fuel.card.balance.report.wizard'
    _description = 'Asistente para Informe de Balance Contable de Combustible'
    
    date_from = fields.Date(string='Fecha Inicial', required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Fecha Final', required=True, default=lambda self: fields.Date.today())
    carrier_ids = fields.Many2many('fuel.carrier', string='Portadores')
    card_ids = fields.Many2many('fuel.magnetic.card', string='Tarjetas')
    include_inactive = fields.Boolean(string='Incluir Tarjetas Inactivas', default=False)
    
    def _get_initial_balance(self, card, date_from):
        """Obtiene el saldo inicial de la tarjeta a la fecha inicial (en litros y valor monetario)"""
        initial_liters = 0.0
        initial_value = 0.0
        
        # Obtener el precio actual del portador principal de la tarjeta para conversiones
        # Si la tarjeta tiene múltiples portadores, se usa el primero para esta conversión
        card_price = card.carrier_id.current_price if card.carrier_id else 0.0

        # Cargas antes de la fecha inicial
        loads = self.env['fuel.card.load'].search([
            ('card_id', '=', card.id),
            ('date', '<', date_from),
            ('state', '=', 'confirmed')
        ])
        for load in loads:
            initial_liters += load.amount # Litros cargados
            initial_value += load.amount * load.carrier_id.current_price # Valor monetario de la carga

        # Consumos (fleet.vehicle.log.fuel) antes de la fecha inicial
        consumptions = self.env['fleet.vehicle.log.fuel'].search([
            ('card_main_id', '=', card.id), # Usar card_main_id para el modelo de consumo
            ('date', '<', date_from),
            ('state', '=', 'done') # Usar estado 'done' para consumos confirmados
        ])
        for consumption in consumptions:
            initial_liters -= consumption.liter # Litros consumidos
            initial_value -= consumption.amount # Valor monetario consumido

        # Ajustes antes de la fecha inicial
        adjustments = self.env['fuel.balance.adjustment'].search([
            ('card_id', '=', card.id),
            ('date', '<', date_from),
            ('state', '=', 'confirmed')
        ])
        for adj in adjustments:
            adj_value = adj.amount if adj.adjustment_type == 'increase' else -adj.amount
            initial_value += adj_value
            if card_price > 0: # Convertir ajuste monetario a litros si el precio está disponible
                initial_liters += adj_value / card_price

        # Transferencias antes de la fecha inicial
        transfers_in = self.env['fuel.balance.transfer'].search([
            ('target_card_id', '=', card.id),
            ('date', '<', date_from),
            ('state', '=', 'confirmed')
        ])
        transfers_out = self.env['fuel.balance.transfer'].search([
            ('source_card_id', '=', card.id),
            ('date', '<', date_from),
            ('state', '=', 'confirmed')
        ])
        for transfer in transfers_in:
            initial_value += transfer.amount
            if card_price > 0:
                initial_liters += transfer.amount / card_price
        for transfer in transfers_out:
            initial_value -= transfer.amount
            if card_price > 0:
                initial_liters -= transfer.amount / card_price
        
        return initial_liters, initial_value
    
    def _get_loaded_amount(self, card, date_from, date_to):
        """Obtiene el monto cargado en el período (en litros y valor monetario)"""
        domain = [
            ('card_id', '=', card.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('state', '=', 'confirmed')
        ]
        
        loads = self.env['fuel.card.load'].search(domain)
        load_liters = sum(loads.mapped('amount'))
        # Calcular el valor monetario sumando el valor de cada carga individualmente
        load_value = sum(load.amount * load.carrier_id.current_price for load in loads)
        
        return load_liters, load_value
    
    def _get_consumption_amount(self, card, date_from, date_to):
        """Obtiene el monto consumido en el período (en litros y valor monetario)"""
        domain = [
            ('card_main_id', '=', card.id), # Usar card_main_id para el modelo de consumo
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('state', '=', 'done') # Usar estado 'done' para consumos confirmados
        ]
        
        consumptions = self.env['fleet.vehicle.log.fuel'].search(domain) # Usar el modelo correcto
        consumption_liters = sum(consumptions.mapped('liter')) # Litros consumidos
        consumption_value = sum(consumptions.mapped('amount')) # Valor monetario consumido
        
        return consumption_liters, consumption_value
    
    def _get_adjustment_amount(self, card, date_from, date_to):
        """Obtiene el monto de ajustes y transferencias en el período (en litros y valor monetario)"""
        total_liters = 0.0
        total_value = 0.0
        
        # Obtener el precio actual del portador principal de la tarjeta para conversiones
        card_price = card.carrier_id.current_price if card.carrier_id else 0.0

        # Ajustes
        adjustment_domain = [
            ('card_id', '=', card.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('state', '=', 'confirmed')
        ]
        
        adjustments = self.env['fuel.balance.adjustment'].search(adjustment_domain)
        for adj in adjustments:
            adj_value = adj.amount if adj.adjustment_type == 'increase' else -adj.amount
            total_value += adj_value
            if card_price > 0:
                total_liters += adj_value / card_price

        # Transferencias entrantes
        transfers_in = self.env['fuel.balance.transfer'].search([
            ('target_card_id', '=', card.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('state', '=', 'confirmed')
        ])
        for transfer in transfers_in:
            total_value += transfer.amount
            if card_price > 0:
                total_liters += transfer.amount / card_price
        
        # Transferencias salientes
        transfers_out = self.env['fuel.balance.transfer'].search([
            ('source_card_id', '=', card.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('state', '=', 'confirmed')
        ])
        for transfer in transfers_out:
            total_value -= transfer.amount
            if card_price > 0:
                total_liters -= transfer.amount / card_price
        
        return total_liters, total_value
    
    def _get_final_balance(self, initial_liters, loaded_liters, consumption_liters, adjustment_liters):
        """Calcula el saldo final en litros"""
        final_liters = initial_liters + loaded_liters - consumption_liters + adjustment_liters
        return final_liters
    
    def _prepare_report_data(self):
        """Prepara los datos para el informe"""
        self.ensure_one()
        
        # Dominio para las tarjetas
        card_domain = []
        if self.card_ids:
            card_domain.append(('id', 'in', self.card_ids.ids))
        if self.carrier_ids:
            card_domain.append(('carrier_id', 'in', self.carrier_ids.ids))
        if not self.include_inactive:
            card_domain.append(('state', '!=', 'cancelled'))
        
        cards = self.env['fuel.magnetic.card'].search(card_domain)
        
        # Agrupar tarjetas por portador
        cards_by_carrier = {}
        for card in cards:
            carrier = card.carrier_id # Usar el portador principal de la tarjeta para agrupar
            if carrier not in cards_by_carrier:
                cards_by_carrier[carrier] = []
            cards_by_carrier[carrier].append(card)
        
        # Preparar datos del informe
        report_data = []
        carrier_totals = {}
        
        for carrier, carrier_cards in cards_by_carrier.items():
            carrier_name = carrier.name if carrier else _('Sin Portador')
            carrier_total = {
                'initial_balance': 0.0, # Litros
                'initial_value': 0.0,
                'loaded_amount': 0.0, # Litros
                'loaded_value': 0.0,
                'consumption_amount': 0.0, # Litros
                'consumption_value': 0.0,
                'adjustment_amount': 0.0, # Litros
                'adjustment_value': 0.0,
                'final_balance': 0.0, # Litros
                'final_value': 0.0,
            }
            
            for card in carrier_cards:
                # Obtener datos para cada tarjeta (litros y valor monetario)
                initial_liters, initial_value = self._get_initial_balance(card, self.date_from)
                loaded_liters, loaded_value = self._get_loaded_amount(card, self.date_from, self.date_to)
                consumption_liters, consumption_value = self._get_consumption_amount(card, self.date_from, self.date_to)
                adjustment_liters, adjustment_value = self._get_adjustment_amount(card, self.date_from, self.date_to)
                
                # Calcular saldo final en litros
                final_liters = self._get_final_balance(initial_liters, loaded_liters, consumption_liters, adjustment_liters)
                price = carrier.current_price if carrier else 0.0
                final_value = final_liters * price # Calcular valor final basado en litros finales y precio actual del portador

                # Añadir datos de la tarjeta como valores planos
                card_data = {
                    'card_name': card.name,
                    'card_number': card.name, # Usar name para number, ya que es el campo de 16 dígitos
                    'carrier_name': carrier_name,
                    'initial_balance': initial_liters,
                    'initial_value': initial_value,
                    'loaded_amount': loaded_liters,
                    'loaded_value': loaded_value,
                    'consumption_amount': consumption_liters,
                    'consumption_value': consumption_value,
                    'adjustment_amount': adjustment_liters,
                    'adjustment_value': adjustment_value,
                    'final_balance': final_liters,
                    'final_value': final_value,
                }
                report_data.append(card_data)
                
                # Actualizar totales del portador
                carrier_total['initial_balance'] += initial_liters
                carrier_total['initial_value'] += initial_value
                carrier_total['loaded_amount'] += loaded_liters
                carrier_total['loaded_value'] += loaded_value
                carrier_total['consumption_amount'] += consumption_liters
                carrier_total['consumption_value'] += consumption_value
                carrier_total['adjustment_amount'] += adjustment_liters
                carrier_total['adjustment_value'] += adjustment_value
                carrier_total['final_balance'] += final_liters
                carrier_total['final_value'] += final_value
            
            carrier_totals[carrier_name] = carrier_total
        
        return {
            'report_data': report_data,
            'carrier_totals': carrier_totals,
            'date_from': self.date_from,
            'date_to': self.date_to,
        }
    
    def action_print_report(self):
        """Imprime el informe en PDF"""
        self.ensure_one()
        
        # Añadir depuración
        data = self._prepare_report_data()
        _logger.info("Generando informe de balance contable de combustible")
        _logger.info("Fecha desde: %s, Fecha hasta: %s", data['date_from'], data['date_to'])
        _logger.info("Número de tarjetas: %s", len(data['report_data']))
        
        return self.env.ref('fuel_card_management.action_report_fuel_card_balance').report_action(self, data=data)
    
    def action_preview_report(self):
        """Muestra una vista previa del informe en HTML"""
        self.ensure_one()
        
        data = self._prepare_report_data()
        
        return self.env.ref('fuel_card_management.action_report_fuel_card_balance_html').report_action(self, data=data)
    
    def action_select_carrier_cards(self):
        """Selecciona todas las tarjetas de los portadores seleccionados"""
        self.ensure_one()
        
        if not self.carrier_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Advertencia'),
                    'message': _('Debe seleccionar al menos un portador.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Buscar todas las tarjetas de los portadores seleccionados
        domain = [('carrier_id', 'in', self.carrier_ids.ids)]
        if not self.include_inactive:
            domain.append(('state', '!=', 'cancelled'))
        
        cards = self.env['fuel.magnetic.card'].search(domain)
        
        if not cards:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Información'),
                    'message': _('No se encontraron tarjetas para los portadores seleccionados.'),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Actualizar las tarjetas seleccionadas
        self.write({'card_ids': [(6, 0, cards.ids)]})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Éxito'),
                'message': _('Se han seleccionado %s tarjetas.') % len(cards),
                'type': 'success',
                'sticky': False,
            }
        }

