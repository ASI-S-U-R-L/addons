# -*- coding: utf-8 -*-

from odoo import api, fields, models
from collections import defaultdict
from datetime import datetime

class ProductMoveReport(models.AbstractModel):
    _name = 'report.asi_stock_move_report.product_move_report_template'
    _description = 'Reporte de Movimientos por Producto'

    @api.model
    def _get_report_values(self, docids, data=None):
        if not data:
            data = {}
        
        date_start = data.get('date_start')
        date_end = data.get('date_end')
        product_id = data.get('product_id')
        warehouse_id = data.get('warehouse_id')
        
        # Obtener el producto seleccionado
        product = self.env['product.product'].browse(product_id)
        
        # Obtener ubicaciones del almacén seleccionado
        warehouse = self.env['stock.warehouse'].browse(warehouse_id) if warehouse_id else None
        warehouse_locations = self.env['stock.location']
        
        if warehouse:
            # Incluir todas las ubicaciones internas del almacén
            warehouse_locations = warehouse.lot_stock_id.child_ids | warehouse.lot_stock_id
            # También incluir ubicaciones virtuales relacionadas al almacén si existen
            virtual_locations = self.env['stock.location'].search([
                ('name', 'ilike', warehouse.code),
                ('usage', 'in', ['inventory', 'production', 'procurement'])
            ])
            warehouse_locations = warehouse_locations | virtual_locations
        
        # Obtener la existencia inicial correcta usando quants
        initial_stock = self._get_stock_quantity_at_date(product, date_start, warehouse_locations)
        
        # Obtener todos los movimientos del producto en el rango de fechas
        domain = [
            ('date', '>=', date_start),
            ('date', '<=', date_end),
            ('state', '=', 'done'),
            ('product_id', '=', product_id),
        ]
        
        # Filtrar por ubicaciones del almacén si se especifica
        if warehouse_locations:
            domain.append('|')
            domain.append(('location_id', 'in', warehouse_locations.ids))
            domain.append(('location_dest_id', 'in', warehouse_locations.ids))
        
        moves = self.env['stock.move'].search(domain, order='date asc')
        
        # Preparar datos de movimientos
        moves_data = []
        
        # Contadores detallados para el resumen
        totals = {
            'entradas_recepcion': 0.0,
            'entradas_ajuste': 0.0,
            'entradas_transferencia': 0.0,
            'entradas_devolucion': 0.0,
            'salidas_venta': 0.0,
            'salidas_transferencia': 0.0,
            'salidas_ajuste': 0.0,
            'salidas_consumo': 0.0,
        }
        
        for move in moves:
            # Verificar si el movimiento realmente afecta el stock del almacén
            stock_impact = self._calculate_stock_impact(move, warehouse_locations)
            if stock_impact == 0:
                continue  # No afecta el stock, saltar
                
            move_type = self._classify_move_detailed(move, warehouse_locations)
            quantity = abs(stock_impact)  # Usar el impacto calculado
            
            # Determinar qué ubicación es la del almacén seleccionado
            if warehouse_locations:
                if move.location_dest_id in warehouse_locations:
                    # Es una entrada al almacén, usar final_stock_dest
                    existencia_final = move.final_stock_dest
                elif move.location_id in warehouse_locations:
                    # Es una salida del almacén, usar final_stock_source
                    existencia_final = move.final_stock_source
                else:
                    # No debería llegar aquí, pero por seguridad
                    existencia_final = 0.0
            else:
                # Sin filtro de almacén, usar la ubicación de destino si es interna
                if move.location_dest_id.usage == 'internal':
                    existencia_final = move.final_stock_dest
                else:
                    existencia_final = move.final_stock_source
            
            # Calcular existencia antes del movimiento
            if stock_impact > 0:
                # Entrada: existencia_antes = existencia_final - cantidad
                existencia_antes = existencia_final - quantity
            else:
                # Salida: existencia_antes = existencia_final + cantidad
                existencia_antes = existencia_final + quantity
            
            # Determinar si es entrada o salida según el impacto en stock
            if stock_impact > 0:
                movement_direction = 'Entrada'
                # Asegurar que el tipo sea de entrada
                if not move_type.startswith('entrada_'):
                    move_type = 'entrada_' + move_type.split('_', 1)[-1] if '_' in move_type else 'entrada_recepcion'
                totals[move_type.replace('entrada_', 'entradas_')] += quantity
            else:
                movement_direction = 'Salida'
                # Asegurar que el tipo sea de salida
                if not move_type.startswith('salida_'):
                    move_type = 'salida_' + move_type.split('_', 1)[-1] if '_' in move_type else 'salida_transferencia'
                totals[move_type.replace('salida_', 'salidas_')] += quantity
            
            moves_data.append({
                'date': move.date,
                'cantidad_antes': existencia_antes,
                'cantidad_movida': quantity,
                'movement_direction': movement_direction,
                'product_uom': move.product_uom.name,
                'move_type_display': self._get_move_type_display(move_type),
                'existencia_final': existencia_final,
                'reference': move.reference or move.name or '',
            })
        
        return {
            'doc_ids': [1],
            'doc_model': 'product.move.report.wizard',
            'docs': [self.env['product.move.report.wizard'].browse(1)],
            'date_start': date_start,
            'date_end': date_end,
            'product': product,
            'warehouse': warehouse,
            'moves_data': moves_data,
            'total_movements': len(moves_data),
            'totals': totals,
            'company': self.env.company,
            'initial_stock': initial_stock,
        }
    
    def _calculate_stock_impact(self, move, warehouse_locations):
        """
        Calcula el impacto real del movimiento en el stock del almacén
        Retorna: > 0 para entradas, < 0 para salidas, 0 para movimientos sin impacto
        """
        if not warehouse_locations:
            # Sin filtro de almacén, usar lógica original
            if move.location_dest_id.usage == 'internal' and move.location_id.usage != 'internal':
                return move.product_uom_qty
            elif move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal':
                return -move.product_uom_qty
            return 0
        
        src_in_warehouse = move.location_id in warehouse_locations
        dest_in_warehouse = move.location_dest_id in warehouse_locations
        
        # Caso 1: Entrada desde fuera del almacén
        if not src_in_warehouse and dest_in_warehouse:
            return move.product_uom_qty
        
        # Caso 2: Salida hacia fuera del almacén
        elif src_in_warehouse and not dest_in_warehouse:
            return -move.product_uom_qty
        
        # Caso 3: Transferencia interna (dentro del mismo almacén)
        elif src_in_warehouse and dest_in_warehouse:
            return 0  # No afecta el stock total
        
        # Caso 4: Movimiento externo al almacén
        else:
            return 0
    
    def _classify_move_detailed(self, move, warehouse_locations=None):
        """
        Clasifica un movimiento según su tipo detallado considerando el contexto del almacén
        """
        location_src = move.location_id
        location_dest = move.location_dest_id
        
        # Determinar si es entrada o salida basado en el impacto real
        stock_impact = self._calculate_stock_impact(move, warehouse_locations)
        
        if stock_impact > 0:
            # Es una entrada
            if location_src.usage == 'supplier':
                return 'entrada_recepcion'
            elif location_src.usage == 'inventory':
                return 'entrada_ajuste'
            elif location_src.usage in ['customer', 'production']:
                return 'entrada_devolucion'
            elif location_src.usage in ['internal', 'transit']:
                return 'entrada_transferencia'
            else:
                return 'entrada_recepcion'
        elif stock_impact < 0:
            # Es una salida
            if location_dest.usage == 'customer':
                return 'salida_venta'
            elif location_dest.usage == 'inventory':
                return 'salida_ajuste'
            elif location_dest.usage == 'production':
                return 'salida_consumo'
            elif 'consumo' in location_dest.name.lower() or 'vale' in location_dest.name.lower():
                return 'salida_consumo'
            elif location_dest.usage in ['internal', 'transit']:
                return 'salida_transferencia'
            else:
                return 'salida_transferencia'
        
        # Fallback - no debería llegar aquí si stock_impact es 0
        return 'entrada_recepcion'
    
    def _get_move_type_display(self, move_type):
        """
        Retorna el nombre para mostrar del tipo de movimiento
        """
        type_mapping = {
            'entrada_recepcion': 'Recepción',
            'entrada_ajuste': 'Ajuste',
            'entrada_transferencia': 'Transferencia Interna',
            'entrada_devolucion': 'Devolución',
            'salida_venta': 'Venta',
            'salida_transferencia': 'Transferencia Interna',
            'salida_ajuste': 'Ajuste',
            'salida_consumo': 'Consumo',
        }
        return type_mapping.get(move_type, 'Recepción')
    
    def _get_stock_quantity_at_date(self, product, date, warehouse_locations=None):
        """
        Obtiene la cantidad en stock de un producto en una fecha específica para un almacén
        Usando movimientos históricos para mayor precisión
        """
        # Convertir a zona horaria UTC si es necesario
        if isinstance(date, str):
            date = fields.Datetime.from_string(date)
        
        # Construir dominio para movimientos
        domain = [
            ('product_id', '=', product.id),
            ('date', '<', date),
            ('state', '=', 'done'),
        ]
        
        if warehouse_locations:
            domain.append('|')
            domain.append(('location_id', 'in', warehouse_locations.ids))
            domain.append(('location_dest_id', 'in', warehouse_locations.ids))
        
        moves = self.env['stock.move'].search(domain)
        
        quantity = 0.0
        for move in moves:
            # Solo considerar movimientos que afecten el almacén especificado
            if warehouse_locations:
                # Entrada al almacén
                if move.location_dest_id in warehouse_locations and move.location_id not in warehouse_locations:
                    quantity += move.product_uom_qty
                # Salida del almacén
                elif move.location_id in warehouse_locations and move.location_dest_id not in warehouse_locations:
                    quantity -= move.product_uom_qty
            else:
                # Sin filtro de almacén
                if move.location_dest_id.usage == 'internal' and move.location_id.usage != 'internal':
                    quantity += move.product_uom_qty
                elif move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal':
                    quantity -= move.product_uom_qty
        
        return quantity
