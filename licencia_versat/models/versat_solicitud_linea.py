# -*- coding: utf-8 -*-
from odoo import models, fields


class VersatSolicitudLinea(models.Model):
    _name = 'versat.solicitud.linea'
    _description = 'Línea de Servicio en Solicitud de Licencia'
    _order = 'sequence, id'

    solicitud_id = fields.Many2one('versat.solicitud', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    servicio_id = fields.Many2one('versat.servicio', string='Servicio', required=True)
    clave_registro = fields.Char(string='Clave de Registro', required=True)
    solicitud_pendiente = fields.Boolean(string='⚠ Pendiente', default=False, readonly=True)
    solicitud_pendiente_no = fields.Char(string='Nº Sol. Existente', readonly=True)
    state = fields.Selection([
        ('pendiente', 'Pendiente'),
        ('enviado', 'Enviado'),
        ('error', 'Error'),
    ], default='pendiente', readonly=True)
    respuesta_api = fields.Text(string='Respuesta', readonly=True)
