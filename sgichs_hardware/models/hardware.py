# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class Hardware(models.Model):
    _name = 'it.asset.hardware'
    _description = 'Activo de Hardware'
    _inherit = 'it.asset'

    # Este campo extiende la selección del modelo padre.
    # Odoo combina automáticamente las selecciones de los modelos heredados.
    type = fields.Selection(
        selection_add=[('hardware', 'Hardware')],
        ondelete={'hardware': 'cascade'},
        default='hardware'
    )

    subtype = fields.Selection(
        selection=[
            ('pc', 'PC'),
            ('laptop', 'Laptop'),
            ('server', 'Servidor'),
            ('mobile', 'Dispositivo Móvil'),
            ('other', 'Otro')
        ],
        string='Subtipo',
        required=True,
        tracking=True
    )
    inventory_number = fields.Char(string='Número de Inventario', unique=True, copy=False)
    
    _sql_constraints = [
        ('inventory_number_uniq', 'unique (inventory_number)', 'El número de inventario debe ser único!')
    ]
    
    components_ids = fields.Many2many(
        'it.component',
        'hardware_component_rel',
        'hardware_id',
        'component_id',
        string='Componentes',
        tracking=True
    )
    
    # Campos computados para control de módulos
    has_reporting_module = fields.Boolean(
        compute='_compute_module_status',
        compute_sudo=True,
        string='Tiene Módulo de Reportes?',
        help="Indica si el módulo de reportes está instalado"
    )
    has_network_module = fields.Boolean(
        compute='_compute_module_status',
        compute_sudo=True,
        string='Tiene Módulo de Red?'
    )
    has_software_module = fields.Boolean(
        compute='_compute_module_status',
        compute_sudo=True,
        string='Tiene Módulo de Software?'
    )

    # COMENTARIO: Los campos y la lógica para 'software_ids' y 'ip_ids' (y el ping)
    # han sido OMITIDOS intencionadamente. Serán añadidos por los módulos
    # 'sgich_software' y 'sgich_network' respectivamente, heredando este modelo.
    # Esto previene errores si esos módulos no están instalados.

    # --- LÓGICA DE SINCRONIZACIÓN Y VALIDACIÓN ---
    def _update_component_assignments(self):
        """
        Asegura que la relación bidireccional entre hardware y componente sea correcta.
        Esta función es clave para mantener la integridad de los datos.
        """
        for hardware in self:
            # 1. Asigna este hardware a los componentes que están en su lista
            components_to_assign = hardware.components_ids.filtered(lambda c: c.hardware_id != hardware)
            if components_to_assign:
                components_to_assign.write({'hardware_id': hardware.id})

            # 2. Desasigna este hardware de los componentes que ya no están en su lista
            components_to_unassign = self.env['it.component'].search([
                ('hardware_id', '=', hardware.id),
                ('id', 'not in', hardware.components_ids.ids)
            ])
            if components_to_unassign:
                components_to_unassign.write({'hardware_id': False})

    @api.model_create_multi
    def create(self, vals_list):
        """ Sobrescrito para asegurar la sincronización de componentes al crear. """
        for vals in vals_list:
            vals['type'] = 'hardware'
        hardwares = super(Hardware, self).create(vals_list)
        hardwares._update_component_assignments()
        return hardwares

    def write(self, vals):
        """ Sobrescrito para asegurar la sincronización de componentes al editar. """
        if 'type' in vals and vals['type'] != 'hardware':
            vals['type'] = 'hardware'
        res = super(Hardware, self).write(vals)
        if 'components_ids' in vals:
            self._update_component_assignments()
        return res

    def unlink(self):
        """
        Antes de eliminar un hardware, desasigna todos sus componentes
        para que queden como 'disponibles'.
        """
        for hardware in self:
            hardware.components_ids.write({'hardware_id': False})
        return super(Hardware, self).unlink()
    
    @api.depends_context()
    def _compute_module_status(self):
        """Calcula si los módulos dependientes están instalados"""
        installed_modules = self.env['ir.module.module'].search([
            ('name', 'in', ['sgichs_reporting', 'sgichs_red', 'sgichs_software']),
            ('state', '=', 'installed')
        ]).mapped('name')

        has_reporting = 'sgichs_reporting' in installed_modules
        has_network = 'sgichs_red' in installed_modules
        has_software = 'sgichs_software' in installed_modules

        for record in self:
            record.has_reporting_module = has_reporting
            record.has_network_module = has_network
            record.has_software_module = has_software
    
    def action_manual_ping(self):
        """Manejo seguro para dependencias de módulos"""
        if not self.env['ir.module.module'].search([
            ('name', '=', 'sgichs_network'),
            ('state', '=', 'installed')
        ]):
            # Opción 1: Mostrar advertencia amigable
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Módulo requerido',
                    'message': 'Instale el módulo de redes para esta función',
                    'type': 'warning',
                }
            }
            # Opción 2: No hacer nada
            return False
            
        # Si el módulo está instalado, delegar la acción
        return self.env['network.service'].browse(self.ids).ping_action()
    
    
    def action_llamar_reporte_ficha_tecnica(self):
        self.ensure_one() 
        # Es mejor referenciar la acción de reporte del módulo de reportes
        # para evitar dependencias cruzadas.
        report_action_xml_id = 'sgichs_reporting.action_report_hardware_technical_sheet'
        try:
            report_action = self.env.ref(report_action_xml_id)
            return report_action.report_action(self)
        except ValueError:
            raise UserError(_("La acción de reporte '%s' no se encuentra. Asegúrese de que el módulo de reportes esté instalado correctamente.") % report_action_xml_id)