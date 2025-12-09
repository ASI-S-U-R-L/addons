from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class AlfrescoTaskDocument(models.Model):
    _name = "alfresco.task.document"
    _description = "Documento de Tarea Alfresco"
    _rec_name = "name"

    task_id = fields.Many2one(
        "alfresco.task",
        string="Tarea",
        required=True,
        ondelete="cascade",
        index=True,
        readonly=False,
    )
    node_id = fields.Char(
        string="Node ID Alfresco",
        required=True,
        help="Identificador único del nodo/documento en Alfresco",
        readonly=False,
    )
    name = fields.Char(string="Nombre", required=True, readonly=False)
    mime_type = fields.Char(string="Tipo MIME", readonly=False)
    size = fields.Integer(string="Tamaño (bytes)", readonly=False)
    created_by = fields.Char(string="Creado por", readonly=False)
    created_at = fields.Datetime(string="Fecha Creación", readonly=False)
    modified_by = fields.Char(string="Modificado por", readonly=False)
    modified_at = fields.Datetime(string="Fecha Modificación", readonly=False)

    _sql_constraints = [
        (
            "task_node_unique",
            "UNIQUE(task_id, node_id)",
            "El documento ya está asociado a esta tarea.",
        )
    ]

    def action_download(self):
        """
        Acción para descargar el documento desde Alfresco.
        Retorna una URL de descarga que pasa por el controlador del módulo.
        """
        self.ensure_one()
        _logger.debug(
            "Iniciando descarga de documento: %s (Node ID: %s)",
            self.name,
            self.node_id,
        )
        
        return {
            "type": "ir.actions.act_url",
            "url": f"/alfresco/download/{self.id}",
            "target": "new",
        }
