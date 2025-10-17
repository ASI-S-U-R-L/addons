# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class LocalWorkflowRejectWizard(models.TransientModel):
    _name = 'local.workflow.reject.wizard'
    _description = 'Wizard para Rechazar Solicitud de Firma Local'

    workflow_id = fields.Many2one('local.workflow', string='Flujo', required=True)
    rejection_notes = fields.Text(
        string='Motivo del Rechazo',
        required=True,
        placeholder='Por favor, explique el motivo del rechazo...'
    )

    def action_confirm_rejection(self):
        """Confirma el rechazo de la solicitud"""
        self.ensure_one()
        
        if not self.rejection_notes.strip():
            raise UserError(_('Debe proporcionar un motivo para el rechazo.'))
        
        # Procesar el rechazo en el flujo
        self.workflow_id._process_rejection(self.rejection_notes)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Solicitud de Firma "{self.workflow_id.name}" rechazada exitosamente',
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window_close'
                }
            }
        }
