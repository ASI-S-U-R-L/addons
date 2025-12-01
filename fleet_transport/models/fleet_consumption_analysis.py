# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class FleetConsumptionAnalysis(models.Model):
    _name = 'fleet.consumption.analysis'
    _description = 'Análisis de Consumo de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_start desc, vehicle_id'
    _rec_name = 'display_name'

    # Información básica
    name = fields.Char(string='Código de Análisis', required=True, copy=False, default='Nuevo', tracking=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company, required=True)
    
    # Período de análisis
    period_start = fields.Date(string='Fecha Inicio', required=True, tracking=True)
    period_end = fields.Date(string='Fecha Fin', required=True, tracking=True)
    analysis_type = fields.Selection([
        ('monthly', 'Mensual Automático'),
        ('custom', 'Período Personalizado'),
    ], string='Tipo de Análisis', default='monthly', required=True, tracking=True)
    
    # Información del vehículo (relacionada)
    vehicle_type = fields.Selection(related='vehicle_id.vehicle_custom_type', string='Tipo de Vehículo', store=True, readonly=True)
    license_plate = fields.Char(related='vehicle_id.license_plate', string='Matrícula', store=True, readonly=True)
    driver_id = fields.Many2one(related='vehicle_id.driver_id', string='Conductor', store=True, readonly=True)
    
    # Datos de consumo
    total_fuel_consumed = fields.Float(string='Total Combustible Consumido (L)', digits=(10, 2), tracking=True)
    total_kilometers = fields.Float(string='Total Kilómetros Recorridos', digits=(10, 2), tracking=True)
    total_hours_operation = fields.Float(string='Total Horas de Operación', digits=(10, 2), tracking=True,
                                        help='Para vehículos estacionarios')
    
    # Odómetros
    odometer_start = fields.Float(string='Odómetro Inicial (Km)', digits=(10, 2), tracking=True)
    odometer_end = fields.Float(string='Odómetro Final (Km)', digits=(10, 2), tracking=True)
    odometer_method = fields.Selection([
        ('real', 'Odómetro Real'),
        ('estimated_gps', 'Estimado por GPS'),
        ('fixed_route', 'Ruta Fija Estándar'),
        ('manual', 'Registro Manual'),
        ('historical', 'Promedio Histórico'),
    ], string='Método de Odómetro', default='real', tracking=True)
    
    # Índices calculados
    consumption_index_kml = fields.Float(string='Índice Km/L', compute='_compute_consumption_indexes', store=True, digits=(10, 3))
    consumption_index_lh = fields.Float(string='Índice L/Hora', compute='_compute_consumption_indexes', store=True, digits=(10, 3))
    
    # Normas y comparación
    standard_consumption_kml = fields.Float(string='Norma Km/L', digits=(10, 3), tracking=True,
                                           help='Norma establecida para este tipo de vehículo')
    standard_consumption_lh = fields.Float(string='Norma L/Hora', digits=(10, 3), tracking=True,
                                          help='Norma establecida para vehículos estacionarios')
    
    # Análisis de cumplimiento
    compliance_percentage_kml = fields.Float(string='% Cumplimiento Km/L', compute='_compute_compliance', store=True, digits=(5, 2))
    compliance_percentage_lh = fields.Float(string='% Cumplimiento L/Hora', compute='_compute_compliance', store=True, digits=(5, 2))
    compliance_status = fields.Selection([
        ('excellent', 'Excelente (>100%)'),
        ('good', 'Bueno (95-100%)'),
        ('acceptable', 'Aceptable (90-95%)'),
        ('warning', 'Advertencia (85-90%)'),
        ('critical', 'Crítico (<85%)'),
    ], string='Estado de Cumplimiento', compute='_compute_compliance_status', store=True, tracking=True)
    
    # Contadores y referencias
    fuel_logs_count = fields.Integer(string='Tickets de Combustible', compute='_compute_fuel_info', store=True)
    route_sheets_count = fields.Integer(string='Hojas de Ruta', compute='_compute_route_sheets_info', store=True)
    monthly_closure_count = fields.Integer(string='Cierres Mensuales', compute='_compute_monthly_closure_info', store=True)
    
    # Estado y control
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('calculated', 'Calculado'),
        ('validated', 'Validado'),
        ('archived', 'Archivado'),
    ], string='Estado', default='draft', tracking=True)
    
    # Observaciones y justificaciones
    observations = fields.Text(string='Observaciones', tracking=True)
    deviation_justification = fields.Text(string='Justificación de Desviaciones', tracking=True,
                                         help='Obligatorio cuando el cumplimiento es menor al 90%')
    
    # Campos computados para display
    display_name = fields.Char(string='Nombre para Mostrar', compute='_compute_display_name', store=True)
    period_description = fields.Char(string='Descripción del Período', compute='_compute_period_description', store=True)
    
    # Alertas y validaciones
    has_alerts = fields.Boolean(string='Tiene Alertas', compute='_compute_alerts', store=True)
    alert_messages = fields.Text(string='Mensajes de Alerta', compute='_compute_alerts', store=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.consumption.analysis') or 'Nuevo'
        return super(FleetConsumptionAnalysis, self).create(vals_list)
    
    @api.depends('name', 'vehicle_id.license_plate', 'period_start', 'period_end')
    def _compute_display_name(self):
        for record in self:
            if record.vehicle_id and record.period_start and record.period_end:
                record.display_name = f"{record.name} - {record.vehicle_id.license_plate} ({record.period_start.strftime('%d/%m/%Y')} - {record.period_end.strftime('%d/%m/%Y')})"
            else:
                record.display_name = record.name or 'Nuevo Análisis'
    
    @api.depends('period_start', 'period_end', 'analysis_type')
    def _compute_period_description(self):
        for record in self:
            if record.period_start and record.period_end:
                if record.analysis_type == 'monthly':
                    record.period_description = f"Mensual - {record.period_start.strftime('%B %Y')}"
                else:
                    record.period_description = f"Personalizado - {record.period_start.strftime('%d/%m/%Y')} al {record.period_end.strftime('%d/%m/%Y')}"
            else:
                record.period_description = 'Período no definido'
    
    @api.depends('total_fuel_consumed', 'total_kilometers', 'total_hours_operation', 'vehicle_type')
    def _compute_consumption_indexes(self):
        for record in self:
            # Índice Km/L para vehículos móviles y tecnológicos
            if record.vehicle_type in ['movil', 'tecnologico'] and record.total_fuel_consumed > 0 and record.total_kilometers > 0:
                record.consumption_index_kml = record.total_kilometers / record.total_fuel_consumed
            else:
                record.consumption_index_kml = 0.0
            
            # Índice L/Hora para vehículos estacionarios
            if record.vehicle_type == 'estacionario' and record.total_hours_operation > 0:
                record.consumption_index_lh = record.total_fuel_consumed / record.total_hours_operation
            else:
                record.consumption_index_lh = 0.0
    
    @api.depends('consumption_index_kml', 'consumption_index_lh', 'standard_consumption_kml', 'standard_consumption_lh', 'vehicle_type')
    def _compute_compliance(self):
        for record in self:
            # Cumplimiento para Km/L (móviles y tecnológicos)
            if record.vehicle_type in ['movil', 'tecnologico'] and record.standard_consumption_kml > 0:
                if record.consumption_index_kml > 0:
                    record.compliance_percentage_kml = (record.consumption_index_kml / record.standard_consumption_kml) * 100
                else:
                    record.compliance_percentage_kml = 0.0
            else:
                record.compliance_percentage_kml = 0.0
            
            # Cumplimiento para L/Hora (estacionarios)
            if record.vehicle_type == 'estacionario' and record.standard_consumption_lh > 0:
                if record.consumption_index_lh > 0:
                    # Para L/Hora, menor consumo es mejor, por lo que invertimos el cálculo
                    record.compliance_percentage_lh = (record.standard_consumption_lh / record.consumption_index_lh) * 100
                else:
                    record.compliance_percentage_lh = 0.0
            else:
                record.compliance_percentage_lh = 0.0
    
    @api.depends('compliance_percentage_kml', 'compliance_percentage_lh', 'vehicle_type')
    def _compute_compliance_status(self):
        for record in self:
            # Determinar el porcentaje relevante según el tipo de vehículo
            if record.vehicle_type in ['movil', 'tecnologico']:
                percentage = record.compliance_percentage_kml
            elif record.vehicle_type == 'estacionario':
                percentage = record.compliance_percentage_lh
            else:
                percentage = 0.0
            
            # Clasificar según el porcentaje
            if percentage >= 100:
                record.compliance_status = 'excellent'
            elif percentage >= 95:
                record.compliance_status = 'good'
            elif percentage >= 90:
                record.compliance_status = 'acceptable'
            elif percentage >= 85:
                record.compliance_status = 'warning'
            else:
                record.compliance_status = 'critical'
    
    @api.depends('vehicle_id', 'period_start', 'period_end')
    def _compute_fuel_info(self):
        for record in self:
            if record.vehicle_id and record.period_start and record.period_end:
                fuel_logs = self.env['fleet.vehicle.log.fuel'].search([
                    ('vehicle_id', '=', record.vehicle_id.id),
                    ('date', '>=', record.period_start),
                    ('date', '<=', record.period_end),
                    ('state', '!=', 'cancelled')
                ])
                record.fuel_logs_count = len(fuel_logs)
                # Actualizar el total de combustible consumido
                if fuel_logs:
                    record.total_fuel_consumed = sum(fuel_logs.mapped('liter'))
            else:
                record.fuel_logs_count = 0
    
    @api.depends('vehicle_id', 'period_start', 'period_end')
    def _compute_route_sheets_info(self):
        for record in self:
            if record.vehicle_id and record.period_start and record.period_end:
                route_sheets = self.env['fleet.route.sheet'].search([
                    ('vehicle_id', '=', record.vehicle_id.id),
                    ('date', '>=', record.period_start),
                    ('date', '<=', record.period_end),
                    ('state', '=', 'confirmed')
                ])
                record.route_sheets_count = len(route_sheets)
                # Actualizar el total de kilómetros
                if route_sheets:
                    record.total_kilometers = sum(route_sheets.mapped('manual_total_kilometers'))
            else:
                record.route_sheets_count = 0
    
    @api.depends('vehicle_id', 'period_start', 'period_end')
    def _compute_monthly_closure_info(self):
        for record in self:
            # Por ahora, establecer en 0. Se implementará cuando se cree el modelo de cierre mensual
            record.monthly_closure_count = 0
    
    @api.depends('compliance_status', 'fuel_logs_count', 'route_sheets_count', 'total_fuel_consumed', 'total_kilometers')
    def _compute_alerts(self):
        for record in self:
            alerts = []
            
            # Alerta por cumplimiento crítico
            if record.compliance_status == 'critical':
                alerts.append('⚠️ CRÍTICO: Consumo excede significativamente la norma establecida')
            elif record.compliance_status == 'warning':
                alerts.append('⚠️ ADVERTENCIA: Consumo por encima del rango aceptable')
            
            # Alerta por falta de datos
            if record.fuel_logs_count == 0:
                alerts.append('📋 Sin tickets de combustible registrados en el período')
            
            if record.vehicle_type in ['movil', 'tecnologico'] and record.route_sheets_count == 0:
                alerts.append('📋 Sin hojas de ruta confirmadas en el período')
            
            # Alerta por datos inconsistentes
            if record.total_fuel_consumed <= 0:
                alerts.append('⛽ Total de combustible consumido es cero o negativo')
            
            if record.vehicle_type in ['movil', 'tecnologico'] and record.total_kilometers <= 0:
                alerts.append('🛣️ Total de kilómetros recorridos es cero o negativo')
            
            # Alerta por desbalance de inventario (>3% según normativa)
            if record.fuel_logs_count > 0 and record.route_sheets_count > 0:
                expected_consumption = record.total_kilometers / record.standard_consumption_kml if record.standard_consumption_kml > 0 else 0
                if expected_consumption > 0:
                    variance = abs(record.total_fuel_consumed - expected_consumption) / expected_consumption * 100
                    if variance > 3:
                        alerts.append(f'📊 DESBALANCE: Diferencia del {variance:.1f}% entre consumo real y esperado (>3% normativo)')
            
            record.has_alerts = bool(alerts)
            record.alert_messages = '\n'.join(alerts) if alerts else ''
    
    def action_calculate_consumption(self):
        """Calcular automáticamente el consumo basado en los datos disponibles"""
        for record in self:
            try:
                # Recalcular información de combustible y rutas
                record._compute_fuel_info()
                record._compute_route_sheets_info()
                record._compute_monthly_closure_info()
                
                # Obtener normas estándar si no están definidas
                if not record.standard_consumption_kml and record.vehicle_type in ['movil', 'tecnologico']:
                    standard = self._get_standard_consumption(record.vehicle_id, 'kml')
                    if standard:
                        record.standard_consumption_kml = standard
                
                if not record.standard_consumption_lh and record.vehicle_type == 'estacionario':
                    standard = self._get_standard_consumption(record.vehicle_id, 'lh')
                    if standard:
                        record.standard_consumption_lh = standard
                
                # Calcular odómetros si no están definidos
                if record.vehicle_type in ['movil', 'tecnologico'] and (not record.odometer_start or not record.odometer_end):
                    record._calculate_odometers()
                
                # Cambiar estado
                record.state = 'calculated'
                
                # Crear actividad si hay alertas críticas
                if record.compliance_status in ['critical', 'warning']:
                    record.activity_schedule(
                        'mail.mail_activity_data_todo',
                        summary=f'Revisar Consumo - {record.compliance_status.title()}',
                        note=f'El análisis de consumo muestra estado {record.compliance_status}. Revisar y justificar si es necesario.\n\nAlertas:\n{record.alert_messages}',
                        user_id=record.env.user.id
                    )
                
                # Mensaje en el chatter
                record.message_post(
                    body=f'Análisis de consumo calculado automáticamente.<br/>'
                         f'<strong>Resultado:</strong> {dict(record._fields["compliance_status"].selection)[record.compliance_status]}<br/>'
                         f'<strong>Combustible:</strong> {record.total_fuel_consumed:.2f} L<br/>'
                         f'<strong>Kilómetros:</strong> {record.total_kilometers:.2f} Km<br/>'
                         f'<strong>Índice:</strong> {record.consumption_index_kml:.3f} Km/L' if record.vehicle_type in ['movil', 'tecnologico'] else f'<strong>Índice:</strong> {record.consumption_index_lh:.3f} L/H',
                    message_type='notification'
                )
                
            except Exception as e:
                _logger.error(f"Error calculando consumo para {record.name}: {str(e)}")
                raise UserError(_("Error al calcular el consumo: %s") % str(e))
    
    def action_validate(self):
        """Validar el análisis de consumo"""
        for record in self:
            # Validaciones obligatorias
            if record.compliance_status in ['critical', 'warning'] and not record.deviation_justification:
                raise ValidationError(_("Debe proporcionar una justificación para las desviaciones críticas o de advertencia."))
            
            if record.total_fuel_consumed <= 0:
                raise ValidationError(_("El total de combustible consumido debe ser mayor a cero."))
            
            if record.vehicle_type in ['movil', 'tecnologico'] and record.total_kilometers <= 0:
                raise ValidationError(_("El total de kilómetros debe ser mayor a cero para vehículos móviles."))
            
            record.state = 'validated'
            
            # Mensaje en el chatter
            record.message_post(
                body=f'Análisis de consumo validado por {record.env.user.name}',
                message_type='notification'
            )
    
    def action_archive(self):
        """Archivar el análisis"""
        self.write({'state': 'archived'})
    
    def action_draft(self):
        """Volver a borrador"""
        self.write({'state': 'draft'})
    
    def _get_standard_consumption(self, vehicle, index_type):
        """Obtener norma estándar de consumo para un vehículo"""
        # Por ahora retorna valores por defecto. Se puede extender con una tabla de normas
        if index_type == 'kml':
            if vehicle.vehicle_custom_type == 'movil':
                return 12.0  # 12 Km/L por defecto para móviles
            elif vehicle.vehicle_custom_type == 'tecnologico':
                return 8.0   # 8 Km/L por defecto para tecnológicos
        elif index_type == 'lh':
            if vehicle.vehicle_custom_type == 'estacionario':
                return 5.0   # 5 L/H por defecto para estacionarios
        return 0.0
    
    def _calculate_odometers(self):
        """Calcular odómetros usando diferentes métodos"""
        self.ensure_one()
        
        if self.vehicle_type not in ['movil', 'tecnologico']:
            return
        
        # Método 1: Odómetro real (buscar en registros de odómetro)
        odometer_logs = self.env['fleet.vehicle.odometer'].search([
            ('vehicle_id', '=', self.vehicle_id.id),
            ('date', '>=', self.period_start),
            ('date', '<=', self.period_end)
        ], order='date')
        
        if len(odometer_logs) >= 2:
            self.odometer_start = odometer_logs[0].value
            self.odometer_end = odometer_logs[-1].value
            self.odometer_method = 'real'
            return
        
        # Método 2: Estimación basada en kilómetros de hojas de ruta
        if self.total_kilometers > 0:
            # Buscar último odómetro conocido
            last_odometer = self.env['fleet.vehicle.odometer'].search([
                ('vehicle_id', '=', self.vehicle_id.id),
                ('date', '<', self.period_start)
            ], order='date desc', limit=1)
            
            if last_odometer:
                self.odometer_start = last_odometer.value
                self.odometer_end = self.odometer_start + self.total_kilometers
                self.odometer_method = 'manual'
            else:
                # Si no hay odómetro previo, usar el actual del vehículo
                self.odometer_start = self.vehicle_id.odometer or 0
                self.odometer_end = self.odometer_start + self.total_kilometers
                self.odometer_method = 'estimated_gps'
    
    @api.constrains('period_start', 'period_end')
    def _check_period_dates(self):
        for record in self:
            if record.period_start and record.period_end:
                if record.period_end <= record.period_start:
                    raise ValidationError(_("La fecha de fin debe ser posterior a la fecha de inicio."))
                
                # Verificar que no haya solapamiento con otros análisis del mismo vehículo
                overlapping = self.search([
                    ('vehicle_id', '=', record.vehicle_id.id),
                    ('id', '!=', record.id),
                    ('state', '!=', 'archived'),
                    '|', '|', '|',
                    '&', ('period_start', '<=', record.period_start), ('period_end', '>=', record.period_start),
                    '&', ('period_start', '<=', record.period_end), ('period_end', '>=', record.period_end),
                    '&', ('period_start', '>=', record.period_start), ('period_end', '<=', record.period_end),
                    '&', ('period_start', '<=', record.period_start), ('period_end', '>=', record.period_end),
                ])
                
                if overlapping:
                    raise ValidationError(_("Ya existe un análisis para este vehículo en el período seleccionado: %s") % overlapping[0].display_name)
    
    @api.constrains('standard_consumption_kml', 'standard_consumption_lh')
    def _check_standard_consumption(self):
        for record in self:
            if record.standard_consumption_kml < 0 or record.standard_consumption_lh < 0:
                raise ValidationError(_("Las normas de consumo no pueden ser negativas."))
    
    def action_view_fuel_logs(self):
        """Ver tickets de combustible relacionados"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tickets de Combustible - %s') % self.display_name,
            'res_model': 'fleet.vehicle.log.fuel',
            'view_mode': 'tree,form',
            'domain': [
                ('vehicle_id', '=', self.vehicle_id.id),
                ('date', '>=', self.period_start),
                ('date', '<=', self.period_end)
            ],
            'context': {
                'default_vehicle_id': self.vehicle_id.id,
            }
        }
    
    def action_view_route_sheets(self):
        """Ver hojas de ruta relacionadas"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hojas de Ruta - %s') % self.display_name,
            'res_model': 'fleet.route.sheet',
            'view_mode': 'tree,form',
            'domain': [
                ('vehicle_id', '=', self.vehicle_id.id),
                ('date', '>=', self.period_start),
                ('date', '<=', self.period_end)
            ],
            'context': {
                'default_vehicle_id': self.vehicle_id.id,
            }
        }
    
    @api.model
    def create_monthly_analysis(self, month=None, year=None, vehicle_ids=None):
        """Crear análisis mensual automático para vehículos especificados"""
        if not month:
            month = datetime.now().month
        if not year:
            year = datetime.now().year
        
        # Calcular fechas del mes
        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            period_end = date(year, month + 1, 1) - timedelta(days=1)
        
        # Obtener vehículos
        if vehicle_ids:
            vehicles = self.env['fleet.vehicle'].browse(vehicle_ids)
        else:
            vehicles = self.env['fleet.vehicle'].search([('active', '=', True)])
        
        created_analyses = self.env['fleet.consumption.analysis']
        
        for vehicle in vehicles:
            # Verificar si ya existe análisis para este período
            existing = self.search([
                ('vehicle_id', '=', vehicle.id),
                ('period_start', '=', period_start),
                ('period_end', '=', period_end),
                ('analysis_type', '=', 'monthly')
            ])
            
            if not existing:
                analysis = self.create({
                    'vehicle_id': vehicle.id,
                    'period_start': period_start,
                    'period_end': period_end,
                    'analysis_type': 'monthly',
                })
                
                # Calcular automáticamente
                analysis.action_calculate_consumption()
                created_analyses |= analysis
        
        return created_analyses
    
    def unlink(self):
        for record in self:
            if record.state == 'validated':
                raise ValidationError(_("No puede eliminar un análisis validado. Archívelo en su lugar."))
        return super(FleetConsumptionAnalysis, self).unlink()
