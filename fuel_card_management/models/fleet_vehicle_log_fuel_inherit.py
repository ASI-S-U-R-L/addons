# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class FleetVehicleLogFuelInherit(models.Model):
    _inherit = "fleet.vehicle.log.fuel"
    _order = 'date desc'

    # Campo número de ticket (entrada manual)
    ticket_number = fields.Char(
        string='Número de Ticket',
        help="Número de ticket del abastecimiento",
        states={'done': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )
    
    # CAMBIO: Modificar el dominio para mostrar SOLO las tarjetas asignadas
    card_main_id = fields.Many2one(
        'fuel.magnetic.card',
        string='Tarjeta',
        domain="[('operational_state', '=', 'assigned')]",  # Solo tarjetas asignadas
        states={'done': [('readonly', True)], 'cancelled': [('readonly', True)]},
        help="Tarjeta magnética utilizada para el abastecimiento (solo tarjetas asignadas)"
    )

    # Campo relacionado para mostrar el saldo de la tarjeta
    card_current_balance = fields.Float(
        string='Saldo Tarjeta',
        related='card_main_id.current_balance',
        readonly=True,
        help="Saldo actual de la tarjeta seleccionada"
    )

    # NUEVO CAMPO: Para que el dominio de selected_carrier_id funcione en la vista
    card_carrier_ids = fields.Many2many(
        'fuel.carrier',
        string='Portadores de la Tarjeta',
        compute='_compute_card_carrier_ids',
        readonly=True,
        store=False, # No es necesario almacenar, se calcula dinámicamente
    )

    selected_carrier_id = fields.Many2one(
        'fuel.carrier',
        string='Portador de Combustible',
        # El dominio ahora usa el nuevo campo computado card_carrier_ids
        domain="[('id', 'in', card_carrier_ids)]", 
        states={'done': [('readonly', True)], 'cancelled': [('readonly', True)]},
        help="Portador de combustible utilizado en este abastecimiento (debe estar entre los de la tarjeta)"
    )

    # Sobrescribir el campo price_per_liter para que sea computado
    price_per_liter = fields.Float(
        string='Precio por Litro',
        digits=(16, 3),
        readonly=True, # Will be set by onchange, but read-only in UI
        help="Precio automático según el portador seleccionado"
    )

    # Campo para rastrear si ya se descontó el saldo
    balance_deducted = fields.Boolean(
        string='Saldo Descontado',
        default=False,
        readonly=True,
        help="Indica si ya se descontó el saldo de la tarjeta"
    )

    @api.depends('card_main_id')
    def _compute_card_carrier_ids(self):
        """Calcula los portadores disponibles para la tarjeta seleccionada."""
        for record in self:
            record.card_carrier_ids = record.card_main_id.carrier_ids

    @api.constrains('liter', 'card_main_id', 'selected_carrier_id')
    def _check_card_and_carrier_required(self):
        """Validar que se seleccione tarjeta y portador si hay litros cargados"""
        for record in self:
            if record.liter > 0:
                if not record.card_main_id:
                    raise ValidationError(_("Debe seleccionar una tarjeta cuando hay litros registrados."))
                if not record.selected_carrier_id:
                    raise ValidationError(_("Debe seleccionar un portador de combustible para el abastecimiento."))

    @api.constrains('card_main_id', 'liter', 'price_per_liter')
    def _check_card_balance(self):
        """Validar que la tarjeta tenga saldo suficiente"""
        for record in self:
            # Only validate if state is not cancelled, there's a card, liters, and price is defined
            if record.card_main_id and record.liter > 0 and record.state != 'cancelled' and record.price_per_liter > 0:
                total_amount = record.liter * record.price_per_liter
                if record.card_main_id.current_balance < total_amount:
                    raise ValidationError(_(
                        'Saldo insuficiente en tarjeta %s.\n'
                        'Saldo actual: %.2f\n'
                        'Monto requerido: %.2f'
                    ) % (record.card_main_id.name, record.card_main_id.current_balance, total_amount))

    @api.constrains('vehicle_id')
    def _check_vehicle_availability_for_fuel_log(self):
        """
        Valida que no se pueda registrar combustible para un vehículo si:
        1. Su estado general indica que está inactivo (ej. 'Out of Service', 'Retired').
        2. Tiene servicios de mantenimiento activos (estado 'open').
        """
        for record in self:
            if not record.vehicle_id:
                continue

            vehicle = record.vehicle_id

            # 1. Verificar el estado general del vehículo
            # Asumimos que 'Out of Service' o 'Retired' indican que el vehículo no está disponible para uso.
            # Estos son nombres comunes para los estados en el módulo fleet base.
            if vehicle.state_id and vehicle.state_id.name in ['Out of Service', 'Retired']:
                raise ValidationError(_(
                    "No se puede registrar combustible para el vehículo '%s' porque su estado actual es '%s'. "
                    "El vehículo está inhabilitado para operaciones."
                ) % (vehicle.name, vehicle.state_id.name))

            # 2. Verificar si tiene servicios de mantenimiento activos
            # Un servicio en estado 'open' significa que está en curso y el vehículo no debería usarse.
            active_services = self.env['fleet.vehicle.log.services'].search([
                ('vehicle_id', '=', vehicle.id),
                ('state', '=', 'open'), # 'open' es el estado por defecto para servicios en curso
            ])
            if active_services:
                service_names = ', '.join(active_services.mapped('name'))
                raise ValidationError(_(
                    "No se puede registrar combustible para el vehículo '%s' porque tiene servicios de mantenimiento activos: %s. "
                    "El vehículo está inhabilitado para operaciones."
                ) % (vehicle.name, service_names))

    @api.onchange('card_main_id')
    def _onchange_card_main_id(self):
        """Actualizar vehículo y portador automáticamente cuando cambia la tarjeta"""
        if self.card_main_id:
            # If the card has an assigned vehicle, use it automatically
            if self.card_main_id.vehicle_id:
                self.vehicle_id = self.card_main_id.vehicle_id
            else:
                # If the card has no assigned vehicle, show warning
                if not self.vehicle_id: # Only if a vehicle is not already selected
                    return {
                        'warning': {
                            'title': _('Tarjeta sin Vehículo'),
                            'message': _(
                                'La tarjeta %s no tiene vehículo asignado. '
                                'Debe seleccionar un vehículo manualmente.'
                            ) % self.card_main_id.name
                        }
                    }
            
            # Autoselect carrier if only one is available for the card
            if len(self.card_main_id.carrier_ids) == 1:
                self.selected_carrier_id = self.card_main_id.carrier_ids[0]
            else:
                self.selected_carrier_id = False # Clear if multiple or none
            
            # Validate available balance if there are liters and price is already determined
            if self.liter > 0 and self.price_per_liter > 0: # Check price_per_liter directly now
                total_amount = self.liter * self.price_per_liter
                if self.card_main_id.current_balance < total_amount:
                    return {
                        'warning': {
                            'title': _('Saldo Insuficiente'),
                            'message': _(
                                'La tarjeta %s tiene saldo insuficiente.\n'
                                'Saldo actual: %.2f\n'
                                'Monto requerido: %.2f'
                            ) % (self.card_main_id.name, self.card_main_id.current_balance, total_amount)
                        }
                    }
        else:
            self.selected_carrier_id = False # Clear selected carrier if card is cleared
            self.price_per_liter = 0.0 # Clear price if card is cleared

    @api.onchange('selected_carrier_id')
    def _onchange_selected_carrier_id(self):
        """Update price per liter when the selected carrier changes"""
        if self.selected_carrier_id:
            self.price_per_liter = self.selected_carrier_id.current_price
        else:
            self.price_per_liter = 0.0
        
        # Re-evaluate balance if there are liters when changing the carrier
        if self.card_main_id and self.liter > 0 and self.price_per_liter > 0:
            total_amount = self.liter * self.price_per_liter
            if self.card_main_id.current_balance < total_amount:
                return {
                    'warning': {
                        'title': _('Saldo Insuficiente'),
                        'message': _(
                            'La tarjeta %s tiene saldo insuficiente.\n'
                            'Saldo actual: %.2f\n'
                            'Monto requerido: %.2f'
                        ) % (self.card_main_id.name, self.card_main_id.current_balance, total_amount)
                    }
                }

    @api.model
    def create(self, vals):
        """Overwrite create to ensure vehicle_id is present and validate carrier"""
        # If no vehicle_id but there's a card_main_id, try to get it from the card
        if not vals.get('vehicle_id') and vals.get('card_main_id'):
            card = self.env['fuel.magnetic.card'].browse(vals['card_main_id'])
            if card.vehicle_id:
                vals['vehicle_id'] = card.vehicle_id.id
        
        # If still no vehicle_id, search for the first active vehicle
        if not vals.get('vehicle_id'):
            vehicle = self.env['fleet.vehicle'].search([('active', '=', True)], limit=1)
            if vehicle:
                vals['vehicle_id'] = vehicle.id
            else:
                raise ValidationError(_("No hay vehículos activos disponibles. Debe crear al menos un vehículo."))
        
        # If there are liters and a card, ensure selected_carrier_id and price_per_liter are present
        if vals.get('liter', 0) > 0 and vals.get('card_main_id') and not vals.get('selected_carrier_id'):
            card = self.env['fuel.magnetic.card'].browse(vals['card_main_id'])
            if len(card.carrier_ids) == 1: # If only one carrier available, auto-assign
                vals['selected_carrier_id'] = card.carrier_ids[0].id
                vals['price_per_liter'] = card.carrier_ids[0].current_price
            else:
                # If multiple carriers are available, or none, and it's not set, raise error.
                raise ValidationError(_("Debe seleccionar un portador de combustible para el abastecimiento."))
        elif vals.get('liter', 0) > 0 and vals.get('selected_carrier_id') and 'price_per_liter' not in vals:
            # If selected_carrier_id is provided but price_per_liter is not, set it
            carrier = self.env['fuel.carrier'].browse(vals['selected_carrier_id'])
            vals['price_per_liter'] = carrier.current_price


        return super().create(vals)

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """
        Handles vehicle-card consistency and vehicle availability checks.
        """
        res = {} # Dictionary to hold warnings

        if self.vehicle_id:
            vehicle = self.vehicle_id

            # 1. Check general vehicle state for unavailability
            if vehicle.state_id and vehicle.state_id.name in ['Out of Service', 'Retired']:
                res['warning'] = {
                    'title': _('Vehículo Inhabilitado'),
                    'message': _(
                        "El vehículo '%s' está inhabilitado para operaciones porque su estado actual es '%s'. "
                        "No se recomienda registrar combustible."
                    ) % (vehicle.name, vehicle.state_id.name)
                }
                return res # Return immediately if a critical warning is found

            # 2. Check for active service records
            active_services = self.env['fleet.vehicle.log.services'].search([
                ('vehicle_id', '=', vehicle.id),
                ('state', '=', 'open'),
            ])
            if active_services:
                service_names = ', '.join(active_services.mapped('name'))
                res['warning'] = {
                    'title': _('Servicios Activos'),
                    'message': _(
                        "El vehículo '%s' tiene servicios de mantenimiento activos: %s. "
                        "No se recomienda registrar combustible."
                    ) % (vehicle.name, service_names)
                }
                return res # Return immediately if a critical warning is found

            # 3. Existing logic: Validate consistency between vehicle and card
            if self.card_main_id:
                if self.card_main_id.vehicle_id and self.card_main_id.vehicle_id != self.vehicle_id:
                    res['warning'] = {
                        'title': _('Inconsistencia Vehículo-Tarjeta'),
                        'message': _(
                            'El vehículo seleccionado (%s) no coincide con el vehículo '
                            'asignado a la tarjeta (%s).\n'
                            'Se recomienda usar el vehículo de la tarjeta para mantener consistencia.'
                        ) % (self.vehicle_id.name, self.card_main_id.vehicle_id.name)
                    }
        
        return res # Return the accumulated warnings, or empty dict if none

    @api.onchange('liter')
    def _onchange_liter(self):
        """Validar saldo cuando cambian los litros"""
        if self.card_main_id and self.liter > 0 and self.price_per_liter > 0: # Ensure price is set
            total_amount = self.liter * self.price_per_liter
            if self.card_main_id.current_balance < total_amount:
                return {
                    'warning': {
                        'title': _('Saldo Insuficiente'),
                        'message': _(
                            'La tarjeta %s tiene saldo insuficiente.\n'
                            'Saldo actual: %.2f\n'
                            'Monto requerido: %.2f'
                        ) % (self.card_main_id.name, self.card_main_id.current_balance, total_amount)
                    }
                }

    def button_done(self):
        """Overwrite to deduct card balance and validate carrier"""
        for record in self:
            if not record.vehicle_id:
                raise ValidationError(_("Debe seleccionar un vehículo antes de confirmar."))
            if record.liter > 0 and not record.selected_carrier_id:
                raise ValidationError(_("Debe seleccionar un portador de combustible para el abastecimiento antes de confirmar."))

        result = super().button_done()
        
        for record in self.filtered(lambda x: x.state == 'done' and not x.balance_deducted):
            if record.card_main_id and record.liter > 0:
                record._deduct_card_balance()
                record.balance_deducted = True
                
        return result

    def button_cancel(self):
        """Sobrescribir para revertir descuento de saldo"""
        # Revertir descuentos antes de cancelar
        for record in self.filtered(lambda x: x.balance_deducted and x.card_main_id):
            record._revert_card_balance()
            record.balance_deducted = False
            
        # Ejecutar lógica original
        return super().button_cancel()

    def _deduct_card_balance(self):
        """Descuenta saldo de la tarjeta y registra el movimiento"""
        self.ensure_one()
        if not self.card_main_id or self.liter <= 0:
            return
            
        total_amount = self.amount
        card = self.card_main_id
        
        # Verificar saldo suficiente
        if card.current_balance < total_amount:
            raise UserError(_(
                'Saldo insuficiente en tarjeta %s.\n'
                'Saldo actual: %.2f\n'
                'Monto a descontar: %.2f'
            ) % (card.name, card.current_balance, total_amount))
        
        # Descontar saldo
        new_balance = card.current_balance - total_amount
        card.write({'current_balance': new_balance})
        
        card.message_post(
            body=_(
                "Descuento por abastecimiento:<br/>"
                "• Vehículo: %s<br/>"
                "• Tarjeta: %s<br/>" # Add card name for clarity
                "• Portador: %s<br/>" # Add selected carrier
                "• Fecha: %s<br/>"
                "• Litros: %.2f<br/>"
                "• Precio/L: %.3f<br/>"
                "• Monto: %.2f<br/>"
                "• Ticket: %s<br/>"
                "• Saldo anterior: %.2f<br/>"
                "• Saldo actual: %.2f"
            ) % (
                self.vehicle_id.name,
                self.card_main_id.name,
                self.selected_carrier_id.name, # Use selected_carrier_id
                self.date,
                self.liter,
                self.price_per_liter,
                total_amount,
                self.ticket_number or 'N/A',
                card.current_balance + total_amount,
                card.current_balance
            ),
            subject=_("Abastecimiento de Combustible")
        )

        _logger.info(
            f"Saldo descontado - Tarjeta: {card.name}, "
            f"Portador: {self.selected_carrier_id.name}, "
            f"Monto: {total_amount}, Saldo restante: {card.current_balance}"
        )

    def _revert_card_balance(self):
        """Revierte el descuento de saldo de la tarjeta"""
        self.ensure_one()
        if not self.card_main_id or self.liter <= 0:
            return
            
        total_amount = self.amount
        card = self.card_main_id
        
        # Revertir saldo
        new_balance = card.current_balance + total_amount
        card.write({'current_balance': new_balance})
        
        # Registrar movimiento
        card.message_post(
            body=_(
                "Reversión por cancelación:<br/>"
                "• Monto revertido: %.2f<br/>"
                "• Saldo actual: %.2f"
            ) % (total_amount, card.current_balance),
            subject=_("Reversión de Abastecimiento")
        )
        
        _logger.info(
            f"Saldo revertido - Tarjeta: {card.name}, "
            f"Monto: {total_amount}, Saldo actual: {card.current_balance}"
        )

    def unlink(self):
        """Prevenir eliminación de logs que ya descontaron saldo"""
        for record in self:
            if record.balance_deducted and record.state == 'done':
                raise ValidationError(_(
                    'No se puede eliminar un registro que ya descontó saldo de la tarjeta. '
                    'Primero debe cancelarlo.'
                ))
        return super().unlink()

