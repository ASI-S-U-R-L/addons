# -*- coding: utf-8 -*-
from odoo import models, fields


class VersatPersona(models.Model):
    _name = 'versat.persona'
    _description = 'Persona Solicitante Versat'
    _order = 'nombre_completo'

    persona_id = fields.Char(string='ID Externo', required=True, index=True)
    nombre_completo = fields.Char(string='Nombre Completo', required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('persona_id_unique', 'UNIQUE(persona_id)', 'El ID de persona debe ser único.'),
    ]

    def name_get(self):
        return [(r.id, r.nombre_completo) for r in self]
