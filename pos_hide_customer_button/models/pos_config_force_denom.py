from odoo import fields, models

class PosConfigForceDenominations(models.Model):
    _inherit = 'pos.config'

    force_opening_by_denominations = fields.Boolean(
        string="Forzar apertura por denominaciones",
        help="Obliga a usar el conteo por monedas/billetes para fijar el efectivo de apertura y desactiva la edición manual."
    )
