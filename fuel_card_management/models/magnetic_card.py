# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta
import re
import logging

_logger = logging.getLogger(__name__)

class FuelMagneticCard(models.Model):
    _name = 'fuel.magnetic.card'
    _description = 'Tarjeta Magnética de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    
    # --- Campos básicos ---
    name = fields.Char(
        string='Número de Tarjeta', 
        required=True, 
        copy=False, 
        tracking=True,
        help="Número de 16 dígitos de la tarjeta"
    )
    
    active = fields.Boolean(
        default=True, 
        tracking=True
    )
    
    card_type = fields.Selection([
        ('basica', 'Básica'),
        ('reserva', 'Reserva')
    ], string='Tipo de Tarjeta', default='basica', required=True, tracking=True,
       help="Básica: Tarjeta de uso normal. Reserva: Tarjeta de emergencia o respaldo")
    
    issue_date = fields.Date(
        string='Fecha de Emisión', 
        default=fields.Date.context_today, 
        required=True, 
        tracking=True
    )
    
    expiry_date = fields.Date(
        string='Fecha de Vencimiento', 
        required=True, 
        tracking=True
    )
    
    # MODIFICADO: Cambio de Many2one a Many2many para múltiples portadores
    carrier_ids = fields.Many2many(
        'fuel.carrier', 
        'fuel_card_carrier_rel',
        'card_id',
        'carrier_id',
        string='Portadores de Combustible', 
        tracking=True,
        help="Tipos de combustible asociados a esta tarjeta"
    )
    
    # Campo computado para mantener compatibilidad con código existente
    carrier_id = fields.Many2one(
        'fuel.carrier',
        string='Portador Principal',
        compute='_compute_carrier_id',
        store=True,
        help="Primer portador de combustible (para compatibilidad)"
    )
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle', 
        string='Vehículo Asignado', 
        tracking=True,
        domain="[('active', '=', True)]"
    )
    
    driver_id = fields.Many2one(
        'res.partner', 
        string='Conductor Asignado', 
        tracking=True,
        domain="[('is_driver', '=', True)]"
    )
    
    # Campo para especificar el motor en vehículos tecnológicos
    engine_type = fields.Selection([
        ('main', 'Motor Principal'),
        ('secondary', 'Motor Secundario')
    ], string='Tipo de Motor', tracking=True,
       help="Para vehículos tecnológicos, especifica a qué motor está asignada la tarjeta")
    
    pin = fields.Char(
        string='PIN', 
        groups="fuel_card_management.group_fuel_card_manager", 
        tracking=True
    )
    
    initial_balance = fields.Float(
        string='Saldo Inicial', 
        default=0.0, 
        tracking=True,
        states={'available': [('readonly', True)], 'assigned': [('readonly', True)], 'expired': [('readonly', True)], 'blocked': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )
    
    current_balance = fields.Float(
        string='Saldo Actual', 
        default=0.0, 
        tracking=True,
    )
    
    # --- Estados y operaciones ---
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('available', 'Disponible'),
        ('assigned', 'Asignada'),
        ('expired', 'Vencida'),
        ('blocked', 'Bloqueada'),
        ('cancelled', 'Cancelada')
    ], string='Estado', default='draft', tracking=True)
    
    operational_state = fields.Selection([
        ('draft', 'Borrador'),
        ('available', 'Disponible'),
        ('assigned', 'Asignada'),
        ('expired', 'Vencida'),
        ('blocked', 'Bloqueada'),
        ('cancelled', 'Cancelada')
    ], string='Estado Operativo', compute='_compute_operational_state', store=True)
    
    is_delivered = fields.Boolean(
        string='Entregada', 
        default=False, 
        tracking=True
    )
    
    # Campos relacionados del vehículo para mostrar información
    vehicle_custom_type = fields.Selection(
        related='vehicle_id.vehicle_custom_type', 
        string='Tipo de Vehículo', 
        readonly=True
    )
    
    notes = fields.Text(string='Notas')
    
    # --- Relaciones ---
    fuel_log_ids = fields.One2many(
        'fleet.vehicle.log.fuel', 
        'card_main_id', 
        string='Registros de Combustible'
    )

    # --- Constraints y validaciones ---
    _sql_constraints = [
        ('name_uniq', 'unique(name)', '¡El número de tarjeta debe ser único!'),
        ('balance_positive', 'CHECK(current_balance >= 0)', '¡El saldo no puede ser negativo!')
    ]

    # NUEVO: Método computado para carrier_id (compatibilidad)
    @api.depends('carrier_ids')
    def _compute_carrier_id(self):
        """Asigna el primer portador como portador principal para compatibilidad"""
        for card in self:
            card.carrier_id = card.carrier_ids[0] if card.carrier_ids else False

    @api.constrains('name')
    def _check_card_number_format(self):
        """Validar formato de 16 dígitos"""
        for card in self:
            if card.name:
                clean_number = card.name.replace(' ', '')
                if not re.match(r'^\d{16}$', clean_number):
                    raise ValidationError(_("El número de tarjeta debe tener exactamente 16 dígitos numéricos."))

    @api.constrains('expiry_date')
    def _check_expiry_date(self):
        for card in self:
            if card.expiry_date and card.expiry_date < fields.Date.today():
                raise ValidationError(_("La fecha de vencimiento no puede ser anterior a la fecha actual."))

    @api.constrains('initial_balance')
    def _check_initial_balance(self):
        for card in self:
            if card.initial_balance < 0:
                raise ValidationError(_("El saldo inicial no puede ser negativo."))

    # NUEVO: Validación para portadores de combustible
    @api.constrains('carrier_ids')
    def _check_carrier_ids(self):
        """Validar que se asigne al menos un portador de combustible"""
        for card in self:
            if not card.carrier_ids:
                raise ValidationError(_("La tarjeta debe tener al menos un portador de combustible asignado."))

    # Validación específica para vehículos tecnológicos
    @api.constrains('vehicle_id', 'engine_type')
    def _check_engine_type_assignment(self):
        """Validar asignación de tipo de motor según el tipo de vehículo"""
        for card in self:
            if card.vehicle_id:
                vehicle_type = card.vehicle_id.vehicle_custom_type
                
                if vehicle_type == 'tecnologico':
                    if not card.engine_type:
                        raise ValidationError(_(
                            "Para vehículos tecnológicos debe especificar el tipo de motor "
                            "(Principal o Secundario)."
                        ))
                elif vehicle_type in ['movil', 'estacionario']:
                    if card.engine_type:
                        raise ValidationError(_(
                            "Los vehículos móviles y estacionarios no requieren especificar tipo de motor."
                        ))

    # --- Métodos computados ---
    @api.depends('state', 'is_delivered', 'vehicle_id', 'driver_id', 'expiry_date')
    def _compute_operational_state(self):
        for card in self:
            if card.expiry_date and card.expiry_date < fields.Date.today():
                card.operational_state = 'expired'
            elif card.state in ['expired', 'blocked', 'cancelled', 'draft']:
                card.operational_state = card.state
            else:
                if card.is_delivered or card.vehicle_id or card.driver_id:
                    card.operational_state = 'assigned'
                else:
                    card.operational_state = 'available'

    # --- Métodos de negocio ---
    def action_activate(self):
        """Activar tarjeta (de borrador a disponible)"""
        for card in self.filtered(lambda x: x.state == 'draft'):
            card.write({
                'state': 'available',
                'is_delivered': False
            })
        return True

    def action_block(self):
        """Bloquear tarjeta"""
        for card in self.filtered(lambda x: x.state not in ['expired', 'cancelled']):
            card.state = 'blocked'
        return True

    def action_unblock(self):
        """Desbloquear tarjeta"""
        for card in self.filtered(lambda x: x.state == 'blocked'):
            if card.expiry_date and card.expiry_date < fields.Date.today():
                card.state = 'expired'
            else:
                card.state = 'available'
        return True

    def action_cancel(self):
        """Cancelar tarjeta"""
        for card in self.filtered(lambda x: x.state != 'cancelled'):
            card.write({
                'state': 'cancelled',
                'is_delivered': False,
                'driver_id': False,
                'vehicle_id': False,
                'engine_type': False
            })
        return True

    def action_reset_to_draft(self):
        """Reiniciar tarjeta a borrador desde estado cancelado"""
        for card in self.filtered(lambda x: x.state == 'cancelled'):
            card.write({
                'state': 'draft',
                'is_delivered': False,
                'driver_id': False,
                'vehicle_id': False,
                'engine_type': False
            })
            card.message_post(
                body=_("Tarjeta reiniciada a borrador"),
                subject=_("Estado cambiado")
            )
        return True

    # --- Métodos auxiliares ---
    def _format_card_number(self, number):
        """Formatear número con espacios cada 4 dígitos"""
        if not number:
            return number
        clean_number = ''.join(filter(str.isdigit, str(number)))[:16]
        return ' '.join([clean_number[i:i+4] for i in range(0, len(clean_number), 4)])

    @api.onchange('name')
    def _onchange_card_number(self):
        if self.name:
            self.name = self._format_card_number(self.name)

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Lógica específica según el tipo de vehículo"""
        if self.vehicle_id:
            # Asignar conductor si el vehículo tiene uno
            if hasattr(self.vehicle_id, 'driver_id') and self.vehicle_id.driver_id:
                self.driver_id = self.vehicle_id.driver_id
            
            # Limpiar engine_type al cambiar vehículo
            self.engine_type = False
            
            # Para vehículos no tecnológicos, asegurar que engine_type esté vacío
            if self.vehicle_id.vehicle_custom_type in ['movil', 'estacionario']:
                self.engine_type = False
        else:
            self.engine_type = False

    @api.model
    def create(self, vals):
        if vals.get('name'):
            vals['name'] = self._format_card_number(vals['name'])
        if vals.get('state') == 'draft':
            vals['state'] = 'available'
        
        # NEW: Initialize current_balance with initial_balance if not explicitly set
        if 'initial_balance' in vals and 'current_balance' not in vals:
            vals['current_balance'] = vals['initial_balance']
            
        return super().create(vals)

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = self._format_card_number(vals['name'])
        return super().write(vals)

    def name_get(self):
        """Personalizar la representación del nombre para incluir el tipo y motor"""
        result = []
        for card in self:
            try:
                card_type_label = dict(card._fields['card_type'].selection).get(card.card_type, card.card_type)
                name = f"{card.name} ({card_type_label})"
                
                # Añadir información del motor para vehículos tecnológicos
                if card.engine_type and card.vehicle_id and card.vehicle_id.vehicle_custom_type == 'tecnologico':
                    engine_label = dict(card._fields['engine_type'].selection)[card.engine_type]
                    name += f" - {engine_label}"
                
                # NUEVO: Añadir información de portadores
                if card.carrier_ids:
                    carriers_names = ', '.join(card.carrier_ids.mapped('name'))
                    name += f" [{carriers_names}]"
                
                result.append((card.id, name))
            except Exception as e:
                _logger.warning(f"Error en name_get para tarjeta {card.id}: {e}")
                result.append((card.id, card.name or ''))
        return result

    def can_be_delivered(self):
        """Verificar si la tarjeta puede ser entregada"""
        self.ensure_one()
        return self.operational_state == 'available' and self.active

    def can_be_returned(self):
        """Verificar si la tarjeta puede ser devuelta"""
        self.ensure_one()
        return self.operational_state == 'assigned' and self.active

    def _set_delivered(self, driver_id=False, vehicle_id=False, engine_type=False):
        """Marcar tarjeta como entregada y asignar conductor/vehículo/motor"""
        self.ensure_one()
        vals = {
            'is_delivered': True,
            'state': 'assigned'
        }
        if driver_id:
            vals['driver_id'] = driver_id
        if vehicle_id:
            vals['vehicle_id'] = vehicle_id
        if engine_type:
            vals['engine_type'] = engine_type
        self.write(vals)

    def _set_returned(self):
        """Marcar tarjeta como devuelta y limpiar asignaciones"""
        self.ensure_one()
        self.write({
            'is_delivered': False,
            'state': 'available',
            'driver_id': False,
            'vehicle_id': False,
            'engine_type': False
        })

    def unlink(self):
        """Prevenir eliminación de tarjetas con historial"""
        for card in self:
            if card.fuel_log_ids:
                raise ValidationError(_("No se puede eliminar una tarjeta con historial de transacciones. Considere desactivarla en su lugar."))
        return super().unlink()

    # NUEVO: Método para verificar si un portador específico está asignado
    def has_carrier(self, carrier_id):
        """Verificar si la tarjeta tiene un portador específico asignado"""
        self.ensure_one()
        return carrier_id in self.carrier_ids.ids

    # NUEVO: Método para obtener nombres de portadores
    def get_carriers_display(self):
        """Obtener nombres de portadores para mostrar"""
        self.ensure_one()
        return ', '.join(self.carrier_ids.mapped('name')) if self.carrier_ids else _('Sin portadores')

    # --- MÉTODOS CRON PARA NOTIFICACIONES ---
    
    @api.model
    def _cron_check_expired_cards(self):
        """Marcar tarjetas vencidas como expiradas"""
        today = fields.Date.today()
        expired_cards = self.search([
            ('expiry_date', '<', today),
            ('state', 'in', ['available', 'assigned'])
        ])
        
        for card in expired_cards:
            card.write({'state': 'expired'})
            card.message_post(
                body=_("Tarjeta marcada como vencida automáticamente"),
                subject=_("Tarjeta Vencida")
            )
            _logger.info("Tarjeta %s marcada como vencida automáticamente", card.name)

    @api.model
    def _cron_notify_expiring_cards(self):
        """Crear actividades para tarjetas que vencen en 30 días"""
        today = fields.Date.today()
        expiry_limit = today + timedelta(days=30)
        
        expiring_cards = self.search([
            ('expiry_date', '<=', expiry_limit),
            ('expiry_date', '>=', today),
            ('state', 'in', ['available', 'assigned'])
        ])
        
        for card in expiring_cards:
            days_until_expiry = (card.expiry_date - today).days
            
            # Buscar si ya existe una actividad pendiente para esta tarjeta
            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', 'fuel.magnetic.card'),
                ('res_id', '=', card.id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
                ('summary', 'ilike', 'vencer')
            ])
            
            if not existing_activity:
                card.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_("Tarjeta próxima a vencer"),
                    note=_(
                        "La tarjeta %s vence el %s (en %d días).\n"
                        "Por favor, tome las acciones necesarias."
                    ) % (card.name, card.expiry_date, days_until_expiry),
                    user_id=card.create_uid.id,
                    date_deadline=card.expiry_date - timedelta(days=7)
                )
                _logger.info("Actividad creada para tarjeta %s que vence en %d días", card.name, days_until_expiry)