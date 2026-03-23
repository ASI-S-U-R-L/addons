# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from odoo import models

_logger = logging.getLogger(__name__)


class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'

    def _get_recurrent_dates(self, base_event):
        _logger.error(">>> OVERRIDE REAL EJECUTADO EN _get_recurrent_dates(), recurrence_id=%s", self.id)
        return super()._get_recurrent_dates(base_event)
