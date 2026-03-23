from datetime import datetime
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    def _get_recurrence_dates(self, base_event):
        """
        Recorta silenciosamente las fechas generadas por la recurrencia
        para que NO pasen del año de inicio del evento base.
        """
        dates = super()._get_recurrence_dates(base_event)

        if not base_event.start:
            return dates

        base_year = base_event.start.year
        limit_dt = datetime(base_year, 12, 31, 23, 59, 59)

        filtered = [dt for dt in dates if dt <= limit_dt]

        if len(filtered) != len(dates):
            _logger.info(
                "[EVENT RRULE TRIM] base_event_id=%s %s→%s (límite=%s)",
                base_event.id, len(dates), len(filtered), limit_dt
            )

        return filtered
