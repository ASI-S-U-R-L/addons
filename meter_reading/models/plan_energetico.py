from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class PlanEnergeticoDia(models.Model):
    _name = 'meter.reading.plan.dia'
    _description = 'Consumo Diario del Plan Energético'
    _rec_name = 'fecha'
    
    plan_id = fields.Many2one(
        'meter.reading.plan.energetico',
        string='Plan',
        required=True,
        ondelete='cascade'
    )
    fecha = fields.Date(string='Fecha', required=True)
    consumo_planificado = fields.Float(
        string='Consumo Planificado (kWh)',
        required=True,
        default=0.0
    )
    dia_semana = fields.Char(
        string='Día',
        compute='_compute_dia_semana',
        store=True
    )
    modificado_manualmente = fields.Boolean(
        string='Modificado Manualmente',
        default=False,
        help='Indica si este día fue modificado manualmente por el usuario'
    )
    
    @api.depends('fecha')
    def _compute_dia_semana(self):
        dias = ['LUN', 'MAR', 'MIE', 'JUE', 'VIE', 'SAB', 'DOM']
        for record in self:
            if record.fecha:
                record.dia_semana = dias[record.fecha.weekday()]
            else:
                record.dia_semana = ''
    
    def name_get(self):
        """Personalizar el nombre mostrado en el calendario"""
        result = []
        for record in self:
            name = '%s - %.2f kWh' % (record.dia_semana, record.consumo_planificado)
            result.append((record.id, name))
        return result
    
    @api.constrains('consumo_planificado')
    def _check_consumo_no_supera_total(self):
        """Validar que la suma total no supere el Consumo Periodo Total"""
      
        if self.env.context.get('skip_validation'):
            return
            
        for record in self:
            if record.plan_id:
                
                self.env.cr.execute("""
                    SELECT COALESCE(SUM(consumo_planificado), 0)
                    FROM meter_reading_plan_dia
                    WHERE plan_id = %s
                """, (record.plan_id.id,))
                total_consumo = self.env.cr.fetchone()[0]
                
                
                if total_consumo > (record.plan_id.consumo_mensual_plan + 0.01):
                    exceso = total_consumo - record.plan_id.consumo_mensual_plan
                    raise ValidationError(
                        _('El consumo total asignado (%.2f kWh) supera el Presupuesto Total (%.2f kWh) por %.2f kWh.\n\n'
                          'Los sábados y domingos mantienen sus valores fijos. Reduce el valor de uno o más días laborables, o usa el botón "Resetear" para volver a la distribución inicial.') % 
                        (total_consumo, record.plan_id.consumo_mensual_plan, exceso)
                    )
    
    def write(self, vals):
        """Marcar como modificado y redistribuir automáticamente CON VALIDACIÓN"""
        # Si estamos en contexto de redistribución, evitar recursión
        if self.env.context.get('skip_write_redistribution'):
            return super(PlanEnergeticoDia, self).write(vals)
        
       
        if 'consumo_planificado' in vals and self.plan_id:
            nuevo_consumo = vals['consumo_planificado']
            
            # Calcular el consumo total si aplicamos este cambio
            consumo_otros_dias_modificados = sum(
                self.plan_id.consumo_dias_especificos.filtered(
                    lambda d: d.id != self.id and d.modificado_manualmente and d.fecha.weekday() < 5
                ).mapped('consumo_planificado')
            )
            
            consumo_fines_semana = sum(
                self.plan_id.consumo_dias_especificos.filtered(
                    lambda d: d.fecha.weekday() >= 5  # Sábados y domingos
                ).mapped('consumo_planificado')
            )
            
            # SUMA TOTAL: nuevo valor + otros días modificados + fines de semana
            # (Los días automáticos se ajustarán después, pueden quedar en 0)
            consumo_total_fijo = nuevo_consumo + consumo_otros_dias_modificados + consumo_fines_semana
            
            # VALIDAR: Si la suma de valores fijos excede el presupuesto total
            if consumo_total_fijo > self.plan_id.consumo_mensual_plan + 0.01: 
                exceso = consumo_total_fijo - self.plan_id.consumo_mensual_plan
                raise ValidationError(
                    _('ALERTA: El valor ingresado excede el Presupuesto Total\n\n'
                      'Valor que intentas asignar a este día: %.2f kWh\n'
                      'Otros días laborables modificados: %.2f kWh\n'
                      'Fines de semana (fijos): %.2f kWh\n'
                      '─────────────────────────────────\n'
                      'SUMA TOTAL: %.2f kWh\n'
                      'Presupuesto Total disponible: %.2f kWh\n'
                      'EXCESO: %.2f kWh\n\n'
                      'No se puede aplicar este cambio porque excede el presupuesto.\n'
                      'Reduce el valor de este día o de otros días modificados manualmente.') % 
                    (
                        nuevo_consumo,
                        consumo_otros_dias_modificados,
                        consumo_fines_semana,
                        consumo_total_fijo,
                        self.plan_id.consumo_mensual_plan,
                        exceso
                    )
                )
        
        # Marcar como modificado
        if 'consumo_planificado' in vals and 'modificado_manualmente' not in vals:
            vals['modificado_manualmente'] = True
        
        result = super(PlanEnergeticoDia, self).write(vals)
        
        # Redistribuir automáticamente DESPUÉS del cambio (ya validado)
        # Los días automáticos se ajustarán, pueden quedar en 0 si no hay presupuesto
        if 'consumo_planificado' in vals and self.plan_id:
            self.plan_id.with_context(skip_validation=True)._redistribuir_automatico()
        
        return result


