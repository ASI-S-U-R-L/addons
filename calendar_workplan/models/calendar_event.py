import ast
from odoo import models, fields, api, Command
from odoo.tools import ustr
from dateutil.rrule import rrulestr
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
from datetime import datetime
import calendar  
import logging  
    
_logger = logging.getLogger(__name__)  

class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    workplan_id = fields.Many2one('calendar_workplan.plan', 'Plan')
    section_id = fields.Many2one('calendar_workplan.section', "Section", domain="[('workplan_ids', '=', workplan_id)]")
    workplan_scope = fields.Selection(related='workplan_id.scope')
    channel_ids = fields.Many2many('mail.channel', string="Canales")
    priority = fields.Selection([('0', 'Normal'), ('1', 'High')], default='0', string="Priority")
    attendees_filter_domain = fields.Char(string='Attendees filter', compute='_compute_attendees_filter_domain')
    
#***** Limitando la creacion de eventos fuera del año actual
    @api.constrains('start', 'stop', 'recurrency')
    def _check_dates_within_current_year(self):
        _logger.warning(">>> [CHECK] Entrando a _check_dates_within_current_year para IDs: %s", self.ids)

        current_year = datetime.now().year
        max_date = datetime(current_year, 12, 31)

        for event in self:
            _logger.warning(
                ">>> [CHECK] Evento ID=%s | start=%s | stop=%s | recurrency=%s",
                event.id, event.start, event.stop, event.recurrency
            )

            start_date = event.start.date() if event.start else None
            stop_date = event.stop.date() if event.stop else None

            if (start_date and start_date > max_date.date()) or (stop_date and stop_date > max_date.date()):
                _logger.error(
                    ">>> [ERROR] Evento fuera del año actual: start=%s stop=%s límite=%s",
                    start_date, stop_date, max_date.date()
                )
                raise ValidationError("❌ Las fechas del evento no pueden superar el 31/12/%s" % current_year)

            # Validación de recurrencia
            if hasattr(event, 'until') and event.recurrency and event.until:
                _logger.warning(">>> [CHECK] until=%s", event.until)
                if event.until > max_date.date():
                    _logger.error(
                        ">>> [ERROR] Recurrencia fuera del año actual: until=%s límite=%s",
                        event.until, max_date.date()
                    )
                    raise ValidationError("❌ La recurrencia no puede extenderse más allá del 31/12/%s" % current_year)

    def _get_recurrence_dates(self, base_event):
        dates = super()._get_recurrence_dates(base_event)

        if not base_event.start:
            return dates

        year = base_event.start.year
        limit_dt = datetime(year, 12, 31, 23, 59, 59)

        filtered = [dt for dt in dates if dt <= limit_dt]

        return filtered

        
    @api.model_create_multi
    def create(self, vals_list):
        current_year = datetime.now().year
        max_date = datetime(current_year, 12, 31).date()
        
        for vals in vals_list:
            if vals.get('recurrency') and vals.get('until_date') and vals['until_date'] > max_date:
                vals['until_date'] = max_date
                
        return super().create(vals_list)        
        
#*****   
    @api.depends('channel_ids')
    def _compute_attendees_filter_domain(self):
        for record in self:
            record.attendees_filter_domain = [('channel_ids', 'in', record.channel_ids.ids)]



    def _get_calendar_event_attendees_by_filter_domain(self):
        attendees_domain = ast.literal_eval(ustr(self.attendees_filter_domain))
        return self.env['res.partner'].search(attendees_domain) - self.partner_ids

    @api.onchange('attendees_filter_domain')
    def onchange_attendees_filter_domain(self):
        if self.attendees_filter_domain and self.attendees_filter_domain != "[]":
            self.partner_ids = [Command.link(attendee.id) for attendee in self._get_calendar_event_attendees_by_filter_domain()]

    def get_recurrent_days(self, year, month):  # Añade el parámetro year
        self.ensure_one()
        if not self.recurrence_id:
            return []
        
        try:
            # Obtener último día del mes
            _, last_day = calendar.monthrange(year, month)
            start_date = datetime(year, month, 1)
            end_date = datetime(year, month, last_day)
            
            rrule = self.recurrence_id._get_rrule()
            dates = list(rrule.between(start_date, end_date, inc=True))
            
            return list({d.day for d in dates if d.month == month})
        except Exception as e:
            _logger.error(f"Error calculando días recurrentes: {str(e)}")
            return []


    def get_sections_with_events(self):
        """Agrupa eventos por sección con ordenamiento"""
        sections = []
        Section = self.env['calendar_workplan.section']
        
        for section in Section.search([], order='name'):
            events = self.meeting_ids.filtered(
                lambda e: e.section_id == section
            ).sorted(key=lambda e: e.start)  # Ordenar por hora de inicio
            
            if events:
                sections.append({
                    'name': section.name,
                    'events': events
                })
        
        return sections

    def get_localized_time(self, plan_tz):
        """Devuelve la hora formateada en la zona horaria del plan"""
        self.ensure_one()
        try:
            tz = timezone(plan_tz or 'UTC')
            start = self.start.astimezone(tz).strftime('%H:%M')
            stop = self.stop.astimezone(tz).strftime('%H:%M')
            return f"{start} - {stop}"
        except Exception as e:
            _logger.error("Error converting time: %s", str(e))
            return self.display_time

    def get_sorted_recurrent_days(self, year, month):
        """Días recurrentes ordenados sin duplicados"""
        days = list(set(self.get_recurrent_days(year, month)))  # Elimina duplicados
        return sorted(days) if days else []    

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)

        for event in events:
            if event.recurrence_id and event.recurrence_id.base_event_id:
                base = event.recurrence_id.base_event_id
                year = base.start.year
                limit_date = date(year, 12, 31)

                # Convertimos start a date
                event_date = event.start.date()

                if event_date > limit_date:
                    raise ValidationError(
                        f"No se pueden generar eventos más allá del {limit_date} "
                        f"(evento generado: {event_date})."
                    )

        return events
