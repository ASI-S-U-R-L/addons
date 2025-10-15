# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
import calendar


class ConsumoTotalEmpresa(models.TransientModel):
    _name = 'consumo.total.empresa'
    _description = 'Consumo Total de la Empresa'

    mes = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
        ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
        ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')
    ], string='Mes', required=True, default=lambda self: str(fields.Date.context_today(self).month))
    
    ano = fields.Integer(
        string='Año',
        required=True,
        default=lambda self: fields.Date.context_today(self).year
    )

    def get_nombre_reporte_consumo_total(self):
        """Genera nombre personalizado para el reporte de consumo total en español"""
        self.ensure_one()
        mes_nombre = dict(self._fields['mes'].selection).get(self.mes, self.mes)
        return f'Consumo_Total_{mes_nombre}_{self.ano}.pdf'

    def action_vista_previa(self):
        """Muestra vista previa del reporte en HTML (como la bitácora)"""
        if not self.mes or not self.ano:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Datos requeridos',
                    'message': 'Por favor seleccione mes y año',
                    'type': 'warning',
                }
            }
        
        datos_reporte = self._get_datos_reporte()
        
        if not datos_reporte['metrocontadores']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin datos',
                    'message': 'No hay metrocontadores activos para generar el reporte',
                    'type': 'warning',
                }
            }
        
        # Usar el reporte HTML para vista previa
        return self.env.ref('meter_reading.report_consumo_total_empresa_html').report_action(self)

    def action_generar_pdf(self):
        """Genera el reporte directamente en PDF"""
        if not self.mes or not self.ano:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Datos requeridos',
                    'message': 'Por favor seleccione mes y año',
                    'type': 'warning',
                }
            }
        
        datos_reporte = self._get_datos_reporte()
        
        if not datos_reporte['metrocontadores']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin datos',
                    'message': 'No hay metrocontadores activos para generar el reporte',
                    'type': 'warning',
                }
            }
        
        # Generar PDF directamente
        return self.env.ref('meter_reading.report_consumo_total_empresa_pdf').report_action(self)

    def get_datos_reporte(self):
        """Método público para ser llamado desde el template (como la bitácora)"""
        return self._get_datos_reporte()

    def _get_datos_reporte(self):
        """Obtener todos los datos para el reporte - CALCULA PREPAGO DESDE LECTURAS"""
        self.ensure_one()
        
        mes_int = int(self.mes)
        fecha_inicio = datetime(self.ano, mes_int, 1)
        ultimo_dia = calendar.monthrange(self.ano, mes_int)[1]
        fecha_fin = datetime(self.ano, mes_int, ultimo_dia)
        
        metrocontadores = self.env['meter.reading.metrocontador'].search([('activo', '=', True)])
        
        datos_metrocontadores = []
        total_general = 0.0
        
        for metro in metrocontadores:
            consumo_mensual = 0.0
            tipo_calculo = 'Automático'
            
            if metro.tipo_medidor == 'prepago':
               
                lecturas_prepago = self.env['meter.reading.lectura.consumo'].search([
                    ('metrocontador_id', '=', metro.id),
                    ('fecha', '>=', fecha_inicio.date()),
                    ('fecha', '<=', fecha_fin.date()),
                    ('tipo_medidor', '=', 'prepago')
                ])
                consumo_mensual = sum(lecturas_prepago.mapped('consumo_mes'))
                tipo_calculo = 'Automático (Recargas)'
            else:
                # Calcular automáticamente para metrocontadores normales e inteligentes
                lecturas = self.env['meter.reading.lectura.consumo'].search([
                    ('metrocontador_id', '=', metro.id),
                    ('fecha', '>=', fecha_inicio.date()),
                    ('fecha', '<=', fecha_fin.date())
                ])
                consumo_mensual = sum(lecturas.mapped('consumo_parcial'))
                tipo_calculo = 'Automático'
            
            datos_metrocontadores.append({
                'nombre': metro.name,
                'ubicacion': metro.ubicacion or 'Sin ubicación',
                'tipo_medidor': metro.tipo_medidor,
                'responsable': metro.responsable_id.name if metro.responsable_id else 'Sin asignar',
                'consumo_mensual': consumo_mensual,
                'tipo_calculo': tipo_calculo
            })
            
            total_general += consumo_mensual
        
        # Formatear fecha de generación
        fecha_generacion = fields.Date.context_today(self).strftime('%d/%m/%Y')
        mes_nombre = dict(self._fields['mes'].selection).get(self.mes)
        
        return {
            'mes_nombre': mes_nombre,
            'ano': self.ano,
            'periodo': f"{mes_nombre} {self.ano}",
            'fecha_generacion': fecha_generacion,
            'metrocontadores': datos_metrocontadores,
            'total_general': total_general,
            'cantidad_metrocontadores': len(metrocontadores),
            'promedio_por_metro': total_general / len(metrocontadores) if metrocontadores else 0.0
        }