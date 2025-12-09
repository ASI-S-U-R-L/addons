from odoo import api, fields, models, _
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)


class PosSessionDenominationExtension(models.Model):
    """
    Extensión del modelo pos.session para integrar control de denominaciones
    """
    _inherit = 'pos.session'

    denomination_control_ids = fields.One2many(
        'pos.session.denomination.control',
        'session_id',
        string='Controles de Denominaciones',
        readonly=True
    )

    opening_denomination_control = fields.Many2one(
        'pos.session.denomination.control',
        string='Control de Apertura',
        compute='_compute_denomination_controls'
    )

    closing_denomination_control = fields.Many2one(
        'pos.session.denomination.control',
        string='Control de Cierre',
        compute='_compute_denomination_controls'
    )

    has_denomination_control = fields.Boolean(
        string='Tiene Control de Denominaciones',
        compute='_compute_has_denomination_control'
    )

    denomination_opening_total = fields.Float(
        string='Total Apertura por Denominaciones',
        compute='_compute_denomination_totals'
    )

    denomination_closing_total = fields.Float(
        string='Total Cierre por Denominaciones',
        compute='_compute_denomination_totals'
    )

    denomination_difference = fields.Float(
        string='Diferencia por Denominaciones',
        compute='_compute_denomination_difference'
    )

    @api.depends('denomination_control_ids', 'denomination_control_ids.control_type')
    def _compute_denomination_controls(self):
        """Computa los controles de apertura y cierre"""
        for session in self:
            opening_controls = session.denomination_control_ids.filtered(
                lambda ctrl: ctrl.control_type == 'opening'
            )
            closing_controls = session.denomination_control_ids.filtered(
                lambda ctrl: ctrl.control_type == 'closing'
            )

            session.opening_denomination_control = opening_controls[:1]
            session.closing_denomination_control = closing_controls[:1]

    @api.depends('denomination_control_ids')
    def _compute_has_denomination_control(self):
        """Verifica si la sesión tiene controles de denominaciones"""
        for session in self:
            session.has_denomination_control = bool(session.denomination_control_ids)

    @api.depends(
        'denomination_control_ids',
        'denomination_control_ids.total_amount',
        'denomination_control_ids.control_type'
    )
    def _compute_denomination_totals(self):
        """Computa los totales de apertura y cierre por denominaciones"""
        for session in self:
            opening_total = 0.0
            closing_total = 0.0

            for ctrl in session.denomination_control_ids:
                if ctrl.control_type == 'opening':
                    opening_total = ctrl.total_amount
                elif ctrl.control_type == 'closing':
                    closing_total = ctrl.total_amount

            session.denomination_opening_total = opening_total
            session.denomination_closing_total = closing_total

    @api.depends(
        'denomination_opening_total',
        'denomination_closing_total',
        'cash_register_balance_start',
        'cash_register_total_entry_encoding'
    )
    def _compute_denomination_difference(self):
        """Computa la diferencia entre el conteo por denominaciones y el balance teórico"""
        for session in self:
            if session.denomination_closing_total > 0:
                # Comparar con el balance teórico de cierre
                theoretical_closing = (
                    session.denomination_opening_total +
                    session.cash_register_total_entry_encoding
                )
                session.denomination_difference = (
                    session.denomination_closing_total - theoretical_closing
                )
            else:
                session.denomination_difference = 0.0

    def save_denomination_control(self, control_type, total_amount, denominations_data=None):
        """
        Guarda el control de denominaciones para la sesión actual.

        Args:
            control_type (str): 'opening' o 'closing'
            total_amount (float): Total contado
            denominations_data (dict): Datos detallados de denominaciones

        Returns:
            pos.session.denomination.control: Registro creado o actualizado
        """
        self.ensure_one()

        # Buscar control existente del mismo tipo
        existing_control = self.denomination_control_ids.filtered(
            lambda ctrl: ctrl.control_type == control_type
        )

        # Preparar valores para crear/actualizar
        vals = {
            'session_id': self.id,
            'control_type': control_type,
            'total_amount': total_amount,
            'control_date': fields.Datetime.now(),
        }

        if denominations_data:
            try:
                import json
                vals['denominations_data'] = json.dumps(denominations_data, ensure_ascii=False, indent=2)
            except (TypeError, ValueError) as e:
                _logger.error(f"Error encoding denominations data: {e}")
                vals['denominations_data'] = json.dumps({}, ensure_ascii=False, indent=2)

        # Crear o actualizar el control
        if existing_control:
            existing_control.write(vals)
            return existing_control
        else:
            return self.env['pos.session.denomination.control'].create(vals)

    def get_denomination_summary(self):
        """
        Obtiene un resumen de los controles de denominaciones de la sesión.

        Returns:
            dict: Resumen con información de apertura, cierre y diferencias
        """
        self.ensure_one()

        opening_control = self.opening_denomination_control
        closing_control = self.closing_denomination_control

        summary = {
            'session_id': self.id,
            'session_name': self.name,
            'opening_control': {
                'exists': bool(opening_control),
                'total_amount': opening_control.total_amount if opening_control else 0.0,
                'date': opening_control.control_date.isoformat() if opening_control and opening_control.control_date else None,
                'denominations_count': opening_control.denominations_count if opening_control else 0
            },
            'closing_control': {
                'exists': bool(closing_control),
                'total_amount': closing_control.total_amount if closing_control else 0.0,
                'date': closing_control.control_date.isoformat() if closing_control and closing_control.control_date else None,
                'denominations_count': closing_control.denominations_count if closing_control else 0
            },
            'differences': {
                'denomination_difference': self.denomination_difference,
                'cash_difference': self.cash_register_difference,
                'theoretical_closing': self.denomination_opening_total + self.cash_register_total_entry_encoding
            },
            'has_denomination_control': self.has_denomination_control
        }

        return summary

    def action_view_denomination_controls(self):
        """Acción para ver los controles de denominaciones de la sesión"""
        self.ensure_one()

        return {
            'name': _('Controles de Denominaciones'),
            'type': 'ir.actions.act_window',
            'res_model': 'pos.session.denomination.control',
            'view_mode': 'tree,form',
            'domain': [('session_id', '=', self.id)],
            'context': {
                'default_session_id': self.id,
                'search_default_session_id': self.id
            },
            'target': 'current',
        }


    @api.model
    def save_denomination_control_from_ui(self, session_id, control_type, total_amount, denominations_data=None):
        """
        Método para ser llamado desde la interfaz de usuario.
        Guarda el control de denominaciones via RPC.

        Args:
            session_id (int): ID de la sesión
            control_type (str): Tipo de control ('opening' o 'closing')
            total_amount (float): Total contado
            denominations_data (dict): Datos de denominaciones

        Returns:
            dict: Resultado con success=True/False y mensaje
        """
        try:
            session = self.browse(session_id)
            if not session.exists():
                return {
                    'success': False,
                    'message': 'Sesión no encontrada'
                }

            control = session.save_denomination_control(
                control_type=control_type,
                total_amount=total_amount,
                denominations_data=denominations_data
            )

            return {
                'success': True,
                'message': 'Control de denominaciones guardado correctamente',
                'control_id': control.id,
                'control_data': {
                    'id': control.id,
                    'total_amount': control.total_amount,
                    'control_type': control.control_type,
                    'control_date': control.control_date.isoformat() if control.control_date else None
                }
            }

        except Exception as e:
            _logger.error(f"Error saving denomination control: {e}")
            return {
                'success': False,
                'message': f'Error al guardar control de denominaciones: {str(e)}'
            }