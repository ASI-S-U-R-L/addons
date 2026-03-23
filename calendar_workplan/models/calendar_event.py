# -*- coding: utf-8 -*-
import ast
import calendar
import logging
from datetime import datetime, date

from pytz import timezone
from odoo import api, fields, models, Command
from odoo.exceptions import ValidationError
from odoo.tools import ustr

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    # =========================
    # CAMPOS PERSONALIZADOS
    # =========================
    workplan_id = fields.Many2one('calendar_workplan.plan', 'Plan')
    section_id = fields.Many2one(
        'calendar_workplan.section',
        "Section",
        domain="[('workplan_ids', '=', workplan_id)]"
    )
    workplan_scope = fields.Selection(related='workplan_id.scope')
    channel_ids = fields.Many2many('mail.channel', string="Canales")
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'High')],
        default='0',
        string="Priority"
    )
    attendees_filter_domain = fields.Char(
        string='Attendees filter',
        compute='_compute_attendees_filter_domain'
    )

    # =========================
    # VALIDACIÓN DE FECHAS
    # =========================
    @api.constrains('start', 'stop', 'recurrency', 'until')
    def _check_dates_within_year(self):
        """
        Limita eventos y recurrencias al año del evento base.
        """
        for event in self:
            if not event.start:
                continue

            base_year = event.start.year
            max_date = date(base_year, 12, 31)

            start_date = event.start.date()
            stop_date = event.stop.date() if event.stop else None

            _logger.debug(
                "[YEAR CHECK] ID=%s | base_year=%s | start=%s | stop=%s | until=%s",
                event.id, base_year, start_date, stop_date, getattr(event, 'until', None)
            )

            # Validación de fechas simples
            if start_date > max_date or (stop_date and stop_date > max_date):
                _logger.warning(
                    "[YEAR CHECK] Evento fuera de límite: start=%s stop=%s límite=%s",
                    start_date, stop_date, max_date
                )
                raise ValidationError(f"Las fechas del evento no pueden superar el 31/12/{base_year}")

            # Validación de recurrencia
            if event.recurrency and event.until and event.until > max_date:
                _logger.warning(
                    "[YEAR CHECK] Recurrencia fuera de límite: until=%s límite=%s",
                    event.until, max_date
                )
                raise ValidationError(f"La recurrencia no puede extenderse más allá del 31/12/{base_year}")

    # =========================
    # LIMITAR FECHAS GENERADAS POR RRULE
    # =========================
    def _get_recurrence_dates(self, base_event):
        dates = super()._get_recurrence_dates(base_event)

        if not base_event.start:
            return dates

        year = base_event.start.year
        limit_dt = datetime(year, 12, 31, 23, 59, 59)

        filtered = [dt for dt in dates if dt <= limit_dt]

        if len(filtered) != len(dates):
            _logger.info(
                "[RRULE] Recurrence filtered for base_event=%s: %s → %s (limit=%s)",
                base_event.id, len(dates), len(filtered), limit_dt
            )

        return filtered

    # =========================
    # CREATE ÚNICO Y OPTIMIZADO
    # =========================
    @api.model_create_multi
    def create(self, vals_list):
        _logger.debug("[CREATE] Incoming vals_list: %s", vals_list)

        # Ajustar until_date si excede el año del start
        for vals in vals_list:
            if vals.get('start') and vals.get('until_date'):
                start_dt = fields.Datetime.from_string(vals['start'])
                base_year = start_dt.year
                max_date = date(base_year, 12, 31)

                if vals['until_date'] > max_date:
                    _logger.info(
                        "[CREATE] Ajustando until_date %s → %s para año base %s",
                        vals['until_date'], max_date, base_year
                    )
                    vals['until_date'] = max_date

        events = super().create(vals_list)

        # Validación final para eventos generados por recurrencia
        for event in events:
            if event.recurrence_id and event.recurrence_id.base_event_id:
                base = event.recurrence_id.base_event_id
                base_year = base.start.year
                limit_date = date(base_year, 12, 31)
                event_date = event.start.date()

                _logger.debug(
                    "[CREATE] Recurrent event ID=%s | event_date=%s | limit=%s",
                    event.id, event_date, limit_date
                )

                if event_date > limit_date:
                    _logger.error(
                        "[CREATE] Evento recurrente fuera de límite: %s > %s",
                        event_date, limit_date
                    )
                    raise ValidationError(
                        f"No se pueden generar eventos más allá del {limit_date} (evento generado: {event_date})."
                    )

        return events

    # =========================
    # DOMINIO DE ASISTENTES
    # =========================
    @api.depends('channel_ids')
    def _compute_attendees_filter_domain(self):
        for record in self:
            if record.channel_ids:
                domain = [('channel_ids', 'in', record.channel_ids.ids)]
                record.attendees_filter_domain = ustr(domain)
                _logger.debug("[ATTENDEES] Domain for ID=%s: %s", record.id, domain)
            else:
                record.attendees_filter_domain = "[]"

    def _get_calendar_event_attendees_by_filter_domain(self):
        self.ensure_one()
        domain_str = self.attendees_filter_domain or "[]"

        try:
            domain = ast.literal_eval(domain_str)
        except Exception as e:
            _logger.error("[ATTENDEES] Error parsing domain: %s", e)
            return self.env['res.partner']

        attendees = self.env['res.partner'].search(domain) - self.partner_ids
        _logger.debug("[ATTENDEES] Found %s attendees for ID=%s", len(attendees), self.id)
        return attendees

    @api.onchange('attendees_filter_domain')
    def onchange_attendees_filter_domain(self):
        for record in self:
            if record.attendees_filter_domain and record.attendees_filter_domain != "[]":
                attendees = record._get_calendar_event_attendees_by_filter_domain()
                record.partner_ids = [Command.link(a.id) for a in attendees]
                _logger.debug("[ATTENDEES] Applied %s attendees to ID=%s", len(attendees), record.id)

    # =========================
    # UTILIDADES DE WORKPLAN
    # =========================
    def get_recurrent_days(self, year, month):
        self.ensure_one()
        if not self.recurrence_id:
            return []

        try:
            _, last_day = calendar.monthrange(year, month)
            start_date = datetime(year, month, 1)
            end_date = datetime(year, month, last_day)

            rrule = self.recurrence_id._get_rrule()
            dates = list(rrule.between(start_date, end_date, inc=True))

            days = sorted({d.day for d in dates if d.month == month})
            _logger.debug("[WORKPLAN] Recurrent days for ID=%s: %s", self.id, days)
            return days
        except Exception as e:
            _logger.error("[WORKPLAN] Error: %s", e)
            return []

    def get_sections_with_events(self):
        sections_data = []
        Section = self.env['calendar_workplan.section']

        for section in Section.search([], order='name'):
            events = self.filtered(lambda e: e.section_id == section).sorted(key=lambda e: e.start)
            if events:
                sections_data.append({'name': section.name, 'events': events})
                _logger.debug("[WORKPLAN] Section %s has %s events", section.name, len(events))

        return sections_data

    def get_localized_time(self, plan_tz):
        self.ensure_one()
        try:
            tz = timezone(plan_tz or 'UTC')
            start = self.start.astimezone(tz).strftime('%H:%M')
            stop = self.stop.astimezone(tz).strftime('%H:%M')
            return f"{start} - {stop}"
        except Exception as e:
            _logger.error("[WORKPLAN] Error converting time: %s", e)
            return self.display_time
