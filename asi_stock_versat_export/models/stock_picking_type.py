# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    # Definir la lista de selección para conceptos VERSAT
    VERSAT_CONCEPTS = [
        ('202', '202: Compras'),
        ('2100', '2100: Ventas'),
        ('203', '203: Transf. Recibidas'),
        ('2102', '2102: Transf. Enviadas'),
        ('2107', '2107: Devoluciones'),
        ('3116', '3116: Ventas POS'),
        ('3118', '3118: Salidas'),
        ('3119', '3119: Entradas'),
    ]

    versat_concept = fields.Selection(
        string='Concepto VERSAT',
        selection=VERSAT_CONCEPTS,
        help='Seleccione el concepto VERSAT para este tipo de operación'
    )
    
    versat_description = fields.Char(
        string='Descripción VERSAT',
        compute='_compute_versat_description',
        store=True
    )

    @api.depends('versat_concept')
    def _compute_versat_description(self):
        concept_mapping = {
            '202': 'Compras a proveedores',
            '2100': 'Ventas a clientes', 
            '203': 'Transferencias recibidas',
            '2102': 'Transferencias enviadas',
            '2107': 'Devoluciones de compra',
            '3116': 'Ventas punto de venta',
            '3118': 'Salidas de mercancía',
            '3119': 'Entradas de mercancía'
        }
        for record in self:
            if record.versat_concept:
                record.versat_description = concept_mapping.get(record.versat_concept, '')
            else:
                record.versat_description = 'No configurado'