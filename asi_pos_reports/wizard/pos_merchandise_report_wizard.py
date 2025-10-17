# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import xlsxwriter
import base64
from io import BytesIO
from datetime import datetime

_logger = logging.getLogger(__name__)


class PosMerchandiseReportWizard(models.TransientModel):
    _name = 'pos.merchandise.report.wizard'
    _description = 'Wizard para Reporte de Ventas por Mercancías'

    session_id = fields.Many2one('pos.session', string='Sesión POS', required=True)
    date_start = fields.Datetime(string='Fecha Inicio', required=True)
    date_stop = fields.Datetime(string='Fecha Fin', required=True)
    
    def action_print_report(self):
        """Acción para imprimir el reporte principal (ahora usa el mejorado)"""
        self.ensure_one()
        
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión POS'))
        
        # Generar el reporte mejorado
        return self.env.ref('asi_pos_reports.action_report_pos_merchandise_sales').report_action(
            self.session_id.ids
        )
    
    def action_preview_ticket(self):
        """Acción para previsualizar el formato de ticket"""
        self.ensure_one()
        
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión POS'))
        
        # Generar la previsualización del ticket
        return self.env.ref('asi_pos_reports.action_report_pos_merchandise_ticket_preview').report_action(
            self.session_id.ids
        )
    
    def action_print_ticket(self):
        """Acción para imprimir ticket en impresora Epson"""
        self.ensure_one()
        
        report_data = self.session_id._prepare_merchandise_report_data()
        self.session_id._try_print_to_epson_printer(report_data)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Impresión de Ticket'),
                'message': _('Se ha enviado el ticket a la impresora Epson'),
                'type': 'success',
            }
        }

    def action_generate_excel(self):
        """Generar reporte Excel"""
        self.ensure_one()
        
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión POS'))
        
        # Obtener datos del reporte
        data = self.session_id.get_merchandise_report_grouped_data()
        
        # Crear archivo Excel
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Ventas por Mercancías')

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
        number_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})

        # Título
        worksheet.merge_range('A1:E1', 'VENTAS POR MERCANCÍAS', title_format)
        worksheet.write('A2', f"Sesión: {data['session_name']}")
        worksheet.write('A3', f"Usuario: {data['user_name']}")
        worksheet.write('A4', f"Fecha: {data['session_date'].strftime('%d/%m/%Y %H:%M')}")
        if data['session_close_date']:
            worksheet.write('A5', f"Cierre: {data['session_close_date'].strftime('%d/%m/%Y %H:%M')}")

        # Encabezados
        row = 7
        worksheet.write(row, 0, 'Categoría', header_format)
        worksheet.write(row, 1, 'Producto', header_format)
        worksheet.write(row, 2, 'Cantidad', header_format)
        worksheet.write(row, 3, 'Precio Unit.', header_format)
        worksheet.write(row, 4, 'Total', header_format)

        row += 1

        # Datos por categoría
        for category_name, products in data['categories_data'].items():
            # Escribir categoría
            worksheet.merge_range(f'A{row+1}:E{row+1}', category_name, category_format)
            row += 1

            # Escribir productos
            for product in products:
                worksheet.write(row, 0, '')  # Categoría vacía para productos
                worksheet.write(row, 1, product['product_name'], data_format)
                worksheet.write(row, 2, product['quantity'], number_format)
                worksheet.write(row, 3, product['price_unit'], number_format)
                worksheet.write(row, 4, product['total_amount'], number_format)
                row += 1

        # Total
        row += 1
        worksheet.write(row, 3, 'TOTAL GENERAL:', header_format)
        worksheet.write(row, 4, data['total_amount'], number_format)

        # Ajustar columnas
        worksheet.set_column('A:A', 20)
        worksheet.set_column('B:B', 40)
        worksheet.set_column('C:C', 15)
        worksheet.set_column('D:D', 15)
        worksheet.set_column('E:E', 15)

        workbook.close()
        output.seek(0)

        # Crear attachment
        filename = f"ventas_mercancias_{data['session_name'].replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
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

    def action_debug_data(self):
        """Método para debug - verificar datos de la sesión"""
        self.ensure_one()
        
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión POS'))
        
        # Obtener información de debug
        orders = self.session_id.order_ids
        paid_orders = orders.filtered(lambda o: o.state in ['paid', 'done', 'invoiced'])
        refund_orders = orders.filtered(lambda o: 'REEMBOLSO' in o.name)
        
        debug_info = f"""
        INFORMACIÓN DE DEBUG:
        
        Sesión: {self.session_id.name}
        Estado: {self.session_id.state}
        Total órdenes: {len(orders)}
        Órdenes pagadas: {len(paid_orders)}
        Órdenes de reembolso: {len(refund_orders)}
        
        Órdenes de reembolso encontradas:
        """
        
        for order in refund_orders:
            debug_info += f"\n- {order.name} (Estado: {order.state}, Líneas: {len(order.lines)})"
            for line in order.lines:
                debug_info += f"\n  * {line.product_id.name} - Qty: {line.qty} - Precio: {line.price_unit}"
        
        # Mostrar en log
        _logger.info(debug_info)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Debug Info'),
                'message': f'Sesión: {self.session_id.name}, Órdenes: {len(orders)}, Pagadas: {len(paid_orders)}, Reembolsos: {len(refund_orders)}. Ver log para detalles.',
                'type': 'info',
            }
        }
