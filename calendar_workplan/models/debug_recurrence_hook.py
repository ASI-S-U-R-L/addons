import logging
from odoo import models

_logger = logging.getLogger(__name__)


class DebugCalendarEvent(models.Model):
    _inherit = 'calendar.event'

    def _get_recurrence_dates(self, base_event):
        _logger.warning(">>> DEBUG HOOK: calendar.event._get_recurrence_dates()")
        return super()._get_recurrence_dates(base_event)

    def _get_recurrent_dates(self, base_event):
        _logger.warning(">>> DEBUG HOOK: calendar.event._get_recurrent_dates()")
        return super()._get_recurrent_dates(base_event)

    def _apply_recurrence(self):
        _logger.warning(">>> DEBUG HOOK: calendar.event._apply_recurrence()")
        return super()._apply_recurrence()

    def _compute_recurrence_dates(self):
        _logger.warning(">>> DEBUG HOOK: calendar.event._compute_recurrence_dates()")
        return super()._compute_recurrence_dates()


class DebugCalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'

    def _get_recurrence_dates(self, dtstart, tz=None):
        _logger.warning(">>> DEBUG HOOK: calendar.recurrence._get_recurrence_dates()")
        return super()._get_recurrence_dates(dtstart, tz=tz)

    def _get_recurrent_dates(self, dtstart, tz=None):
        _logger.warning(">>> DEBUG HOOK: calendar.recurrence._get_recurrent_dates()")
        return super()._get_recurrent_dates(dtstart, tz=tz)

    def _apply_recurrence(self):
        _logger.warning(">>> DEBUG HOOK: calendar.recurrence._apply_recurrence()")
        return super()._apply_recurrence()

    def _compute_recurrence_dates(self):
        _logger.warning(">>> DEBUG HOOK: calendar.recurrence._compute_recurrence_dates()")
        return super()._compute_recurrence_dates()
