# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def get_merchandise_report_data(self):
        """Obtiene datos del pedido para el reporte de mercancías"""
        self.ensure_one()
        
        lines_data = []
        for line in self.lines:
            category = line.product_id.pos_categ_id or line.product_id.categ_id
            lines_data.append({
                'product_name': line.product_id.name,
                'category_name': category.name if category else 'Sin Categoría',
                'quantity': line.qty,
                'price_unit': line.price_unit,
                'total_amount': line.qty * line.price_unit,
            })
        
        return lines_data
