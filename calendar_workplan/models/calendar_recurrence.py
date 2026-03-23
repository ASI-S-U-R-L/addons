# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from odoo import models

_logger = logging.getLogger(__name__)


class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'

    def _get_recurrent_dates(self, base_event):
        """
        Recorta silenciosamente las fechas generadas por la recurrencia
        para que NO pasen del año del evento base.
        """
        # 1) Obtener fechas originales usando el método real de Odoo
        dates = super()._get_recurrent_dates(base_event)

        if not base_event.start:
            return dates

        # 2) Año del evento base
        base_year = base_event.start.year
        limit_dt = datetime(base_year, 12, 31, 23, 59, 59)

        # 3) Recortar
        filtered = [dt for dt in dates if dt <= limit_dt]

        if len(filtered) != len(dates):
            _logger.warning(
                "[TRIM] Recortando %s → %s fechas para recurrence_id=%s (límite=%s)",
                len(dates), len(filtered), self.id, limit_dt
            )

        return filtered
