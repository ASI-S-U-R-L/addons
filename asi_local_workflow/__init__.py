# -*- coding: utf-8 -*-
from . import models
from . import wizards
from . import controllers
from odoo import api, SUPERUSER_ID

def uninstall_conflicting_module(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    module_to_remove = "asi_signature_workflow"

    module = env['ir.module.module'].search([('name', '=', module_to_remove)], limit=1)
    if module and module.state == 'installed':
        module.button_uninstall()