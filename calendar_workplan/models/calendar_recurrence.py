from odoo import models, api
from datetime import datetime, date
import logging  
    
_logger = logging.getLogger(__name__)  

class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'

    def _apply_recurrence(self):
        self.ensure_one()
        _logger.warning(
            "ANTES: end_type=%s, end_date=%s, count=%s, base_start=%s",
            self.end_type, self.end_date, self.count, self.base_event_id.start
        )
        base_event = self.base_event_id
        if base_event and base_event.start:
            year = base_event.start.year
            limit_date = date(year, 12, 31)

            # Caso 1: usuario eligió fecha final
            if self.end_type == 'end_date':
                if self.end_date and self.end_date > limit_date:
                    self.end_date = limit_date

            # Caso 2: usuario eligió número de ocurrencias o sin fin
            else:
                # Convertimos a fecha final
                if not self.end_date or self.end_date > limit_date:
                    self.end_type = 'end_date'
                    self.end_date = limit_date
        _logger.warning(
            "DESPUÉS: end_type=%s, end_date=%s, count=%s",
            self.end_type, self.end_date, self.count
        return super()._apply_recurrence()
