# -*- coding: utf-8 -*-
from odoo import models, fields


class VersatServicio(models.Model):
    _name = 'versat.servicio'
    _description = 'Servicio Versat'
    _order = 'descripcion'

    servicio_id = fields.Char(string='ID Externo', required=True, index=True)
    descripcion = fields.Char(string='Descripción', required=True)
    clave_registro = fields.Char(string='Clave de Registro')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('servicio_id_unique', 'UNIQUE(servicio_id)', 'El ID del servicio debe ser único.'),
    ]

    def name_get(self):
        return [(r.id, r.descripcion) for r in self]
