# -*- coding: utf-8 -*-

from odoo import api, fields, models

class ProductWarehouseQtyHistory(models.Model):
    _name = 'product.warehouse.qty.history'
    _description = 'Histórico de Cantidades por Producto y Almacén'
    _order = 'create_date desc'

    move_id = fields.Many2one('stock.move', string='Movimiento', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Almacén', required=True)
    qty_after = fields.Float(string='Cantidad después del movimiento', digits='Product Unit of Measure')
    date = fields.Datetime(string='Fecha', related='move_id.date', store=True)