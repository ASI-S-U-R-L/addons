# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class FirmaDocumentoWizardExtension(models.TransientModel):
    _inherit = 'firma.documento.wizard'
    
    from_workflow = fields.Boolean(string='Desde Solicitud de Firma', default=False)
    workflow_id = fields.Many2one('local.workflow', string='Solicitud de Firma')
    readonly_signature_config = fields.Boolean(string='Configuración de Solo Lectura', default=False)

    @api.model
    def default_get(self, fields_list):
        """Valores por defecto para el asistente"""
        res = super(FirmaDocumentoWizardExtension, self).default_get(fields_list)
        
        context = self.env.context
        if context.get('from_workflow') and context.get('workflow_id'):
            workflow = self.env['local.workflow'].browse(context.get('workflow_id'))
            if workflow.exists():
                res.update({
                    'from_workflow': True,
                    'workflow_id': workflow.id,
                    'readonly_signature_config': context.get('readonly_signature_config', False),
                })
                
                # Obtener datos del destinatario actual
                recipient_data = workflow._get_current_user_recipient_data()
                if recipient_data:
                    if 'signature_role' in fields_list and recipient_data['role']:
                        res['signature_role'] = recipient_data['role'].id
                    
                    if 'signature_position' in fields_list and recipient_data['position']:
                        res['signature_position'] = recipient_data['position']
                    
                    if 'signature_opaque_background' in fields_list:
                        res['signature_opaque_background'] = workflow.signature_opaque_background
                    
                    if 'sign_all_pages' in fields_list:
                        res['sign_all_pages'] = workflow.sign_all_pages
                    
                    _logger.info(
                        f"Wizard de firma local configurado desde solicitud {workflow.id} "
                        f"con rol {recipient_data['role'].name if recipient_data['role'] else 'N/A'} "
                        f"y posición {recipient_data['position']}"
                    )
        
        return res

    def action_firmar_documentos(self):
        """Acción principal para firmar todos los documentos seleccionados"""
        try:
            result = super(FirmaDocumentoWizardExtension, self).action_firmar_documentos()
            
            # Solo procesar el flujo si la firma fue exitosa
            if self.from_workflow and self.workflow_id and self.status == 'completado':
                try:
                    self._save_signed_documents_to_workflow()
                    self.workflow_id.action_mark_as_signed()
                    _logger.info(f"Solicitud de firma {self.workflow_id.id} marcada como firmada automáticamente")
                except Exception as e:
                    _logger.error(f"Error guardando documentos firmados o marcando solicitud: {e}")
                    # No re-lanzar el error para no afectar la firma exitosa
            
            return result
            
        except Exception as e:
            _logger.error(
                f"Error en action_firmar_documentos desde solicitud de firma "
                f"{self.workflow_id.id if self.workflow_id else 'N/A'}: {e}"
            )
            raise

    def _save_signed_documents_to_workflow(self):
        """Actualiza los documentos originales con las versiones firmadas"""
        if not self.from_workflow or not self.workflow_id:
            return
        
        _logger.info(f"Guardando documentos firmados para solicitud {self.workflow_id.id}")
        
        for doc_line in self.document_ids.filtered(lambda d: d.pdf_signed):
            try:
                _logger.info(f"Procesando documento firmado: {doc_line.document_name}")
                
                # Buscar el documento correspondiente en el flujo
                workflow_doc = self.workflow_id.document_ids.filtered(
                    lambda wd: wd.name == doc_line.document_name
                )
                
                if not workflow_doc:
                    # Intentar buscar por nombre base (sin extensión)
                    base_name = doc_line.document_name.replace('.pdf', '') if doc_line.document_name.endswith('.pdf') else doc_line.document_name
                    workflow_doc = self.workflow_id.document_ids.filtered(
                        lambda wd: wd.name.replace('.pdf', '') == base_name
                    )
                    
                    if workflow_doc:
                        _logger.info(f"Encontrado documento por nombre base: {workflow_doc[0].name}")
                    else:
                        _logger.error(f"No se pudo encontrar documento del flujo para {doc_line.document_name}")
                        continue
                
                workflow_doc = workflow_doc[0]
                
                if workflow_doc.attachment_id:
                    # Actualizar el contenido del adjunto original con la versión firmada
                    workflow_doc.attachment_id.write({
                        'datas': doc_line.pdf_signed,
                    })
                    _logger.info(f"Adjunto original {workflow_doc.attachment_id.id} actualizado con versión firmada")
                else:
                    # Si no existe adjunto original, crear uno nuevo
                    new_attachment = self.env['ir.attachment'].create({
                        'name': workflow_doc.name,
                        'datas': doc_line.pdf_signed,
                        'res_model': 'local.workflow.document',
                        'res_id': workflow_doc.id,
                        'mimetype': 'application/pdf',
                        'description': f'Documento firmado de la solicitud {self.workflow_id.name}',
                    })
                    workflow_doc.write({
                        'attachment_id': new_attachment.id,
                    })
                    _logger.info(f"Nuevo adjunto {new_attachment.id} creado para documento sin adjunto original")
                
                workflow_doc.write({
                    'is_signed': True,
                    'signed_date': fields.Datetime.now(),
                })
                
                _logger.info(
                    f"Documento {doc_line.document_name} actualizado exitosamente "
                    f"y marcado como firmado"
                )
                
            except Exception as e:
                _logger.error(f"Error guardando documento firmado {doc_line.document_name}: {e}")
                continue

    @api.onchange('signature_role', 'signature_position', 'signature_opaque_background', 'sign_all_pages')
    def _onchange_signature_config(self):
        """Prevenir cambios en configuración cuando viene de solicitud de firma"""
        if self.readonly_signature_config and self.from_workflow:
            if self.workflow_id:
                recipient_data = self.workflow_id._get_current_user_recipient_data()
                if recipient_data:
                    if recipient_data['role']:
                        self.signature_role = recipient_data['role'].id
                    if recipient_data['position']:
                        self.signature_position = recipient_data['position']
                    self.signature_opaque_background = self.workflow_id.signature_opaque_background
                    self.sign_all_pages = self.workflow_id.sign_all_pages
                    
                    return {
                        'warning': {
                            'title': _('Configuración Bloqueada'),
                            'message': _(
                                'La configuración de firma está definida por el creador '
                                'de la solicitud de firma y no puede ser modificada.'
                            )
                        }
                    }
