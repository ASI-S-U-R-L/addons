# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import base64
from io import BytesIO
import xlsxwriter

_logger = logging.getLogger(__name__)

class PosCoinsReportWizard(models.TransientModel):
    _name = 'pos.coins.report.wizard'
    _description = 'Asistente para Reporte de Monedas'

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
        string='Sesión',
        required=True,
        help='Seleccione la sesión para generar el reporte'
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
        """Calcula las sesiones disponibles según el POS y fecha seleccionados"""
        for wizard in self:
            if wizard.pos_config_id and wizard.report_date:
                # Buscar todas las sesiones del POS
                sessions = self.env['pos.session'].search([
                    ('config_id', '=', wizard.pos_config_id.id),
                    ('start_at', '!=', False),
                ])
                
                # Filtrar por fecha usando el contexto del usuario
                filtered_sessions = self.env['pos.session']
                for session in sessions:
                    # Convertir start_at a la fecha local del usuario
                    session_date = fields.Date.context_today(session, session.start_at)
                    if session_date == wizard.report_date:
                        filtered_sessions |= session
                
                wizard.available_session_ids = filtered_sessions
                wizard.session_count = len(filtered_sessions)
                
                # Si solo hay una sesión, seleccionarla automáticamente
                if len(filtered_sessions) == 1:
                    wizard.session_id = filtered_sessions[0]
                elif wizard.session_id and wizard.session_id not in filtered_sessions:
                    wizard.session_id = False
            else:
                wizard.available_session_ids = False
                wizard.session_count = 0
                wizard.session_id = False

    @api.onchange('pos_config_id', 'report_date')
    def _onchange_pos_or_date(self):
        """Limpia la sesión seleccionada cuando cambia el POS o la fecha"""
        self.session_id = False
        
        # Si solo hay una sesión disponible, seleccionarla automáticamente
        if self.session_count == 1:
            self.session_id = self.available_session_ids[0]

    def action_generate_pdf(self):
        """Genera el reporte en formato PDF"""
        self.ensure_one()
        
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión.'))
        
        return self.env.ref('asi_pos_reports.action_report_pos_coins').report_action(self.session_id)

    def action_generate_excel(self):
        """Genera el reporte en formato Excel"""
        self.ensure_one()
        
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión.'))
        
        # Obtener datos del reporte
        session = self.session_id
        data = session._get_coins_data()
        
        # Crear archivo Excel
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Monedas')
        
        # Formatos
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1
        })
        
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'bg_color': '#D9E1F2',
            'border': 1,
            'align': 'left'
        })
        
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left'
        })
        
        currency_format = workbook.add_format({
            'border': 1,
            'num_format': '$#,##0.00',
            'align': 'right'
        })
        
        # Configurar ancho de columnas
        worksheet.set_column('A:A', 25)
        worksheet.set_column('B:B', 20)
        
        row = 0
        
        # Título
        worksheet.merge_range(row, 0, row, 1, 'REPORTE DE MONEDAS', title_format)
        row += 2
        
        # Información de la sesión
        worksheet.write(row, 0, 'Fecha:', header_format)
        worksheet.write(row, 1, data['date'], cell_format)
        row += 1
        
        worksheet.write(row, 0, 'Usuario:', header_format)
        worksheet.write(row, 1, data['user_name'], cell_format)
        row += 1
        
        worksheet.write(row, 0, 'Sesión:', header_format)
        worksheet.write(row, 1, data['session_name'], cell_format)
        row += 2
        
        # Información de la empresa
        worksheet.write(row, 0, 'Empresa:', header_format)
        worksheet.write(row, 1, data['empresa_name'], cell_format)
        row += 1
        
        worksheet.write(row, 0, 'Entidad:', header_format)
        worksheet.write(row, 1, data['company_name'], cell_format)
        row += 1
        
        worksheet.write(row, 0, 'Dirección:', header_format)
        worksheet.write(row, 1, data['company_address'], cell_format)
        row += 1
        
        worksheet.write(row, 0, 'Teléfono:', header_format)
        worksheet.write(row, 1, data['company_phone'], cell_format)
        row += 1
        
        worksheet.write(row, 0, 'Desde:', header_format)
        worksheet.write(row, 1, data['start_date'], cell_format)
        row += 1
        
        worksheet.write(row, 0, 'Hasta:', header_format)
        worksheet.write(row, 1, data['end_date'], cell_format)
        row += 2
        
        # Sección Final
        worksheet.merge_range(row, 0, row, 1, 'FINAL', header_format)
        row += 1
        
        worksheet.write(row, 0, 'CUP Importe:', cell_format)
        worksheet.write(row, 1, data['opening_balance'], currency_format)
        row += 2
        
        # Sección Retiro
        worksheet.merge_range(row, 0, row, 1, 'RETIRO', header_format)
        row += 1
        
        worksheet.write(row, 0, 'CUP Importe:', cell_format)
        worksheet.write(row, 1, data['closing_withdrawal'], currency_format)
        row += 1
        
        workbook.close()
        output.seek(0)
        
        # Crear adjunto
        filename = f'Monedas_{session.name}_{fields.Date.today()}.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': 'pos.session',
            'res_id': session.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_preview_ticket(self):
        """Previsualiza el ticket en pantalla"""
        self.ensure_one()
        
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión.'))
        
        return self.env.ref('asi_pos_reports.action_report_pos_coins_ticket_preview').report_action(self.session_id.ids)

    def action_print_ticket(self):
        """Intenta impresión directa, falla a PDF"""
        self.ensure_one()
    
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión POS'))
    
        # Intentar impresión directa
        success = self.session_id.print_ticket_direct('coins')  # o 'shift_balance', 'coins'
    
        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Impresión exitosa'),
                    'message': _('Ticket enviado a la impresora del POS'),
                    'type': 'success',
                }
            }
        else:
            # Fallback: abrir PDF para impresión manual
            _logger.info("Fallback a PDF - No hay IoT configurado")
            report = self.env.ref('asi_pos_reports.action_report_pos_coins_ticket')
            return report.report_action(self.session_id)
