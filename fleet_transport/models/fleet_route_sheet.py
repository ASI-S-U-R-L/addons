# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date

class FleetRouteSheet(models.Model):
    _name = 'fleet.route.sheet'
    _description = 'Hojas de Ruta de Vehículos'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'

    name = fields.Char(string='Hoja de Ruta No.', required=True, copy=False, default='Nuevo', tracking=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True, tracking=True)
    
    # Campos automáticos del vehículo (relacionados - no duplicados)
    vehicle_custom_type = fields.Selection(related='vehicle_id.vehicle_custom_type', string='Tipo de Vehículo', store=True, readonly=True)
    vehicle_brand = fields.Char(string='Marca', related='vehicle_id.model_id.brand_id.name', readonly=True)
    vehicle_model = fields.Char(string='Modelo', related='vehicle_id.model_id.name', readonly=True)
    license_plate = fields.Char(string='Matrícula', related='vehicle_id.license_plate', readonly=True)
    circulation_number = fields.Char(string='Número de Circulación', related='vehicle_id.circulation_number', readonly=True)
    tank_capacity_main = fields.Float(string='Capacidad Tanque Principal (L)', related='vehicle_id.tank_capacity_main', readonly=True)
    tank_capacity_secondary = fields.Float(string='Capacidad Tanque Secundario (L)', related='vehicle_id.tank_capacity_secondary', readonly=True)
    current_consumption_type = fields.Char(string='Tipo de Consumo', related='vehicle_id.current_consumption_type', readonly=True)
    
    # Campos automáticos del chofer (relacionados - no duplicados)
    driver_id = fields.Many2one('res.partner', string='Conductor', tracking=True)
    driver_license_summary = fields.Char(string='Licencias del Conductor', related='driver_id.license_types_summary', readonly=True)
    driver_active_licenses = fields.Integer(string='Licencias Vigentes', related='driver_id.active_licenses_count', readonly=True)
    
    # Campos automáticos de la empresa
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company, required=True)
    entity = fields.Char(string='Entidad', related='company_id.name', readonly=True)
    company_vat = fields.Char(string='NIT/RUC', related='company_id.vat', readonly=True)
    
    # Campos manuales simplificados
    enabled_by = fields.Many2one('res.partner', string='Habilitada por', tracking=True, required=True, 
                            help='Persona que habilita la hoja de ruta')
    authorized_service = fields.Char(string='Servicio Autorizado', tracking=True, required=True)
    
    # Campos manuales para totales (NUEVA FUNCIONALIDAD)
    manual_total_trips = fields.Integer(string='Total de Viajes Realizados', default=0, tracking=True,
                                       help='Cantidad total de viajes realizados con esta hoja de ruta')
    manual_total_kilometers = fields.Float(string='Total de Kilómetros Recorridos', default=0.0, tracking=True, digits=(10, 2),
                                          help='Total de kilómetros recorridos por el vehículo en esta hoja de ruta')
    
    # Campos opcionales para detalles adicionales
    cupo = fields.Char(string='Cupo', tracking=True)
    parqueo = fields.Char(string='Parqueo', tracking=True)
    signature = fields.Binary(string='Firma', attachment=True, tracking=True)
    signature_filename = fields.Char(string='Nombre del archivo de firma')
    
    # Campos computados para análisis (NUEVA FUNCIONALIDAD - INTEGRACIÓN)
    fuel_efficiency = fields.Float(string='Eficiencia de Combustible (Km/L)', compute='_compute_fuel_efficiency', store=True, digits=(10, 2))
    fuel_logs_count = fields.Integer(string='Registros de Combustible', compute='_compute_fuel_info', store=True)
    total_fuel_consumed = fields.Float(string='Total Combustible Consumido (L)', compute='_compute_fuel_info', store=True, digits=(10, 2))
    
    # Viajes detallados (OPCIONALES - para futura app móvil)
    trip_ids = fields.One2many('fleet.route.sheet.trip', 'route_sheet_id', string='Viajes Detallados (Opcional)', tracking=True)
    detailed_total_kilometers = fields.Float(string='Kms de Viajes Detallados', compute='_compute_detailed_totals', store=True)
    detailed_total_trips = fields.Integer(string='Cantidad Viajes Detallados', compute='_compute_detailed_totals', store=True)
    
    # Estados y control
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmada'),
        ('cancelled', 'Cancelada')
    ], string='Estado', default='draft', tracking=True)
    
    # Archivos
    pdf_file = fields.Binary(string='Archivo PDF', attachment=True)
    pdf_filename = fields.Char(string='Nombre del archivo PDF')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.route.sheet') or 'Nuevo'
        return super(FleetRouteSheet, self).create(vals_list)
    
    # NUEVA FUNCIONALIDAD: Integración con Log Fuel
    @api.depends('manual_total_kilometers', 'total_fuel_consumed')
    def _compute_fuel_efficiency(self):
        for sheet in self:
            if sheet.manual_total_kilometers > 0 and sheet.total_fuel_consumed > 0:
                sheet.fuel_efficiency = sheet.manual_total_kilometers / sheet.total_fuel_consumed
            else:
                sheet.fuel_efficiency = 0.0
    
    # NUEVA FUNCIONALIDAD: Correlación automática con tickets de combustible
    @api.depends('vehicle_id', 'date')
    def _compute_fuel_info(self):
        for sheet in self:
            if sheet.vehicle_id and sheet.date:
                # Buscar registros de combustible del mismo día y vehículo
                fuel_logs = self.env['fleet.vehicle.log.fuel'].search([
                    ('vehicle_id', '=', sheet.vehicle_id.id),
                    ('date', '=', sheet.date),
                    ('state', '!=', 'cancelled')
                ])
                sheet.fuel_logs_count = len(fuel_logs)
                sheet.total_fuel_consumed = sum(fuel_logs.mapped('liter'))
            else:
                sheet.fuel_logs_count = 0
                sheet.total_fuel_consumed = 0.0
    
    @api.depends('trip_ids.kilometers', 'trip_ids')
    def _compute_detailed_totals(self):
        for sheet in self:
            sheet.detailed_total_kilometers = sum(trip.kilometers for trip in sheet.trip_ids)
            sheet.detailed_total_trips = len(sheet.trip_ids)

    # NUEVA FUNCIONALIDAD: Automatización total al seleccionar vehículo
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Automatizar TODOS los campos cuando se selecciona un vehículo"""
        if self.vehicle_id:
            # Asignar automáticamente el conductor del vehículo
            if self.vehicle_id.driver_id:
                self.driver_id = self.vehicle_id.driver_id
            
            # Verificar que el vehículo tenga hoja de ruta habilitada
            if not self.vehicle_id.has_route_sheet:
                return {
                    'warning': {
                        'title': _('Advertencia'),
                        'message': _('El vehículo seleccionado no está configurado para usar hojas de ruta. Active la opción "Posee Hoja de Ruta" en la ficha del vehículo.')
                    }
                }
    
    def action_confirm(self):
        for record in self:
            # Validaciones básicas
            if record.manual_total_kilometers <= 0:
                raise ValidationError(_("Debe ingresar el total de kilómetros recorridos."))
            
            if record.manual_total_trips <= 0:
                raise ValidationError(_("Debe ingresar el total de viajes realizados."))
            
            # NUEVA FUNCIONALIDAD: Validar que el conductor tenga licencias vigentes
            if record.driver_id and hasattr(record.driver_id, 'active_licenses_count') and record.driver_id.active_licenses_count == 0:
                raise ValidationError(_("El conductor %s no tiene licencias vigentes.") % record.driver_id.name)
            
            # NUEVA FUNCIONALIDAD: Validar compatibilidad conductor-vehículo (usando método del BaseTransporte)
            if record.driver_id and hasattr(record.driver_id, 'check_license_for_vehicle_type'):
                if not record.driver_id.check_license_for_vehicle_type(record.vehicle_id.vehicle_custom_type):
                    raise ValidationError(_("El conductor %s no tiene licencias válidas para el tipo de vehículo %s.") % 
                                        (record.driver_id.name, record.vehicle_id.vehicle_custom_type))
            
            record.write({'state': 'confirmed'})
            
            # Crear actividad para seguimiento
            record.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Hoja de Ruta Confirmada'),
                note=_('La hoja de ruta %s ha sido confirmada. Total: %s viajes, %s km.') % 
                     (record.name, record.manual_total_trips, record.manual_total_kilometers),
                user_id=record.env.user.id
            )
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_draft(self):
        self.write({'state': 'draft'})
    
    # NUEVA FUNCIONALIDAD: Ver registros de combustible relacionados
    def action_view_fuel_logs(self):
        """Acción para ver los registros de combustible relacionados"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Registros de Combustible - %s') % self.name,
            'res_model': 'fleet.vehicle.log.fuel',
            'view_mode': 'tree,form',
            'domain': [
                ('vehicle_id', '=', self.vehicle_id.id),
                ('date', '=', self.date)
            ],
            'context': {
                'default_vehicle_id': self.vehicle_id.id,
                'default_date': self.date,
            }
        }
    
    @api.constrains('date')
    def _check_date(self):
        for record in self:
            if record.date > fields.Date.today():
                raise ValidationError(_("La fecha de la hoja de ruta no puede ser futura."))
    
    @api.constrains('vehicle_id')
    def _check_vehicle(self):
        for record in self:
            if not record.vehicle_id.has_route_sheet:
                raise ValidationError(_("El vehículo seleccionado no está configurado para usar hojas de ruta. Active la opción 'Posee Hoja de Ruta' en la ficha del vehículo."))
    
    @api.constrains('manual_total_kilometers', 'manual_total_trips')
    def _check_manual_totals(self):
        for record in self:
            if record.state == 'confirmed':
                if record.manual_total_kilometers <= 0:
                    raise ValidationError(_("El total de kilómetros debe ser mayor a cero."))
                if record.manual_total_trips <= 0:
                    raise ValidationError(_("El total de viajes debe ser mayor a cero."))
    
    def write(self, vals):
        # Verificar si se está intentando modificar una hoja de ruta confirmada o cancelada
        for record in self:
            if record.state in ['confirmed', 'cancelled'] and any(field not in ['state', 'pdf_file', 'pdf_filename'] for field in vals.keys()):
                raise ValidationError(_("No puede modificar una hoja de ruta que está confirmada o cancelada."))
        return super(FleetRouteSheet, self).write(vals)
    
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_("No puede eliminar una hoja de ruta que no está en estado borrador."))
        return super(FleetRouteSheet, self).unlink()


