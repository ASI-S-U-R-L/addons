# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class LocalWorkflowController(http.Controller):
    
    @http.route('/local_workflow/download_signed/<int:workflow_id>', type='http', auth='user')
    def download_signed_documents(self, workflow_id, **kwargs):
        """Controlador para mostrar página de descarga de documentos firmados"""
        try:
            workflow = request.env['local.workflow'].browse(workflow_id)
            
            if not workflow.exists():
                return request.not_found()
            
            # Verificar permisos (solo creador o destinatarios pueden descargar)
            current_user = request.env.user
            allowed_users = [workflow.creator_id]
            
            for i in range(1, 5):
                user = getattr(workflow, f'target_user_id_{i}')
                if user:
                    allowed_users.append(user)
            
            if current_user not in allowed_users:
                return request.redirect('/web/login')
            
            if workflow.state != 'completed':
                return request.not_found()
            
            return request.render('asi_local_workflow.download_signed_documents_page', {
                'workflow': workflow,
                'signed_documents': workflow.document_ids.filtered('is_signed'),
            })
            
        except Exception as e:
            _logger.error(f"Error accediendo a documentos de la solicitud {workflow_id}: {e}")
            return request.not_found()
