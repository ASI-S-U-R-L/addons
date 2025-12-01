# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

class FleetMonthlyClosureAdmin(models.Model):
    _name = 'fleet.monthly.closure.admin'
    _description = 'Cierre Mensual para Vehículos Administrativos'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'closure_date desc, vehicle_id'
    _rec_name = 'display_name'

    # Información básica
    name = fields.Char(string='Código de Cierre', required=True, copy=False, default='Nuevo', tracking=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True, tracking=True,
                                domain="[('vehicle_custom_type', 'in', ['movil', 'tecnologico']), ('has_route_sheet', '=', False)]")
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company, required=True)
    
    # Fecha del cierre
    closure_date = fields.Date(string='Fecha de Cierre', required=True, default=fields.Date.today, tracking=True)
    closure_month = fields.Integer(string='Mes', compute='_compute_closure_period', store=True)
    closure_year = fields.Integer(string='Año', compute='_compute_closure_period', store=True)
    
    # Información del vehículo (relacionada)
    vehicle_type = fields.Selection(related='vehicle_id.vehicle_custom_type', string='Tipo de Vehículo', store=True, readonly=True)
    license_plate = fields.Char(related='vehicle_id.license_plate', string='Matrícula', store=True, readonly=True)
    driver_id = fields.Many2one(related='vehicle_id.driver_id', string='Conductor', store=True, readonly=True)
    
    # Odómetros del período
    odometer_start = fields.Float(string='Odómetro Inicial (Km)', required=True, digits=(10, 2), tracking=True)
    odometer_end = fields.Float(string='Odómetro Final (Km)', required=True, digits=(10, 2), tracking=True)
    total_kilometers = fields.Float(string='Total Kilómetros', compute='_compute_totals', store=True, digits=(10, 2))
    
    # Horas de operación (para tecnológicos)
    hours_start = fields.Float(string='Horas Iniciales', digits=(10, 2), tracking=True,
                              help='Para vehículos tecnológicos con horómetro')
    hours_end = fields.Float(string='Horas Finales', digits=(10, 2), tracking=True)
    total_hours = fields.Float(string='Total Horas', compute='_compute_totals', store=True, digits=(10, 2))
    
    # Combustible consumido (se obtiene automáticamente de Log Fuel)
    total_fuel_consumed = fields.Float(string='Total Combustible (L)', compute='_compute_fuel_consumed', store=True, digits=(10, 2))
    fuel_logs_count = fields.Integer(string='Tickets de Combustible', compute='_compute_fuel_consumed', store=True)
    
    # Servicios realizados
    services_description = fields.Text(string='Descripción de Servicios', tracking=True,
                                      help='Descripción de los servicios administrativos realizados')
    destinations = fields.Text(string='Destinos Principales', tracking=True,
                              help='Principales destinos visitados durante el mes')
    
    # Estado y validación
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('closed', 'Cerrado'),
    ], string='Estado', default='draft', tracking=True)
    
    # Responsable del cierre
    responsible_id = fields.Many2one('res.users', string='Responsable del Cierre', 
                                    default=lambda self: self.env.user, tracking=True)
    
    # Observaciones
    observations = fields.Text(string='Observaciones', tracking=True)
    
    # Campo computado para display
    display_name = fields.Char(string='Nombre para Mostrar', compute='_compute_display_name', store=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.monthly.closure.admin') or 'Nuevo'
        return super(FleetMonthlyClosureAdmin, self).create(vals_list)
    
    @api.depends('closure_date')
    def _compute_closure_period(self):
        for record in self:
            if record.closure_date:
                record.closure_month = record.closure_date.month
                record.closure_year = record.closure_date.year
            else:
                record.closure_month = 0
                record.closure_year = 0
    
    @api.depends('name', 'vehicle_id.license_plate', 'closure_date')
    def _compute_display_name(self):
        for record in self:
            if record.vehicle_id and record.closure_date:
                month_name = record.closure_date.strftime('%B %Y')
                record.display_name = f"{record.name} - {record.vehicle_id.license_plate} ({month_name})"
            else:
                record.display_name = record.name or 'Nuevo Cierre'
    
    @api.depends('odometer_start', 'odometer_end', 'hours_start', 'hours_end')
    def _compute_totals(self):
        for record in self:
            record.total_kilometers = record.odometer_end - record.odometer_start if record.odometer_end > record.odometer_start else 0.0
            record.total_hours = record.hours_end - record.hours_start if record.hours_end > record.hours_start else 0.0
    
    @api.depends('vehicle_id', 'closure_date')
    def _compute_fuel_consumed(self):
        for record in self:
            if record.vehicle_id and record.closure_date:
                # Calcular el rango del mes
                start_date = record.closure_date.replace(day=1)
                if record.closure_date.month == 12:
                    end_date = record.closure_date.replace(year=record.closure_date.year + 1, month=1, day=1) - relativedelta(days=1)
                else:
                    end_date = record.closure_date.replace(month=record.closure_date.month + 1, day=1) - relativedelta(days=1)
                
                # Buscar tickets de combustible del mes
                fuel_logs = self.env['fleet.vehicle.log.fuel'].search([
                    ('vehicle_id', '=', record.vehicle_id.id),
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('state', '!=', 'cancelled')
                ])
                
                record.fuel_logs_count = len(fuel_logs)
                record.total_fuel_consumed = sum(fuel_logs.mapped('liter'))
            else:
                record.fuel_logs_count = 0
                record.total_fuel_consumed = 0.0
    
    def action_confirm(self):
        """Confirmar el cierre mensual"""
        for record in self:
            # Validaciones
            if record.total_kilometers <= 0:
                raise ValidationError(_("El total de kilómetros debe ser mayor a cero."))
            
            if record.total_fuel_consumed <= 0:
                raise ValidationError(_("Debe haber consumo de combustible registrado para el período."))
            
            if not record.services_description:
                raise ValidationError(_("Debe describir los servicios realizados durante el mes."))
            
            record.state = 'confirmed'
            
            # Crear análisis de consumo automáticamente
            self._create_consumption_analysis()
            
            # Mensaje en el chatter
            record.message_post(
                body=f'Cierre mensual confirmado.<br/>'
                     f'<strong>Kilómetros:</strong> {record.total_kilometers:.2f} Km<br/>'
                     f'<strong>Combustible:</strong> {record.total_fuel_consumed:.2f} L<br/>'
                     f'<strong>Eficiencia:</strong> {record.total_kilometers/record.total_fuel_consumed:.3f} Km/L' if record.total_fuel_consumed > 0 else '',
                message_type='notification'
            )
    
    def action_close(self):
        """Cerrar definitivamente el cierre mensual"""
        for record in self:
            if record.state != 'confirmed':
                raise ValidationError(_("Solo se pueden cerrar cierres confirmados."))
            
            record.state = 'closed'
    
    def action_draft(self):
        """Volver a borrador"""
        self.write({'state': 'draft'})
    
    def _create_consumption_analysis(self):
        """Crear análisis de consumo basado en este cierre"""
        self.ensure_one()
        
        # Calcular fechas del mes
        start_date = self.closure_date.replace(day=1)
        if self.closure_date.month == 12:
            end_date = self.closure_date.replace(year=self.closure_date.year + 1, month=1, day=1) - relativedelta(days=1)
        else:
            end_date = self.closure_date.replace(month=self.closure_date.month + 1, day=1) - relativedelta(days=1)
        
        # Verificar si ya existe análisis
        existing_analysis = self.env['fleet.consumption.analysis'].search([
            ('vehicle_id', '=', self.vehicle_id.id),
            ('period_start', '=', start_date),
            ('period_end', '=', end_date),
            ('analysis_type', '=', 'monthly')
        ])
        
        if existing_analysis:
            # Actualizar análisis existente
            existing_analysis.write({
                'total_kilometers': self.total_kilometers,
                'total_hours_operation': self.total_hours,
                'odometer_start': self.odometer_start,
                'odometer_end': self.odometer_end,
                'odometer_method': 'manual',
                'observations': f"Basado en cierre mensual {self.name}\n{self.observations or ''}",
            })
            existing_analysis.action_calculate_consumption()
            return existing_analysis
        else:
            # Crear nuevo análisis
            analysis = self.env['fleet.consumption.analysis'].create({
                'vehicle_id': self.vehicle_id.id,
                'period_start': start_date,
                'period_end': end_date,
                'analysis_type': 'monthly',
                'total_kilometers': self.total_kilometers,
                'total_hours_operation': self.total_hours,
                'odometer_start': self.odometer_start,
                'odometer_end': self.odometer_end,
                'odometer_method': 'manual',
                'observations': f"Basado en cierre mensual {self.name}\n{self.observations or ''}",
            })
            analysis.action_calculate_consumption()
            return analysis
    
    def action_view_fuel_logs(self):
        """Ver tickets de combustible del mes"""
        self.ensure_one()
        
        # Calcular rango del mes
        start_date = self.closure_date.replace(day=1)
        if self.closure_date.month == 12:
            end_date = self.closure_date.replace(year=self.closure_date.year + 1, month=1, day=1) - relativedelta(days=1)
        else:
            end_date = self.closure_date.replace(month=self.closure_date.month + 1, day=1) - relativedelta(days=1)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Combustible - %s') % self.display_name,
            'res_model': 'fleet.vehicle.log.fuel',
            'view_mode': 'tree,form',
            'domain': [
                ('vehicle_id', '=', self.vehicle_id.id),
                ('date', '>=', start_date),
                ('date', '<=', end_date)
            ],
            'context': {
                'default_vehicle_id': self.vehicle_id.id,
            }
        }
    
    def action_view_consumption_analysis(self):
        """Ver análisis de consumo relacionado"""
        self.ensure_one()
        
        # Calcular fechas del mes
        start_date = self.closure_date.replace(day=1)
        if self.closure_date.month == 12:
            end_date = self.closure_date.replace(year=self.closure_date.year + 1, month=1, day=1) - relativedelta(days=1)
        else:
            end_date = self.closure_date.replace(month=self.closure_date.month + 1, day=1) - relativedelta(days=1)
        
        analysis = self.env['fleet.consumption.analysis'].search([
            ('vehicle_id', '=', self.vehicle_id.id),
            ('period_start', '=', start_date),
            ('period_end', '=', end_date)
        ])
        
        if analysis:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Análisis de Consumo - %s') % self.display_name,
                'res_model': 'fleet.consumption.analysis',
                'view_mode': 'form',
                'res_id': analysis.id,
                'target': 'current',
            }
        else:
            # Crear análisis si no existe
            analysis = self._create_consumption_analysis()
            return {
                'type': 'ir.actions.act_window',
                'name': _('Análisis de Consumo - %s') % self.display_name,
                'res_model': 'fleet.consumption.analysis',
                'view_mode': 'form',
                'res_id': analysis.id,
                'target': 'current',
            }
    
    @api.constrains('odometer_start', 'odometer_end')
    def _check_odometers(self):
        for record in self:
            if record.odometer_end <= record.odometer_start:
                raise ValidationError(_("El odómetro final debe ser mayor que el inicial."))
    
    @api.constrains('hours_start', 'hours_end')
    def _check_hours(self):
        for record in self:
            if record.hours_end and record.hours_start and record.hours_end <= record.hours_start:
                raise ValidationError(_("Las horas finales deben ser mayores que las iniciales."))
    
    @api.constrains('closure_date', 'vehicle_id')
    def _check_unique_closure(self):
        for record in self:
            existing = self.search([
                ('vehicle_id', '=', record.vehicle_id.id),
                ('closure_month', '=', record.closure_month),
                ('closure_year', '=', record.closure_year),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValidationError(_("Ya existe un cierre para este vehículo en %s %s") % 
                                    (record.closure_date.strftime('%B'), record.closure_year))
    
    def unlink(self):
        for record in self:
            if record.state == 'closed':
                raise ValidationError(_("No puede eliminar un cierre cerrado."))
        return super(FleetMonthlyClosureAdmin, self).unlink()
