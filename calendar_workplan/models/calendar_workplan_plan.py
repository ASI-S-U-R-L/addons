# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, Command, SUPERUSER_ID
from odoo.fields import Date
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, date, time, timedelta
from dateutil.relativedelta import relativedelta
import calendar
import pytz
from pytz import timezone, utc


import logging

_logger = logging.getLogger(__name__)


class CalendarWorkplanPlan(models.Model):
    _name = 'calendar_workplan.plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Work Plan'
    _parent_store = True
    _order = 'plan_sequence'


    def duplicate_plan_next_year(self):
        """
        Duplica el plan actual al siguiente año en estado borrador,
        copiando solo los eventos principales recurrentes (no las ocurrencias),
        con fecha de inicio +1 año.
        """
        self.ensure_one()

        next_year = int(self.plan_year) + 1
        new_plan = self.create({
            'scope': self.scope,
            'parent_id': self.parent_id.id if self.parent_id else False,
            'plan_year': f"{next_year:04d}",
            'plan_month': self.plan_month,
            'date_start': self.date_start.replace(year=next_year),
            'date_end': self.date_end.replace(year=next_year),
            'state': 'draft',
            'presented_by_partner_id': self.presented_by_partner_id.id,
            'approved_by_partner_id': self.approved_by_partner_id.id,
            'plan_tz': self.plan_tz,
        })

        Event = self.env['calendar.event']
        for event in self.meeting_ids:
            # Solo duplicar eventos principales (los que tienen recurrence_id definido)
            if event.recurrence_id:
                new_start = event.start + timedelta(days=365)
                new_stop = event.stop + timedelta(days=365) if event.stop else None

                vals = {
                    'name': f"{event.name} ({next_year})",
                    'start': new_start,
                    'stop': new_stop,
                    'allday': event.allday,
                    'partner_ids': [(6, 0, event.partner_ids.ids)],
                    'workplan_id': new_plan.id,
                    'section_id': event.section_id.id,
                    'priority': event.priority,
                    'recurrence_id': event.recurrence_id.id,  # mantiene la regla de recurrencia
                }
                Event.create(vals)

        return new_plan


    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Establecer presented_by_partner_id para planes individuales
        if self._context.get('default_scope') == 'individual':
            res['presented_by_partner_id'] = self.env.user.partner_id.id
        
        # Si hay un padre definido y es plan individual
        parent_id = self._context.get('default_parent_id') or res.get('parent_id')
        if parent_id and self._context.get('default_scope') == 'individual':
            parent_plan = self.env['calendar_workplan.plan'].browse(parent_id)
            if parent_plan.exists():
                res['date_start'] = parent_plan.date_start
                res['date_end'] = parent_plan.date_end
                res['plan_month'] = parent_plan.plan_month
                res['plan_year'] = parent_plan.plan_year
        
        return res

    @api.model
    def _get_years(self):
        current_year = fields.Datetime.today().year
        return [('%04d' % year_number, '%02d' % year_number) for year_number in range(current_year, current_year+3)]

    @api.model
    def _get_months(self):
        # Usar nombres en inglés como clave de traducción
        months = [
            ('01', _('January')),
            ('02', _('February')),
            ('03', _('March')),
            ('04', _('April')),
            ('05', _('May')),
            ('06', _('June')),
            ('07', _('July')),
            ('08', _('August')),
            ('09', _('September')),
            ('10', _('October')),
            ('11', _('November')),
            ('12', _('December')),
        ]
        return months
        
    @api.model
    def _get_default_presented_by(self):
        """Obtiene el presentador según el tipo de plan"""
        if self._context.get('scope') == 'individual' and self._context.get('employee_id'):
            employee = self.env['hr.employee'].browse(self._context['employee_id'])
            return employee.user_id.partner_id.id if employee.user_id else None
        
        # Para planes mensuales/anuales
        company = self.env.company
        if company.workplan_planner_partner_id:
            return company.workplan_planner_partner_id.id
        return self.env.user.partner_id.id

    @api.model
    def _get_default_approved_by(self):
        """Obtiene el aprobador según el tipo de plan"""
        if self._context.get('scope') == 'individual' and self._context.get('employee_id'):
            employee = self.env['hr.employee'].browse(self._context['employee_id'])
            if employee.parent_id and employee.parent_id.user_id:
                return employee.parent_id.user_id.partner_id.id
            return self.env.ref('base.partner_admin').id  # Fallback
        
        # Para planes mensuales/anuales
        company = self.env.company
        if company.workplan_approver_partner_id:
            return company.workplan_approver_partner_id.id
        
        # Fallback para aprobador de planes generales
        return self.env.ref('base.partner_admin').id

       
    name = fields.Char(string="Plan name", compute="_compute_name")
    display_name = fields.Char(string="Nombre completo", compute="_compute_display_name", store=True)

   
    date_start = fields.Date("Start Date", required=True, tracking=True)
    date_end = fields.Date("End Date", required=True, tracking=True)
    utc_start = fields.Datetime(compute="_compute_utc_period_limits", store=True)
    utc_end = fields.Datetime(compute="_compute_utc_period_limits", store=True)
    scope = fields.Selection([
        ('annual', 'Annual'),
        ('monthly', 'Mensual')        ,
        ('individual', 'Individual')], string="Scope", default='annual', required=True)
    plan_year = fields.Selection(_get_years, string="Year", default=lambda self: '%04d' % fields.Datetime.today().year)
    plan_month = fields.Selection(_get_months, string="Month")
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('posted', 'Posted'),
            ('approved', 'Approved'),
            ('closed', 'Closed'),
        ],
        string='Status',
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
        default='draft',
    )
    company_id = fields.Many2one('res.company', string='Company', index=True, default=lambda self: self.env.company)
    parent_id = fields.Many2one('calendar_workplan.plan', string='Parent Plan', index=True, domain="[('id', '!=', id), ('company_id', 'in', [False, company_id])]", ondelete="restrict")
    child_ids = fields.One2many('calendar_workplan.plan', 'parent_id', string='Child Plans')
    parent_path = fields.Char(index=True, unaccent=False)
    active = fields.Boolean(default=True, tracking=True)
    plan_sequence = fields.Char(compute='_compute_name', store=True)
    presented_by_partner_id = fields.Many2one(
        "res.partner", 
        string="Presented by", 
        required=True, 
        default=_get_default_presented_by,
        domain="[('company_id', 'in', [False, company_id])]"
    )
    approved_by_partner_id = fields.Many2one(
        "res.partner", 
        string="Approved by", 
        required=True, 
        default=_get_default_approved_by,
        domain="[('company_id', 'in', [False, company_id])]"
    ) 
    goal_ids = fields.Many2many('gamification.challenge', relation='calendar_workplan_plan_goals', column1='plan_id', column2='goal_id', string="Plan's Goals", domain=[('challenge_category', '=', 'hr')])
    meeting_ids = fields.One2many('calendar.event', 'workplan_id', string="Meetings")
    inherited_meeting_ids = fields.Many2many('calendar.event', string="Inherited Meetings", compute="_compute_inherited_meeting_ids", recursive=True)

    plan_tz = fields.Selection(
        _tz_get, 
        string='Timezone', 
        default=lambda self: self.env.user.tz or 'UTC',  # Fallback a UTC
        required=True
    )

    is_my_plan = fields.Boolean(
        string="Is My Plan",
        compute="_compute_is_my_plan",
        search="_search_is_my_plan",
    )
    requires_my_approval = fields.Boolean(
        string="My approval required",
        compute="_compute_requires_my_approval",
        search="_search_requires_my_approval",
    )
    
    def _compute_is_my_plan(self):
        my_partner_id = self.env.user.partner_id.id
        for record in self:
            record.is_my_plan = record.presented_by_partner_id.id == my_partner_id
    
    def _search_is_my_plan(self, operator, value):
        my_partner_id = self.env.user.partner_id.id
        return [('presented_by_partner_id', '=', my_partner_id)]

    
    def _compute_requires_my_approval(self):
        my_partner_id = self.env.user.partner_id.id
        for record in self:
            record.requires_my_approval = record.approved_by_partner_id.id == my_partner_id
    
    def _search_requires_my_approval(self, operator, value):
        my_partner_id = self.env.user.partner_id.id
        return [('approved_by_partner_id', '=', my_partner_id)]        
        
    _sql_constraints = [
        ('check_valid_tz', 
         "CHECK (plan_tz IN %s)" % str(tuple(pytz.all_timezones)),  # Lista de todas las zonas válidas
         "La zona horaria seleccionada no es válida")
]


    @api.constrains('scope', 'plan_year', 'plan_month', 'presented_by_partner_id', 'parent_id')
    def _check_unique_name(self):
        for plan in self:
            # Sólo aplicamos cuando ya tenemos fechas y scope definidos
            # (puedes ajustar la lista de campos si tienes otras fuentes de name)
            # Buscamos todos los planes bajo el mismo padre
            siblings = self.search([('parent_id', '=', plan.parent_id.id or False)])
            # Recorremos y comparamos el nombre generado
            for sib in siblings:
                if sib.id != plan.id and sib.name == plan.name:
                    raise ValidationError(
                        _("⚠️ Ya existe un plan con el mismo nombre bajo este padre: %s") 
                        % plan.name
                    )

    @api.depends("scope", "plan_year", "plan_month", "company_id", "presented_by_partner_id")
    def _compute_name(self):
        for plan in self:
            if plan.scope == "annual":
                # Formato: aaaa-NombreCompañia
                plan.name = f"{plan.plan_year}-{plan.company_id.name}"
            elif plan.scope == "monthly":
                # Formato: aaaa/mm-NombreCompañia
                plan.name = f"{plan.plan_year}/{plan.plan_month}-{plan.company_id.name}"
            elif plan.scope == "individual":
                # Formato: aaaa/mm-NombreCompañia-Usuario
                plan.name = (
                    f"{plan.plan_year}/{plan.plan_month}-"
                    f"{plan.presented_by_partner_id.name}"
                )
            else:
                # Fallback por si hay nuevos alcances no contemplados
                plan.name = plan_year
 
    @api.depends("scope", "plan_year", "plan_month", "company_id", "presented_by_partner_id")
    def _compute_display_name(self):
        for plan in self:
            if plan.scope == "annual":
                plan.display_name = f"PA-{plan.name}"
            elif plan.scope == "monthly":
               plan.display_name = f"PM-{plan.name}"
            elif plan.scope == "individual":
               plan.display_name = f"PI-{plan.name}"
            else:
                # Fallback por si hay nuevos alcances no contemplados
                plan.display_name = plan.name
   

    def _is_event_in_plan_date_range(self, event, plan_tz):
        """ Verifica si el evento está dentro del rango de fechas del plan, considerando la zona horaria. """
        event_start = event.start.astimezone(plan_tz)  # Convertir a la zona horaria del plan
        return (self.date_start <= event_start.date() <= self.date_end) 

    @api.depends('parent_id', 'meeting_ids')
    def _compute_inherited_meeting_ids(self):
        for plan in self:
            plan_tz = timezone(plan.plan_tz)  # Zona horaria del plan
            partner_id = plan.presented_by_partner_id

            # Inicializar con los eventos del plan actual
            if plan.scope == 'individual':
                # Si el plan es individual, filtrar por partner_id
                all_meetings = plan.meeting_ids.filtered(
                    lambda e: partner_id in e.partner_ids
                    and self._is_event_in_plan_date_range(e, plan_tz)
                )
            else:
                # Si el plan no es individual, no filtrar por partner_id
                all_meetings = plan.meeting_ids.filtered(
                    lambda e: self._is_event_in_plan_date_range(e, plan_tz)
                )

            # Recorrer la jerarquía hacia arriba (plan padre, abuelo, etc.)
            parent_plan = plan.parent_id
            while parent_plan:
                if plan.scope == 'individual':
                    # Si el plan es individual, filtrar por partner_id en los planes padres
                    parent_meetings = parent_plan.meeting_ids.filtered(
                        lambda e: partner_id in e.partner_ids
                        and self._is_event_in_plan_date_range(e, plan_tz)
                    )
                else:
                    # Si el plan no es individual, no filtrar por partner_id en los planes padres
                    parent_meetings = parent_plan.meeting_ids.filtered(
                        lambda e: self._is_event_in_plan_date_range(e, plan_tz)
                    )
                all_meetings |= parent_meetings
                parent_plan = parent_plan.parent_id

            # Asignar todos los eventos encontrados
            plan.inherited_meeting_ids = all_meetings

    @api.model
    def _tz_get(self):
        return [(tz, tz) for tz in sorted(pytz.all_timezones, key=lambda tz: tz if not tz.startswith('Etc/') else '_')]




    def migrate(cr, version):
        env = api.Environment(cr, SUPERUSER_ID, {})
        plans = env['calendar_workplan.plan'].search([])
        for plan in plans:
            if not plan.plan_tz or isinstance(plan.plan_tz, bool):
                plan.plan_tz = plan.env.user.tz or 'America/Havana'



    @api.depends('date_start', 'date_end', 'plan_tz')
    def _compute_utc_period_limits(self):
        for record in self:
            record.utc_start = record._from_date_to_orm_datetime(record.date_start)
            record.utc_end = record._from_date_to_orm_datetime(record.date_end, min=False)

    @api.onchange('scope')
    def onchange_periodicity(self):
        if self.scope == 'annual':
            self.plan_month = None
        elif self.scope == 'monthly':
            self.plan_month = '%02d' % fields.Datetime.today().month

    @api.onchange('parent_id')
    def onchange_parent_id(self):
        if self.parent_id:
            self.plan_year = self.parent_id.plan_year
        # Solo para planes individuales
            if self.scope == 'individual':
                self.date_start = self.parent_id.date_start
                self.date_end = self.parent_id.date_end


    
    @api.onchange('scope', 'plan_year', 'plan_month')
    def onchange_period_related_fields(self):
        if self.plan_year:
            if self.scope == 'annual':
                self.date_start = fields.Date.from_string('%s-01-01' % self.plan_year)
                self.date_end = fields.Date.from_string('%s-12-31' % self.plan_year)
            else:
                if self.plan_month:
                    self.date_start = fields.Date.from_string('%s-%s-01' % (self.plan_year, self.plan_month))
                    month_lastday_number = calendar.monthrange(int(self.plan_year), int(self.plan_month))[-1]
                    self.date_end = fields.Date.from_string('%s-%s-%d' % (self.plan_year, self.plan_month, month_lastday_number))

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive work plans.'))

    @api.ondelete(at_uninstall=False)
    def _unlink_except_plan_posted(self):
        if any(plan.state == 'posted' for plan in self):
            raise UserError(_("Can't delete a posted plan!"))

    def child_ids_view(self):
        self.ensure_one()
        domain = [
            ('parent_id', '=', self.id)]
        def_scope = 'individual'    
        if self.scope == 'annual': 
          def_scope= 'monthly'             
        return {
            'name': _('Child plans'),
            'domain': domain,
            'res_model': self._name,
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'context': {'default_scope': def_scope, 'default_parent_id': self.id, 'default_plan_tz': self.plan_tz, 'initial_date': self.utc_start }
        }

    def meeting_ids_view(self):
        self.ensure_one()
        domain = [
                '|',
            ('workplan_id', '=', self.id),
            ('id', 'in', self.inherited_meeting_ids.mapped('id')),
            ]
        view_xml_id = "calendar_workplan.view_calendar_year_mode"
        if self.scope != 'annual':
            view_xml_id = "calendar_workplan.view_calendar_month_mode"
        action = self.env["ir.actions.actions"]._for_xml_id("calendar_workplan.calendar_event_action_workplan_meetings")
        action.update(domain=domain, views=[[self.env.ref(view_xml_id).id, 'calendar'], [False, 'tree'], [False, 'form']])
        action['context'] = {
            'default_workplan_id': self.id,
            'initial_date': self.utc_start,
        }
        return action

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            parent = None

            # Heredar datos desde el padre si existe
            if vals.get('parent_id'):
                parent = self.browse(vals['parent_id'])
                today = fields.Date.today()
                if parent.scope == 'monthly':
                    vals.update({
                        'plan_year': parent.plan_year,                        
                    })
                elif vals.get('scope') == 'individual':
                    vals.setdefault('plan_year', parent.plan_year)
                    vals.setdefault('plan_month', parent.plan_month)
                    vals.setdefault('date_start', parent.date_start)
                    vals.setdefault('date_end', parent.date_end)
                    vals.update({
                        'plan_month': parent.plan_month, }) 
        # Crear registros
        plans = super().create(vals_list)

        # Asociar secciones para planes anuales
        sections = self.env['calendar_workplan.section'].search([])
        for section in sections:
            section.update({
                'workplan_ids': [
                    Command.link(plan.id) 
                    for plan in plans.filtered(lambda it: it.scope == 'annual')
                ]
            })

        return plans
        
    @api.model
    def _create_annual_plan(self, year):
        """Crea un plan anual si no existe"""
        existing_annual = self.search([
            ('scope', '=', 'annual'),
            ('plan_year', '=', '%04d' % year)
        ], limit=1)
        
        if existing_annual:
            return existing_annual
            
        # Obtener presentador y aprobador para plan anual
        presented_by = self._get_default_presented_by()
        approved_by = self._get_default_approved_by()
        
        if not presented_by or not approved_by:
            raise UserError(_("Cannot create annual workplan: missing planner or approver. Please configure default planners in company settings."))
        
        annual_plan = self.create({
            'scope': 'annual',
            'plan_year': '%04d' % year,
            'date_start': date(year, 1, 1),
            'date_end': date(year, 12, 31),
            'state': 'draft',
            'name': f'Annual Work Plan - {year}',
            'presented_by_partner_id': presented_by,
            'approved_by_partner_id': approved_by,
            'plan_tz': self.env.user.tz or 'America/Havana'
        })
        
        return annual_plan

    
    @api.model
    def _create_monthly_plan(self, year=None, month=None):
        """Crea un plan mensual para el mes y año especificados"""
        # 1. Determinar mes/año objetivo
        today = fields.Date.today()
        if not year or not month:
            # Calcular próximo mes si no se especifican
            next_month = today.month + 1 if today.month < 12 else 1
            next_year = today.year + 1 if today.month == 12 else today.year
        else:
            # Validar parámetros recibidos
            if not (1 <= month <= 12):
                raise UserError(_("Mes inválido. Debe estar entre 1 y 12"))
            next_month = month
            next_year = year

       
        annual_plan = self._create_annual_plan(next_year)
        
        existing_monthly = self.search([
            ('scope', '=', 'monthly'),
            ('plan_year', '=', f"{next_year:04d}"),
            ('plan_month', '=', f"{next_month:02d}"),
            ('parent_id', '=', annual_plan.id)
        ], limit=1)
        
        if existing_monthly:
            return existing_monthly

        try:
            date_start = date(next_year, next_month, 1)
            date_end = date_start + relativedelta(months=1, days=-1)
        except ValueError as e:
            raise UserError(_("Configuración de fecha inválida: %s") % e)
        
        return self.create({
            'scope': 'monthly',
            'parent_id': annual_plan.id,
            'plan_year': f"{next_year:04d}",
            'plan_month': f"{next_month:02d}",
            'date_start': date_start,
            'date_end': date_end,
            'state': 'draft',
            'name': f'Monthly Work Plan - {next_month:02d}/{next_year:04d}',
            'presented_by_partner_id': self._get_default_presented_by(),
            'approved_by_partner_id': self._get_default_approved_by(),
            'plan_tz': self.env.user.tz or 'UTC'
        })
    
    @api.model
    def _create_individual_plans(self, monthly_plan):
        """Crea planes individuales para cada empleado activo"""
        Employee = self.env['hr.employee']
        employees = Employee.search([('active', '=', True)])
        
        for employee in employees:
            # Verificar si ya existe un plan individual
            existing_plan = self.search([
                ('scope', '=', 'individual'),
                ('plan_year', '=', monthly_plan.plan_year),
                ('plan_month', '=', monthly_plan.plan_month),
                ('presented_by_partner_id', '=', employee.user_id.partner_id.id if employee.user_id else False)
            ], limit=1)
            
            if existing_plan:
                continue
                
            # Obtener presentador (empleado) y aprobador (jefe) para plan individual
            presented_by = employee.user_id.partner_id.id if employee.user_id else None
            approved_by = employee.parent_id.user_id.partner_id.id if employee.parent_id and employee.parent_id.user_id else None
            
            if not presented_by:
                _logger.warning(f"Skipping workplan for employee {employee.name} (no user assigned)")
                continue
                
            if not approved_by:
                approved_by = self.env.ref('base.partner_admin').id  # Fallback
                _logger.warning(f"Using admin as approver for employee {employee.name} (no manager assigned)")
            
            # Crear plan individual
            self.with_context(
                scope='individual',
                employee_id=employee.id
            ).create({
                'scope': 'individual',
                'parent_id': monthly_plan.id,
                'plan_year': monthly_plan.plan_year,
                'plan_month': monthly_plan.plan_month,
                'date_start': monthly_plan.date_start,
                'date_end': monthly_plan.date_end,
                'plan_tz':  employee.user_id.tz or  'America/Havana',
                'state': 'draft',
                'presented_by_partner_id': presented_by,
                'approved_by_partner_id': approved_by,
                'name': 'Individual Work Plan - %s - %s/%s' % (
                    employee.name, 
                    monthly_plan.plan_month, 
                    monthly_plan.plan_year
                )
            })    
            
    @api.model
    def generate_next_month_plans(self, year=None, month=None):
        """Método principal con parámetros personalizables"""
        monthly_plan = self._create_monthly_plan(year=year, month=month)
        self._create_individual_plans(monthly_plan)
        return True
    
    def _from_date_to_orm_datetime(self, value, min=True):
        _logger.info("=== INICIO CONVERSIÓN ===")
        _logger.info("Fecha recibida (value): %s", value)
        
        if not value:
            _logger.warning("Valor de fecha es False/None")
            return False
            
        try:
            # 1. Obtener zona horaria
            tz_name = self.plan_tz or self.env.user.tz or 'UTC'
            _logger.info("Zona horaria detectada: %s", tz_name)
            
            # 2. Validar zona
            try:
                user_tz = timezone(tz_name)
                _logger.info("Zona horaria válida: %s", user_tz)
            except Exception as e:
                _logger.error("¡ERROR DE ZONA HORARIA! %s. Usando UTC como fallback.", str(e))
                user_tz = timezone('America/Havana')
    
            # 3. Crear datetime naive local
            naive_date = datetime.combine(value, time.min if min else time.max)
            _logger.info("Naive date (local): %s", naive_date)
            
            # 4. Localizar y convertir a UTC
            localized = user_tz.localize(naive_date, is_dst=None)
            _logger.info("Localizado: %s", localized)
            
            utc_time = localized.astimezone(utc)
            _logger.info("Convertido a UTC (aware): %s", utc_time)
            
            # 5. Hacerlo naive
            naive_utc = utc_time.replace(tzinfo=None)
            _logger.info("Naive UTC final: %s", naive_utc)
            
            # 6. Validar tipo de retorno
            result = fields.Datetime.to_datetime(naive_utc)
            _logger.info("Retornando: %s (tipo: %s)", result, type(result))
            
            return result
            
        except Exception as e:
            _logger.exception("¡EXCEPCIÓN CRÍTICA EN CONVERSIÓN!")
            raise UserError(_("Error fatal al convertir fechas: %s") % str(e))
        
        
    def get_partner_meetings(self):
        """ Filtra los eventos de inherited_meeting_ids donde:
            1. El presented_by_partner_id es asistente.
            2. El evento está dentro del rango de fechas del plan, considerando la zona horaria.
        """
        self.ensure_one()
        plan_tz = timezone(self.plan_tz)  # Zona horaria del plan

        return self.inherited_meeting_ids.filtered(
            lambda e: self.presented_by_partner_id in e.partner_ids
            and self._is_event_in_plan_date_range(e, plan_tz)
        )


    def get_main_activities(self):
        """ Devuelve los eventos de calendario con prioridad alta para el partner que presenta el plan."""
        self.ensure_one()
        partner_meetings = self.get_partner_meetings()
        main_activities = partner_meetings.filtered(lambda e: e.priority == '1').mapped('name')
        return list(set(main_activities))  # Esto retorna una lista de strings    
       
       
       
    # Método para obtener la fecha de inicio de la semana actual
    def get_current_week_start(self):
        self.ensure_one()
        today = fields.Date.today()
        start_of_week = today - timedelta(days=today.weekday())  # Lunes de la semana actual
        return start_of_week

    # Método para obtener las semanas del plan
    def get_weeks(self):
        """
        Devuelve una lista de semanas para el mes actual.
        Cada semana es una lista de 7 días (de lunes a domingo).
        Los días que no pertenecen al mes actual se marcan como None.
        """
        weeks = []
        current_date = self.date_start  # Fecha de inicio del período
        first_day_of_month = date(current_date.year, current_date.month, 1)  # Primer día del mes
        last_day_of_month = date(current_date.year, current_date.month + 1, 1) - timedelta(days=1)  # Último día del mes

        # Encontrar el lunes de la primera semana que contiene el día 1
        start_of_week = first_day_of_month - timedelta(days=first_day_of_month.weekday())

        # Iterar hasta cubrir todo el mes
        while start_of_week <= last_day_of_month:
            week = []
            for i in range(7):
                day = start_of_week + timedelta(days=i)
                if day.month == first_day_of_month.month:
                    week.append(day)  # Día pertenece al mes actual
                else:
                    week.append(None)  # Día no pertenece al mes actual
            weeks.append(week)
            start_of_week += timedelta(days=7)  # Mover a la siguiente semana

        return weeks

    # Método para obtener eventos de un día específico, convirtiendo las fechas a la zona horaria del plan
    def get_events_by_day(self, day):
        self.ensure_one()
        # Obtener la zona horaria del plan
        plan_tz = timezone(self.plan_tz or 'UTC')

        # Definir los límites del día en la zona horaria UTC
        day_start = fields.Datetime.to_datetime(day).replace(hour=0, minute=0, second=0)
        day_end = day_start + timedelta(days=1)

        # Obtener eventos usando get_partner_meetings()
        events = self.get_partner_meetings().filtered(lambda e: day_start <= e.start < day_end)

        # Crear una lista de eventos con las fechas convertidas a la zona horaria del plan
        event_list = [{
            'name': event.name,
            'start': self.convert_utc_to_tz(event.start, plan_tz),
            'stop': self.convert_utc_to_tz(event.stop, plan_tz),
            'allday': event.allday,
            'priority': event.priority,
        } for event in events]
        
        # Ordenar la lista de eventos por fecha y hora de inicio
        event_list = sorted(event_list, key=lambda e: e['start'])

        return event_list
        

    def get_approved_absences(self):
        """
        Devuelve las ausencias aprobadas del empleado asociado al plan.
        Formato de salida: Lista de diccionarios con el tipo de ausencia y las fechas como date objects.
        """
        self.ensure_one()
        employee = self.env['hr.employee'].search([
            ('user_id.partner_id', '=', self.presented_by_partner_id.id)
        ], limit=1)

        if not employee:
            return []

        absences = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', self.date_end),
            ('date_to', '>=', self.date_start),
        ])

        # Convertir datetime a date y formatear
        formatted_absences = []
        for absence in absences:
            date_from = absence.date_from.date()  # Extraer date desde datetime
            date_to = absence.date_to.date()
            formatted_absences.append({
                'name': absence.holiday_status_id.name,
                'date_from': date_from,
                'date_to': date_to,
            })

        return formatted_absences

    def get_absences_for_day(self, day):
        """Devuelve los nombres de ausencias para un día específico"""
        self.ensure_one()
        return [
            absence['name'] for absence in self.get_approved_absences()
            if day and absence['date_from'] <= day <= absence['date_to']
        ]



    # Método para convertir una fecha UTC a una zona horaria específica
    def convert_utc_to_tz(self, utc_datetime, target_tz):
        if not utc_datetime:
            return utc_datetime
        if isinstance(utc_datetime, str):
            utc_dt = fields.Datetime.from_string(utc_datetime).replace(tzinfo=utc)
        else:
            utc_dt = utc_datetime.replace(tzinfo=utc)
        return utc_dt.astimezone(target_tz).replace(tzinfo=None)

    # Metodos para el plan mensual
    def get_sorted_meetings(self):
        self.ensure_one()
        plan_tz = timezone(self.plan_tz or 'UTC')  # Obtener la zona horaria del plan
        
        # Obtener y ordenar los eventos por fecha de inicio
        sorted_meetings = self.inherited_meeting_ids.sorted(key=lambda m: m.start)
        
        # Convertir las fechas a la zona horaria del plan
        meetings_with_tz = []
        for meeting in sorted_meetings:
            meetings_with_tz.append({
                'id': meeting.id,
                'name': meeting.name,
                'start': self.convert_utc_to_tz(meeting.start, plan_tz),
                'stop': self.convert_utc_to_tz(meeting.stop, plan_tz),
                'duration': meeting.duration,
                'priority': meeting.priority,
                'allday': meeting.allday,
                'location': meeting.location,
                'channel_ids': meeting.channel_ids,
                'partner_ids': meeting.partner_ids,                
                # Agrega otros campos que necesites
            })
        
        return meetings_with_tz
    
    def get_main_month_activities(self):
        # Filtrar eventos de prioridad alta y obtener descripciones únicas
        main_activities = self.inherited_meeting_ids.filtered(
            lambda m: m.priority == '1'  # Prioridad alta (ajusta según tu configuración)
        ).mapped('name')
        # Eliminar duplicados
        return list(set(main_activities))
        

    def get_sections_with_events(self):
        sections = []
        Section = self.env['calendar_workplan.section']
        for section in Section.search([]):
            events = self.meeting_ids.filtered(
                lambda e: e.section_id == section
            )
            if events:
                sections.append({
                    'name': section.name,
                    'events': events
                })
        return sections

    # Metodos del plan anual
    def get_grouped_events_by_section(self):
        """Agrupa eventos únicos por sección con hora localizada"""
        self.ensure_one()
        sections = []
        
        # Obtener eventos únicos (sin duplicados por recurrencia)
        unique_events = self.meeting_ids.filtered(lambda e: not e.recurrence_id)
        recurring_masters = self.meeting_ids.filtered(lambda e: e.recurrence_id and e.recurrence_id.calendar_event_ids[0] == e)
        all_events = unique_events | recurring_masters
        
        # Agrupar por sección
        for section in self.env['calendar_workplan.section'].search([], order='name'):
            section_events = all_events.filtered(
                lambda e: e.section_id == section
            ).sorted(key=lambda e: e.start)  # Ordenar por hora
            
            if section_events:
                sections.append({
                    'name': section.name,
                    'events': section_events
                })
        
        return sections

    # Método para imprimir el informe "Plan Individual"
    def action_print_individual_plan(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'calendar_workplan.report_individual_plan',
            'report_type': 'qweb-pdf',
            'model': 'calendar_workplan.plan',
            'res_id': self.id,
            'context': {'active_ids': [self.id]},
        }
        
        
    def action_print_report(self):
        # Llamar al reporte directamente
        return self.env.ref('calendar_workplan.action_report_workplan').report_action(self)
        
    def action_post_plan(self):
        for plan in self:
            #  Verificar si el usuario es presentador o administrador
            is_presenter = plan.presented_by_partner_id == self.env.user.partner_id
            is_admin = self.env.user.has_group("calendar_workplan.calendar_workplan_group_manager")  # Grupo de administradores
            
            if not (is_presenter or is_admin):
                raise UserError("Solo el presentador o un administrador pueden publicar este plan.")
            
            if plan.state != 'draft':
                raise UserError("El plan debe estar en estado 'Borrador' para ser publicado.")
            
            plan.write({'state': 'posted'})
        return True
        
    
    def action_approve_plan(self):
        # Validar todos los registros seleccionados
        if any(plan.approved_by_partner_id != self.env.user.partner_id for plan in self):
            raise UserError("Solo el usuario aprobador puede aprobar estos planes.")
        if any(plan.state != 'posted' for plan in self):
            raise UserError("Todos los planes deben estar en estado 'Solicitado' para ser aprobados.")
        
        # Aplicar cambios masivamente
        self.write({'state': 'approved'})
        return True
    
    def action_decline_plan(self):
        if any(plan.approved_by_partner_id != self.env.user.partner_id for plan in self):
            raise UserError("Solo el usuario aprobador puede desaprobar estos planes.")
        if any(plan.state != 'posted' for plan in self):
            raise UserError("Todos los planes deben estar en estado 'Solicitado' para ser desaprobados.")
        
        self.write({'state': 'draft'})
        return True
    
    def action_close_plan(self):
        if any(plan.approved_by_partner_id != self.env.user.partner_id for plan in self):
            raise UserError("Solo el usuario aprobador puede cerrar estos planes.")
        if any(plan.state != 'posted' for plan in self):
            raise UserError("Todos los planes deben estar en estado 'Solicitado' para ser cerrados.")
        
        self.write({'state': 'closed'})
        return True 