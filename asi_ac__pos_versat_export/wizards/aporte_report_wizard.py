# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
import io
import base64
import logging

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    _logger.warning('xlsxwriter no está instalado. La exportación a Excel no estará disponible.')
    xlsxwriter = None

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
except ImportError:
    _logger.warning('reportlab no está instalado. La exportación a PDF no estará disponible.')


class AporteReportWizard(models.TransientModel):
    _name = 'aporte.report.wizard'
    _description = 'Wizard para Reporte de Aportes por Período'

    fecha_desde = fields.Date(
        string='Fecha Desde',
        required=True,
        default=fields.Date.context_today
    )
    fecha_hasta = fields.Date(
        string='Fecha Hasta',
        required=True,
        default=fields.Date.context_today
    )
    agrupacion = fields.Selection([
        ('dia', 'Por Día'),
        ('mes', 'Por Mes')
    ], string='Agrupar por', required=True, default='dia')
    
    formato = fields.Selection([
        ('txt', 'Texto (TXT)'),
        ('xlsx', 'Excel (XLSX)'),
        ('pdf', 'PDF')
    ], string='Formato', required=True, default='txt')
    
    archivo_generado = fields.Binary(string='Archivo', readonly=True)
    nombre_archivo = fields.Char(string='Nombre del Archivo', readonly=True)

    @api.constrains('fecha_desde', 'fecha_hasta')
    def _check_fechas(self):
        for record in self:
            if record.fecha_desde > record.fecha_hasta:
                raise UserError(_('La fecha desde debe ser menor o igual a la fecha hasta.'))

    def _is_pos_move(self, move):
        """Detecta si un asiento proviene de POS"""
        if not move.ref:
            return False
        ref = move.ref.upper()
        return '/POS/' in ref or ref.startswith('POS/') or 'POS' in ref

    def _get_ventas_data(self):
        """Obtiene los datos de ventas en el período seleccionado"""
        domain = [
            ('date', '>=', self.fecha_desde),
            ('date', '<=', self.fecha_hasta),
            ('state', '=', 'posted'),
            ('move_type', 'in', ['out_invoice', 'out_refund', 'entry']),  # Facturas y asientos misceláneos
        ]
        
        moves = self.env['account.move'].search(domain, order='date asc')
        
        ventas_data = []
        total_facturas = 0.0
        total_pos = 0.0
        
        for move in moves:
            # Ignorar notas de crédito
            if move.move_type == 'out_refund':
                continue
            
            
            is_pos = False
            if move.move_type == 'out_invoice':
                # Es una factura de cliente
                tipo = 'Factura'
                base = abs(move.amount_untaxed_signed)
                total_facturas += base
            elif move.move_type == 'entry' and self._is_pos_move(move):
                
                
                tiene_ingresos = any(
                    line.credit > 0 and line.account_id.account_type in ['income', 'income_other']
                    for line in move.line_ids
                )
                
                if not tiene_ingresos:
                    
                    continue
                    
                is_pos = True
                tipo = 'POS'
                base = abs(move.amount_total)
                total_pos += base
            else:
                
                continue
            
            # Calcular aportes
            aporte_1 = base * 0.01
            aporte_10 = base * 0.10
            
            ventas_data.append({
                'fecha': move.date,
                'tipo': tipo,
                'documento': move.name,
                'base': base,
                'aporte_1': aporte_1,
                'aporte_10': aporte_10,
                'total_aportes': aporte_1 + aporte_10
            })
        
        return ventas_data, total_facturas, total_pos

    def _agrupar_por_dia(self, ventas_data):
        """Agrupa los datos por día"""
        agrupado = {}
        for venta in ventas_data:
            fecha_str = venta['fecha'].strftime('%d/%m/%Y')
            if fecha_str not in agrupado:
                agrupado[fecha_str] = {
                    'fecha': venta['fecha'],
                    'ventas': 0.0,
                    'aporte_1': 0.0,
                    'aporte_10': 0.0,
                    'total': 0.0
                }
            agrupado[fecha_str]['ventas'] += venta['base']
            agrupado[fecha_str]['aporte_1'] += venta['aporte_1']
            agrupado[fecha_str]['aporte_10'] += venta['aporte_10']
            agrupado[fecha_str]['total'] += venta['total_aportes']
        
        return sorted(agrupado.values(), key=lambda x: x['fecha'])

    def _agrupar_por_mes(self, ventas_data):
        """Agrupa los datos por mes"""
        agrupado = {}
        meses = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        
        for venta in ventas_data:
            mes_key = f"{venta['fecha'].year}-{venta['fecha'].month:02d}"
            mes_nombre = f"{meses[venta['fecha'].month]} {venta['fecha'].year}"
            
            if mes_key not in agrupado:
                agrupado[mes_key] = {
                    'fecha': venta['fecha'],
                    'mes_nombre': mes_nombre,
                    'ventas': 0.0,
                    'aporte_1': 0.0,
                    'aporte_10': 0.0,
                    'total': 0.0
                }
            agrupado[mes_key]['ventas'] += venta['base']
            agrupado[mes_key]['aporte_1'] += venta['aporte_1']
            agrupado[mes_key]['aporte_10'] += venta['aporte_10']
            agrupado[mes_key]['total'] += venta['total_aportes']
        
        return sorted(agrupado.values(), key=lambda x: x['fecha'])

    def _format_currency(self, amount):
        """Formatea un monto como moneda"""
        return f"${amount:,.2f}"

    def _generar_txt(self, datos_agrupados, total_facturas, total_pos):
        """Genera el reporte en formato TXT"""
        lineas = []
        
        # Encabezado
        lineas.append("=" * 79)
        titulo = "REPORTE DE APORTES VERSAT"
        if self.agrupacion == 'dia':
            titulo += " - AGRUPADO POR DÍA"
        else:
            titulo += " - AGRUPADO POR MES"
        lineas.append(titulo.center(79))
        lineas.append("=" * 79)
        lineas.append(f"Período: {self.fecha_desde.strftime('%d/%m/%Y')} - {self.fecha_hasta.strftime('%d/%m/%Y')}")
        lineas.append(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        lineas.append("")
        
        # Resumen general
        lineas.append("-" * 79)
        lineas.append("RESUMEN GENERAL DEL PERÍODO")
        lineas.append("-" * 79)
        total_ventas = total_facturas + total_pos
        total_aporte_1 = total_ventas * 0.01
        total_aporte_10 = total_ventas * 0.10
        total_aportes = total_aporte_1 + total_aporte_10
        
        lineas.append(f"Total Ventas (Facturas):        {self._format_currency(total_facturas):>20}")
        lineas.append(f"Total Ventas (POS):              {self._format_currency(total_pos):>20}")
        lineas.append(f"                                 {'-' * 20}")
        lineas.append(f"TOTAL VENTAS:                    {self._format_currency(total_ventas):>20}")
        lineas.append("")
        lineas.append(f"Aporte 1% Desarrollo Local:      {self._format_currency(total_aporte_1):>20}")
        lineas.append(f"Aporte 10% Ventas:               {self._format_currency(total_aporte_10):>20}")
        lineas.append(f"                                 {'-' * 20}")
        lineas.append(f"TOTAL APORTES A PAGAR:           {self._format_currency(total_aportes):>20}")
        lineas.append("")
        
        # Detalle
        lineas.append("-" * 79)
        if self.agrupacion == 'dia':
            lineas.append("DETALLE POR DÍA")
        else:
            lineas.append("DETALLE POR MES")
        lineas.append("-" * 79)
        
        # Encabezado de tabla
        if self.agrupacion == 'dia':
            lineas.append(f"{'Fecha':<12} | {'Ventas':>13} | {'Aporte 1%':>11} | {'Aporte 10%':>11} | {'Total':>11}")
        else:
            lineas.append(f"{'Mes':<15} | {'Ventas':>13} | {'Aporte 1%':>11} | {'Aporte 10%':>11} | {'Total':>11}")
        lineas.append("-" * 79)
        
        # Datos
        for dato in datos_agrupados:
            if self.agrupacion == 'dia':
                fecha_str = dato['fecha'].strftime('%d/%m/%Y')
                lineas.append(
                    f"{fecha_str:<12} | "
                    f"{self._format_currency(dato['ventas']):>13} | "
                    f"{self._format_currency(dato['aporte_1']):>11} | "
                    f"{self._format_currency(dato['aporte_10']):>11} | "
                    f"{self._format_currency(dato['total']):>11}"
                )
            else:
                lineas.append(
                    f"{dato['mes_nombre']:<15} | "
                    f"{self._format_currency(dato['ventas']):>13} | "
                    f"{self._format_currency(dato['aporte_1']):>11} | "
                    f"{self._format_currency(dato['aporte_10']):>11} | "
                    f"{self._format_currency(dato['total']):>11}"
                )
        
        # Total
        lineas.append("-" * 79)
        if self.agrupacion == 'dia':
            lineas.append(
                f"{'TOTAL':<12} | "
                f"{self._format_currency(total_ventas):>13} | "
                f"{self._format_currency(total_aporte_1):>11} | "
                f"{self._format_currency(total_aporte_10):>11} | "
                f"{self._format_currency(total_aportes):>11}"
            )
        else:
            lineas.append(
                f"{'TOTAL':<15} | "
                f"{self._format_currency(total_ventas):>13} | "
                f"{self._format_currency(total_aporte_1):>11} | "
                f"{self._format_currency(total_aporte_10):>11} | "
                f"{self._format_currency(total_aportes):>11}"
            )
        
        lineas.append("")
        lineas.append("=" * 79)
        lineas.append("Fin del Reporte".center(79))
        lineas.append("=" * 79)
        
        return '\n'.join(lineas)

    def _generar_xlsx(self, datos_agrupados, total_facturas, total_pos):
        """Genera el reporte en formato Excel"""
        if not xlsxwriter:
            raise UserError(_('La librería xlsxwriter no está instalada. No se puede generar el archivo Excel.'))
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Reporte de Aportes')
        
        # Formatos
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#4472C4',
            'font_color': 'white'
        })
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
            'align': 'center'
        })
        currency_format = workbook.add_format({
            'num_format': '$#,##0.00',
            'border': 1
        })
        total_format = workbook.add_format({
            'bold': True,
            'num_format': '$#,##0.00',
            'border': 1,
            'bg_color': '#FFF2CC'
        })
        text_format = workbook.add_format({'border': 1})
        
        # Título
        worksheet.merge_range('A1:E1', 'REPORTE DE APORTES VERSAT', title_format)
        worksheet.write('A2', f"Período: {self.fecha_desde.strftime('%d/%m/%Y')} - {self.fecha_hasta.strftime('%d/%m/%Y')}")
        worksheet.write('A3', f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        
        # Resumen
        row = 5
        worksheet.write(row, 0, 'RESUMEN GENERAL', header_format)
        worksheet.merge_range(row, 1, row, 4, '', header_format)
        row += 1
        
        total_ventas = total_facturas + total_pos
        total_aporte_1 = total_ventas * 0.01
        total_aporte_10 = total_ventas * 0.10
        total_aportes = total_aporte_1 + total_aporte_10
        
        worksheet.write(row, 0, 'Total Ventas (Facturas):')
        worksheet.write(row, 1, total_facturas, currency_format)
        row += 1
        worksheet.write(row, 0, 'Total Ventas (POS):')
        worksheet.write(row, 1, total_pos, currency_format)
        row += 1
        worksheet.write(row, 0, 'TOTAL VENTAS:', total_format)
        worksheet.write(row, 1, total_ventas, total_format)
        row += 2
        
        worksheet.write(row, 0, 'Aporte 1% Desarrollo Local:')
        worksheet.write(row, 1, total_aporte_1, currency_format)
        row += 1
        worksheet.write(row, 0, 'Aporte 10% Ventas:')
        worksheet.write(row, 1, total_aporte_10, currency_format)
        row += 1
        worksheet.write(row, 0, 'TOTAL APORTES A PAGAR:', total_format)
        worksheet.write(row, 1, total_aportes, total_format)
        row += 3
        
        # Detalle
        if self.agrupacion == 'dia':
            worksheet.write(row, 0, 'Fecha', header_format)
        else:
            worksheet.write(row, 0, 'Mes', header_format)
        worksheet.write(row, 1, 'Ventas', header_format)
        worksheet.write(row, 2, 'Aporte 1%', header_format)
        worksheet.write(row, 3, 'Aporte 10%', header_format)
        worksheet.write(row, 4, 'Total', header_format)
        row += 1
        
        for dato in datos_agrupados:
            if self.agrupacion == 'dia':
                worksheet.write(row, 0, dato['fecha'].strftime('%d/%m/%Y'), text_format)
            else:
                worksheet.write(row, 0, dato['mes_nombre'], text_format)
            worksheet.write(row, 1, dato['ventas'], currency_format)
            worksheet.write(row, 2, dato['aporte_1'], currency_format)
            worksheet.write(row, 3, dato['aporte_10'], currency_format)
            worksheet.write(row, 4, dato['total'], currency_format)
            row += 1
        
        # Total
        worksheet.write(row, 0, 'TOTAL', total_format)
        worksheet.write(row, 1, total_ventas, total_format)
        worksheet.write(row, 2, total_aporte_1, total_format)
        worksheet.write(row, 3, total_aporte_10, total_format)
        worksheet.write(row, 4, total_aportes, total_format)
        
        # Ajustar anchos de columna
        worksheet.set_column('A:A', 20)
        worksheet.set_column('B:E', 15)
        
        workbook.close()
        output.seek(0)
        return output.read()

    def _generar_pdf(self, datos_agrupados, total_facturas, total_pos):
        """Genera el reporte en formato PDF"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        except ImportError:
            raise UserError(_('La librería reportlab no está instalada. No se puede generar el archivo PDF.'))
        
        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#4472C4'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        titulo = "REPORTE DE APORTES VERSAT"
        if self.agrupacion == 'dia':
            titulo += " - AGRUPADO POR DÍA"
        else:
            titulo += " - AGRUPADO POR MES"
        elements.append(Paragraph(titulo, title_style))
        
        # Información del período
        info_text = f"Período: {self.fecha_desde.strftime('%d/%m/%Y')} - {self.fecha_hasta.strftime('%d/%m/%Y')}<br/>"
        info_text += f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        elements.append(Paragraph(info_text, styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Resumen general
        total_ventas = total_facturas + total_pos
        total_aporte_1 = total_ventas * 0.01
        total_aporte_10 = total_ventas * 0.10
        total_aportes = total_aporte_1 + total_aporte_10
        
        resumen_data = [
            ['RESUMEN GENERAL DEL PERÍODO', ''],
            ['Total Ventas (Facturas):', self._format_currency(total_facturas)],
            ['Total Ventas (POS):', self._format_currency(total_pos)],
            ['TOTAL VENTAS:', self._format_currency(total_ventas)],
            ['', ''],
            ['Aporte 1% Desarrollo Local:', self._format_currency(total_aporte_1)],
            ['Aporte 10% Ventas:', self._format_currency(total_aporte_10)],
            ['TOTAL APORTES A PAGAR:', self._format_currency(total_aportes)],
        ]
        
        resumen_table = Table(resumen_data, colWidths=[4*inch, 2*inch])
        resumen_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
            ('FONTNAME', (0, 7), (-1, 7), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#FFF2CC')),
            ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor('#FFF2CC')),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        elements.append(resumen_table)
        elements.append(Spacer(1, 30))
        
        # Detalle
        if self.agrupacion == 'dia':
            detalle_data = [['Fecha', 'Ventas', 'Aporte 1%', 'Aporte 10%', 'Total']]
        else:
            detalle_data = [['Mes', 'Ventas', 'Aporte 1%', 'Aporte 10%', 'Total']]
        
        for dato in datos_agrupados:
            if self.agrupacion == 'dia':
                fecha_str = dato['fecha'].strftime('%d/%m/%Y')
            else:
                fecha_str = dato['mes_nombre']
            
            detalle_data.append([
                fecha_str,
                self._format_currency(dato['ventas']),
                self._format_currency(dato['aporte_1']),
                self._format_currency(dato['aporte_10']),
                self._format_currency(dato['total'])
            ])
        
        # Fila de totales
        detalle_data.append([
            'TOTAL',
            self._format_currency(total_ventas),
            self._format_currency(total_aporte_1),
            self._format_currency(total_aporte_10),
            self._format_currency(total_aportes)
        ])
        
        detalle_table = Table(detalle_data, colWidths=[1.5*inch, 1.3*inch, 1.3*inch, 1.3*inch, 1.3*inch])
        detalle_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D9E1F2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFF2CC')),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        elements.append(detalle_table)
        
        doc.build(elements)
        output.seek(0)
        return output.read()

    def action_generar_reporte(self):
        """Acción principal para generar el reporte"""
        self.ensure_one()
        
        # Obtener datos de ventas
        ventas_data, total_facturas, total_pos = self._get_ventas_data()
        
        if not ventas_data:
            raise UserError(_('No se encontraron ventas en el período seleccionado.'))
        
        # Agrupar datos
        if self.agrupacion == 'dia':
            datos_agrupados = self._agrupar_por_dia(ventas_data)
        else:
            datos_agrupados = self._agrupar_por_mes(ventas_data)
        
        # Generar archivo según formato
        if self.formato == 'txt':
            contenido = self._generar_txt(datos_agrupados, total_facturas, total_pos)
            archivo_bytes = contenido.encode('utf-8')
            extension = 'txt'
        elif self.formato == 'xlsx':
            archivo_bytes = self._generar_xlsx(datos_agrupados, total_facturas, total_pos)
            extension = 'xlsx'
        elif self.formato == 'pdf':
            archivo_bytes = self._generar_pdf(datos_agrupados, total_facturas, total_pos)
            extension = 'pdf'
        else:
            raise UserError(_('Formato no soportado.'))
        
        # Generar nombre de archivo
        fecha_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre_archivo = f"Reporte_Aportes_{fecha_str}.{extension}"
        
        # Guardar archivo en el wizard
        self.write({
            'archivo_generado': base64.b64encode(archivo_bytes),
            'nombre_archivo': nombre_archivo
        })
        
        # Retornar acción para descargar
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/aporte.report.wizard/{self.id}/archivo_generado/{nombre_archivo}?download=true',
            'target': 'self',
        }
