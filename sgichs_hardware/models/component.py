# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class Component(models.Model):
    _name = 'it.component'
    _description = 'Componente de TI'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'model'

    model = fields.Char(string='Modelo', required=True)
    manufacturer = fields.Char(string='Fabricante', default='Desconocido')
    type = fields.Selection(related='subtype_id.type', string='Tipo', readonly=True, store=True)
    subtype_id = fields.Many2one('it.component.subtype', string='Subtipo', required=True)
    serial_number = fields.Char(string='Número de Serie', copy=False)
    inventory_number = fields.Char(string='Número de Inventario')
    
    size_gb = fields.Float(string='Tamaño (GB)')
    ram_type = fields.Selection(
        selection=[
            ('ddr', 'DDR'),
            ('ddr2', 'DDR2'),
            ('ddr3', 'DDR3'),
            ('ddr4', 'DDR4'),
            ('ddr5', 'DDR5'),
            ('otro', 'Otro'),
        ],
        string='Tipo de RAM'
    )
    
    subtype_name = fields.Char(
        related='subtype_id.name',
        string='Nombre del Subtipo',
        store=True,
        readonly=True
    )
    
    status = fields.Selection(
        selection=[
            ('operational', 'Operativo'), ('maintenance', 'En Mantenimiento'),
            ('failed', 'Averiado'), ('retired', 'Retirado'), ('lost', 'Perdido')
        ], string='Estado', default='operational', tracking=True
    )
    hardware_id = fields.Many2one(
        'it.asset.hardware', string='Asignado a Hardware', ondelete='set null', tracking=True
    )

    assignment_status = fields.Selection(
        selection=[
            ('available', 'Disponible'), ('assigned', 'Asignado'),
            ('conflict', 'Conflicto de Asignación')
        ], string='Estado de Asignación', compute='_compute_assignment_status', store=True
    )

    _sql_constraints = [
        ('serial_number_uniq', 'unique(serial_number)', 'El número de serie debe ser único si está definido!'),
    ]

    @api.depends('hardware_id')
    def _compute_assignment_status(self):
        """Calcula el estado de asignación basado en si tiene un hardware_id."""
        for component in self:
            # La lógica de conflicto se maneja por separado para generar incidentes.
            if component.hardware_id:
                component.assignment_status = 'assigned'
            else:
                component.assignment_status = 'available'

    def _create_conflict_incident(self, hardware_list):
        """Crea un incidente por conflicto de asignación."""
        self.ensure_one()
        hardware_names = ', '.join(hardware_list.mapped('name'))
        title = _("Conflicto de Asignación de Componente: %s", self.model)
        description = _(
            "Se ha detectado que el componente con S/N '%s' está asignado a múltiples activos de hardware simultáneamente:\n\n"
            "- **Componente:** %s\n"
            "- **Hardware en Conflicto:** %s\n\n"
            "ACCIÓN REQUERIDA: Corregir la asignación. Un componente solo puede estar en un hardware a la vez.",
            self.serial_number, self.model, hardware_names
        )
        self.env['it.incident'].create({
            'title': title, 'description': description, 'severity': 'high',
            'asset_model': self.hardware_id._name, 'asset_id': self.hardware_id.id,
        })

    def check_assignment_conflicts(self):
        """Verifica y reporta conflictos de asignación para los componentes actuales."""
        for component in self.filtered(lambda c: c.serial_number):
            hardware_list = self.env['it.asset.hardware'].search([
                ('components_ids', 'in', component.id)
            ])
            if len(hardware_list) > 1:
                component.assignment_status = 'conflict'
                component._create_conflict_incident(hardware_list)
                _logger.warning(f"Conflicto detectado: Componente S/N {component.serial_number} asignado a {len(hardware_list)} hardware.")

    def write(self, vals):
        res = super().write(vals)
        if 'hardware_id' in vals:
            self.check_assignment_conflicts()
        return res

    @api.constrains('subtype_id', 'inventory_number')
    def _check_inventory_number_for_peripheral(self):
        """Valida que los periféricos tengan número de inventario."""
        for component in self:
            if component.subtype_id.type == 'peripheral' and not component.inventory_number:
                raise ValidationError(_("Los componentes de tipo 'Periférico' deben tener un Número de Inventario."))

    def action_unassign_from_hardware(self):
        """Desasigna el componente del hardware actual."""
        hardware_name = self.hardware_id.name
        self.hardware_id = False
        self.message_post(body=_("Componente desasignado del hardware: %s", hardware_name))

    def action_view_assigned_hardware(self):
        """
        Acción para navegar al formulario del hardware asignado.
        """
        self.ensure_one()
        # Esta acción solo será visible si hardware_id tiene un valor,
        # por lo que podemos asumir que existe.
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hardware: %s', self.hardware_id.name),
            'res_model': 'it.asset.hardware',
            'res_id': self.hardware_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_component_form(self):
        """
        Acción para navegar al formulario del propio componente.
        Es utilizada desde la vista de lista en el modelo de hardware.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Componente: {self.model}', # Nombre dinámico para la vista
            'res_model': 'it.component',
            'res_id': self.id, # El ID del componente actual
            'view_mode': 'form',
            'target': 'current',
        }