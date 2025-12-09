from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class AlfrescoDownloadController(http.Controller):
    
    @http.route(
        "/alfresco/download/<int:document_id>",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def download_document(self, document_id, **kwargs):
        """
        Controlador HTTP para descargar documentos de Alfresco.
        No almacena el documento en Odoo, lo descarga directamente desde Alfresco
        y lo envía al navegador del usuario.
        """
        _logger.debug("Solicitud de descarga para documento ID: %d", document_id)
        
        # Buscar el documento en Odoo
        document = request.env["alfresco.task.document"].sudo().browse(document_id)
        
        if not document.exists():
            _logger.warning("Documento no encontrado: %d", document_id)
            return request.not_found()
        
        _logger.debug(
            "Descargando documento: %s (Node ID: %s)",
            document.name,
            document.node_id,
        )
        
        # Descargar el contenido desde Alfresco
        TaskModel = request.env["alfresco.task"].sudo()
        content, file_name, mime_type = TaskModel._download_document_content(document.node_id)
        
        if content is None:
            _logger.error(
                "No se pudo descargar el documento desde Alfresco: %s",
                document.node_id,
            )
            return request.not_found()
        
        # Usar el nombre del documento almacenado si está disponible
        if document.name:
            file_name = document.name
        
        _logger.debug(
            "Enviando documento al usuario - Nombre: %s, MIME: %s, Tamaño: %d bytes",
            file_name,
            mime_type,
            len(content),
        )
        
        # Crear respuesta HTTP con el contenido del documento
        headers = [
            ("Content-Type", mime_type),
            ("Content-Disposition", f'attachment; filename="{file_name}"'),
            ("Content-Length", str(len(content))),
        ]
        
        return request.make_response(content, headers=headers)
