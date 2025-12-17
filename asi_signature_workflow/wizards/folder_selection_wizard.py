# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class FolderSelectionWizard(models.TransientModel):
    _name = 'folder.selection.wizard'
    _description = 'Asistente para Selección de Carpeta de Alfresco'

    # Referencia al wizard principal
    workflow_wizard_id = fields.Many2one(
        'signature.workflow.wizard', 
        string='Wizard Principal',
        ondelete='cascade'
    )
    
    # Carpeta seleccionada
    selected_folder_id = fields.Many2one(
        'alfresco.folder', 
        string='Carpeta Seleccionada'
    )
    selected_folder_path = fields.Char(
        string='Ruta Seleccionada', 
        compute='_compute_selected_folder_path'
    )
    
    # Navegación de carpetas
    current_folder_id = fields.Many2one('alfresco.folder', string='Carpeta Actual')
    folder_path = fields.Char(string='Ruta Actual', compute='_compute_folder_path')
    parent_folder_id = fields.Many2one(
        'alfresco.folder', 
        string='Carpeta Padre', 
        compute='_compute_parent_folder'
    )
    child_folder_ids = fields.Many2many(
        'alfresco.folder', 
        string='Subcarpetas',
        compute='_compute_child_folders'
    )

    @api.depends('selected_folder_id')
    def _compute_selected_folder_path(self):
        for record in self:
            if record.selected_folder_id:
                record.selected_folder_path = record.selected_folder_id.complete_path or record.selected_folder_id.name
            else:
                record.selected_folder_path = ''

    @api.depends('current_folder_id')
    def _compute_folder_path(self):
        for record in self:
            if record.current_folder_id:
                record.folder_path = record.current_folder_id.complete_path or '/'
            else:
                record.folder_path = '/'

    @api.depends('current_folder_id')
    def _compute_parent_folder(self):
        for record in self:
            if record.current_folder_id and record.current_folder_id.parent_id:
                record.parent_folder_id = record.current_folder_id.parent_id
            else:
                record.parent_folder_id = False

    @api.depends('current_folder_id')
    def _compute_child_folders(self):
        for record in self:
            if record.current_folder_id:
                record.child_folder_ids = record.current_folder_id.child_ids
            else:
                # Mostrar carpetas raíz
                root_folders = self.env['alfresco.folder'].search([('parent_id', '=', False)])
                record.child_folder_ids = root_folders

    @api.model
    def default_get(self, fields_list):
        """Valores por defecto"""
        res = super(FolderSelectionWizard, self).default_get(fields_list)
        
        # Si no hay carpeta actual, usar la primera carpeta raíz disponible
        if 'current_folder_id' in fields_list and not res.get('current_folder_id'):
            root_folder = self.env['alfresco.folder'].search([('parent_id', '=', False)], limit=1)
            if root_folder:
                res['current_folder_id'] = root_folder.id
        
        return res

    def action_navigate_to_folder(self):
        """Navega a una carpeta específica desde el contexto"""
        self.ensure_one()
        folder_id = self.env.context.get('active_id')
        if folder_id:
            _logger.info("[FOLDER_SELECT] Navigating to folder ID: %s", folder_id)
            folder = self.env['alfresco.folder'].browse(folder_id)
            if folder.exists():
                self.current_folder_id = folder
                _logger.info("[FOLDER_SELECT] Successfully navigated to folder: %s", folder.name)
        return self._reload_wizard()

    def action_go_to_parent(self):
        """Navega a la carpeta padre"""
        self.ensure_one()
        if self.parent_folder_id:
            self.current_folder_id = self.parent_folder_id
        else:
            self.current_folder_id = False
        return self._reload_wizard()

    def action_go_to_root(self):
        """Navega a la carpeta raíz"""
        self.ensure_one()
        self.current_folder_id = False
        return self._reload_wizard()

    def action_select_current_folder(self):
        """Selecciona la carpeta actual como destino"""
        self.ensure_one()
        
        if not self.current_folder_id:
            raise UserError(_('Debe navegar a una carpeta para seleccionarla.'))
        
        self.selected_folder_id = self.current_folder_id
        _logger.info("[FOLDER_SELECT] Selected folder: %s (ID: %s)", 
                    self.current_folder_id.name, self.current_folder_id.id)
        
        return self._reload_wizard()

    def action_select_folder_from_list(self):
        """Selecciona una carpeta de la lista y navega a ella"""
        self.ensure_one()
        folder_id = self.env.context.get('active_id')
        
        if folder_id:
            folder = self.env['alfresco.folder'].browse(folder_id)
            if folder.exists():
                # Seleccionar y navegar a esta carpeta
                self.write({
                    'selected_folder_id': folder.id,
                    'current_folder_id': folder.id,
                })
                _logger.info("[FOLDER_SELECT] Selected and navigated to folder: %s (ID: %s)", 
                            folder.name, folder.id)
        
        return self._reload_wizard()

    def action_confirm_selection(self):
        """Confirma la selección y regresa al wizard principal"""
        self.ensure_one()
        
        if not self.selected_folder_id:
            raise UserError(_('Debe seleccionar una carpeta de destino.'))
        
        # Actualizar el wizard principal con la carpeta seleccionada
        if self.workflow_wizard_id:
            self.workflow_wizard_id.write({
                'destination_folder_id': self.selected_folder_id.id,
            })
            
            _logger.info("[FOLDER_SELECT] Updated workflow wizard with destination folder: %s", 
                        self.selected_folder_id.name)
            
            # Regresar al wizard principal
            return {
                'type': 'ir.actions.act_window',
                'name': 'Iniciar Solicitud de Firma',
                'res_model': 'signature.workflow.wizard',
                'res_id': self.workflow_wizard_id.id,
                'view_mode': 'form',
                'target': 'new',
            }
        
        return {'type': 'ir.actions.act_window_close'}

    def action_clear_selection(self):
        """Limpia la selección actual"""
        self.ensure_one()
        self.selected_folder_id = False
        return self._reload_wizard()

    def _reload_wizard(self):
        """Recarga el wizard actual"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Seleccionar Carpeta de Destino',
            'res_model': 'folder.selection.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
