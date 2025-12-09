# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FleetConsumptionStandard(models.Model):
    _name = 'fleet.consumption.standard'
    _description = 'Normas de Consumo de Combustible'
    _order = 'vehicle_type, brand_id, model_id'
    _rec_name = 'display_name'

    # Información básica
    name = fields.Char(string='Nombre de la Norma', required=True)
    active = fields.Boolean(string='Activo', default=True)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    
    # Criterios de aplicación
    vehicle_type = fields.Selection([
        ('movil', 'Móvil'),
        ('tecnologico', 'Tecnológico'),
        ('estacionario', 'Estacionario'),
    ], string='Tipo de Vehículo', required=True)
    
    brand_id = fields.Many2one('fleet.vehicle.model.brand', string='Marca')
    model_id = fields.Many2one('fleet.vehicle.model', string='Modelo')
    category_id = fields.Many2one('fleet.vehicle.model.category', string='Categoría')
    
    # Normas de consumo
    standard_kml = fields.Float(string='Norma Km/L', digits=(10, 3),
                               help='Norma de consumo en kilómetros por litro')
    standard_lh = fields.Float(string='Norma L/Hora', digits=(10, 3),
                              help='Norma de consumo en litros por hora (para estacionarios)')
    
    # Tolerancias
    tolerance_percentage = fields.Float(string='Tolerancia (%)', default=5.0, digits=(5, 2),
                                       help='Porcentaje de tolerancia permitido')
    
    # Fechas de vigencia
    date_from = fields.Date(string='Vigente Desde', default=fields.Date.today)
    date_to = fields.Date(string='Vigente Hasta')
    
    # Información adicional
    notes = fields.Text(string='Observaciones')
    legal_reference = fields.Char(string='Referencia Legal',
                                 help='Decreto, resolución o norma que establece este estándar')
    
    # Campo computado para display
    display_name = fields.Char(string='Nombre para Mostrar', compute='_compute_display_name', store=True)
    
    @api.depends('name', 'vehicle_type', 'brand_id', 'model_id')
    def _compute_display_name(self):
        for record in self:
            parts = [record.name]
            if record.brand_id:
                parts.append(record.brand_id.name)
            if record.model_id:
                parts.append(record.model_id.name)
            parts.append(dict(record._fields['vehicle_type'].selection)[record.vehicle_type])
            record.display_name = ' - '.join(parts)
    
    @api.constrains('standard_kml', 'standard_lh', 'vehicle_type')
    def _check_standards(self):
        for record in self:
            if record.vehicle_type in ['movil', 'tecnologico'] and record.standard_kml <= 0:
                raise ValidationError(_("La norma Km/L debe ser mayor a cero para vehículos móviles y tecnológicos."))
            
            if record.vehicle_type == 'estacionario' and record.standard_lh <= 0:
                raise ValidationError(_("La norma L/Hora debe ser mayor a cero para vehículos estacionarios."))
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_to and record.date_from and record.date_to <= record.date_from:
                raise ValidationError(_("La fecha de fin debe ser posterior a la fecha de inicio."))
    
    @api.constrains('tolerance_percentage')
    def _check_tolerance(self):
        for record in self:
            if record.tolerance_percentage < 0 or record.tolerance_percentage > 50:
                raise ValidationError(_("La tolerancia debe estar entre 0% y 50%."))
    
    @api.model
    def get_standard_for_vehicle(self, vehicle, date_ref=None):
        """Obtener la norma aplicable para un vehículo en una fecha específica"""
        if not date_ref:
            date_ref = fields.Date.today()
        
        # Buscar norma específica (más específica primero)
        domain = [
            ('vehicle_type', '=', vehicle.vehicle_custom_type),
            ('active', '=', True),
            ('date_from', '<=', date_ref),
            '|', ('date_to', '=', False), ('date_to', '>=', date_ref)
        ]
        
        # Buscar por modelo específico
        if vehicle.model_id:
            specific_standard = self.search(domain + [('model_id', '=', vehicle.model_id.id)], limit=1)
            if specific_standard:
                return specific_standard
        
        # Buscar por marca
        if vehicle.model_id and vehicle.model_id.brand_id:
            brand_standard = self.search(domain + [
                ('brand_id', '=', vehicle.model_id.brand_id.id),
                ('model_id', '=', False)
            ], limit=1)
            if brand_standard:
                return brand_standard
        
        # Buscar por categoría
        if vehicle.category_id:
            category_standard = self.search(domain + [
                ('category_id', '=', vehicle.category_id.id),
                ('brand_id', '=', False),
                ('model_id', '=', False)
            ], limit=1)
            if category_standard:
                return category_standard
        
        # Buscar norma general por tipo
        general_standard = self.search(domain + [
            ('brand_id', '=', False),
            ('model_id', '=', False),
            ('category_id', '=', False)
        ], limit=1)
        
        return general_standard
    
    def action_apply_to_vehicles(self):
        """Aplicar esta norma a vehículos que coincidan con los criterios"""
        self.ensure_one()
        
        domain = [('vehicle_custom_type', '=', self.vehicle_type)]
        
        if self.brand_id:
            domain.append(('model_id.brand_id', '=', self.brand_id.id))
        if self.model_id:
            domain.append(('model_id', '=', self.model_id.id))
        if self.category_id:
            domain.append(('category_id', '=', self.category_id.id))
        
        vehicles = self.env['fleet.vehicle'].search(domain)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vehículos que Aplican - %s') % self.display_name,
            'res_model': 'fleet.vehicle',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', vehicles.ids)],
            'context': {'create': False}
        }
