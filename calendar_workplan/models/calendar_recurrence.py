# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from odoo import models

_logger = logging.getLogger(__name__)


class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'

    def _apply_recurrence(self):
        """
        Recorta silenciosamente las fechas generadas por la recurrencia
        para que NO pasen del año del evento base.
        """
        self.ensure_one()

        base_event = self.base_event_id
        if not base_event or not base_event.start:
            return super()._apply_recurrence()

        base_year = base_event.start.year
        limit_dt = datetime(base_year, 12, 31, 23, 59, 59)

        # 1) Obtener fechas usando el método interno real de Odoo
        #    Este método SÍ existe en tu build.
        dates = self._get_recurrent_dates(base_event)

        # 2) Filtrar por año del evento base
        filtered_dates = [dt for dt in dates if dt <= limit_dt]

        if len(filtered_dates) != len(dates):
            _logger.warning(
                "[APPLY TRIM] Recortando %s → %s fechas para recurrence_id=%s (límite=%s)",
                len(dates), len(filtered_dates), self.id, limit_dt
            )

        # 3) Crear eventos hijos SOLO con fechas válidas
        Event = self.env['calendar.event']
        for dt in filtered_dates:
            values = self._get_event_values(base_event, dt)
            Event.create(values)

        return True
