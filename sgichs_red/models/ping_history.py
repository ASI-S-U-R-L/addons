# -*- coding: utf-8 -*-
from odoo import models, fields

class PingHistory(models.Model):
    _name = 'it.hardware.ping.history'
    _description = 'Historial de Ping de Hardware'
    _order = 'ping_time desc'

    hardware_id = fields.Many2one(
        'it.asset.hardware',
        string='Hardware',
        required=True,
        ondelete='cascade'
    )
    ping_time = fields.Datetime(string='Fecha y Hora', default=fields.Datetime.now, required=True)
    status = fields.Selection([
        ('online', 'Online'),
        ('online_agent', 'Online (Vía Agente)'),
        ('offline', 'Offline'),
        ('unreachable', 'Inalcanzable'),
        ('pending', 'Pendiente'),
        ('unknown', 'Desconocido')
    ], string='Estado', required=True)
    response_time_ms = fields.Float(string='Tiempo de Respuesta (ms)')