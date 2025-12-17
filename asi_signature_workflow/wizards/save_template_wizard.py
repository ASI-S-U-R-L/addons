# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class SaveTemplateWizard(models.TransientModel):
    _name = 'save.template.wizard'
    _description = 'Asistente para Guardar Plantilla de Flujo'

    # Referencia al wizard principal
    workflow_wizard_id = fields.Many2one(
        'signature.workflow.wizard', 
        string='Wizard Principal',
        required=True,
        ondelete='cascade'
    )
    
    # Opción de guardar
    save_as_template = fields.Boolean(
        string='¿Guardar como nueva plantilla?',
        default=False
    )
    
    template_name = fields.Char(
        string='Nombre de la Plantilla',
        help='Nombre con el que se guardará la plantilla'
    )
    
    template_description = fields.Text(
        string='Descripción de la Plantilla',
        help='Descripción opcional de la plantilla'
    )
    
    # Campos informativos (solo lectura)
    document_source_display = fields.Char(
        string='Origen de Documentos', 
        compute='_compute_display_fields'
    )
    sign_all_pages_display = fields.Boolean(
        string='Firma todas las páginas', 
        compute='_compute_display_fields'
    )
    opaque_background_display = fields.Boolean(
        string='Fondo opaco', 
        compute='_compute_display_fields'
    )
    recipients_display = fields.Html(
        string='Destinatarios', 
        compute='_compute_display_fields'
    )

    @api.depends('workflow_wizard_id')
    def _compute_display_fields(self):
        for record in self:
            wizard = record.workflow_wizard_id
            if wizard:
                # Origen de documentos
                source_dict = dict(wizard._fields['document_source'].selection)
                record.document_source_display = source_dict.get(wizard.document_source, '')
                
                record.sign_all_pages_display = wizard.sign_all_pages
                record.opaque_background_display = wizard.signature_opaque_background
                
                # Construir HTML de destinatarios
                recipients_html = '<ul>'
                for i in range(1, 5):
                    user = getattr(wizard, f'target_user_id_{i}')
                    if user:
                        role = getattr(wizard, f'signature_role_id_{i}')
                        position = getattr(wizard, f'signature_position_{i}')
                        position_name = dict(wizard._fields['signature_position_1'].selection).get(position, '')
                        recipients_html += f'<li><strong>{i}.</strong> Usuario: {user.name}, Rol: {role.name if role else "N/A"}, Posición: {position_name}</li>'
                recipients_html += '</ul>'
                record.recipients_display = recipients_html
            else:
                record.document_source_display = ''
                record.sign_all_pages_display = False
                record.opaque_background_display = False
                record.recipients_display = ''

    @api.constrains('save_as_template', 'template_name')
    def _check_template_name(self):
        for record in self:
            if record.save_as_template and not record.template_name:
                raise ValidationError(_('Debe proporcionar un nombre para la plantilla.'))

    def action_continue_without_saving(self):
        """Continúa sin guardar la plantilla"""
        self.ensure_one()
        return self._create_workflow()

    def action_save_and_continue(self):
        """Guarda la plantilla y luego crea el flujo"""
        self.ensure_one()
        
        if not self.template_name:
            raise UserError(_('Debe proporcionar un nombre para la plantilla.'))
        
        # Crear la plantilla
        template = self._create_template()
        _logger.info(f"Plantilla '{template.name}' creada exitosamente con ID: {template.id}")
        
        # Crear el flujo
        return self._create_workflow()

    def _create_template(self):
        """Crea una nueva plantilla basada en los datos del wizard"""
        self.ensure_one()
        wizard = self.workflow_wizard_id
        
        # Crear plantilla base
        template_vals = {
            'name': self.template_name,
            'description': self.template_description,
            'document_source': wizard.document_source,
            'signature_opaque_background': wizard.signature_opaque_background,
            'sign_all_pages': wizard.sign_all_pages,
        }
        
        template = self.env['signature.workflow.template'].create(template_vals)
        
        # Crear líneas de destinatarios
        sequence = 10
        for i in range(1, 5):
            user = getattr(wizard, f'target_user_id_{i}')
            if user:
                role = getattr(wizard, f'signature_role_id_{i}')
                position = getattr(wizard, f'signature_position_{i}')
                
                self.env['signature.workflow.template.recipient'].create({
                    'template_id': template.id,
                    'sequence': sequence,
                    'target_user_id': user.id,
                    'signature_role_id': role.id,
                    'signature_position': position,
                })
                sequence += 10
        
        return template

    def _create_workflow(self):
        """Delega la creación del flujo al wizard principal"""
        self.ensure_one()
        return self.workflow_wizard_id._do_create_workflow()
