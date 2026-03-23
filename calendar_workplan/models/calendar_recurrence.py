# -*- coding: utf-8 -*-
import logging
from datetime import datetime, date

from odoo import models, fields

_logger = logging.getLogger(__name__)


class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'

    def _get_recurrence_dates(self, dtstart, tz=None):
        """
        Recorta silenciosamente las fechas generadas por la recurrencia
        para que NO pasen del año del evento base.
        """
        dates = super()._get_recurrence_dates(dtstart, tz=tz)

        if not dtstart:
            return dates

        # Año del evento base
        base_year = dtstart.year
        limit_dt = datetime(base_year, 12, 31, 23, 59, 59)

        filtered = [dt for dt in dates if dt <= limit_dt]

        if len(filtered) != len(dates):
            _logger.info(
                "[RRULE TRIM] Recortando %s → %s fechas para recurrence_id=%s (límite=%s)",
                len(dates), len(filtered), self.ids, limit_dt
            )

        return filtered

