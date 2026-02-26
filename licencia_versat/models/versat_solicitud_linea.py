# -*- coding: utf-8 -*-
from odoo import models, fields


class VersatSolicitudLinea(models.Model):
    _name = 'versat.solicitud.linea'
    _description = 'Línea de Servicio en Solicitud de Licencia'
    _order = 'sequence, id'

    solicitud_id = fields.Many2one(
        'versat.solicitud',
        string='Solicitud',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    servicio_id = fields.Many2one(
        'versat.servicio',
        string='Servicio',
        required=True,
    )
    clave_registro = fields.Char(string='Clave de Registro', required=True)

    # Indica si ya existe una solicitud pendiente para este servicio en la API
    solicitud_pendiente = fields.Boolean(
        string='Solicitud Pendiente',
        default=False,
        readonly=True,
        help='Ya existe una solicitud pendiente (no otorgada) para este servicio en el sistema.',
    )
    solicitud_pendiente_no = fields.Char(
        string='Nº Sol. Pendiente',
        readonly=True,
    )

    state = fields.Selection(
        selection=[
            ('pendiente', 'Pendiente'),
            ('enviado', 'Enviado'),
            ('error', 'Error'),
        ],
        string='Estado',
        default='pendiente',
        readonly=True,
    )
    respuesta_api = fields.Text(string='Respuesta', readonly=True)
