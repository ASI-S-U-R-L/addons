from odoo import api, fields, models, _
import json
import logging

_logger = logging.getLogger(__name__)


class PosSessionDenominationControl(models.Model):
    """
    Modelo para almacenar el control de denominaciones en sesiones POS.
    Persiste los datos de apertura y cierre de caja por denominaciones para auditoría e informes.
    """
    _name = 'pos.session.denomination.control'
    _description = 'Control de Denominaciones por Sesión POS'
    _order = 'id desc'
    _rec_name = 'display_name'

    session_id = fields.Many2one(
        'pos.session', 
        string='Sesión POS', 
        required=True, 
        index=True,
        ondelete='cascade'
    )
    
    config_id = fields.Many2one(
        'pos.config', 
        string='Configuración POS', 
        related='session_id.config_id', 
        store=True, 
        readonly=True
    )
    
    user_id = fields.Many2one(
        'res.users', 
        string='Usuario', 
        related='session_id.user_id', 
        store=True, 
        readonly=True
    )
    
    control_type = fields.Selection(
        [
            ('opening', 'Apertura de Caja'),
            ('closing', 'Cierre de Caja')
        ], 
        string='Tipo de Control', 
        required=True,
        index=True
    )
    
    denominations_data = fields.Text(
        string='Datos de Denominaciones',
        help='JSON con el detalle de denominaciones contadas'
    )
    
    total_amount = fields.Float(
        string='Total Contado',
        required=True,
        help='Total calculado a partir de las denominaciones'
    )
    
    control_date = fields.Datetime(
        string='Fecha del Control',
        default=lambda self: fields.Datetime.now(),
        required=True
    )
    
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name',
        store=True
    )
    
    # Campos computados para fácil acceso
    denominations_count = fields.Integer(
        string='Cantidad de Denominaciones',
        compute='_compute_denominations_count',
        store=True
    )
    
    has_denominations_data = fields.Boolean(
        string='Tiene Datos de Denominaciones',
        compute='_compute_has_denominations_data',
        store=True
    )
    
    @api.depends('session_id.name', 'control_type', 'control_date')
    def _compute_display_name(self):
        for record in self:
            session_name = record.session_id.name or 'Sin Sesión'
            control_type_str = dict(record._fields['control_type'].selection).get(record.control_type, '')
            date_str = record.control_date.strftime('%Y-%m-%d %H:%M') if record.control_date else ''
            record.display_name = f"{session_name} - {control_type_str} ({date_str})"
    
    @api.depends('denominations_data')
    def _compute_denominations_count(self):
        for record in self:
            count = 0
            if record.denominations_data:
                try:
                    data = json.loads(record.denominations_data)
                    if isinstance(data, dict) and 'denominations' in data:
                        count = len(data['denominations'])
                    elif isinstance(data, list):
                        count = len(data)
                except (json.JSONDecodeError, TypeError, KeyError) as e:
                    _logger.warning(f"Error parsing denominations data: {e}")
                    count = 0
            record.denominations_count = count
    
    @api.depends('denominations_data')
    def _compute_has_denominations_data(self):
        for record in self:
            record.has_denominations_data = bool(record.denominations_data)
    
    def get_denominations_dict(self):
        """
        Método para obtener las denominaciones como diccionario Python.
        Returns:
            dict: Diccionario con los datos de denominaciones o dict vacío si hay error
        """
        self.ensure_one()
        if not self.denominations_data:
            return {}
        
        try:
            return json.loads(self.denominations_data)
        except json.JSONDecodeError as e:
            _logger.error(f"Error decoding denominations JSON for record {self.id}: {e}")
            return {}
    
    def set_denominations_dict(self, data_dict):
        """
        Método para establecer las denominaciones desde un diccionario Python.
        Args:
            data_dict (dict): Diccionario con los datos de denominaciones
        """
        self.ensure_one()
        try:
            self.denominations_data = json.dumps(data_dict, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as e:
            _logger.error(f"Error encoding denominations data for record {self.id}: {e}")
            raise ValueError(f"Error al guardar datos de denominaciones: {e}")
    
    @api.constrains('total_amount')
    def _check_total_amount(self):
        for record in self:
            if record.total_amount < 0:
                raise ValueError(_("El total contado no puede ser negativo"))
    
    @api.constrains('session_id', 'control_type')
    def _check_unique_control_per_session(self):
        """
        Constraint para evitar múltiples controles del mismo tipo por sesión.
        """
        for record in self:
            existing = self.search([
                ('session_id', '=', record.session_id.id),
                ('control_type', '=', record.control_type),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValueError(_(
                    "Ya existe un control de %(type)s para la sesión %(session)s",
                    type=dict(self._fields['control_type'].selection).get(record.control_type),
                    session=record.session_id.name
                ))
    
    def action_view_session(self):
        """Acción para ver la sesión asociada"""
        self.ensure_one()
        return {
            'name': _('Sesión POS'),
            'type': 'ir.actions.act_window',
            'res_model': 'pos.session',
            'view_mode': 'form',
            'res_id': self.session_id.id,
            'target': 'current',
        }
    
    def export_denominations_data(self):
        """Método para exportar los datos de denominaciones"""
        self.ensure_one()
        denominations_dict = self.get_denominations_dict()
        return {
            'session_name': self.session_id.name,
            'control_type': dict(self._fields['control_type'].selection).get(self.control_type),
            'total_amount': self.total_amount,
            'control_date': self.control_date.isoformat() if self.control_date else None,
            'denominations': denominations_dict
        }
    
    @api.model
    def create_denomination_control(self, session_id, control_type, total_amount, denominations_data=None):
        """
        Método factory para crear un control de denominaciones.
        
        Args:
            session_id (int): ID de la sesión POS
            control_type (str): 'opening' o 'closing'
            total_amount (float): Total contado
            denominations_data (dict): Datos de denominaciones (opcional)
            
        Returns:
            pos.session.denomination.control: Registro creado
        """
        vals = {
            'session_id': session_id,
            'control_type': control_type,
            'total_amount': total_amount,
            'control_date': fields.Datetime.now(),
        }
        
        if denominations_data:
            try:
                vals['denominations_data'] = json.dumps(denominations_data, ensure_ascii=False, indent=2)
            except (TypeError, ValueError) as e:
                _logger.warning(f"Error encoding denominations data: {e}")
                vals['denominations_data'] = json.dumps({}, ensure_ascii=False, indent=2)
        
        return self.create(vals)
    
    def name_get(self):
        result = []
        for record in self:
            name = record.display_name or f"Control {record.id}"
            result.append((record.id, name))
        return result