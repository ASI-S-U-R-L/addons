
from odoo import fields, models

class PosConfig(models.Model):
    _inherit = "pos.config"

    hide_customer_button = fields.Boolean(
        string="Ocultar botón de cliente en POS",
        help="Si está activo, el botón 'Cliente' no se muestra en la pantalla de productos del POS.",
        default=False,
    )

#   force_opening_by_denominations = fields.Boolean(
#         string="Forzar apertura por denominaciones",
#         help="Obliga a usar el conteo por monedas/billetes para fijar el efectivo de apertura y desactiva la edición manual."
#     )
