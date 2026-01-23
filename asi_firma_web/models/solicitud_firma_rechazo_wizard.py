# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SolicitudFirmaRechazoWizard(models.TransientModel):
    _name = 'solicitud.firma.rechazo.wizard'
    _description = 'Wizard para Rechazar Solicitud de Firma'

    solicitud_id = fields.Many2one(
        'solicitud.firma',
        string='Solicitud',
        required=True,
        readonly=True
    )
    
    motivo_rechazo = fields.Text(
        string='Motivo de Rechazo',
        required=True,
        help='Por favor indique el motivo del rechazo'
    )
    
    def action_rechazar(self):
        """Rechazar la solicitud con el motivo proporcionado"""
        self.ensure_one()
        if self.solicitud_id:
            self.solicitud_id.action_marcar_como_rechazado(self.motivo_rechazo)
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}