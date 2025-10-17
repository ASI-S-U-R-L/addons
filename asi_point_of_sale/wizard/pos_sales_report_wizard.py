# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import datetime, timedelta, date
import calendar
import logging

_logger = logging.getLogger(__name__)

class PosSalesReportWizard(models.TransientModel):
    _name = 'pos.sales.report.wizard'
    _description = 'Asistente para Reporte de Ventas POS'

    period_type = fields.Selection([
        ('day', 'Día'),
        ('week', 'Semana'),
        ('month', 'Mes'),
        ('year', 'Año'),
    ], string='Tipo de Período', default='day', required=True)
    
    # Campos para selección de día
    day_date = fields.Date(string='Fecha', default=fields.Date.today)
    
    # Campos para selección de semana
    week_month = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
        ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
        ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')
    ], string='Mes', default=lambda self: str(fields.Date.today().month))
    
    week_year = fields.Integer(string='Año', default=lambda self: fields.Date.today().year)
    
    week_number = fields.Selection([
        ('1', '1ra Semana'),
        ('2', '2da Semana'),
        ('3', '3ra Semana'),
        ('4', '4ta Semana'),
        ('5', '5ta Semana')
    ], string='Semana', default='1')
    
    # Campos para selección de mes
    month = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
        ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
        ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')
    ], string='Mes', default=lambda self: str(fields.Date.today().month))
    
    month_year = fields.Integer(string='Año', default=lambda self: fields.Date.today().year)
    
    # Campo para selección de año
    year = fields.Integer(string='Año', default=lambda self: fields.Date.today().year)
    
    # Campos ocultos para almacenar las fechas de inicio y fin calculadas
    date_start = fields.Datetime(string='Fecha Inicio', required=True)
    date_end = fields.Datetime(string='Fecha Fin', required=True)
    
    @api.onchange('period_type', 'day_date', 'week_month', 'week_year', 'week_number', 'month', 'month_year', 'year')
    def _onchange_period_fields(self):
        """Actualiza las fechas de inicio y fin basadas en los campos seleccionados"""
        if self.period_type == 'day' and self.day_date:
            # Para día: desde las 00:00:00 hasta las 23:59:59 del día seleccionado
            start_date = datetime.combine(self.day_date, datetime.min.time())
            end_date = datetime.combine(self.day_date, datetime.max.time())
            
        elif self.period_type == 'week' and self.week_month and self.week_year and self.week_number:
            # Para semana: calculamos el primer día del mes
            month = int(self.week_month)
            year = self.week_year
            week_num = int(self.week_number)
            
            # Primer día del mes
            first_day = date(year, month, 1)
            
            # Calculamos el inicio de la semana seleccionada
            # La primera semana comienza el día 1
            # La segunda semana comienza el día 8
            # La tercera semana comienza el día 15
            # La cuarta semana comienza el día 22
            # La quinta semana comienza el día 29 (si existe)
            start_day = 1 + (week_num - 1) * 7
            
            # Verificamos que el día exista en el mes
            last_day_of_month = calendar.monthrange(year, month)[1]
            if start_day > last_day_of_month:
                # Si el día no existe (por ejemplo, la 5ta semana en un mes de 28 días)
                # usamos el último día del mes
                start_day = last_day_of_month
            
            start_date = datetime.combine(date(year, month, start_day), datetime.min.time())
            
            # La semana termina 6 días después o el último día del mes, lo que ocurra primero
            end_day = min(start_day + 6, last_day_of_month)
            end_date = datetime.combine(date(year, month, end_day), datetime.max.time())
            
        elif self.period_type == 'month' and self.month and self.month_year:
            # Para mes: desde el primer día hasta el último día del mes seleccionado
            month = int(self.month)
            year = self.month_year
            
            start_date = datetime.combine(date(year, month, 1), datetime.min.time())
            
            # Último día del mes
            last_day = calendar.monthrange(year, month)[1]
            end_date = datetime.combine(date(year, month, last_day), datetime.max.time())
            
        elif self.period_type == 'year' and self.year:
            # Para año: desde el 1 de enero hasta el 31 de diciembre del año seleccionado
            year = self.year
            
            start_date = datetime.combine(date(year, 1, 1), datetime.min.time())
            end_date = datetime.combine(date(year, 12, 31), datetime.max.time())
            
        else:
            # Si no se han completado los campos necesarios, no actualizamos las fechas
            return
        
        self.date_start = start_date
        self.date_end = end_date
    
    def action_generate_report(self):
        """Genera el reporte de ventas basado en el período seleccionado"""
        self.ensure_one()
        
        # Aseguramos que las fechas estén actualizadas
        self._onchange_period_fields()
        
        # Preparamos el contexto para el reporte
        data = {
            'date_start': self.date_start,
            'date_stop': self.date_end,
            'config_ids': False,  # Todos los TPV
            'session_ids': False  # Todas las sesiones
        }
        
        # Retornamos la acción para generar el reporte
        return {
            'type': 'ir.actions.report',
            'report_name': 'point_of_sale.report_saledetails',
            'report_type': 'qweb-pdf',
            'data': data,
        }
