# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from odoo import models

_logger = logging.getLogger(__name__)


class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'until' not in vals and 'base_event_id' in vals:
                base_event = self.env['calendar.event'].browse(vals['base_event_id'])
                if base_event.start:
                    # Forzar límite al 31 de diciembre del año inicial
                    vals['until'] = datetime(base_event.start.year, 12, 31, 23, 59, 59)
        return super().create(vals_list)


    def _get_recurrent_dates(self, base_event):
        dates = super()._get_recurrent_dates(base_event)

        if not base_event.start:
            return dates

        base_year = base_event.start.year
        limit_dt = datetime(base_year, 12, 31, 23, 59, 59)

        filtered = [dt for dt in dates if dt <= limit_dt]

        if len(filtered) != len(dates):
            _logger.warning(
                "[TRIM] Recortando %s → %s fechas para recurrence_id=%s (límite=%s)",
                len(dates), len(filtered), self.id, limit_dt
            )

        return filtered