class PlanEnergetico(models.Model):
    _name = 'meter.reading.plan.energetico'
    _description = 'Plan Energético'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nombre del Plan',
        required=True,
        tracking=True,
        help='Nombre descriptivo del plan energético'
    )
    
    fecha_inicio = fields.Date(
        string='Fecha Inicio',
        required=True,
        tracking=True
    )
    
    fecha_fin = fields.Date(
        string='Fecha Fin',
        required=True,
        tracking=True
    )
    
    consumo_mensual_plan = fields.Float(
        string='Presupuesto Total (kWh)',
        required=True,
        tracking=True,
        help='Consumo total planificado para el periodo'
    )
    
    consumo_sabados = fields.Float(
        string='Presupuesto para Sábados (kWh)',
        default=0.0,
        tracking=True,
        help='Consumo asignado a cada sábado'
    )
    
    consumo_domingos = fields.Float(
        string='Presupuesto para Domingos (kWh)',
        default=0.0,
        tracking=True,
        help='Consumo asignado a cada domingo'
    )
    
    consumo_diario_semana = fields.Float(
        string='Presupuesto Diario Lun-Vie (kWh)',
        compute='_compute_consumo_diario',
        store=True,
        help='Consumo diario calculado para días de semana'
    )
    
    consumo_diario_plan = fields.Float(
        string='Consumo Diario Promedio (kWh)',
        compute='_compute_consumo_diario',
        store=True,
        help='Consumo diario promedio (para compatibilidad)'
    )
    
    metrocontador_id = fields.Many2one(
        'meter.reading.metrocontador',
        string='Metrocontador',
        required=True,
        tracking=True
    )
    
    # Campos de estado
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('finished', 'Finalizado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    # Campos calculados
    dias_plan = fields.Integer(
        string='Días del Plan',
        compute='_compute_dias_plan',
        store=True
    )
    
    dias_semana = fields.Integer(
        string='Días de Semana',
        compute='_compute_dias_plan',
        store=True
    )
    
    sabados_total = fields.Integer(
        string='Total Sábados',
        compute='_compute_dias_plan',
        store=True
    )
    
    domingos_total = fields.Integer(
        string='Total Domingos',
        compute='_compute_dias_plan',
        store=True
    )
    
    consumo_real_acumulado = fields.Float(
        string='Consumo Real Acumulado (kWh)',
        compute='_compute_consumo_real'
    )
    
    porcentaje_cumplimiento = fields.Float(
        string='% Consumido',
        compute='_compute_porcentaje_cumplimiento'
    )
    
    # Campo para distribución por día
    consumo_dias_especificos = fields.One2many(
        'meter.reading.plan.dia',
        'plan_id',
        string='Distribución por Día',
        readonly=False
    )
    
    @api.constrains('fecha_inicio', 'fecha_fin')
    def _check_fechas(self):
        """Validar que la fecha de inicio sea anterior a la fecha de fin"""
        for record in self:
            if record.fecha_inicio and record.fecha_fin:
                if record.fecha_inicio > record.fecha_fin:
                    raise ValidationError(
                        _('La fecha de inicio debe ser anterior a la fecha de fin')
                    )

    @api.constrains('consumo_mensual_plan')
    def _check_consumo_total(self):
        """Validar que el consumo total sea positivo"""
        for record in self:
            if record.consumo_mensual_plan <= 0:
                raise ValidationError(
                    _('El presupuesto total debe ser mayor que cero')
                )
    
    @api.depends('fecha_inicio', 'fecha_fin')
    def _compute_dias_plan(self):
        for record in self:
            if record.fecha_inicio and record.fecha_fin and record.fecha_inicio <= record.fecha_fin:
                delta = record.fecha_fin - record.fecha_inicio
                record.dias_plan = delta.days + 1
                
                dias_semana = 0
                sabados = 0
                domingos = 0
                
                current_date = record.fecha_inicio
                while current_date <= record.fecha_fin:
                    weekday = current_date.weekday()
                    if weekday < 5:  # 0-4 = Lunes-Viernes
                        dias_semana += 1
                    elif weekday == 5:  # Sábado
                        sabados += 1
                    else:  # weekday == 6, Domingo
                        domingos += 1
                    current_date += timedelta(days=1)
                
                record.dias_semana = dias_semana
                record.sabados_total = sabados
                record.domingos_total = domingos
            else:
                record.dias_plan = 0
                record.dias_semana = 0
                record.sabados_total = 0
                record.domingos_total = 0
    
    @api.depends('consumo_mensual_plan', 'consumo_sabados', 'consumo_domingos', 'dias_semana', 'sabados_total', 'domingos_total')
    def _compute_consumo_diario(self):
        for record in self:
            consumo_total_sabados = record.consumo_sabados * record.sabados_total
            consumo_total_domingos = record.consumo_domingos * record.domingos_total
            consumo_total_fines_semana = consumo_total_sabados + consumo_total_domingos
            
            consumo_restante = record.consumo_mensual_plan - consumo_total_fines_semana
            
            if record.dias_semana > 0:
                record.consumo_diario_semana = consumo_restante / record.dias_semana
            else:
                record.consumo_diario_semana = 0.0
            
            if record.dias_plan > 0:
                record.consumo_diario_plan = record.consumo_mensual_plan / record.dias_plan
            else:
                record.consumo_diario_plan = 0.0
    
    def get_consumo_diario_fecha(self, fecha):
        """Obtener el consumo diario planificado para una fecha específica"""
        self.ensure_one()
        dia_especifico = self.consumo_dias_especificos.filtered(lambda d: d.fecha == fecha)
        if dia_especifico:
            return dia_especifico.consumo_planificado
        
        weekday = fecha.weekday()
        if weekday < 5:
            return self.consumo_diario_semana
        elif weekday == 5:
            return self.consumo_sabados
        else:
            return self.consumo_domingos
    
    def _compute_consumo_real(self):
        for record in self:
            if record.metrocontador_id:
                domain = [
                    ('metrocontador_id', '=', record.metrocontador_id.id),
                    ('fecha', '>=', record.fecha_inicio),
                    ('fecha', '<=', record.fecha_fin)
                ]
                lecturas = self.env['meter.reading.lectura.consumo'].search(domain)
                record.consumo_real_acumulado = sum(lecturas.mapped('consumo_parcial'))
            else:
                record.consumo_real_acumulado = 0.0
    
    def _compute_porcentaje_cumplimiento(self):
        for record in self:
            if record.consumo_mensual_plan > 0:
                record.porcentaje_cumplimiento = (
                    record.consumo_real_acumulado / record.consumo_mensual_plan
                ) * 100
            else:
                record.porcentaje_cumplimiento = 0.0

    @api.model
    def create(self, vals):
        record = super(PlanEnergetico, self).create(vals)
        record._generar_distribucion_automatica()
        return record
    
    def write(self, vals):
        campos_distribucion = ['consumo_mensual_plan', 'consumo_sabados', 'consumo_domingos', 'fecha_inicio', 'fecha_fin']
        necesita_regenerar = any(campo in vals for campo in campos_distribucion)
        
        result = super(PlanEnergetico, self).write(vals)
        
        if necesita_regenerar:
            self._generar_distribucion_automatica()
        
        return result

    def _generar_distribucion_automatica(self):
        """Generar distribución automática que evita problemas de redondeo"""
        for plan in self:
            if not plan.fecha_inicio or not plan.fecha_fin:
                continue
            
            # Eliminar distribución anterior
            plan.consumo_dias_especificos.unlink()
            
            dias_crear = []
            current_date = plan.fecha_inicio
            total_asignado = 0.0
            
            # Calcular días laborables y fines de semana
            dias_laborables = []
            dias_fin_semana = []
            
            temp_date = plan.fecha_inicio
            while temp_date <= plan.fecha_fin:
                weekday = temp_date.weekday()
                if weekday < 5:  # Lunes a Viernes
                    dias_laborables.append(temp_date)
                else:  # Fin de semana
                    dias_fin_semana.append(temp_date)
                temp_date += timedelta(days=1)
            
            # Asignar fines de semana (valores fijos)
            for fecha in dias_fin_semana:
                weekday = fecha.weekday()
                if weekday == 5:  # Sábado
                    consumo_dia = plan.consumo_sabados
                else:  # Domingo
                    consumo_dia = plan.consumo_domingos
                
                consumo_dia = round(consumo_dia, 2)
                total_asignado += consumo_dia
                
                dias_crear.append({
                    'fecha': fecha,
                    'consumo_planificado': consumo_dia,
                    'modificado_manualmente': False
                })
            
            # Asignar días laborables con ajuste en el último día
            consumo_disponible_laborables = plan.consumo_mensual_plan - total_asignado
            
            if dias_laborables:
                # Calcular consumo base por día laborable
                consumo_base_laborable = consumo_disponible_laborables / len(dias_laborables)
                
                # Asignar a todos los días laborables excepto el último
                for i, fecha in enumerate(dias_laborables[:-1]):  # Todos excepto el último
                    consumo_dia = round(consumo_base_laborable, 2)
                    total_asignado += consumo_dia
                    
                    dias_crear.append({
                        'fecha': fecha,
                        'consumo_planificado': consumo_dia,
                        'modificado_manualmente': False
                    })
                
                # ÚLTIMO DÍA: Asignar el resto exacto para completar el presupuesto
                ultimo_dia = dias_laborables[-1]
                consumo_ultimo_dia = round(plan.consumo_mensual_plan - total_asignado, 2)
                
                # Verificar que no sea negativo (por seguridad)
                if consumo_ultimo_dia < 0:
                    consumo_ultimo_dia = 0.0
                
                dias_crear.append({
                    'fecha': ultimo_dia,
                    'consumo_planificado': consumo_ultimo_dia,
                    'modificado_manualmente': False
                })
            
            # Ordenar por fecha
            dias_crear.sort(key=lambda x: x['fecha'])
            
            # Crear registros
            plan.consumo_dias_especificos = [(0, 0, dia) for dia in dias_crear]

    def _redistribuir_automatico(self):
        """Redistribución automática que evita problemas de redondeo - SOLO días laborables"""
        self.ensure_one()
        
        if not self.consumo_dias_especificos:
            return
        
        # Separar días en categorías
        dias_laborables_modificados = self.consumo_dias_especificos.filtered(
            lambda d: d.modificado_manualmente and d.fecha.weekday() < 5
        )
        
        dias_laborables_automaticos = self.consumo_dias_especificos.filtered(
            lambda d: not d.modificado_manualmente and d.fecha.weekday() < 5
        )
        
        # Sábados y domingos (fines de semana) - NO se redistribuyen
        dias_sabados = self.consumo_dias_especificos.filtered(
            lambda d: d.fecha.weekday() == 5  # Sábado
        )
        
        dias_domingos = self.consumo_dias_especificos.filtered(
            lambda d: d.fecha.weekday() == 6  # Domingo
        )
        
        if not dias_laborables_automaticos:
            return
        
        # Calcular consumo ya asignado
        # Consumo de días laborables modificados
        consumo_laborables_modificados = sum(dias_laborables_modificados.mapped('consumo_planificado'))
        
        # Consumo de fines de semana (siempre fijos)
        consumo_sabados = sum(dias_sabados.mapped('consumo_planificado'))
        consumo_domingos = sum(dias_domingos.mapped('consumo_planificado'))
        consumo_fines_semana = consumo_sabados + consumo_domingos
        
        # Calcular disponible para días laborables automáticos
        consumo_disponible = self.consumo_mensual_plan - consumo_laborables_modificados - consumo_fines_semana
        
        # PERMITIR que consumo_disponible sea 0 o negativo
        # Si es negativo o 0, los días automáticos quedarán en 0
        if consumo_disponible < 0:
            consumo_disponible = 0
        
        # Ordenar días laborables automáticos por fecha
        dias_automaticos_ordenados = dias_laborables_automaticos.sorted(key=lambda d: d.fecha)
        
        if len(dias_automaticos_ordenados) > 1:
            # Calcular consumo base para días laborables
            consumo_base = consumo_disponible / len(dias_automaticos_ordenados)
            
            # Asignar a todos excepto el último
            for dia in dias_automaticos_ordenados[:-1]:
                consumo_redondeado = round(consumo_base, 2)
                dia.with_context(skip_write_redistribution=True).write({
                    'consumo_planificado': consumo_redondeado
                })
                consumo_disponible -= consumo_redondeado
            
            # Último día: asignar el resto exacto
            ultimo_dia = dias_automaticos_ordenados[-1]
            ultimo_dia.with_context(skip_write_redistribution=True).write({
                'consumo_planificado': round(consumo_disponible, 2)
            })
        else:
            # Solo un día laborable automático
            dias_automaticos_ordenados[0].with_context(skip_write_redistribution=True).write({
                'consumo_planificado': round(consumo_disponible, 2)
            })

    def action_activate(self):
        """Activar el plan energético"""
        self.state = 'active'
    
    def action_finish(self):
        """Finalizar el plan energético"""
        self.state = 'finished'
    
    def action_cancel(self):
        """Cancelar el plan energético"""
        self.state = 'cancelled'