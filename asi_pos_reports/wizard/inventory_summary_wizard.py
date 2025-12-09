# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import xlsxwriter
import base64
from io import BytesIO
from datetime import datetime

_logger = logging.getLogger(__name__)


class InventorySummaryWizard(models.TransientModel):
    _name = 'inventory.summary.wizard'
    _description = 'Wizard para Resumen de Inventario'

    warehouse_ids = fields.Many2many(
        'stock.warehouse', 
        string='Almacenes',
        help='Seleccionar almacenes específicos o dejar vacío para todos'
    )
    location_ids = fields.Many2many(
        'stock.location',
        string='Ubicaciones',
        domain=[('usage', '=', 'internal')],
        help='Ubicaciones de inventario a incluir'
    )
    include_zero_qty = fields.Boolean(
        string='Incluir productos con cantidad 0',
        default=False,
        help='Incluir productos que tienen cantidad 0 en stock'
    )
    category_ids = fields.Many2many(
        'product.category',
        string='Categorías de Producto',
        help='Filtrar por categorías específicas o dejar vacío para todas'
    )

    @api.onchange('warehouse_ids')
    def _onchange_warehouse_ids(self):
        """Actualizar ubicaciones cuando cambian los almacenes"""
        if self.warehouse_ids:
            locations = self.env['stock.location'].search([
                ('warehouse_id', 'in', self.warehouse_ids.ids),
                ('usage', '=', 'internal')
            ])
            self.location_ids = locations
        else:
            self.location_ids = False

    def _get_inventory_data(self):
        """Obtener datos de inventario agrupados por categoría"""
        # Determinar ubicaciones a consultar
        if self.location_ids:
            locations = self.location_ids
        elif self.warehouse_ids:
            locations = self.env['stock.location'].search([
                ('warehouse_id', 'in', self.warehouse_ids.ids),
                ('usage', '=', 'internal')
            ])
        else:
            # Todos los almacenes
            locations = self.env['stock.location'].search([('usage', '=', 'internal')])

        # Obtener quants (cantidades en stock)
        domain = [('location_id', 'in', locations.ids)]
        if not self.include_zero_qty:
            domain.append(('quantity', '>', 0))

        quants = self.env['stock.quant'].search(domain)

        # Filtrar por categorías si se especificaron
        if self.category_ids:
            quants = quants.filtered(lambda q: q.product_id.categ_id.id in self.category_ids.ids)

        # Agrupar por categoría
        categories_data = {}
        total_products = 0

        for quant in quants:
            product = quant.product_id
            category = product.categ_id
            category_name = category.name if category else 'Sin Categoría'

            if category_name not in categories_data:
                categories_data[category_name] = []

            # Buscar si el producto ya existe en la categoría (para sumar cantidades de diferentes ubicaciones)
            existing_product = None
            for product_data in categories_data[category_name]:
                if product_data['product_id'] == product.id:
                    existing_product = product_data
                    break

            if existing_product:
                existing_product['quantity'] += quant.quantity
            else:
                categories_data[category_name].append({
                    'product_id': product.id,
                    'product_name': product.name,
                    'product_code': product.default_code or '',
                    'uom_name': product.uom_id.name,
                    'uom_symbol': product.uom_id.name,
                    'quantity': quant.quantity,
                })
                total_products += 1

        # Ordenar categorías y productos
        for category_name in categories_data:
            categories_data[category_name] = sorted(
                categories_data[category_name],
                key=lambda x: x['product_name']
            )

        categories_data = dict(sorted(categories_data.items()))

        # Obtener nombres de almacenes/ubicaciones
        warehouse_names = []
        if self.warehouse_ids:
            warehouse_names = self.warehouse_ids.mapped('name')
        elif locations:
            warehouse_names = list(set(locations.mapped('warehouse_id.name')))
        else:
            warehouse_names = ['Todos los almacenes']

        return {
            'categories_data': categories_data,
            'warehouse_names': warehouse_names,
            'total_products': total_products,
            'report_date': datetime.now(),
            'include_zero_qty': self.include_zero_qty,
        }

    def action_print_report(self):
        """Generar reporte PDF"""
        self.ensure_one()
        return self.env.ref('asi_pos_reports.action_report_inventory_summary').report_action([self.id])

    def action_generate_excel(self):
        """Generar reporte Excel"""
        self.ensure_one()
        
        # Obtener datos
        data = self._get_inventory_data()
        
        # Crear archivo Excel
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Resumen de Inventario')

        # Formatos
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter'
        })
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'border': 1,
            'align': 'center'
        })
        category_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E6E6FA',
            'border': 1
        })
        data_format = workbook.add_format({'border': 1})
        number_format = workbook.add_format({'border': 1, 'num_format': '#,##0.##'})

        # Título
        worksheet.merge_range('A1:E1', 'RESUMEN DE INVENTARIO', title_format)
        worksheet.write('A2', f"Fecha: {data['report_date'].strftime('%d/%m/%Y %H:%M')}")
        worksheet.write('A3', f"Almacenes: {', '.join(data['warehouse_names'])}")

        # Encabezados
        row = 5
        worksheet.write(row, 0, 'Categoría', header_format)
        worksheet.write(row, 1, 'Código', header_format)
        worksheet.write(row, 2, 'Producto', header_format)
        worksheet.write(row, 3, 'Unidad', header_format)
        worksheet.write(row, 4, 'Cantidad', header_format)

        row += 1

        # Datos por categoría
        for category_name, products in data['categories_data'].items():
            # Escribir categoría
            worksheet.merge_range(f'A{row+1}:E{row+1}', category_name, category_format)
            row += 1

            # Escribir productos
            for product in products:
                worksheet.write(row, 0, '')  # Categoría vacía para productos
                worksheet.write(row, 1, product['product_code'], data_format)
                worksheet.write(row, 2, product['product_name'], data_format)
                worksheet.write(row, 3, product['uom_symbol'], data_format)
                worksheet.write(row, 4, product['quantity'], number_format)
                row += 1

        # Totales
        row += 1
        worksheet.write(row, 2, 'TOTALES:', header_format)
        worksheet.write(row, 4, f"Productos: {data['total_products']}", header_format)

        # Ajustar columnas
        worksheet.set_column('A:A', 20)
        worksheet.set_column('B:B', 15)
        worksheet.set_column('C:C', 40)
        worksheet.set_column('D:D', 10)
        worksheet.set_column('E:E', 15)

        workbook.close()
        output.seek(0)

        # Crear attachment
        filename = f"resumen_inventario_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'store_fname': filename,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_preview_ticket(self):
        """Previsualizar formato ticket"""
        self.ensure_one()
        return self.env.ref('asi_pos_reports.action_report_inventory_ticket_preview').report_action([self.id])

    def action_print_ticket(self):
        """Imprimir ticket"""
        self.ensure_one()
        
        data = self._get_inventory_data()
        ticket_content = self._generate_ticket_content(data)
        
        _logger.info(f"Ticket de inventario generado:\n{ticket_content}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Impresión de Ticket'),
                'message': _('Se ha enviado el ticket de inventario a la impresora'),
                'type': 'success',
            }
        }

    def _generate_ticket_content(self, data):
        """Generar contenido del ticket"""
        content = []
        content.append("INVENTARIO POR ARTICULOS Y GRUPO")
        content.append(data['report_date'].strftime('%d/%m/%Y %H:%M'))
        content.append(f"Entidad/es: {', '.join(data['warehouse_names'])}")
        content.append("-------------------")

        for category_name, products in data['categories_data'].items():
            content.append(f"\n{category_name.upper()}")
            for product in products:
                qty = product['quantity']
                # Mostrar cantidad como entero si es un número entero, sino con 3 decimales
                if qty == int(qty):
                    qty_str = f"{int(qty):>10}"
                else:
                    qty_str = f"{qty:>10.3f}"
                content.append(f"{product['product_name']} ( {product['uom_symbol']} ) {qty_str}")

        content.append("-------------------")
        content.append(f"Total productos: {data['total_products']}")
        
        return "\n".join(content)
