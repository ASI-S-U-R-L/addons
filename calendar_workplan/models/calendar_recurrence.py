from odoo import models, api
from datetime import datetime

class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'
    
    @api.model

    def get_exception_dates(self):
        self.ensure_one()
        exceptions = set()
        for event in self.calendar_event_ids:
            if event.recurrence_id and event != event.recurrence_id.base_event_id:
                if event.start and isinstance(event.start, datetime):
                    start_date = event.start.date()
                    exceptions.add((start_date.year, start_date.month, start_date.day))
        return exceptions       

    def _apply_recurrence(self):
        self.ensure_one()

        base_event = self.base_event_id
        if base_event and base_event.start:
            year = base_event.start.year
            limit_date = datetime(year, 12, 31, 23, 59, 59)

            # Si no tiene until, se lo ponemos
            if not self.until:
                self.until = limit_date

            # Si tiene until pero es mayor, lo recortamos
            elif self.until > limit_date:
                self.until = limit_date

        return super()._apply_recurrence()
