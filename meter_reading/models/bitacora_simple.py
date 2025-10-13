# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.misc import format_date
from datetime import datetime, timedelta
import calendar

class BitacoraSimple(models.TransientModel):
    _name = 'bitacora.simple'
    _description = 'Bitácora Simple de Consumo'

    metrocontador_id = fields.Many2one('meter.reading.metrocontador', string='Metrocontador', required=True)
    
    # Campo para seleccionar el plan energético
    plan_energetico_id = fields.Many2one(
        'meter.reading.plan.energetico', 
        string='Plan Energético',
        required=True,
        domain="[('metrocontador_id', '=', metrocontador_id)]"
    )
    
    
    fecha_inicio_plan = fields.Date(
        string='Fecha Inicio Plan', 
        compute='_compute_fechas_plan',
        store=False 
    )
    fecha_fin_plan = fields.Date(
        string='Fecha Fin Plan', 
        compute='_compute_fechas_plan',
        store=False  
    )

    @api.depends('plan_energetico_id')
    def _compute_fechas_plan(self):
        """Obtener fechas directamente del plan seleccionado"""
        for record in self:
            if record.plan_energetico_id:
                record.fecha_inicio_plan = record.plan_energetico_id.fecha_inicio
                record.fecha_fin_plan = record.plan_energetico_id.fecha_fin
            else:
                record.fecha_inicio_plan = False
                record.fecha_fin_plan = False

    def get_dia_semana_espanol(self, fecha):
        """Devuelve el día de la semana en español"""
        dias_ingles_espanol = {
            'Mon': 'LUN',
            'Tue': 'MAR', 
            'Wed': 'MIE',
            'Thu': 'JUE',
            'Fri': 'VIE',
            'Sat': 'SAB',
            'Sun': 'DOM'
        }
        dia_ingles = fecha.strftime('%a')
        return dias_ingles_espanol.get(dia_ingles, dia_ingles)

    def get_nombre_reporte_bitacora(self):
        """Genera nombre personalizado para el reporte de bitácora en español"""
        self.ensure_one()
        metro_name = self.metrocontador_id.name.replace(' ', '_') if self.metrocontador_id else 'Metrocontador'
        
        # Mapear meses a español
        meses_espanol = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        
        # Obtener fecha del plan directamente
        if self.plan_energetico_id and self.plan_energetico_id.fecha_inicio:
            mes_nombre = meses_espanol.get(self.plan_energetico_id.fecha_inicio.month, '')
            año = self.plan_energetico_id.fecha_inicio.year
            return f'Bitacora_{metro_name}_{mes_nombre}_{año}.pdf'
        else:
            return f'Bitacora_{metro_name}.pdf'

    @api.onchange('metrocontador_id')
    def _onchange_metrocontador_id(self):
        """Cuando se selecciona un metrocontador, cargar su plan activo o el más reciente"""
        if self.metrocontador_id:
            # Buscar primero el plan activo
            plan = self.env['meter.reading.plan.energetico'].search([
                ('metrocontador_id', '=', self.metrocontador_id.id),
                ('state', '=', 'active')
            ], limit=1, order='fecha_inicio desc')
            
            # Si no hay plan activo, buscar el más reciente (cualquier estado)
            if not plan:
                plan = self.env['meter.reading.plan.energetico'].search([
                    ('metrocontador_id', '=', self.metrocontador_id.id)
                ], limit=1, order='fecha_inicio desc')
            
            if plan:
                self.plan_energetico_id = plan.id
             
            else:
                self.plan_energetico_id = False
        else:
            self.plan_energetico_id = False

    def action_vista_previa(self):
        """Muestra vista previa del reporte en HTML como lo hace Odoo nativo"""
        if not self.metrocontador_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Datos requeridos',
                    'message': 'Por favor seleccione un metrocontador',
                    'type': 'warning',
                }
            }
        
        if not self.plan_energetico_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Plan requerido',
                    'message': f'Por favor seleccione un plan energético para {self.metrocontador_id.name}',
                    'type': 'warning',
                }
            }
        
        
        if not self._validar_datos_disponibles():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin datos',
                    'message': self._get_mensaje_sin_datos(),
                    'type': 'warning',
                }
            }
        
        # Usar el reporte HTML específico
        return self.env.ref('meter_reading.report_bitacora_simple_html').report_action(self)

    def action_generar_bitacora(self):
        """Genera el reporte directamente en PDF"""
        if not self.metrocontador_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Datos requeridos',
                    'message': 'Por favor seleccione un metrocontador',
                    'type': 'warning',
                }
            }
        
        if not self.plan_energetico_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Plan requerido',
                    'message': f'Por favor seleccione un plan energético para {self.metrocontador_id.name}',
                    'type': 'warning',
                }
            }
        
       
        if not self._validar_datos_disponibles():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin datos',
                    'message': self._get_mensaje_sin_datos(),
                    'type': 'warning',
                }
            }
        
        # Generar PDF directamente
        return self.env.ref('meter_reading.report_bitacora_simple').report_action(self)

    def _validar_datos_disponibles(self):
        """
         NUEVO MÉTODO: Valida que haya datos disponibles ANTES de generar el reporte
        """
        self.ensure_one()
        
        if not self.metrocontador_id or not self.plan_energetico_id:
            return False
        
        
        plan = self.plan_energetico_id
        if not plan.fecha_inicio or not plan.fecha_fin:
            return False
        
        # Buscar si hay ALGUNA lectura para este metrocontador en el rango del plan
        lecturas_count = self.env['meter.reading.lectura.consumo'].search_count([
            ('metrocontador_id', '=', self.metrocontador_id.id),
            ('fecha', '>=', plan.fecha_inicio),
            ('fecha', '<=', plan.fecha_fin)
        ])
        
        return lecturas_count > 0

    def _get_mensaje_sin_datos(self):
        """
         NUEVO MÉTODO: Genera un mensaje informativo cuando no hay datos
        """
        self.ensure_one()
        
        # Contar lecturas totales del metrocontador
        lecturas_totales = self.env['meter.reading.lectura.consumo'].search_count([
            ('metrocontador_id', '=', self.metrocontador_id.id)
        ])
        
        if lecturas_totales == 0:
            return (f'No hay lecturas registradas para {self.metrocontador_id.name}. '
                   f'Por favor, registre lecturas antes de generar la bitácora.')
        
      
        plan = self.plan_energetico_id
        
        # Buscar la primera y última lectura
        primera_lectura = self.env['meter.reading.lectura.consumo'].search([
            ('metrocontador_id', '=', self.metrocontador_id.id)
        ], limit=1, order='fecha asc')
        
        ultima_lectura = self.env['meter.reading.lectura.consumo'].search([
            ('metrocontador_id', '=', self.metrocontador_id.id)
        ], limit=1, order='fecha desc')
        
        mensaje = (f'No se encontraron lecturas para {self.metrocontador_id.name} '
                  f'en el período del plan ({plan.fecha_inicio.strftime("%d/%m/%Y")} - '
                  f'{plan.fecha_fin.strftime("%d/%m/%Y")}).\n\n')
        
        if primera_lectura and ultima_lectura:
            mensaje += (f'Lecturas disponibles: desde {primera_lectura.fecha.strftime("%d/%m/%Y")} '
                       f'hasta {ultima_lectura.fecha.strftime("%d/%m/%Y")}.\n\n')
            mensaje += 'Sugerencias:\n'
            mensaje += '• Verifique que el plan energético cubra el período donde existen lecturas\n'
            mensaje += '• O registre lecturas dentro del período del plan actual'
        
        return mensaje

    def get_datos_bitacora(self):
        """Obtiene todos los datos necesarios para el reporte"""
        self.ensure_one()
        
        if not self.metrocontador_id or not self.plan_energetico_id:
            return {'datos': []}
        
        #  Obtener fechas directamente del plan
        plan = self.plan_energetico_id
        fecha_inicio = plan.fecha_inicio
        fecha_fin = plan.fecha_fin
        
        if not fecha_inicio or not fecha_fin:
            return {'datos': []}

        # Buscar lecturas
        lecturas = self.env['meter.reading.lectura.consumo'].search([
            ('metrocontador_id', '=', self.metrocontador_id.id),
            ('fecha', '>=', fecha_inicio),
            ('fecha', '<=', fecha_fin)
        ], order='fecha asc, hora asc')

        #  LOG para debugging
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"\n{'='*60}")
        _logger.info(f"BITÁCORA DEBUG - {self.metrocontador_id.name}")
        _logger.info(f"{'='*60}")
        _logger.info(f"Plan ID: {plan.id} - {plan.name}")
        _logger.info(f"Plan Estado: {plan.state}")
        _logger.info(f"Fecha Inicio Plan: {fecha_inicio}")
        _logger.info(f"Fecha Fin Plan: {fecha_fin}")
        _logger.info(f"Metrocontador ID: {self.metrocontador_id.id}")
        _logger.info(f"Metrocontador Tipo: {self.metrocontador_id.tipo_medidor}")
        _logger.info(f"Metrocontador Activo: {self.metrocontador_id.activo}")
        _logger.info(f"-" * 60)
        _logger.info(f"LECTURAS ENCONTRADAS: {len(lecturas)}")
        
        if lecturas:
            _logger.info(f"Primera lectura: {lecturas[0].fecha} - {lecturas[0].hora} - {lecturas[0].lectura_kwh} kWh")
            _logger.info(f"Última lectura: {lecturas[-1].fecha} - {lecturas[-1].hora} - {lecturas[-1].lectura_kwh} kWh")
            # Mostrar algunas lecturas de muestra
            for idx, lec in enumerate(lecturas[:5]):
                _logger.info(f"  [{idx+1}] {lec.fecha} {lec.hora}: {lec.lectura_kwh} kWh (consumo: {lec.consumo_parcial} kWh)")
            if len(lecturas) > 5:
                _logger.info(f"  ... ({len(lecturas) - 5} lecturas más)")
        else:
            _logger.warning(f"⚠️  NO SE ENCONTRARON LECTURAS")
            # Buscar lecturas fuera del rango
            todas_lecturas = self.env['meter.reading.lectura.consumo'].search([
                ('metrocontador_id', '=', self.metrocontador_id.id)
            ], order='fecha asc')
            if todas_lecturas:
                _logger.info(f"Pero existen {len(todas_lecturas)} lecturas para este metrocontador:")
                _logger.info(f"  Rango de lecturas: {todas_lecturas[0].fecha} a {todas_lecturas[-1].fecha}")
                _logger.info(f"  Rango del plan: {fecha_inicio} a {fecha_fin}")
                _logger.info(f"  ❌ NO HAY OVERLAP - Las fechas no coinciden")
            else:
                _logger.error(f"❌ NO HAY NINGUNA LECTURA para este metrocontador")
        _logger.info(f"{'='*60}\n")

        def get_plan_diario(fecha, plan_obj):
            """Obtiene el consumo planificado para una fecha específica según el plan"""
            if not plan_obj:
                return 100  # Valor por defecto si no hay plan
            return plan_obj.get_consumo_diario_fecha(fecha)

        datos_por_dia = {}
        for lectura in lecturas:
            fecha_str = lectura.fecha.strftime('%Y-%m-%d')
            if fecha_str not in datos_por_dia:
                datos_por_dia[fecha_str] = {
                    'fecha': lectura.fecha,
                    'consumo_total': 0,
                    'lectura_final': 0,
                    'horarios_lecturas': {'madrugada': 0, 'dia': 0, 'pico': 0, 'reactivo': 0}, 
                    'horarios_consumos': {'madrugada': 0, 'dia': 0, 'pico': 0, 'reactivo': 0}   
                }
            
            consumo_parcial = lectura.consumo_parcial or 0
            datos_por_dia[fecha_str]['consumo_total'] += consumo_parcial
            
            if lectura.lectura_kwh and lectura.lectura_kwh > datos_por_dia[fecha_str]['lectura_final']:
                datos_por_dia[fecha_str]['lectura_final'] = lectura.lectura_kwh
                
            hora = lectura.hora or 'dia'
            if hora in datos_por_dia[fecha_str]['horarios_consumos']:
                datos_por_dia[fecha_str]['horarios_consumos'][hora] += consumo_parcial

        resultado = []
        plan_acum = 0
        real_acum = 0
        
        # Variables para acumular consumos de franjas horarias (para totales)
        total_consumo_madrugada = 0
        total_consumo_dia = 0
        total_consumo_pico = 0
        total_consumo_reactivo = 0
        
        fecha_actual = fecha_inicio
        while fecha_actual <= fecha_fin:
            fecha_str = fecha_actual.strftime('%Y-%m-%d')
            
            if fecha_str in datos_por_dia:
                dia_data = datos_por_dia[fecha_str]
                consumo_diario = dia_data['consumo_total']
                lectura_final = dia_data['lectura_final']
                horarios = dia_data['horarios_consumos']
                
                # Acumular consumos para totales
                total_consumo_madrugada += dia_data['horarios_consumos']['madrugada']
                total_consumo_dia += dia_data['horarios_consumos']['dia']
                total_consumo_pico += dia_data['horarios_consumos']['pico']
                total_consumo_reactivo += dia_data['horarios_consumos']['reactivo']
            else:
                consumo_diario = 0
                lectura_final = 0
                horarios = {'madrugada': 0, 'dia': 0, 'pico': 0, 'reactivo': 0}
            
            plan_diario = get_plan_diario(fecha_actual, plan)
            plan_acum += plan_diario
            real_acum += consumo_diario
            
            resultado.append({
                'fecha': fecha_actual,
                'dia_semana': self.get_dia_semana_espanol(fecha_actual), 
                'plan_diario': plan_diario,
                'lectura_diaria': lectura_final,
                'consumo_diario': consumo_diario,
                'plan_acumulado': plan_acum,
                'real_acumulado': real_acum,
                'diferencia': real_acum - plan_acum,
                'madrugada': horarios['madrugada'], 
                'dia': horarios['dia'],             
                'pico': horarios['pico'],           
                'reactivo': horarios['reactivo']     
            })
            
            fecha_actual += timedelta(days=1)

        total_consumo = sum(row['consumo_diario'] for row in resultado)
        total_plan = sum(row['plan_diario'] for row in resultado)

        # Fórmula porcentaje consumido
        porcentaje_consumido = 0
        if total_plan > 0:
            porcentaje_consumido = (total_consumo / total_plan) * 100
        else:
            porcentaje_consumido = 0

        # Formatear el período para mostrar
        periodo = f"{fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}"

        return {
            'datos': resultado,
            'totales': {
                'plan_total': total_plan,
                'real_total': real_acum,
                'diferencia_total': real_acum - total_plan,
                'consumo_total': total_consumo,
                'madrugada_total': total_consumo_madrugada,  
                'dia_total': total_consumo_dia,              
                'pico_total': total_consumo_pico,           
                'reactivo_total': total_consumo_reactivo,    
                'porcentaje_consumido': porcentaje_consumido 
            },
            'metrocontador': self.metrocontador_id.name,
            'periodo': periodo,
            'plan_info': {
                'nombre': plan.name if plan else 'Plan por defecto',
                'consumo_mensual': plan.consumo_mensual_plan if plan else total_plan
            },
            'fecha_generacion': format_date(self.env, fields.Date.today())
        }