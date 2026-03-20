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
            # límite como date, porque end_date es date
            limit_date = datetime(year, 12, 31).date()

            # Caso 1: el usuario eligió fecha final
            if self.end_type == 'end_date':
                if self.end_date and self.end_date > limit_date:
                    self.end_date = limit_date

            # Caso 2: el usuario eligió número de ocurrencias o sin fin
            else:
                # Forzamos a que la recurrencia termine como máximo el 31/12 de ese año
                self.end_type = 'end_date'
                # Solo ponemos end_date si no hay una más restrictiva
                if not self.end_date or self.end_date > limit_date:
                    self.end_date = limit_date

        return super()._apply_recurrence()

