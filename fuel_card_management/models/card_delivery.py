# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FuelCardDelivery(models.Model):
    _name = 'fuel.card.delivery'
    _description = 'Entrega/Devolución de Tarjeta de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo'), tracking=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    
    card_id = fields.Many2one('fuel.magnetic.card', string='Tarjeta', required=True, tracking=True)
    
    delivery_type = fields.Selection([
        ('delivery', 'Entrega'),
        ('return', 'Devolución')
    ], string='Tipo', required=True, default='delivery', tracking=True)
    
    # Cambiado a res.partner con dominio para conductores
    driver_id = fields.Many2one(
        'res.partner', 
        string='Conductor', 
        tracking=True, 
        domain="[('is_driver', '=', True)]"
    )
    
    # MODIFICADO: Vehículo ahora es obligatorio
    vehicle_id = fields.Many2one(
        'fleet.vehicle', 
        string='Vehículo', 
        tracking=True,
        required=True
    )
    
    # Campo para especificar el motor en vehículos tecnológicos
    engine_type = fields.Selection([
        ('main', 'Motor Principal'),
        ('secondary', 'Motor Secundario')
    ], string='Tipo de Motor', tracking=True,
       help="Para vehículos tecnológicos, especifica a qué motor se asigna la tarjeta")
    
    balance = fields.Float(string='Saldo Actual', related='card_id.current_balance', readonly=True)
    
    # Campos relacionados para mostrar información de la tarjeta
    card_type = fields.Selection(related='card_id.card_type', string='Tipo de Tarjeta', readonly=True)
    card_operational_state = fields.Selection(related='card_id.operational_state', string='Estado Operativo', readonly=True)
    card_expiry_date = fields.Date(related='card_id.expiry_date', string='Fecha de Vencimiento', readonly=True)
    
    # Campos para mostrar asignación actual (para devoluciones)
    card_current_driver_id = fields.Many2one(related='card_id.driver_id', string='Conductor Actual', readonly=True)
    card_current_vehicle_id = fields.Many2one(related='card_id.vehicle_id', string='Vehículo Actual', readonly=True)
    
    # Campos relacionados del vehículo
    vehicle_custom_type = fields.Selection(related='vehicle_id.vehicle_custom_type', string='Tipo de Vehículo', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    notes = fields.Text(string='Notas')
    
    def _get_sequence_code(self):
        """Obtener el código de secuencia según el tipo de operación"""
        if self.delivery_type == 'delivery':
            return 'fuel.card.delivery'
        else:  # return
            return 'fuel.card.return'
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            # Crear registro temporal para determinar la secuencia
            temp_record = self.new(vals)
            sequence_code = temp_record._get_sequence_code()
            vals['name'] = self.env['ir.sequence'].next_by_code(sequence_code) or _('Nuevo')
        return super(FuelCardDelivery, self).create(vals)
    
    @api.onchange('delivery_type')
    def _onchange_delivery_type(self):
        # Limpiar la tarjeta seleccionada al cambiar el tipo
        self.card_id = False
        self.driver_id = False
        self.vehicle_id = False
        self.engine_type = False
        
        # Regenerar secuencia si es necesario
        if self.name == _('Nuevo') or not self.name:
            sequence_code = self._get_sequence_code()
            self.name = self.env['ir.sequence'].next_by_code(sequence_code) or _('Nuevo')
        
        if self.delivery_type == 'delivery':
            # Para entrega, mostrar solo tarjetas disponibles
            return {'domain': {'card_id': [('operational_state', '=', 'available'), ('active', '=', True)]}}
        else:
            # Para devolución, mostrar solo tarjetas asignadas
            return {'domain': {'card_id': [('operational_state', '=', 'assigned'), ('active', '=', True)]}}
    
    @api.onchange('card_id')
    def _onchange_card_id(self):
        if self.card_id:
            # Si es devolución, llenar con los datos actuales de la tarjeta
            if self.delivery_type == 'return':
                self.driver_id = self.card_id.driver_id
                self.vehicle_id = self.card_id.vehicle_id
                # AUTO-COMPLETAR: Obtener el tipo de motor de la tarjeta si está asignada
                if self.card_id.engine_type:
                    self.engine_type = self.card_id.engine_type
            else:
                # Si es entrega, limpiar los campos para permitir asignación nueva
                self.driver_id = False
                self.vehicle_id = False
                self.engine_type = False
    
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Lógica específica según el tipo de vehículo"""
        if self.vehicle_id:
            # Solo limpiar engine_type al cambiar vehículo si es una entrega
            # En devoluciones, mantener el engine_type que viene de la tarjeta
            if self.delivery_type == 'delivery':
                self.engine_type = False
            
            # Si el vehículo tiene conductor asignado, sugerirlo
            if hasattr(self.vehicle_id, 'driver_id') and self.vehicle_id.driver_id:
                self.driver_id = self.vehicle_id.driver_id
            
            # Mostrar/ocultar campo engine_type según el tipo de vehículo
            if self.vehicle_id.vehicle_custom_type == 'tecnologico':
                # Para vehículos tecnológicos en entregas, el campo engine_type es requerido
                if self.delivery_type == 'delivery':
                    return {
                        'warning': {
                            'title': _('Vehículo Tecnológico'),
                            'message': _('Este vehículo tecnológico puede tener hasta 2 tarjetas. '
                                       'Debe especificar el tipo de motor para la asignación.')
                        }
                    }
        else:
            # Solo limpiar engine_type si es una entrega
            if self.delivery_type == 'delivery':
                self.engine_type = False
    
    @api.constrains('card_id', 'delivery_type')
    def _check_card_state(self):
        for delivery in self:
            if delivery.card_id:
                if delivery.delivery_type == 'delivery' and not delivery.card_id.can_be_delivered():
                    raise ValidationError(_("Solo puede entregar tarjetas que estén disponibles."))
                elif delivery.delivery_type == 'return' and not delivery.card_id.can_be_returned():
                    raise ValidationError(_("Solo puede recibir tarjetas que estén asignadas."))
    
    @api.constrains('card_type', 'vehicle_id', 'delivery_type', 'engine_type')
    def _check_card_type_assignment(self):
        """Validar que la asignación sea compatible con el tipo de tarjeta y vehículo"""
        for delivery in self:
            if delivery.delivery_type == 'delivery' and delivery.card_id:
                # OBLIGATORIO: Verificar que siempre haya un vehículo en entregas
                if not delivery.vehicle_id:
                    raise ValidationError(_("Es obligatorio seleccionar un vehículo para realizar entregas de tarjetas."))
                
                card_type = delivery.card_type
                
                # Validaciones específicas por tipo de tarjeta
                if card_type == 'vehicle':
                    if not delivery.vehicle_id:
                        raise ValidationError(_("Las tarjetas de vehículo requieren un vehículo asignado."))
                
                # Validaciones específicas por tipo de vehículo SOLO para entregas
                if delivery.vehicle_id:
                    vehicle_type = delivery.vehicle_id.vehicle_custom_type
                    
                    if vehicle_type == 'tecnologico':
                        if not delivery.engine_type:
                            raise ValidationError(_(
                                "Para vehículos tecnológicos debe especificar el tipo de motor "
                                "(Principal o Secundario) al asignar la tarjeta."
                            ))
                    elif vehicle_type in ['movil', 'estacionario']:
                        if delivery.engine_type:
                            raise ValidationError(_(
                                "Los vehículos móviles y estacionarios no requieren especificar tipo de motor."
                            ))
    
    @api.constrains('vehicle_id', 'delivery_type', 'state', 'engine_type')
    def _check_unique_assignment(self):
        """Validar asignación única según el tipo de vehículo"""
        for delivery in self:
            if delivery.delivery_type == 'delivery' and delivery.state in ['draft', 'confirmed']:
                
                if delivery.vehicle_id:
                    vehicle_type = delivery.vehicle_id.vehicle_custom_type
                    
                    if vehicle_type == 'tecnologico':
                        # Para vehículos tecnológicos, validar por tipo de motor
                        if delivery.engine_type:
                            existing_cards = self.env['fuel.magnetic.card'].search([
                                ('vehicle_id', '=', delivery.vehicle_id.id),
                                ('engine_type', '=', delivery.engine_type),
                                ('operational_state', '=', 'assigned'),
                                ('active', '=', True),
                                ('id', '!=', delivery.card_id.id)
                            ])
                            
                            if existing_cards:
                                engine_label = dict(self._fields['engine_type'].selection)[delivery.engine_type]
                                card_names = ', '.join(existing_cards.mapped('name'))
                                raise ValidationError(_(
                                    "El vehículo tecnológico '%s' ya tiene asignada una tarjeta al %s: %s.\n"
                                    "Cada motor solo puede tener una tarjeta asignada."
                                ) % (delivery.vehicle_id.name, engine_label.lower(), card_names))
                        
                        # Validar que no exceda el límite de 2 tarjetas por vehículo tecnológico
                        total_cards = self.env['fuel.magnetic.card'].search_count([
                            ('vehicle_id', '=', delivery.vehicle_id.id),
                            ('operational_state', '=', 'assigned'),
                            ('active', '=', True),
                            ('id', '!=', delivery.card_id.id)
                        ])
                        
                        if total_cards >= 2:
                            raise ValidationError(_(
                                "El vehículo tecnológico '%s' ya tiene el máximo de 2 tarjetas asignadas.\n"
                                "Debe devolver una tarjeta antes de asignar otra."
                            ) % delivery.vehicle_id.name)
                    
                    elif vehicle_type in ['movil', 'estacionario']:
                        # Para vehículos móviles y estacionarios, solo una tarjeta
                        existing_cards = self.env['fuel.magnetic.card'].search([
                            ('vehicle_id', '=', delivery.vehicle_id.id),
                            ('operational_state', '=', 'assigned'),
                            ('active', '=', True),
                            ('id', '!=', delivery.card_id.id)
                        ])
                        
                        if existing_cards:
                            vehicle_type_label = dict(delivery.vehicle_id._fields['vehicle_custom_type'].selection)[vehicle_type]
                            card_names = ', '.join(existing_cards.mapped('name'))
                            raise ValidationError(_(
                                "El vehículo %s '%s' ya tiene asignada la tarjeta: %s.\n"
                                "Los vehículos %s solo pueden tener una tarjeta asignada."
                            ) % (vehicle_type_label.lower(), delivery.vehicle_id.name, 
                                card_names, vehicle_type_label.lower()))
    
    def _validate_delivery_requirements(self):
        """Validar todos los requisitos antes de confirmar una entrega"""
        self.ensure_one()
        
        if self.delivery_type == 'delivery':
            # OBLIGATORIO: Debe tener un vehículo asignado para todas las entregas
            if not self.vehicle_id:
                raise ValidationError(_("Debe asignar un vehículo para realizar la entrega de la tarjeta."))
            
            # Validar asignación según tipo de tarjeta
            if self.card_type == 'vehicle' and not self.vehicle_id:
                raise ValidationError(_("Debe asignar un vehículo para tarjetas de tipo vehículo."))
            
            # Validar requisitos específicos por tipo de vehículo SOLO para entregas
            if self.vehicle_id:
                vehicle_type = self.vehicle_id.vehicle_custom_type
                
                if vehicle_type == 'tecnologico' and not self.engine_type:
                    raise ValidationError(_(
                        "Para vehículos tecnológicos debe especificar el tipo de motor."
                    ))
        
        # Para devoluciones, no validar engine_type ya que se auto-completa
    
    def action_confirm(self):
        for delivery in self:
            if delivery.state == 'draft':
                # Validar requisitos antes de confirmar
                delivery._validate_delivery_requirements()
                
                if delivery.delivery_type == 'delivery':
                    # Verificar que la tarjeta esté disponible
                    if not delivery.card_id.can_be_delivered():
                        raise ValidationError(_("Solo puede entregar tarjetas que estén disponibles."))
                    
                    # Verificación final de asignación única justo antes de confirmar
                    if delivery.vehicle_id:
                        vehicle_type = delivery.vehicle_id.vehicle_custom_type
                        
                        if vehicle_type == 'tecnologico':
                            # Para tecnológicos, verificar por tipo de motor
                            if delivery.engine_type:
                                existing_cards = self.env['fuel.magnetic.card'].search([
                                    ('vehicle_id', '=', delivery.vehicle_id.id),
                                    ('engine_type', '=', delivery.engine_type),
                                    ('operational_state', '=', 'assigned'),
                                    ('active', '=', True)
                                ])
                                if existing_cards:
                                    engine_label = dict(delivery._fields['engine_type'].selection)[delivery.engine_type]
                                    card_names = ', '.join(existing_cards.mapped('name'))
                                    raise ValidationError(_(
                                        "No se puede confirmar la entrega. El %s del vehículo '%s' "
                                        "ya tiene asignada la tarjeta: %s."
                                    ) % (engine_label.lower(), delivery.vehicle_id.name, card_names))
                        else:
                            # Para móviles y estacionarios, verificar asignación única
                            existing_cards = self.env['fuel.magnetic.card'].search([
                                ('vehicle_id', '=', delivery.vehicle_id.id),
                                ('operational_state', '=', 'assigned'),
                                ('active', '=', True)
                            ])
                            if existing_cards:
                                card_names = ', '.join(existing_cards.mapped('name'))
                                raise ValidationError(_(
                                    "No se puede confirmar la entrega. El vehículo '%s' ya tiene asignada "
                                    "la tarjeta: %s.\nPrimero debe devolver la tarjeta existente."
                                ) % (delivery.vehicle_id.name, card_names))
                    
                    # Entregar tarjeta
                    delivery.card_id._set_delivered(
                        driver_id=delivery.driver_id.id if delivery.driver_id else False,
                        vehicle_id=delivery.vehicle_id.id if delivery.vehicle_id else False,
                        engine_type=delivery.engine_type if delivery.engine_type else False
                    )
                    
                    # Mensaje de seguimiento
                    engine_info = ""
                    if delivery.engine_type and delivery.vehicle_id.vehicle_custom_type == 'tecnologico':
                        engine_label = dict(delivery._fields['engine_type'].selection)[delivery.engine_type]
                        engine_info = f" ({engine_label})"
                    
                    delivery.card_id.message_post(
                        body=_("Tarjeta entregada mediante: %s%s") % (delivery.name, engine_info),
                        message_type='notification'
                    )
                    
                else: 
                    # Verificar que la tarjeta esté asignada
                    if not delivery.card_id.can_be_returned():
                        raise ValidationError(_("Solo puede recibir tarjetas que estén asignadas."))
                    
                    # Devolver tarjeta
                    delivery.card_id._set_returned()
                    
                    # Mensaje de seguimiento
                    delivery.card_id.message_post(
                        body=_("Tarjeta devuelta mediante: %s") % delivery.name,
                        message_type='notification'
                    )
                
                delivery.state = 'confirmed'
                
                # Mensaje en el registro de entrega
                delivery.message_post(
                    body=_("Proceso de %s confirmado para la tarjeta %s") % (
                        'entrega' if delivery.delivery_type == 'delivery' else 'devolución',
                        delivery.card_id.name
                    ),
                    message_type='notification'
                )
    
    def action_cancel(self):
        for delivery in self:
            if delivery.state == 'confirmed':
                # Revertir cambios en la tarjeta
                if delivery.delivery_type == 'delivery':
                    # Si fue una entrega, devolver la tarjeta a disponible
                    delivery.card_id._set_returned()
                    
                    # Mensaje de seguimiento
                    delivery.card_id.message_post(
                        body=_("Entrega cancelada, tarjeta devuelta a disponible: %s") % delivery.name,
                        message_type='notification'
                    )
                    
                else:  
                    # Si fue una devolución, volver a asignar la tarjeta
                    delivery.card_id._set_delivered(
                        driver_id=delivery.driver_id.id if delivery.driver_id else False,
                        vehicle_id=delivery.vehicle_id.id if delivery.vehicle_id else False,
                        engine_type=delivery.engine_type if delivery.engine_type else False
                    )
                    
                    # Mensaje de seguimiento
                    delivery.card_id.message_post(
                        body=_("Devolución cancelada, tarjeta vuelve a estar asignada: %s") % delivery.name,
                        message_type='notification'
                    )
                
                delivery.state = 'cancelled'
            elif delivery.state == 'draft':
                delivery.state = 'cancelled'
            
            # Mensaje en el registro de entrega
            delivery.message_post(
                body=_("Proceso de %s cancelado") % (
                    'entrega' if delivery.delivery_type == 'delivery' else 'devolución'
                ),
                message_type='notification'
            )
    
    def action_reset_to_draft(self):
        for delivery in self:
            if delivery.state == 'cancelled':
                delivery.state = 'draft'
                
                # Mensaje en el registro de entrega
                delivery.message_post(
                    body=_("Proceso devuelto a borrador"),
                    message_type='notification'
                )
    
    def name_get(self):
        """Personalizar la representación del nombre"""
        result = []
        for delivery in self:
            name = delivery.name
            if delivery.card_id:
                operation = _('Entrega') if delivery.delivery_type == 'delivery' else _('Devolución')
                engine_info = ""
                if delivery.engine_type and delivery.vehicle_id and delivery.vehicle_id.vehicle_custom_type == 'tecnologico':
                    engine_label = dict(delivery._fields['engine_type'].selection)[delivery.engine_type]
                    engine_info = f" - {engine_label}"
                name = f"{name} - {operation} {delivery.card_id.name}{engine_info}"
            result.append((delivery.id, name))
        return result
