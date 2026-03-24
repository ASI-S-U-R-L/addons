# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from odoo import models

_logger = logging.getLogger(__name__)


class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'

    def _get_rrule(self, dtstart=None):
        # Llamar al método original con el mismo argumento
        rrule = super()._get_rrule(dtstart=dtstart)

        # Si hay evento base, recortar con UNTIL
        if self.base_event_id and self.base_event_id.start:
            limit_dt = datetime(self.base_event_id.start.year, 12, 31, 23, 59, 59)
            # Forzar límite en la regla
            rrule._until = limit_dt

        return rrule

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
