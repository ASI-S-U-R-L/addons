# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    versat_api_base_url = fields.Char(
        string='URL Base API Versat',
        config_parameter='licencia_versat.api_base_url',
        default='https://comercializador.versat.cu',
    )
    versat_api_username = fields.Char(
        string='Usuario API',
        config_parameter='licencia_versat.api_username',
    )
    versat_api_password = fields.Char(
        string='Contraseña API',
        config_parameter='licencia_versat.api_password',
    )
