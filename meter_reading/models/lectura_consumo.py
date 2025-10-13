from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, time, timedelta


class LecturaConsumo(models.Model):
    _name = 'meter.reading.lectura.consumo'
    _description = 'Lectura de Consumo'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha desc, hora desc'

    metrocontador_id = fields.Many2one(
        'meter.reading.metrocontador',
        string='Metrocontador',
        required=True,
        tracking=True
    )
    
    fecha = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    

    consumo_mes = fields.Float(
        string='Consumo del Mes (kWh)',
        tracking=True,
        help='Consumo mensual para metrocontadores prepago (recarga)'
    )
    
    hora = fields.Selection(
        selection='_get_hora_selection',
        string='Franja Horaria', 
        tracking=True
    )
    
    lectura_kwh = fields.Float(
        string='Lectura (kWh)',
        tracking=True,
        help='Lectura acumulada del medidor'
    )
    
    consumo_parcial = fields.Float(
        string='Consumo Parcial (kWh)',
        compute='_compute_consumo_parcial',
        store=True,
        help='Consumo desde la lectura anterior según el tipo de medidor.'
    )
        
    consumo_reactivo = fields.Float(
        string='Consumo Reactivo (kWh)',
        compute='_compute_consumo_reactivo',
        store=True,
        help='Consumo reactivo (solo para medidores inteligentes)'
    )
    
    tipo_horario = fields.Selection([
        ('pico', 'Pico'),
        ('valle', 'Valle')
    ], string='Tipo Horario', compute='_compute_tipo_horario', store=True)
    
    observaciones = fields.Text(
        string='Observaciones'
    )
    
    usuario_registro_id = fields.Many2one(
        'res.users',
        string='Usuario Registro',
        default=lambda self: self.env.user,
        required=True
    )
    
    # Campos relacionados
    responsable_id = fields.Many2one(
        related='metrocontador_id.responsable_id',
        string='Responsable Metrocontador',
        store=True
    )
    
    tipo_medidor = fields.Selection(
        related='metrocontador_id.tipo_medidor',
        string='Tipo de Medidor',
        store=True
    )
    
    # Campos de alerta
    excede_plan = fields.Boolean(
        string='Excede Plan',
        compute='_compute_excede_plan',
        store=True
    )
    
    plan_diario_proporcional = fields.Float(
        string='Plan Diario Proporcional',
        compute='_compute_plan_diario_proporcional',
        store=True
    )
    
    consumo_diario_acumulado = fields.Float(
        string='Consumo Total del Día (kWh)',
        compute='_compute_consumo_diario_acumulado',
        store=True,
        help='Consumo total acumulado del día (suma de todos los consumos parciales del día)'
    )

    def _get_hora_selection(self):
        """Obtener opciones de franja horaria según el tipo de medidor."""
        metrocontador_id = self._context.get('default_metrocontador_id')
        
        if metrocontador_id:
            metrocontador = self.env['meter.reading.metrocontador'].browse(metrocontador_id)
            if metrocontador.tipo_medidor == 'inteligente':
                return [
                    ('madrugada', 'Madrugada'),
                    ('dia', 'Día'),
                    ('pico', 'Pico'),
                    ('reactivo', 'Reactivo')
                ]
            elif metrocontador.tipo_medidor == 'prepago':
                return []  # No tiene franjas horarias
            else: 
                return [
                    ('madrugada', 'Madrugada'),
                    ('dia', 'Día'),
                    ('pico', 'Pico')
                ]
        
        # Si no hay contexto, mostrar todas las opciones
        return [
            ('madrugada', 'Madrugada'),
            ('dia', 'Día'),
            ('pico', 'Pico'),
            ('reactivo', 'Reactivo (Solo Inteligentes)')
        ]

    @api.depends('hora')
    def _compute_tipo_horario(self):
        """Determinar si es pico o valle según la franja horaria"""
        for record in self:
            if record.tipo_medidor == 'prepago':
                record.tipo_horario = False
            elif record.hora == 'pico':
                record.tipo_horario = 'pico'
            elif record.hora in ['madrugada', 'dia']:
                record.tipo_horario = 'valle'
            else:
                record.tipo_horario = False

    @api.onchange('metrocontador_id')
    def _onchange_metrocontador_id(self):
        """Limpiar la selección de hora cuando cambia el metrocontador"""
        self.hora = False
        return {'domain': {'hora': []}}
    
    @api.depends('metrocontador_id', 'fecha', 'hora', 'lectura_kwh', 'metrocontador_id.factor_conversion')
    def _compute_consumo_parcial(self):
        """
        Calcular el consumo parcial aplicando el factor de conversión
        según las nuevas reglas para cada tipo de medidor.
        El consumo se calcula a partir de la SEGUNDA lectura del sistema.
        ⚠️ NO aplica para metrocontadores PREPAGO
        """
        for record in self:
            # 🆕 PREPAGO: No calcular consumo parcial
            if record.tipo_medidor == 'prepago':
                record.consumo_parcial = 0.0
                continue
            
            if not all([record.metrocontador_id, record.fecha, record.hora]):
                record.consumo_parcial = 0.0
                continue

            # Obtener el factor de conversión (default 1.0 si no está definido)
            factor = record.metrocontador_id.factor_conversion or 1.0
            
            lectura_anterior_obj = None
            
            # Buscar la lectura anterior según el tipo de medidor
            if record.tipo_medidor == 'inteligente':
                # Para inteligentes: comparar con la misma franja del día anterior
                fecha_anterior = record.fecha - timedelta(days=1)
                lectura_anterior_obj = self.search([
                    ('metrocontador_id', '=', record.metrocontador_id.id),
                    ('fecha', '=', fecha_anterior),
                    ('hora', '=', record.hora)
                ], limit=1, order='fecha desc, hora desc')
            else:
                # Para normales: lógica secuencial dentro del mismo día o día anterior
                if record.hora == 'madrugada':
                    # Primera lectura del día - buscar 'pico' del día anterior
                    fecha_anterior = record.fecha - timedelta(days=1)
                    lectura_anterior_obj = self.search([
                        ('metrocontador_id', '=', record.metrocontador_id.id),
                        ('fecha', '=', fecha_anterior),
                        ('hora', '=', 'pico')
                    ], limit=1, order='fecha desc, hora desc')
                elif record.hora == 'dia':
                    # Segunda lectura - buscar 'madrugada' del mismo día
                    lectura_anterior_obj = self.search([
                        ('metrocontador_id', '=', record.metrocontador_id.id),
                        ('fecha', '=', record.fecha),
                        ('hora', '=', 'madrugada')
                    ], limit=1, order='fecha desc, hora desc')
                elif record.hora == 'pico':
                    # Tercera lectura - buscar 'dia' del mismo día
                    lectura_anterior_obj = self.search([
                        ('metrocontador_id', '=', record.metrocontador_id.id),
                        ('fecha', '=', record.fecha),
                        ('hora', '=', 'dia')
                    ], limit=1, order='fecha desc, hora desc')

            # Si hay lectura anterior, calcular la diferencia CON factor de conversión
            if lectura_anterior_obj:
                consumo_sin_factor = record.lectura_kwh - lectura_anterior_obj.lectura_kwh
                record.consumo_parcial = consumo_sin_factor * factor
            else:
                # Si es la PRIMERA lectura del sistema, el consumo parcial es 0
                # porque no tenemos referencia anterior para calcular la diferencia
                record.consumo_parcial = 0.0
    
    @api.depends('hora', 'consumo_parcial', 'tipo_medidor')
    def _compute_consumo_reactivo(self):
        """Calcula el consumo reactivo, que es el consumo parcial de la franja 'reactivo'."""
        for record in self:
            if record.tipo_medidor == 'inteligente' and record.hora == 'reactivo':
                record.consumo_reactivo = record.consumo_parcial
            else:
                record.consumo_reactivo = 0.0

    @api.depends('metrocontador_id', 'fecha', 'consumo_parcial')
    def _compute_consumo_diario_acumulado(self):
        """
        Calcular el consumo total del día.
        Este valor será el mismo para todas las lecturas del mismo día y medidor.
        ⚠️ NO aplica para metrocontadores PREPAGO
        """
        for record in self:
            if record.tipo_medidor == 'prepago':
                record.consumo_diario_acumulado = 0.0
                continue
        
        if not self.ids:
            for record in self:
                record.consumo_diario_acumulado = 0.0
            return

        # Para asegurar que el cálculo se hace sobre datos guardados
        self.flush_model(['metrocontador_id', 'fecha', 'consumo_parcial'])
        
        query = """
            SELECT metrocontador_id, fecha, SUM(consumo_parcial)
            FROM {table}
            WHERE (metrocontador_id, fecha) IN %s
            GROUP BY metrocontador_id, fecha
        """.format(table=self._table)
        
        keys = list(set((rec.metrocontador_id.id, rec.fecha) for rec in self))
        self.env.cr.execute(query, (tuple(keys),))
        
        totals = {}
        for metro_id, f, total in self.env.cr.fetchall():
            totals[(metro_id, f)] = total
            
        for record in self:
            if record.tipo_medidor == 'prepago':
                record.consumo_diario_acumulado = 0.0
            else:
                key = (record.metrocontador_id.id, record.fecha)
                record.consumo_diario_acumulado = totals.get(key, 0.0)

    @api.depends('metrocontador_id', 'fecha')
    def _compute_plan_diario_proporcional(self):
        """Calcular el plan diario completo - NO aplica para PREPAGO"""
        for record in self:
            if record.tipo_medidor == 'prepago':
                record.plan_diario_proporcional = 0.0
                continue
            
            plan = self.env['meter.reading.plan.energetico'].search([
                ('metrocontador_id', '=', record.metrocontador_id.id),
                ('state', '=', 'active'),
                ('fecha_inicio', '<=', record.fecha),
                ('fecha_fin', '>=', record.fecha)
            ], limit=1)
            
            if plan:
                record.plan_diario_proporcional = plan.get_consumo_diario_fecha(record.fecha)
            else:
                record.plan_diario_proporcional = 0.0
    
    @api.depends('consumo_diario_acumulado', 'plan_diario_proporcional')
    def _compute_excede_plan(self):
        """Verificar si el consumo diario acumulado excede el plan - NO aplica para PREPAGO"""
        for record in self:
            if record.tipo_medidor == 'prepago':
                record.excede_plan = False
                continue
            
            if record.plan_diario_proporcional > 0:
                record.excede_plan = record.consumo_diario_acumulado > record.plan_diario_proporcional
            else:
                record.excede_plan = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records.filtered('excede_plan'):
            if record.tipo_medidor != 'prepago':
                record._send_alert_exceso_consumo()
        return records
    
    def write(self, vals):
        result = super().write(vals)
        for record in self.filtered('excede_plan'):
            if record.tipo_medidor != 'prepago':
                # Re-evaluar si la alerta debe ser enviada
                if 'consumo_diario_acumulado' in vals or 'plan_diario_proporcional' in vals:
                     record._send_alert_exceso_consumo()
        return result
    
    def _send_alert_exceso_consumo(self):
        self.ensure_one()
        selection_dict = dict(self._fields['hora']._description_selection(self.env))
        franja_actual = selection_dict.get(self.hora, f'Franja {self.hora}')
        
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            activity_type = self.env['mail.activity.type'].search([('name', 'ilike', 'todo')], limit=1)
        
        if activity_type and self.responsable_id:
            self.activity_schedule(
                activity_type_id=activity_type.id,
                user_id=self.responsable_id.id,
                summary=f'Exceso de consumo diario - {self.metrocontador_id.name}',
                note=f'El metrocontador {self.metrocontador_id.name} ha excedido el plan energético diario:\n\n'
                     f'Fecha: {self.fecha}\n'
                     f'Franja actual: {franja_actual}\n'
                     f'Consumo diario acumulado: {self.consumo_diario_acumulado:.2f} kWh\n'
                     f'Plan diario: {self.plan_diario_proporcional:.2f} kWh\n'
                     f'Exceso: {self.consumo_diario_acumulado - self.plan_diario_proporcional:.2f} kWh\n\n'
                     f'¡Tome medidas inmediatas para controlar el consumo!'
            )
        
        self.message_post(
            body=f'<p><strong>⚠️ ALERTA: Exceso de consumo diario detectado</strong></p>'
                 f'<ul>'
                 f'<li>Consumo diario acumulado: {self.consumo_diario_acumulado:.2f} kWh</li>'
                 f'<li>Plan diario: {self.plan_diario_proporcional:.2f} kWh</li>'
                 f'<li>Exceso: {self.consumo_diario_acumulado - self.plan_diario_proporcional:.2f} kWh</li>'
                 f'<li>Franja actual: {franja_actual}</li>'
                 f'</ul>'
                 f'<p><strong>¡Tome medidas inmediatas para controlar el consumo!</strong></p>',
            message_type='notification',
            subtype_xmlid='mail.mt_comment'
        )
    
    @api.constrains('metrocontador_id', 'fecha', 'hora', 'lectura_kwh', 'consumo_mes')
    def _check_lectura_ascendente(self):
        """Validar que las lecturas sean siempre ascendentes - NO aplica para PREPAGO."""
        for record in self:
            if record.tipo_medidor == 'prepago':
                continue 
            
            # Re-calcula el consumo parcial para la validación
            record._compute_consumo_parcial()
            if record.consumo_parcial < 0:
                raise ValidationError(
                    _('El consumo parcial no puede ser negativo. La lectura actual (%.2f) debe ser mayor o igual a la anterior.') % record.lectura_kwh
                )

    @api.constrains('metrocontador_id', 'fecha', 'hora')
    def _check_lectura_unica(self):
        """Evitar lecturas duplicadas - Adaptado para PREPAGO"""
        for record in self:
            if record.tipo_medidor == 'prepago':
               
                continue
            else:
                # Para normal/inteligente: validar unicidad por fecha+hora
                domain = [
                    ('id', '!=', record.id),
                    ('metrocontador_id', '=', record.metrocontador_id.id),
                    ('fecha', '=', record.fecha),
                    ('hora', '=', record.hora),
                ]
                if self.search_count(domain) > 0:
                    raise ValidationError(
                        _('Ya existe una lectura para el metrocontador %s en la fecha %s y franja %s.') %
                        (record.metrocontador_id.name, record.fecha, record.hora)
                    )

    @api.constrains('metrocontador_id', 'hora')
    def _check_hora_tipo_medidor(self):
        """Validar que la franja horaria corresponda al tipo de medidor."""
        for record in self:
            if record.metrocontador_id and record.tipo_medidor != 'prepago':
                tipo = record.metrocontador_id.tipo_medidor
                if tipo == 'inteligente':
                    if record.hora not in ['madrugada', 'dia', 'pico', 'reactivo']:
                        raise ValidationError(
                            _('Los medidores inteligentes solo admiten las franjas: Madrugada, Día, Pico y Reactivo.')
                        )
                else: # normal
                    if record.hora not in ['madrugada', 'dia', 'pico']:
                        raise ValidationError(
                             _('Los medidores normales solo admiten las franjas: Madrugada, Día y Pico.')
                        )

    @api.constrains('lectura_kwh', 'consumo_mes', 'tipo_medidor')
    def _check_lectura_positiva(self):
        """Validar valores positivos según tipo de medidor"""
        for record in self:
            if record.tipo_medidor == 'prepago':
                # Para prepago: validar consumo_mes
                if record.consumo_mes and record.consumo_mes < 0:
                    raise ValidationError(_('El consumo del mes no puede ser negativo.'))
            else:
                # Para normal/inteligente: validar lectura_kwh
                if record.lectura_kwh and record.lectura_kwh < 0:
                    raise ValidationError(_('La lectura no puede ser negativa.'))
    
    @api.constrains('metrocontador_id', 'hora', 'lectura_kwh', 'consumo_mes')
    def _check_campos_requeridos_tipo_medidor(self):
        """Validar campos requeridos según tipo de medidor"""
        for record in self:
            if record.tipo_medidor == 'prepago':
                # Para prepago: solo requiere consumo_mes
                if not record.consumo_mes or record.consumo_mes <= 0:
                    raise ValidationError(
                        _('Para metrocontadores prepago, debe ingresar el Consumo del Mes (mayor a cero).')
                    )
            else:
                # Para normal/inteligente: requiere hora y lectura_kwh
                if not record.hora:
                    raise ValidationError(
                        _('Para metrocontadores normales e inteligentes, debe seleccionar una Franja Horaria.')
                    )
                if not record.lectura_kwh or record.lectura_kwh < 0:
                    raise ValidationError(
                        _('Para metrocontadores normales e inteligentes, debe ingresar la Lectura (kWh).')
                    )