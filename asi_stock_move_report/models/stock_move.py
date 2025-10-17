# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move"

    final_stock_source = fields.Float(
        string='Existencia Final Origen',
        digits='Product Unit of Measure',
        readonly=True,
        store=True,
        copy=False,
        help='Cantidad disponible en la ubicación de origen después del movimiento'
    )

    final_stock_dest = fields.Float(
        string='Existencia Final Destino',
        digits='Product Unit of Measure',
        readonly=True,
        store=True,
        copy=False,
        help='Cantidad disponible en la ubicación de destino después del movimiento'
    )

    def _get_final_stock_quantity(self, product, location):
        """Obtener la cantidad disponible de un producto en una ubicación específica.
        Retorna 0 si la ubicación no es un almacén propio (ej: Partner)."""
        if not product or not location:
            return 0.0

        # Si la ubicación no es de tipo 'internal' (almacén propio), retornar 0
        if location.usage != 'internal':
            return 0.0

        # Obtener cantidad disponible usando stock.quant
        return self.env['stock.quant']._get_available_quantity(product, location)

    def _compute_final_stocks(self):
        """Calcular existencias finales para almacén origen y destino después del movimiento."""
        for move in self:
            product = move.product_id
            qty_done = move.quantity_done or 0.0

            if float_is_zero(qty_done, precision_rounding=product.uom_id.rounding):
                move.final_stock_source = 0.0
                move.final_stock_dest = 0.0
                continue

            # Calcular existencia final en origen
            source_stock = 0.0
            if move.location_id:
                current_source_stock = self._get_final_stock_quantity(product, move.location_id)
                # Para origen: stock actual (si es almacén propio)
                if move.location_id.usage == 'internal':
                    source_stock = current_source_stock 
                else:
                    source_stock = 0.0  # No propio = 0

            # Calcular existencia final en destino
            dest_stock = 0.0
            if move.location_dest_id:
                current_dest_stock = self._get_final_stock_quantity(product, move.location_dest_id)
                # Para destino: stock actual (si es almacén propio)
                if move.location_dest_id.usage == 'internal':
                    dest_stock = current_dest_stock 
                else:
                    dest_stock = 0.0  # No propio = 0

            move.final_stock_source = source_stock
            move.final_stock_dest = dest_stock

    def _action_done(self, cancel_backorder=False):
        res = super(StockMove, self)._action_done(cancel_backorder)
        
        # Calcular existencias finales después de que se complete el movimiento
        res._compute_final_stocks()
        
        # Registrar cantidad restante por almacén en el historial
        History = self.env['product.warehouse.qty.history']
        for move in res:
            # Solo procesar movimientos completados que afecten productos almacenables
            if move.state != 'done' or move.product_id.type != 'product':
                continue
            
            # Determinar almacenes afectados
            warehouses = set()
            if move.location_id.warehouse_id:
                warehouses.add(move.location_id.warehouse_id)
            if move.location_dest_id.warehouse_id:
                warehouses.add(move.location_dest_id.warehouse_id)
            
            for warehouse in warehouses:
                # Usar las existencias finales calculadas según la ubicación
                if warehouse == move.location_id.warehouse_id:
                    qty_after = move.final_stock_source
                elif warehouse == move.location_dest_id.warehouse_id:
                    qty_after = move.final_stock_dest
                else:
                    # Fallback: obtener cantidad actual en el almacén
                    qty_after = move.product_id.with_context(
                        warehouse=warehouse.id
                    ).qty_available
                
                # Crear registro histórico
                History.create({
                    'move_id': move.id,
                    'product_id': move.product_id.id,
                    'warehouse_id': warehouse.id,
                    'qty_after': qty_after,
                })
        
        return res
