# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from datetime import datetime
import xlsxwriter
import base64
from io import BytesIO

_logger = logging.getLogger(__name__)


class PosShiftBalanceWizard(models.TransientModel):
    _name = 'pos.shift.balance.wizard'
    _description = 'Wizard para Balance de Turno'

    pos_config_id = fields.Many2one(
        'pos.config', 
        string='Punto de Venta', 
        required=True,
        help='Seleccione el punto de venta'
    )
    report_date = fields.Date(
        string='Fecha', 
        required=True,
        default=fields.Date.context_today,
        help='Seleccione la fecha para filtrar las sesiones'
    )
    session_id = fields.Many2one(
        'pos.session', 
        string='Sesión POS',
        help='Seleccione la sesión del día'
    )
    available_session_ids = fields.Many2many(
        'pos.session',
        compute='_compute_available_sessions',
        string='Sesiones Disponibles'
    )
    session_count = fields.Integer(
        compute='_compute_available_sessions',
        string='Cantidad de Sesiones'
    )

    @api.depends('pos_config_id', 'report_date')
    def _compute_available_sessions(self):
        """Calcula las sesiones disponibles según el POS y la fecha seleccionada"""
        for wizard in self:
            if wizard.pos_config_id and wizard.report_date:
                # Convertir la fecha a datetime para el inicio y fin del día
                date_start = datetime.combine(wizard.report_date, datetime.min.time())
                date_end = datetime.combine(wizard.report_date, datetime.max.time())
                
                # Buscar sesiones del POS en esa fecha
                sessions = self.env['pos.session'].search([
                    ('config_id', '=', wizard.pos_config_id.id),
                    ('start_at', '>=', date_start),
                    ('start_at', '<=', date_end),
                ])
                
                wizard.available_session_ids = sessions
                wizard.session_count = len(sessions)
                
                # Si solo hay una sesión, seleccionarla automáticamente
                if len(sessions) == 1:
                    wizard.session_id = sessions[0]
                elif wizard.session_id and wizard.session_id not in sessions:
                    wizard.session_id = False
            else:
                wizard.available_session_ids = False
                wizard.session_count = 0
                wizard.session_id = False

    @api.onchange('pos_config_id', 'report_date')
    def _onchange_filters(self):
        """Limpia la sesión seleccionada cuando cambian los filtros"""
        self.session_id = False
        
        # Si solo hay una sesión disponible, seleccionarla automáticamente
        if self.session_count == 1:
            self.session_id = self.available_session_ids[0]

    def action_print_report(self):
        """Acción para imprimir el reporte principal (PDF)"""
        self.ensure_one()
        
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión POS'))
        
        return self.env.ref('asi_pos_reports.action_report_shift_balance').report_action(
            self.session_id.ids
        )
    
    def action_preview_ticket(self):
        """Acción para previsualizar el formato de ticket"""
        self.ensure_one()
        
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión POS'))
        
        return self.env.ref('asi_pos_reports.action_report_shift_balance_ticket_preview').report_action(
            self.session_id.ids
        )
    
    def action_print_ticket(self):
        """Acción para imprimir ticket en impresora"""
        self.ensure_one()
        
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión POS'))
        
        # Aquí se implementaría la impresión directa a la impresora
        _logger.info(f"Imprimiendo balance de turno para sesión {self.session_id.name}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Impresión de Ticket'),
                'message': _('Se ha enviado el balance de turno a la impresora'),
                'type': 'success',
            }
        }

    def action_generate_excel(self):
        """Generar reporte Excel del balance de turno"""
        self.ensure_one()
        
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión POS'))
        
        # Obtener datos del balance de turno
        data = self.session_id._get_shift_balance_data()
        
        # Crear archivo Excel
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Balance de Turno')

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
            'align': 'left'
        })
        section_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E6E6FA',
            'border': 1
        })
        label_format = workbook.add_format({'border': 1, 'bold': True})
        data_format = workbook.add_format({'border': 1})
        number_format = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        currency_format = workbook.add_format({'border': 1, 'num_format': '$#,##0.00'})

        # Título
        worksheet.merge_range('A1:D1', 'BALANCE DE TURNO', title_format)
        
        row = 2
        
        # Información de la sesión
        worksheet.write(row, 0, 'Fecha:', label_format)
        worksheet.write(row, 1, data['date'], data_format)
        row += 1
        
        worksheet.write(row, 0, 'Usuario:', label_format)
        worksheet.write(row, 1, data['user_name'], data_format)
        row += 1
        
        worksheet.write(row, 0, 'Sesión:', label_format)
        worksheet.write(row, 1, data['session_name'], data_format)
        row += 2
        
        # Información de la empresa
        worksheet.merge_range(f'A{row+1}:D{row+1}', 'INFORMACIÓN DE LA EMPRESA', section_format)
        row += 1
        
        worksheet.write(row, 0, 'Empresa:', label_format)
        worksheet.write(row, 1, data['empresa_name'], data_format)
        row += 1
        
        worksheet.write(row, 0, 'Dirección:', label_format)
        worksheet.write(row, 1, data['company_address'], data_format)
        row += 1
        
        worksheet.write(row, 0, 'Teléfono:', label_format)
        worksheet.write(row, 1, data['company_phone'], data_format)
        row += 1
        
        worksheet.write(row, 0, 'Desde:', label_format)
        worksheet.write(row, 1, data['start_date'], data_format)
        row += 1
        
        worksheet.write(row, 0, 'Hasta:', label_format)
        worksheet.write(row, 1, data['end_date'], data_format)
        row += 1
        
        worksheet.write(row, 0, 'Entidad:', label_format)
        worksheet.write(row, 1, data['company_name'], data_format)
        row += 2
        
        # Balance financiero
        worksheet.merge_range(f'A{row+1}:D{row+1}', 'BALANCE FINANCIERO', section_format)
        row += 1
        
        worksheet.write(row, 0, 'Inicio:', label_format)
        worksheet.write(row, 1, data['opening_balance'], currency_format)
        row += 1
        
        worksheet.write(row, 0, 'Efectivo:', label_format)
        worksheet.write(row, 1, data['cash_amount'], currency_format)
        row += 1
        
        worksheet.write(row, 0, 'Otros ingresos:', label_format)
        worksheet.write(row, 1, data['other_income'], currency_format)
        row += 1
        
        worksheet.write(row, 0, 'Gastos:', label_format)
        worksheet.write(row, 1, data['expenses'], currency_format)
        row += 1
        
        worksheet.write(row, 0, 'Balance:', label_format)
        worksheet.write(row, 1, data['balance'], currency_format)
        row += 2
        
        # Métodos de pago
        worksheet.merge_range(f'A{row+1}:D{row+1}', 'PAGOS', section_format)
        row += 1
        
        for payment_method in data['payment_methods']:
            worksheet.write(row, 0, payment_method['name'], data_format)
            worksheet.write(row, 1, payment_method['amount'], currency_format)
            row += 1
        
        row += 1
        
        # Otros conceptos
        worksheet.merge_range(f'A{row+1}:D{row+1}', 'OTROS CONCEPTOS', section_format)
        row += 1
        
        worksheet.write(row, 0, 'Deudas:', label_format)
        worksheet.write(row, 1, data['debts'], currency_format)
        row += 1
        
        worksheet.write(row, 0, 'Servicio:', label_format)
        worksheet.write(row, 1, data['service'], currency_format)
        row += 1
        
        worksheet.write(row, 0, 'Descuento:', label_format)
        worksheet.write(row, 1, data['discount'], currency_format)
        row += 1
        
        worksheet.write(row, 0, 'Devoluciones:', label_format)
        worksheet.write(row, 1, data['returns'], currency_format)
        row += 2
        
        # Resumen final
        worksheet.merge_range(f'A{row+1}:D{row+1}', 'RESUMEN FINAL', section_format)
        row += 1
        
        worksheet.write(row, 0, 'Balance:', label_format)
        worksheet.write(row, 1, data['balance'], currency_format)
        row += 1
        
        worksheet.write(row, 0, 'Retiro:', label_format)
        worksheet.write(row, 1, data['cash_amount'], currency_format)
        row += 1
        
        worksheet.write(row, 0, 'Final:', label_format)
        worksheet.write(row, 1, data['final_balance'], currency_format)
        row += 1
        
        worksheet.write(row, 0, 'Restante:', label_format)
        worksheet.write(row, 1, data['remaining'], currency_format)
        row += 2
        
        # Total
        worksheet.write(row, 0, 'TOTAL:', header_format)
        worksheet.write(row, 1, data['total'], currency_format)

        # Ajustar columnas
        worksheet.set_column('A:A', 25)
        worksheet.set_column('B:B', 30)
        worksheet.set_column('C:D', 15)

        workbook.close()
        output.seek(0)

        # Crear attachment
        filename = f"balance_turno_{data['session_name'].replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
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
