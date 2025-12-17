from odoo import models, api

class AlfrescoFolderExtension(models.Model):
    _inherit = 'alfresco.folder'
    
    def action_navigate_to_folder_wizard(self):
        """Navigate to this folder in the PDF selection wizard"""
        self.ensure_one()
        
        # Get the wizard from context
        wizard_id = self.env.context.get('wizard_id')
        if not wizard_id:
            # Try to find an active wizard
            wizard = self.env['pdf.selection.wizard'].search([
                ('selection_type', '=', 'alfresco')
            ], limit=1)
            if wizard:
                wizard_id = wizard.id
        
        if wizard_id:
            wizard = self.env['pdf.selection.wizard'].browse(wizard_id)
            if wizard.exists():
                # Call the wizard's navigation method
                wizard.action_navigate_to_folder(self.id)
                
                # Return action to refresh the wizard view
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'pdf.selection.wizard',
                    'res_id': wizard_id,
                    'view_mode': 'form',
                    'target': 'new',
                    'context': self.env.context,
                }
        
        return {'type': 'ir.actions.do_nothing'}
    
    def action_navigate_to_folder_selection_wizard(self):
        """Navigate to this folder in the folder selection wizard"""
        self.ensure_one()
        
        wizard_id = self.env.context.get('wizard_id')
        if not wizard_id:
            # Try to find an active folder selection wizard
            wizard = self.env['folder.selection.wizard'].search([], limit=1, order='id desc')
            if wizard:
                wizard_id = wizard.id
        
        if wizard_id:
            wizard = self.env['folder.selection.wizard'].browse(wizard_id)
            if wizard.exists():
                # Update the current folder in the wizard
                wizard.write({'current_folder_id': self.id})
                
                # Return action to refresh the wizard view
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'folder.selection.wizard',
                    'res_id': wizard_id,
                    'view_mode': 'form',
                    'target': 'new',
                    'context': dict(self.env.context, wizard_id=wizard_id),
                }
        
        return {'type': 'ir.actions.do_nothing'}
    
    def action_select_folder_from_list(self):
        """Select this folder and navigate to it in the folder selection wizard"""
        self.ensure_one()
        
        wizard_id = self.env.context.get('wizard_id')
        if not wizard_id:
            # Try to find an active folder selection wizard
            wizard = self.env['folder.selection.wizard'].search([], limit=1, order='id desc')
            if wizard:
                wizard_id = wizard.id
        
        if wizard_id:
            wizard = self.env['folder.selection.wizard'].browse(wizard_id)
            if wizard.exists():
                # Select this folder and navigate to it
                wizard.write({
                    'selected_folder_id': self.id,
                    'current_folder_id': self.id,
                })
                
                # Return action to refresh the wizard view
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'folder.selection.wizard',
                    'res_id': wizard_id,
                    'view_mode': 'form',
                    'target': 'new',
                    'context': dict(self.env.context, wizard_id=wizard_id),
                }
        
        return {'type': 'ir.actions.do_nothing'}
