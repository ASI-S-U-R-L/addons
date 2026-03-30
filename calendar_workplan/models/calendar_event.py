# -*- coding: utf-8 -*-
import ast
import calendar
import logging
from datetime import datetime

from pytz import timezone
from odoo import api, fields, models, Command
from odoo.tools import ustr

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    # -------------------------
    # CAMPOS DE WORKPLAN
    # -------------------------
    workplan_id = fields.Many2one(
        'calendar_workplan.plan',
        string="Plan de trabajo"
    )
    section_id = fields.Many2one(
        'calendar_workplan.section',
        string="Sección",
        domain="[('workplan_ids', '=', workplan_id)]"
    )
    workplan_scope = fields.Selection(
        related='workplan_id.scope',
        string="Ámbito del plan",
        store=True
    )

    # -------------------------
    # CAMPOS DE CALENDARIO
    # -------------------------
    channel_ids = fields.Many2many(
        'mail.channel',
        string="Canales"
    )
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Alta')],
        default='0',
        string="Prioridad"
    )
    attendees_filter_domain = fields.Char(
        string="Dominio de asistentes",
        compute='_compute_attendees_filter_domain'
    )

    # -------------------------
    # DOMINIO DE ASISTENTES
    # -------------------------
    @api.depends('channel_ids')
    def _compute_attendees_filter_domain(self):
        for record in self:
            if record.channel_ids:
                domain = [('channel_ids', 'in', record.channel_ids.ids)]
                record.attendees_filter_domain = ustr(domain)
            else:
                record.attendees_filter_domain = "[]"

    def _get_calendar_event_attendees_by_filter_domain(self):
        self.ensure_one()
        domain_str = self.attendees_filter_domain or "[]"

        try:
            domain = ast.literal_eval(domain_str)
        except Exception:
            return self.env['res.partner']

        return self.env['res.partner'].search(domain) - self.partner_ids

    @api.onchange('attendees_filter_domain')
    def onchange_attendees_filter_domain(self):
        for record in self:
            if record.attendees_filter_domain and record.attendees_filter_domain != "[]":
                attendees = record._get_calendar_event_attendees_by_filter_domain()
                record.partner_ids = [Command.link(a.id) for a in attendees]

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

            return sorted({d.day for d in dates if d.month == month})
        except Exception:
            return []

    def get_sections_with_events(self):
        sections_data = []
        Section = self.env['calendar_workplan.section']

        for section in Section.search([], order='name'):
            events = self.filtered(lambda e: e.section_id == section).sorted(key=lambda e: e.start)
            if events:
                sections_data.append({'name': section.name, 'events': events})

        return sections_data

    def get_localized_time(self, plan_tz):
        self.ensure_one()
        try:
            tz = timezone(plan_tz or 'UTC')
            start = self.start.astimezone(tz).strftime('%H:%M')
            stop = self.stop.astimezone(tz).strftime('%H:%M')
            return f"{start} - {stop}"
        except Exception:
            return self.display_time
