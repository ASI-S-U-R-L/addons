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
        """Override para evitar generar eventos más allá del 31 de diciembre del año del evento base."""
        self.ensure_one()

        # Ejecutamos la lógica original para obtener las fechas generadas
        dates = super()._apply_recurrence()

        if not dates:
            return dates

        # Fecha límite: 31 de diciembre del año del evento base
        base_event = self.base_event_id
        if not base_event or not base_event.start:
            return dates

        year = base_event.start.year
        limit_date = datetime(year, 12, 31, 23, 59, 59)

        # Filtrar fechas que no sobrepasen el límite
        filtered_dates = []
        for dt in dates:
            if dt <= limit_date:
                filtered_dates.append(dt)

        return filtered_dates

