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

    # -------------------------
    # VALIDACIÓN AÑO ACTUAL
    # -------------------------
    @api.constrains('start', 'stop', 'recurrency', 'until')
    def _check_dates_within_current_year(self):
        """
        Limita eventos y recurrencias al AÑO ACTUAL del sistema.
        """
        current_year = fields.Date.context_today(self).year
        max_date = date(current_year, 12, 31)

        for event in self:
            if not event.start:
                continue

            start_date = event.start.date()
            stop_date = event.stop.date() if event.stop else None

            _logger.debug(
                "[YEAR CHECK] ID=%s | current_year=%s | start=%s | stop=%s | until=%s",
                event.id, current_year, start_date, stop_date, getattr(event, 'until', None)
            )

            if start_date > max_date or (stop_date and stop_date > max_date):
                raise ValidationError(
                    f"Las fechas del evento no pueden superar el 31/12/{current_year}"
                )

            if event.recurrency and event.until and event.until > max_date:
                raise ValidationError(
                    f"La recurrencia no puede extenderse más allá del 31/12/{current_year}"
                )

    @api.model_create_multi
    def create(self, vals_list):
        """
        1) Deja que Odoo genere el evento base y todos los hijos recurrentes.
        2) Luego elimina silenciosamente los eventos que caen fuera del año actual.
        """
        current_year = fields.Date.context_today(self).year
        max_date = date(current_year, 12, 31)

        _logger.debug("[CREATE] Incoming vals_list: %s", vals_list)

        # Paso 1: crear todo normalmente
        events = super().create(vals_list)

        # Paso 2: filtrar eventos fuera del año actual
        invalid_events = events.filtered(
            lambda e: e.start and e.start.date() > max_date
        )

        if invalid_events:
            _logger.info(
                "[TRIM] Eliminando %s eventos fuera del año actual. Ejemplo: ID=%s fecha=%s límite=%s",
                len(invalid_events),
                invalid_events[0].id,
                invalid_events[0].start.date(),
                max_date
            )
            invalid_events.unlink()

        return events


    # -------------------------
    # DOMINIO DE ASISTENTES
    # -------------------------
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

    # -------------------------
    # UTILIDADES DE WORKPLAN
    # -------------------------
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
