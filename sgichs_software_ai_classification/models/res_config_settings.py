from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_software_ai_classification = fields.Boolean(
        string="Activar Clasificación Automática de Software con IA",
        config_parameter="sgichs_software_ai_classification.enable",
        help="Habilita la clasificación automática de software no catalogado usando IA."
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        IrConfig = self.env['ir.config_parameter'].sudo()
        res.update(
            enable_software_ai_classification=IrConfig.get_param('sgichs_software_ai_classification.enable', 'False') == 'True',
        )
        return res

    def set_values(self):
        super().set_values()
        IrConfig = self.env['ir.config_parameter'].sudo()
        IrConfig.set_param('sgichs_software_ai_classification.enable', str(self.enable_software_ai_classification))