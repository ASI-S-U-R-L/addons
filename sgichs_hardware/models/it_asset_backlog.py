# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)

class ITAssetBacklog(models.Model):
    _inherit = 'it.asset.backlog'

    components_ids = fields.Many2many(
        'it.component', 
        'backlog_component_rel', 'backlog_id', 'component_id',
        string='Componentes Detectados'
    )
    
    existing_hardware_id = fields.Many2one(
        'it.asset.hardware', string="Hardware Existente",
        compute='_compute_existing_hardware', store=False,
        help="Muestra si ya existe un activo de hardware aprobado con el mismo identificador único."
    )
    analysis_report = fields.Html(string="Informe de Análisis de Cambios", readonly=True)

    # EL MÉTODO _process_software_from_raw_data SE ELIMINA DE AQUÍ

    @api.depends('name')
    def _compute_existing_hardware(self):
        """Busca si ya existe un hardware con el mismo identificador único (Nº Inventario)."""
        for record in self:
    
            if record.name and record.type == 'hardware':
                record.existing_hardware_id = self.env['it.asset.hardware'].search([
                    ('inventory_number', '=', record.name)
                ], limit=1)
            else:
                record.existing_hardware_id = False

    def action_analyze_changes(self):
        """
        Compara el activo del backlog con el hardware existente y genera un informe HTML
        detallando las diferencias para que el usuario pueda tomar una decisión informada.
        """
        self.ensure_one()
        if not self.existing_hardware_id:
            self.analysis_report = "<div class='alert alert-info' role='alert'>Este es un <b>activo nuevo</b>. No existe un hardware aprobado con este identificador.</div>"
            return

        report_parts = ["<h3>Análisis de Cambios para Aprobación</h3>"]
        
        # --- Comparación de Componentes ---
        report_parts.append("<h4><i class='fa fa-cogs'/> Componentes</h4>")
        backlog_comps = {c.serial_number: c for c in self.components_ids if c.serial_number}
        existing_comps = {c.serial_number: c for c in self.existing_hardware_id.components_ids if c.serial_number}
        added_comps = set(backlog_comps.keys()) - set(existing_comps.keys())
        removed_comps = set(existing_comps.keys()) - set(backlog_comps.keys())
        
        if added_comps or removed_comps:
            report_parts.append("<ul>")
            for sn in added_comps: report_parts.append(f"<li><i class='fa fa-plus-circle text-success'/> <b>Añadir:</b> {backlog_comps[sn].model} (S/N: {sn})</li>")
 
            for sn in removed_comps: report_parts.append(f"<li><i class='fa fa-minus-circle text-danger'/> <b>Eliminar:</b> {existing_comps[sn].model} (S/N: {sn})</li>")
            report_parts.append("</ul>")
        else:
            report_parts.append("<p>Sin cambios detectados en componentes con número de serie.</p>")

        # --- Comparación de Software (Modular) ---
        if hasattr(self, 'software_ids') and hasattr(self.existing_hardware_id, 'software_ids'):
            report_parts.append("<h4><i class='fa fa-windows'/> Software</h4>")
            # <<< INICIO DE LA MODIFICACIÓN (SIMPLIFICACIÓN) >>>
            # Ahora usamos el campo software_ids que ya fue procesado
            backlog_sw = {s.display_name for s in self.software_ids}
            # <<< FIN DE LA MODIFICACIÓN >>>
  
            existing_sw = {s.display_name for s in self.existing_hardware_id.software_ids}
            added_sw = backlog_sw - existing_sw
            removed_sw = existing_sw - backlog_sw
            
            if added_sw or removed_sw:
                report_parts.append("<ul>")
                for s in added_sw: report_parts.append(f"<li><i class='fa fa-plus-circle text-success'/> <b>Añadir:</b> {s}</li>")
        
                for s in removed_sw: report_parts.append(f"<li><i class='fa fa-minus-circle text-danger'/> <b>Eliminar:</b> {s}</li>")
                report_parts.append("</ul>")
            else:
                report_parts.append("<p>Sin cambios detectados en el software.</p>")

        self.analysis_report = "".join(report_parts)

    def action_approve(self):
        """
        Lógica "Upsert" SIMPLIFICADA: Ahora confía en que el backlog ya tiene
        los componentes y software listos para ser transferidos.
        """
 
        self.ensure_one()
        if self.type == 'hardware':
            vals = {
                'name': self.description or self.name,
                'inventory_number': self.name,
                'description': self.raw_data,
                'components_ids': [(6, 0, self.components_ids.ids)],
            }
            
            # <<< INICIO DE LA MODIFICACIÓN (SIMPLIFICACIÓN) >>>
            # Se usa directamente el campo software_ids del backlog, que ahora se llena automáticamente
            if hasattr(self, 'software_ids'): 
                vals['software_ids'] = [(6, 0, self.software_ids.ids)]
            # <<< FIN DE LA MODIFICACIÓN >>>
            
            if hasattr(self, 'ip_ids'): 
                vals['ip_ids'] = [(6, 0, self.ip_ids.ids)]

            hardware_to_open = None
            if self.existing_hardware_id:
                _logger.info(f"Aprobación: Actualizando hardware existente (ID: {self.existing_hardware_id.id})")
                
                old_components = self.existing_hardware_id.components_ids
                new_components_from_backlog = self.components_ids
                removed_components = old_components - new_components_from_backlog
                
                if removed_components:
                    _logger.info(f"Desasociando {len(removed_components)} componente(s) del hardware ID {self.existing_hardware_id.id}")
                    removed_components.write({'hardware_id': False})

                self.existing_hardware_id.write(vals)
                hardware_to_open = self.existing_hardware_id
            else:
         
                _logger.info(f"Aprobación: Creando nuevo hardware para '{self.name}'")
                raw_data = json.loads(self.raw_data or '{}')
                vals['subtype'] = raw_data.get('subtype', 'pc')
                hardware_to_open = self.env['it.asset.hardware'].create(vals)

            if hardware_to_open and self.components_ids:
                _logger.info(f"Asignando hardware ID {hardware_to_open.id} a {len(self.components_ids)} componente(s)")
                self.components_ids.write({'hardware_id': hardware_to_open.id})

            self.unlink()
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'it.asset.hardware',
         
                'res_id': hardware_to_open.id,
                'view_mode': 'form',
                'target': 'current',
            }
        
        return super(ITAssetBacklog, self).action_approve()