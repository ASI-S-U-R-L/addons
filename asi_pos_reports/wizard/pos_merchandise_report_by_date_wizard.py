# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PosMerchandiseReportByDateWizard(models.TransientModel):
    _name = 'pos.merchandise.report.by.date.wizard'
    _description = 'Wizard para Reporte de Ventas por Mercancías por Fecha'

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
                    # Si la sesión seleccionada ya no está en las disponibles, limpiarla
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
        """Acción para imprimir el reporte principal"""
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
        """Intenta impresión directa, falla a PDF"""
        self.ensure_one()
    
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión POS'))
    
        # Intentar impresión directa
        success = self.session_id.print_ticket_direct('merchandise')  # o 'shift_balance', 'coins'
    
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
            return self.env.ref('asi_pos_reports.action_report_pos_merchandise_ticket').report_action(self.session_id.ids)

    def action_generate_excel(self):
        """Generar reporte Excel"""
        self.ensure_one()
        
        if not self.session_id:
            raise UserError(_('Debe seleccionar una sesión POS'))
        
        # Reutilizar el método del wizard original
        original_wizard = self.env['pos.merchandise.report.wizard'].create({
            'session_id': self.session_id.id,
            'date_start': self.session_id.start_at,
            'date_stop': self.session_id.stop_at or fields.Datetime.now(),
        })
        
        return original_wizard.action_generate_excel()
