# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class SignatureWorkflowTemplate(models.Model):
    _name = 'signature.workflow.template'
    _description = 'Plantilla de Flujo de Firma Digital'
    _order = 'name'

    name = fields.Char(string='Nombre de la Plantilla', required=True)
    active = fields.Boolean(string='Activo', default=True)
    
    # Configuración general
    document_source = fields.Selection([
        ('local', 'Documentos Locales'),
        ('alfresco', 'Documentos de Alfresco')
    ], string='Origen de Documentos', required=True)
    
    signature_opaque_background = fields.Boolean(
        string='Firma con fondo opaco',
        default=False,
        help='Si está marcado, la firma tendrá fondo blanco opaco en lugar de transparente'
    )
    
    sign_all_pages = fields.Boolean(
        string='Firmar todas las páginas',
        default=False,
        help='Si está marcado, se firmará todas las páginas del documento en lugar de solo la última'
    )
    
    # Destinatarios de la plantilla (almacenados como líneas)
    recipient_ids = fields.One2many(
        'signature.workflow.template.recipient', 
        'template_id', 
        string='Destinatarios'
    )
    
    recipient_count = fields.Integer(
        string='Cantidad de Destinatarios', 
        compute='_compute_recipient_count'
    )
    
    # Información adicional
    description = fields.Text(string='Descripción')
    creator_id = fields.Many2one(
        'res.users', 
        string='Creado por', 
        default=lambda self: self.env.user,
        readonly=True
    )
    create_date = fields.Datetime(string='Fecha de Creación', readonly=True)

    @api.depends('recipient_ids')
    def _compute_recipient_count(self):
        for record in self:
            record.recipient_count = len(record.recipient_ids)

    @api.constrains('recipient_ids')
    def _check_recipients(self):
        """Valida que haya al menos un destinatario y no más de 4"""
        for record in self:
            if len(record.recipient_ids) < 1:
                raise ValidationError(_('La plantilla debe tener al menos un destinatario.'))
            if len(record.recipient_ids) > 4:
                raise ValidationError(_('La plantilla no puede tener más de 4 destinatarios.'))
            
            # Validar posiciones únicas
            positions = [r.signature_position for r in record.recipient_ids]
            if len(positions) != len(set(positions)):
                raise ValidationError(_('Las posiciones de firma no pueden repetirse entre destinatarios.'))
            
            # Validar roles únicos
            roles = [r.signature_role_id.id for r in record.recipient_ids]
            if len(roles) != len(set(roles)):
                raise ValidationError(_('Los roles de firma no pueden repetirse entre destinatarios.'))


class SignatureWorkflowTemplateRecipient(models.Model):
    _name = 'signature.workflow.template.recipient'
    _description = 'Destinatario de Plantilla de Flujo de Firma'
    _order = 'sequence'

    template_id = fields.Many2one(
        'signature.workflow.template', 
        string='Plantilla', 
        required=True, 
        ondelete='cascade'
    )
    
    sequence = fields.Integer(string='Orden', default=10)
    
    target_user_id = fields.Many2one(
        'res.users',
        string='Usuario Destinatario',
        help='Usuario que firmará en esta posición'
    )
    
    signature_role_id = fields.Many2one(
        'document.signature.tag', 
        string='Rol de Firma', 
        required=True
    )
    
    signature_position = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de Firma', required=True)
