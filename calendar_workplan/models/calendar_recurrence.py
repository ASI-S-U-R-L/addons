from odoo import models, api
from odoo.exceptions import ValidationError
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)
class CalendarRecurrence(models.Model):
    _inherit = 'calendar.recurrence'
    
    def _get_rrule(self):
        """
        Parche limpio:
        Limita cualquier recurrencia al 31/12 del año del evento base.
        """

        rule = super()._get_rrule()

        if not self:
            return rule

        rec = self[0]  # ensure_one no siempre es seguro aquí

        if not rec.base_event_id or not rec.base_event_id.start:
            return rule

        year = rec.base_event_id.start.year
        limit_datetime = datetime(year, 12, 31, 23, 59, 59)

        _logger.debug(
            "[Calendar Limit] Recurrence ID=%s | Año base=%s | Límite=%s",
            rec.id, year, limit_datetime
        )

        # 🔥 CLAVE: modificar el UNTIL del rrule
        try:
            if hasattr(rule, '_until'):
                if not rule._until or rule._until > limit_datetime:
                    _logger.debug(
                        "[Calendar Limit] Ajustando UNTIL de %s a %s",
                        rule._until, limit_datetime
                    )
                    rule._until = limit_datetime
        except Exception as e:
            _logger.warning(
                "[Calendar Limit] Error ajustando rrule: %s",
                str(e)
            )

        return rule

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