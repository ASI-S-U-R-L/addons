from odoo import fields, models

class PosConfig(models.Model):
    _inherit = "pos.config"

    hide_customer_button = fields.Boolean(
        string="Ocultar botones de [Cliente, Nota Cliente, Reembolso, Presupuesto/pedidos] en POS",
        help="Si está activo, los botones no se muestran en la pantalla del POS.",
        default=False,
    )

    force_opening_by_denominations = fields.Boolean(
        string="Forzar apertura y cierre de caja por denominaciones de billetes.",
        help="Obliga a usar el conteo por monedas/billetes para fijar el efectivo de apertura/cierre y desactiva la edición manual.",
        default=False,
    )
    
    hide_bank_payment = fields.Boolean(
        string="Ocultar método de pago 'Banco' en pantalla de pagos",
        help="Si está activo, oculta el botón de pago por banco (transferencia) en la pantalla de pagos del POS.",
        default=False,
    )
    # show_product_stock = fields.Boolean(
    #     string="Mostrar stock de productos en POS",
    #     help="Si está activo, muestra el stock actual de los productos en la vista del POS.",
    #     default=False,
    # )

    