# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    # Tipo de vehículo personalizado
    vehicle_custom_type = fields.Selection([
        ('movil', 'Móvil (Normal)'),
        ('tecnologico', 'Tecnológico (Dos motores)'),
        ('estacionario', 'Estacionario (Generador/Turbina)'),
    ], string='Tipo de Vehículo', default='movil', required=True, tracking=True)

    # Número de circulación
    circulation_number = fields.Char(
        string='Número de Circulación',
        help='Indicador del número de circulación del vehículo'
    )

    # Posee hoja de ruta
    has_route_sheet = fields.Boolean(
        string='Posee Hoja de Ruta',
        default=False,
        help='Indica si el vehículo posee hoja de ruta'
    )

    # Tipo de consumo para vehículo móvil
    consumption_type_movil = fields.Selection([
        ('km_liter', 'Kilómetros/Litro'),
        ('hours_liter', 'Horas/Litro'),
    ], string='Tipo de Consumo', default='km_liter')

    # Campos para vehículo tecnológico (motor principal)
    consumption_type_main_engine = fields.Selection([
        ('km_liter', 'Kilómetros/Litro'),
    ], string='Tipo de Consumo Motor Principal', default='km_liter', readonly=True)

    # Campos para vehículo tecnológico (motor secundario)
    consumption_type_secondary_engine = fields.Selection([
        ('hours_liter', 'Horas/Litro'),
    ], string='Tipo de Consumo Motor Secundario', default='hours_liter', readonly=True)

    # Tipo de consumo para vehículo estacionario
    consumption_type_stationary = fields.Selection([
        ('hours_liter', 'Horas/Litro'),
    ], string='Tipo de Consumo', default='hours_liter', readonly=True)

    # Capacidad del tanque principal
    tank_capacity_main = fields.Float(
        string='Capacidad Tanque Principal (Litros)', 
        digits=(10, 2),
        help='Capacidad del tanque principal en litros'
    )

    # Capacidad del tanque secundario (solo para tecnológico)
    tank_capacity_secondary = fields.Float(
        string='Capacidad Tanque Secundario (Litros)', 
        digits=(10, 2),
        help='Capacidad del tanque secundario en litros (solo para vehículos tecnológicos)'
    )

    # Campos para el sistema integral de transporte
    # (Por ahora solo campos básicos, iremos añadiendo más funcionalidades)
    
    # Información de transporte integral
    transport_notes = fields.Text(
        string='Notas de Transporte',
        help='Notas generales sobre el uso del vehículo en el sistema de transporte'
    )

    # Campo para vencimiento del FICAV
    ficav_expiry_date = fields.Date(
        string='Vencimiento del FICAV',
        help='Fecha de vencimiento del FICAV (Ficha de Inspección y Control de Actividad Vehicular)',
        tracking=True
    )

    # Campos computados para el estado del FICAV
    ficav_state = fields.Selection([
        ('valid', 'Vigente'),
        ('expired', 'Vencido'),
        ('expiring_soon', 'Próximo a Vencer'),
        ('not_set', 'No Configurado'),
    ], string='Estado del FICAV', compute='_compute_ficav_state', store=True, tracking=True)

    ficav_days_to_expiry = fields.Integer(
        string='Días para Vencer FICAV',
        compute='_compute_ficav_state',
        store=True,
        help='Días restantes hasta el vencimiento del FICAV'
    )

    is_ficav_expired = fields.Boolean(
        string='FICAV Vencido',
        compute='_compute_ficav_state',
        store=True
    )

    is_ficav_expiring_soon = fields.Boolean(
        string='FICAV Vence Pronto',
        compute='_compute_ficav_state',
        store=True,
        help='FICAV vence en los próximos 30 días'
    )
    
    # Campo computado para mostrar resumen integral
    transport_summary = fields.Char(
        string='Resumen de Transporte',
        compute='_compute_transport_summary',
        store=True,
        help='Resumen integral del vehículo: tipo, combustible, licencias'
    )

    # Campo computado para mostrar el tipo de consumo actual
    current_consumption_type = fields.Char(
        string='Tipo de Consumo Actual',
        compute='_compute_current_consumption_type',
        store=True
    )

    # Campo computado para mostrar información de tanques
    tank_info = fields.Char(
        string='Información de Tanques',
        compute='_compute_tank_info',
        store=True
    )

    # CORRECCIÓN: Removido 'fuel_count' del @depends y de la lógica
    @api.depends('vehicle_custom_type', 'driver_id', 'ficav_state')
    def _compute_transport_summary(self):
        for vehicle in self:
            summary_parts = []
            
            # Tipo de vehículo
            if vehicle.vehicle_custom_type:
                type_name = dict(vehicle._fields['vehicle_custom_type'].selection).get(vehicle.vehicle_custom_type, '')
                summary_parts.append(f"Tipo: {type_name}")
            
            # Información del conductor
            if vehicle.driver_id:
                summary_parts.append(f"Conductor: {vehicle.driver_id.name}")
            
            # Estado del FICAV
            if vehicle.ficav_state:
                ficav_status = dict(vehicle._fields['ficav_state'].selection).get(vehicle.ficav_state, '')
                summary_parts.append(f"FICAV: {ficav_status}")
        
            vehicle.transport_summary = " | ".join(summary_parts) if summary_parts else "Sin información"

    @api.depends('vehicle_custom_type', 'consumption_type_movil')
    def _compute_current_consumption_type(self):
        for record in self:
            if record.vehicle_custom_type == 'movil':
                if record.consumption_type_movil == 'km_liter':
                    record.current_consumption_type = 'Kilómetros/Litro'
                else:
                    record.current_consumption_type = 'Horas/Litro'
            elif record.vehicle_custom_type == 'tecnologico':
                record.current_consumption_type = 'Principal: Km/L - Secundario: Horas/L'
            elif record.vehicle_custom_type == 'estacionario':
                record.current_consumption_type = 'Horas/Litro'
            else:
                record.current_consumption_type = ''

    @api.depends('vehicle_custom_type', 'tank_capacity_main', 'tank_capacity_secondary')
    def _compute_tank_info(self):
        for record in self:
            if record.vehicle_custom_type in ['movil', 'estacionario']:
                record.tank_info = f'1 Tanque: {record.tank_capacity_main or 0} L'
            elif record.vehicle_custom_type == 'tecnologico':
                main_capacity = record.tank_capacity_main or 0
                secondary_capacity = record.tank_capacity_secondary or 0
                record.tank_info = f'2 Tanques: Principal {main_capacity} L - Secundario {secondary_capacity} L'
            else:
                record.tank_info = ''

    @api.depends('ficav_expiry_date')
    def _compute_ficav_state(self):
        today = date.today()
        for record in self:
            # Inicializar todos los campos con valores por defecto
            record.ficav_days_to_expiry = 0
            record.is_ficav_expired = False
            record.is_ficav_expiring_soon = False
            
            # Verificar si la fecha está configurada
            if not record.ficav_expiry_date:
                record.ficav_state = 'not_set'
            else:
                # Calcular días hasta el vencimiento
                delta = record.ficav_expiry_date - today
                record.ficav_days_to_expiry = delta.days
                
                # Determinar el estado basado en los días restantes
                if delta.days < 0:  # Ya venció
                    record.ficav_state = 'expired'
                    record.is_ficav_expired = True
                elif delta.days <= 30:  # Vence pronto (30 días o menos)
                    record.ficav_state = 'expiring_soon'
                    record.is_ficav_expiring_soon = True
                else:  # Vigente
                    record.ficav_state = 'valid'

    @api.constrains('tank_capacity_secondary', 'vehicle_custom_type')
    def _check_secondary_tank_type(self):
        for record in self:
            if record.tank_capacity_secondary and record.vehicle_custom_type != 'tecnologico':
                raise ValidationError(
                    _('Solo los vehículos tecnológicos pueden tener tanque secundario.')
                )

    @api.constrains('license_plate', 'vehicle_custom_type')
    def _check_license_plate_required(self):
        for record in self:
            if record.vehicle_custom_type != 'estacionario' and not record.license_plate:
                raise ValidationError(
                    _('La matrícula es obligatoria para vehículos móviles y tecnológicos.')
                )

    @api.constrains('ficav_expiry_date')
    def _check_ficav_expiry_date(self):
        for record in self:
            if record.ficav_expiry_date and record.ficav_expiry_date <= fields.Date.today():
                # Solo advertencia, no bloquear
                pass  # Se puede añadir lógica adicional si es necesario

    @api.onchange('vehicle_custom_type')
    def _onchange_vehicle_custom_type(self):
        """Limpiar campos no aplicables según el tipo de vehículo"""
        if self.vehicle_custom_type == 'movil':
            self.tank_capacity_secondary = 0
        elif self.vehicle_custom_type == 'estacionario':
            self.tank_capacity_secondary = 0
            self.consumption_type_movil = False
            # Para estacionarios, limpiar campos de conductor y matrícula
            self.driver_id = False
            self.future_driver_id = False
            self.license_plate = False
            # También limpiar número de circulación y hoja de ruta para estacionarios
            self.circulation_number = False
            self.has_route_sheet = False
        elif self.vehicle_custom_type == 'tecnologico':
            self.consumption_type_movil = False

    # Sobrescribir el método name_get para vehículos estacionarios
    @api.depends('model_id.brand_id.name', 'model_id.name', 'license_plate', 'vehicle_custom_type')
    def _compute_vehicle_name(self):
        for record in self:
            if record.vehicle_custom_type == 'estacionario':
                # Para estacionarios, no incluir matrícula en el nombre
                record.name = (record.model_id.brand_id.name or '') + '/' + (record.model_id.name or '') + '/' + 'Estacionario'
            else:
                record.name = (record.model_id.brand_id.name or '') + '/' + (record.model_id.name or '') + '/' + (record.license_plate or _('No Plate'))

    def action_view_transport_dashboard(self):
        """Acción para ver el dashboard integral del vehículo"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Dashboard de Transporte - {self.name}',
            'res_model': 'fleet.vehicle',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'context': {
                'transport_dashboard_mode': True,
            }
        }
