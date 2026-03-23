from datetime import datetime, date
from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'

    def _get_recurrence_dates(self, dtstart, tz=None):
        """
        Limita las fechas generadas por la recurrencia al año actual.
        """
        dates = super()._get_recurrence_dates(dtstart, tz=tz)

        current_year = fields.Date.context_today(self).year
        limit_dt = datetime(current_year, 12, 31, 23, 59, 59)

        filtered = [dt for dt in dates if dt <= limit_dt]

        if len(filtered) != len(dates):
            _logger.info(
                "[RRULE] Recurrence filtered for recurrence_id=%s: %s → %s (limit=%s)",
                self.ids, len(dates), len(filtered), limit_dt
            )

        return filtered