class FleetRouteSheetTrip(models.Model):
    _name = 'fleet.route.sheet.trip'
    _description = 'Viajes de Hoja de Ruta (Opcional - Para App Móvil)'
    _order = 'date, departure_time'
    
    route_sheet_id = fields.Many2one('fleet.route.sheet', string='Hoja de Ruta', required=True, ondelete='cascade')
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True)
    origin = fields.Char(string='Origen', required=True)
    destination = fields.Char(string='Destino', required=True)
    authorized_route = fields.Char(string='Ruta Autorizada', required=True)
    departure_time = fields.Datetime(string='Hora Salida', required=True)
    arrival_time = fields.Datetime(string='Hora Llegada', required=True)
    travel_time = fields.Float(string='Tiempo en horas', compute='_compute_travel_time', store=True)
    departure_odometer = fields.Float(string='Kms Odómetro Salida', required=True)
    arrival_odometer = fields.Float(string='Kms Odómetro Llegada', required=True)
    kilometers = fields.Float(string='Total Kms', compute='_compute_kilometers', store=True)
    driver_number = fields.Char(string='Nro conduce o Carta porte')
    passenger_count = fields.Integer(string='Cantidad de pasajeros', default=0)
    
    @api.depends('departure_time', 'arrival_time')
    def _compute_travel_time(self):
        for trip in self:
            if trip.departure_time and trip.arrival_time:
                delta = trip.arrival_time - trip.departure_time
                trip.travel_time = delta.total_seconds() / 3600
            else:
                trip.travel_time = 0.0
    
    @api.depends('departure_odometer', 'arrival_odometer')
    def _compute_kilometers(self):
        for trip in self:
            trip.kilometers = trip.arrival_odometer - trip.departure_odometer if trip.arrival_odometer > trip.departure_odometer else 0.0
    
    @api.constrains('departure_odometer', 'arrival_odometer')
    def _check_odometer(self):
        for trip in self:
            if trip.arrival_odometer < trip.departure_odometer:
                raise ValidationError(_("El kilometraje de llegada no puede ser menor que el kilometraje de salida."))
    
    @api.constrains('departure_time', 'arrival_time')
    def _check_times(self):
        for trip in self:
            if trip.departure_time and trip.arrival_time and trip.departure_time >= trip.arrival_time:
                raise ValidationError(_("La hora de llegada debe ser posterior a la hora de salida."))
    
    @api.constrains('date')
    def _check_date(self):
        for trip in self:
            if trip.date > fields.Date.today():
                raise ValidationError(_("La fecha del viaje no puede ser futura."))
            
            # Verificar que la fecha del viaje coincida con la fecha de la hoja de ruta
            if trip.route_sheet_id and trip.date != trip.route_sheet_id.date:
                raise ValidationError(_("La fecha del viaje debe coincidir con la fecha de la hoja de ruta."))
    
    @api.constrains('passenger_count')
    def _check_passenger_count(self):
        for trip in self:
            if trip.passenger_count < 0:
                raise ValidationError(_("La cantidad de pasajeros no puede ser negativa."))
    
    def write(self, vals):
        # Verificar si se está intentando modificar un viaje de una hoja de ruta confirmada o cancelada
        for record in self:
            if record.route_sheet_id.state in ['confirmed', 'cancelled']:
                raise ValidationError(_("No puede modificar un viaje de una hoja de ruta que está confirmada o cancelada."))
        return super(FleetRouteSheetTrip, self).write(vals)
    
    def unlink(self):
        for record in self:
            if record.route_sheet_id.state != 'draft':
                raise ValidationError(_("No puede eliminar un viaje de una hoja de ruta que no está en estado borrador."))
        return super(FleetRouteSheetTrip, self).unlink()
