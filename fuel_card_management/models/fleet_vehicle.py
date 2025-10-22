# -*- coding: utf-8 -*-
from odoo import models, fields, api

class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'
   
    plan_to_change_car = fields.Boolean(string='Plan to Change Car', default=False)
    
    # Campos para gestión de combustible
    fuel_type = fields.Many2one(
        'fuel.carrier', 
        string='Tipo de Combustible',
        help='Seleccionar el portador de combustible para este vehículo'
    )
    
    tank_capacity = fields.Float(string='Capacidad del Tanque (L)', default=0.0)
    average_consumption = fields.Float(string='Consumo Promedio (L/100km)', default=0.0)
    fuel_notes = fields.Text(string='Notas de Combustible')
    
    # Relaciones con el módulo de tarjetas de combustible
    fuel_card_ids = fields.One2many('fuel.magnetic.card', 'vehicle_id', string='Tarjetas de Combustible')
    fuel_card_count = fields.Integer(compute='_compute_fuel_card_count', string='Número de Tarjetas')
    
    # CORREGIDO: Cambiar fuel.ticket por fleet.vehicle.log.fuel
    fuel_consumption_ids = fields.One2many('fleet.vehicle.log.fuel', 'vehicle_id', string='Consumo de Combustible')
    total_fuel_consumed = fields.Float(compute='_compute_total_fuel_consumed', string='Total Combustible Consumido (L)')
    
    @api.depends('fuel_card_ids')
    def _compute_fuel_card_count(self):
        for vehicle in self:
            vehicle.fuel_card_count = len(vehicle.fuel_card_ids)
    
    @api.depends('fuel_consumption_ids')
    def _compute_total_fuel_consumed(self):
        for vehicle in self:
            # CORREGIDO: Cambiar 'confirmed' por 'done' y 'liters' por 'liter'
            vehicle.total_fuel_consumed = sum(vehicle.fuel_consumption_ids.filtered(lambda t: t.state == 'done').mapped('liter'))
    
    def action_view_fuel_cards(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tarjetas de Combustible',
            'res_model': 'fuel.magnetic.card',
            'view_mode': 'tree,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id, 'default_card_type': 'vehicle'}
        }
    
    def action_view_fuel_consumption(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Consumo de Combustible',
            'res_model': 'fleet.vehicle.log.fuel',  # CORREGIDO: Cambiar fuel.ticket por fleet.vehicle.log.fuel
            'view_mode': 'tree,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id}
        }
    
    def action_assign_fuel_card(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Asignar Tarjeta de Combustible',
            'res_model': 'fuel.magnetic.card',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_vehicle_id': self.id,
                'default_card_type': 'vehicle',
                'default_state': 'assigned'
            }
        }
    
    def action_register_fuel_consumption(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registrar Consumo de Combustible',
            'res_model': 'fleet.vehicle.log.fuel',  # CORREGIDO: Cambiar fuel.ticket por fleet.vehicle.log.fuel
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_vehicle_id': self.id,
                'default_date': fields.Date.today(),
                'default_odometer': self.odometer
            }
        }
    
    def calculate_fuel_efficiency(self):
        """Calcular eficiencia de combustible basada en tickets recientes"""
        self.ensure_one()
        
        # CORREGIDO: Cambiar fuel.ticket por fleet.vehicle.log.fuel
        recent_tickets = self.env['fleet.vehicle.log.fuel'].search([
            ('vehicle_id', '=', self.id),
            ('state', '=', 'done')  # CORREGIDO: Cambiar 'confirmed' por 'done'
        ], order='date desc, id desc', limit=5)
        
        if len(recent_tickets) < 2:
            return 0.0
        
        # CORREGIDO: Cambiar 'liters' por 'liter'
        total_liters = sum(recent_tickets.mapped('liter'))
        
        # Obtener odómetros inicial y final
        sorted_tickets = recent_tickets.sorted(key=lambda r: r.odometer)
        initial_odometer = sorted_tickets[0].odometer
        final_odometer = sorted_tickets[-1].odometer
        
        if final_odometer <= initial_odometer:
            return 0.0
        
        distance = final_odometer - initial_odometer
        
        # Calcular L/100km
        if distance > 0:
            consumption = (total_liters * 100) / distance
            return consumption
        
        return 0.0
    
    @api.model
    def cron_update_average_consumption(self):
        """Actualizar consumo promedio de todos los vehículos"""
        vehicles = self.search([])
        for vehicle in vehicles:
            consumption = vehicle.calculate_fuel_efficiency()
            if consumption > 0:
                vehicle.average_consumption = consumption
