# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ComponentSubtype(models.Model):
    _name = 'it.component.subtype'
    _description = 'Subtipo de Componente de TI'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', help='Código único para el subtipo (ej. INT_CPU)')
    type = fields.Selection(
        selection=[('internal', 'Interno'), ('peripheral', 'Periférico')],
        string='Tipo de Componente', required=True
    )
    description = fields.Text(string='Descripción')
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)
    component_count = fields.Integer(string='Cantidad de Componentes', compute='_compute_component_count')
    
    # --- Reglas de Negocio ---
    is_critical = fields.Boolean(
        string='Componente Crítico', default=False,
        help='Marca si este tipo de componente es crítico para el funcionamiento del hardware.'
    )
    max_per_hardware = fields.Integer(
        string='Máximo por Hardware', default=0,
        help='Número máximo de este tipo de componente por hardware (0 = sin límite).'
    )

    _sql_constraints = [
        ('name_type_unique', 'UNIQUE(name, type)', 'Ya existe un subtipo con este nombre y tipo.'),
        ('code_unique', 'UNIQUE(code)', 'El código del subtipo debe ser único.'),
    ]

    def _compute_component_count(self):
        """Calcula el número de componentes que usan este subtipo."""
        for record in self:
            record.component_count = self.env['it.component'].search_count([
                ('subtype_id', '=', record.id)
            ])

    def action_view_components(self):
        """Acción para ver los componentes de este subtipo."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Componentes: {self.name}',
            'res_model': 'it.component',
            'view_mode': 'tree,form',
            'domain': [('subtype_id', '=', self.id)],
            'context': {'default_subtype_id': self.id, 'default_type': self.type}
        }
    
    def toggle_active(self):
        """Alterna el estado activo del subtipo, con validación."""
        for record in self:
            if record.active and record.component_count > 0:
                raise ValidationError(f"No se puede desactivar el subtipo '{record.name}' porque tiene {record.component_count} componente(s) asociado(s).")
            record.active = not record.active