from odoo import models, api
from odoo.exceptions import ValidationError
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)
class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'
    

    def _get_rrule(self):
        rule = super()._get_rrule()

        if not self.base_event_id or not self.base_event_id.start:
            return rule

        year = self.base_event_id.start.year
        limit_datetime = datetime(year, 12, 31, 23, 59, 59)

        # ⚠️ Aquí está la clave
        if hasattr(rule, '_until') and (not rule._until or rule._until > limit_datetime):
            rule._until = limit_datetime

        return rule
        
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


    # ---------------------------------------------------------
    # CORE LOGIC
    # ---------------------------------------------------------
    def _limit_to_year(self, vals):
        """
        Fuerza que la recurrencia no pase del año del evento base
        """
        base_event = None

        # Detectar evento base
        if 'base_event_id' in vals:
            base_event = self.env['calendar.event'].browse(vals['base_event_id'])
        elif self and self.base_event_id:
            base_event = self.base_event_id

        if not base_event or not base_event.start:
            _logger.warning("No base_event o sin fecha de inicio. Se omite control.")
            return vals

        year = base_event.start.year
        limit_date = date(year, 12, 31)

        _logger.warning(
            "Aplicando límite de recurrencia. Año base: %s | Fecha límite: %s",
            year, limit_date
        )

        end_type = vals.get('end_type', self.end_type if self else False)

        # -----------------------------------------------------
        # Caso 1: usuario define fecha final
        # -----------------------------------------------------
        if end_type == 'end_date':
            end_date = vals.get('end_date', self.end_date if self else None)

            if end_date and end_date > limit_date:
                _logger.warning(
                    "End date (%s) supera límite. Ajustando a %s",
                    end_date, limit_date
                )
                vals['end_date'] = limit_date

        # -----------------------------------------------------
        # Caso 2: forever o count → lo forzamos
        # -----------------------------------------------------
        else:
            _logger.warning(
                "Recurrencia tipo '%s' no permitida. Forzando end_date=%s",
                end_type, limit_date
            )
            vals['end_type'] = 'end_date'
            vals['end_date'] = limit_date

        return vals

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------
    @api.model
    def create(self, vals):
        _logger.warning("CREATE recurrence vals inicial: %s", vals)

        vals = self._limit_to_year(vals)

        rec = super().create(vals)

        _logger.warning(
            "Recurrence creada ID=%s | end_type=%s | end_date=%s",
            rec.id, rec.end_type, rec.end_date
        )

        return rec

    # ---------------------------------------------------------
    # WRITE
    # ---------------------------------------------------------
    def write(self, vals):
        _logger.warning("WRITE recurrence ID=%s | vals inicial: %s", self.ids, vals)

        vals = self._limit_to_year(vals)

        res = super().write(vals)

        for rec in self:
            _logger.warning(
                "Recurrence actualizada ID=%s | end_type=%s | end_date=%s",
                rec.id, rec.end_type, rec.end_date
            )

        return res

    # ---------------------------------------------------------
    # VALIDACIÓN DURA
    # ---------------------------------------------------------
    def _check_year_limit(self):
        for rec in self:
            if rec.base_event_id and rec.base_event_id.start:
                year = rec.base_event_id.start.year
                limit_date = datetime(year, 12, 31).date()

                if rec.end_type == 'end_date' and rec.end_date and rec.end_date > limit_date:
                    raise ValidationError(
                        "No puedes crear recurrencias más allá del año del evento base."
                    )

    # Activar constraint
    @api.constrains('end_date', 'end_type', 'base_event_id')
    def _constrain_year_limit(self):
        self._check_year_limit()