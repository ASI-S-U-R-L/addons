from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    alfresco_user = fields.Char(
        string="Usuario Alfresco",
        help="Nombre de usuario en Alfresco para mapear tareas. "
             "Debe coincidir exactamente con el campo 'assignee' de las tareas en Alfresco.",
    )
