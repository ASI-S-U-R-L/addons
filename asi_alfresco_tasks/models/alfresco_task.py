from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date, datetime
import requests
import logging
import re

_logger = logging.getLogger(__name__)


class AlfrescoTask(models.Model):
    _name = "alfresco.task"
    _description = "Tarea de Alfresco"
    _rec_name = "display_name"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "state, priority desc, due_at"

    alfresco_task_id = fields.Char(
        string="ID Tarea Alfresco",
        required=True,
        index=True,
        help="Identificador único de la tarea en Alfresco",
    )
    name = fields.Char(string="Nombre", required=True)
    description = fields.Text(string="Descripción")
    assignee = fields.Char(string="Asignado (Alfresco)")
    state = fields.Char(
        string="Estado",
        default="unclaimed",
        index=True,
    )
    state_display = fields.Char(
        string="Estado Display",
        compute="_compute_state_display",
        store=True,
    )
    
    # Nuevo campo para indicar si la tarea fue rechazada
    is_rejected = fields.Boolean(
        string="Rechazada",
        default=False,
        help="Indica si la tarea ha sido rechazada en Alfresco (basado en activityDefinitionId, formResourceKey, name o description)",
    )
    
    priority = fields.Integer(string="Prioridad")
    process_id = fields.Char(string="ID Proceso")
    process_definition_id = fields.Char(string="Definición de Proceso")
    activity_definition_id = fields.Char(string="ID Definición Actividad")
    form_resource_key = fields.Char(string="Clave Recurso Formulario")
    started_at = fields.Datetime(string="Fecha Inicio")
    due_at = fields.Datetime(string="Fecha Vencimiento")
    user_id = fields.Many2one("res.users", string="Usuario Odoo")
    
    display_name = fields.Char(
        string="Nombre Completo",
        compute="_compute_display_name",
        store=True,
    )
    
    is_completed = fields.Boolean(
        string="Completada en Odoo",
        default=False,
        help="Indica si la tarea fue procesada desde Odoo",
    )
    
    document_ids = fields.One2many(
        "alfresco.task.document",
        "task_id",
        string="Documentos",
    )
    document_count = fields.Integer(
        string="Cantidad de Documentos",
        compute="_compute_document_count",
        store=True,
    )
    
    _sql_constraints = [
        (
            "alfresco_task_id_unique",
            "UNIQUE(alfresco_task_id)",
            "El ID de tarea de Alfresco debe ser único.",
        )
    ]

    # =========================================================================
    # CAMPOS COMPUTADOS
    # =========================================================================

    @api.depends("document_ids")
    def _compute_document_count(self):
        for task in self:
            task.document_count = len(task.document_ids)

    @api.depends("name", "description", "process_id", "assignee")
    def _compute_display_name(self):
        """Genera un nombre más descriptivo para la tarea."""
        for task in self:
            parts = [task.name or "Tarea"]
            if task.description:
                desc_short = task.description[:50]
                if len(task.description) > 50:
                    desc_short += "..."
                parts.append(f"- {desc_short}")
            task.display_name = " ".join(parts)

    @api.depends("state")
    def _compute_state_display(self):
        """Genera el texto de display para el estado."""
        state_labels = {
            "unclaimed": "Sin Reclamar",
            "claimed": "Reclamada",
            "completed": "Completada",
            "resolved": "Resuelta",
        }
        for task in self:
            task.state_display = state_labels.get(task.state, task.state or "Desconocido")

    # =========================================================================
    # MÉTODOS PARA DETECTAR TAREAS RECHAZADAS
    # =========================================================================

    def _detectar_si_es_rechazada(self, task_data):
        """
        Detecta si una tarea es rechazada basándose en varios campos.
        Retorna True si encuentra 'rejected' o 'rechazado' en los campos relevantes.
        """
        # Campos a verificar
        campos_a_verificar = [
            task_data.get("activityDefinitionId", ""),
            task_data.get("formResourceKey", ""),
            task_data.get("name", ""),
            task_data.get("description", ""),
            task_data.get("state", ""),  # Añadir estado para detectar tareas completadas
        ]
        
        # Convertir todo a minúsculas para una búsqueda insensible a mayúsculas
        texto_completo = " ".join(str(campo) for campo in campos_a_verificar).lower()
        
        # Palabras clave que indican rechazo (en español e inglés)
        palabras_rechazo = [
            'rejected', 
            'rechazado', 
            'rechazada', 
            'denied', 
            'rejectedtask', 
            'reject',
            'canceled',
            'cancelled',
            'anulado',
            'anulada'
        ]
        
        # Verificar si alguna palabra de rechazo está en el texto
        for palabra in palabras_rechazo:
            if palabra in texto_completo:
                _logger.debug(
                    "Tarea %s detectada como rechazada por palabra clave: %s",
                    task_data.get("id"),
                    palabra,
                )
                return True
        
        # También considerar tareas con estado "completed" como posiblemente rechazadas
        # si tienen ciertos patrones en el nombre o descripción
        if task_data.get("state") == "completed":
            # Verificar patrones específicos en nombre o descripción
            nombre_desc = f"{task_data.get('name', '')} {task_data.get('description', '')}".lower()
            patrones_rechazo = ['rech', 'cancel', 'deny', 'reject']
            
            for patron in patrones_rechazo:
                if patron in nombre_desc:
                    _logger.debug(
                        "Tarea %s detectada como rechazada (completada con patrón: %s)",
                        task_data.get("id"),
                        patron,
                    )
                    return True
        
        return False

    # =========================================================================
    # ACCIONES DE BOTONES
    # =========================================================================

    def action_sign(self):
        """
        Acción para firmar la tarea.
        Abre el wizard de firma digital de documentos.
        """
        self.ensure_one()

        _logger.info(
            "Acción de firma iniciada para tarea: %s",
            self.alfresco_task_id,
        )

        if self.is_completed:
            raise UserError("Esta tarea ya ha sido procesada.")

        # Verificar si la tarea está rechazada
        if self.is_rejected:
            raise UserError("Esta tarea ha sido rechazada y no puede ser firmada.")

        # Verificar que haya documentos para firmar
        if not self.document_ids:
            raise UserError("Esta tarea no tiene documentos para firmar. Use el botón 'Completar' o 'Rechazar' para procesarla.")

        # Abrir el wizard de firma
        return {
            'type': 'ir.actions.act_window',
            'name': 'Firmar Documentos de Tarea',
            'res_model': 'alfresco.task.firma.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_task_id': self.id,
                'active_id': self.id,
            },
        }

    def action_reject(self):
        """
        Acción para rechazar la tarea.
        Actualiza el estado de la tarea en Odoo y en Alfresco.
        """
        self.ensure_one()
        
        _logger.info(
            "Acción de rechazo iniciada para tarea: %s",
            self.alfresco_task_id,
        )
        
        if self.is_completed:
            raise UserError("Esta tarea ya ha sido procesada.")
        
        if self.is_rejected:
            raise UserError("Esta tarea ya ha sido rechazada.")
        
        # Obtener configuración de Alfresco
        url, user, pwd = self._get_alfresco_config()
        
        if not url or not user or not pwd:
            raise UserError('Configuración de Alfresco incompleta')
        
        # Endpoint para actualizar el estado de la tarea en Alfresco
        # Según la API de Alfresco (PDF página 22-24), se usa PUT /tasks/{taskId} con ?select=state
        task_endpoint = f"{url.rstrip('/')}/alfresco/api/-default-/public/workflow/versions/1/tasks/{self.alfresco_task_id}?select=state"
        
        _logger.debug(
            "Actualizando estado de tarea %s a 'completed' en Alfresco (rechazo)",
            self.alfresco_task_id,
        )
        
        try:
            response = requests.put(
                task_endpoint,
                auth=(user, pwd),
                json={"state": "completed"},
                timeout=30,
                allow_redirects=False,
            )
            
            _logger.debug(
                "Respuesta de actualización de tarea (rechazo) - Código: %d",
                response.status_code,
            )
            
            if response.status_code in [200, 201]:
                # Actualizar el estado de la tarea en Odoo
                self.write({
                    'state': 'completed',
                    'is_completed': True,
                    'is_rejected': True,  # Marcar como rechazada
                })
                
                # Marcar actividades como realizadas (procesadas)
                self._mark_activities_done()
                
                _logger.info(
                    "Tarea %s marcada como rechazada en Alfresco y Odoo",
                    self.alfresco_task_id,
                )
                
                # Mostrar mensaje de confirmación
                message = "Tarea rechazada correctamente. El estado se ha actualizado en Alfresco."
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Tarea Rechazada',
                        'message': message,
                        'type': 'success',
                        'sticky': False,
                        'next': {
                            'type': 'ir.actions.client',
                            'tag': 'reload',
                        }
                    }
                }
            else:
                _logger.error(
                    "Error al actualizar tarea %s (rechazo). Código: %d, Respuesta: %s",
                    self.alfresco_task_id,
                    response.status_code,
                    response.text,
                )
                raise UserError('Error al actualizar la tarea en Alfresco. Código: %d' % response.status_code)
                
        except requests.exceptions.RequestException as e:
            _logger.error(
                "Error de conexión al actualizar tarea %s (rechazo): %s",
                self.alfresco_task_id,
                str(e),
            )
            raise UserError('Error de conexión al actualizar la tarea en Alfresco: %s' % str(e))

    def action_complete(self):
        """
        Acción para completar una tarea rechazada.
        Actualiza el estado de la tarea en Odoo y en Alfresco a 'completed'.
        """
        self.ensure_one()
        
        _logger.info(
            "Acción de completar iniciada para tarea rechazada: %s",
            self.alfresco_task_id,
        )
        
        if not self.is_rejected:
            raise UserError("Esta tarea no está rechazada. Use el botón 'Firmar' para completar tareas normales.")
        
        if self.is_completed:
            raise UserError("Esta tarea ya ha sido completada.")
        
        # Obtener configuración de Alfresco
        url, user, pwd = self._get_alfresco_config()
        
        if not url or not user or not pwd:
            raise UserError('Configuración de Alfresco incompleta')
        
        # Endpoint para actualizar el estado de la tarea en Alfresco
        task_endpoint = f"{url.rstrip('/')}/alfresco/api/-default-/public/workflow/versions/1/tasks/{self.alfresco_task_id}?select=state"
        
        _logger.debug(
            "Actualizando estado de tarea rechazada %s a 'completed' en Alfresco",
            self.alfresco_task_id,
        )
        
        try:
            response = requests.put(
                task_endpoint,
                auth=(user, pwd),
                json={"state": "completed"},
                timeout=30,
                allow_redirects=False,
            )
            
            _logger.debug(
                "Respuesta de actualización de tarea (completar) - Código: %d",
                response.status_code,
            )
            
            if response.status_code in [200, 201]:
                # Actualizar el estado de la tarea en Odoo
                # Mantener is_rejected=True porque fue rechazada anteriormente
                self.write({
                    'state': 'completed',
                    'is_completed': True,
                })
                
                # Marcar actividades como realizadas (procesadas)
                self._mark_activities_done()
                
                _logger.info(
                    "Tarea rechazada %s marcada como completada en Alfresco y Odoo",
                    self.alfresco_task_id,
                )
                
                # Mostrar mensaje de confirmación
                message = "Tarea rechazada marcada como completada correctamente. El estado se ha actualizado en Alfresco."
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Tarea Completada',
                        'message': message,
                        'type': 'success',
                        'sticky': False,
                        'next': {
                            'type': 'ir.actions.client',
                            'tag': 'reload',
                        }
                    }
                }
            else:
                _logger.error(
                    "Error al actualizar tarea %s (completar). Código: %d, Respuesta: %s",
                    self.alfresco_task_id,
                    response.status_code,
                    response.text,
                )
                raise UserError('Error al actualizar la tarea en Alfresco. Código: %d' % response.status_code)
                
        except requests.exceptions.RequestException as e:
            _logger.error(
                "Error de conexión al actualizar tarea %s (completar): %s",
                self.alfresco_task_id,
                str(e),
            )
            raise UserError('Error de conexión al actualizar la tarea en Alfresco: %s' % str(e))

    def _mark_activities_done(self):
        """Marca todas las actividades pendientes de esta tarea como realizadas."""
        self.ensure_one()
        for activity in self.activity_ids:
            activity.action_feedback(feedback="Tarea procesada desde Odoo")
        _logger.debug(
            "Actividades marcadas como realizadas para tarea %s",
            self.alfresco_task_id,
        )
    
    def _crear_actividad_rechazada(self):
        """
        Crea una actividad para tareas rechazadas con fecha de vencimiento para el día actual.
        """
        self.ensure_one()

        # Buscar tipo de actividad para tareas rechazadas
        activity_type = self.env["mail.activity.type"].search(
            [("name", "=", "Tarea Rechazada")],
            limit=1,
        )

        if not activity_type:
            # Crear tipo de actividad para tareas rechazadas
            activity_type = self.env["mail.activity.type"].sudo().create({
                "name": "Tarea Rechazada",
                "summary": "Tarea rechazada en Alfresco",
                "icon": "fa-times-circle",
                "delay_count": 0,
            })
            _logger.info("Tipo de actividad 'Tarea Rechazada' creado")

        # Crear actividad con fecha de vencimiento para hoy
        self.env["mail.activity"].sudo().create({
            "activity_type_id": activity_type.id,
            "res_model_id": self.env["ir.model"]._get("alfresco.task").id,
            "res_id": self.id,
            "user_id": self.user_id.id,
            "date_deadline": date.today(),
            "summary": f"[RECHAZADA] {self.name}",
            "note": self.description or "Tarea rechazada en Alfresco",
        })

        _logger.debug(
            "Actividad de rechazo creada para tarea %s",
            self.alfresco_task_id,
        )

    # =========================================================================
    # MÉTODOS PARA DESCARGAR DOCUMENTOS
    # =========================================================================

    @api.model
    def _download_document_content(self, node_id):
        """
        Descarga el contenido de un documento desde Alfresco por su node_id.
        Retorna una tupla (contenido, nombre_archivo, tipo_mime) o (None, None, None) en caso de error.
        """
        url, user, pwd = self._get_alfresco_config()
        
        if not url or not user or not pwd:
            _logger.warning("Configuración de Alfresco incompleta")
            return None, None, None
        
        # Endpoint para descargar contenido de un nodo
        download_endpoint = f"{url.rstrip('/')}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}/content"
        
        _logger.debug(
            "Descargando contenido del nodo: %s desde: %s",
            node_id,
            download_endpoint,
        )
        
        try:
            response = requests.get(
                download_endpoint,
                auth=(user, pwd),
                timeout=30,
                allow_redirects=False,
            )
            
            _logger.debug(
                "Respuesta de descarga - Código: %d",
                response.status_code,
            )
            
            if response.status_code == 200:
                # Obtener el nombre del archivo del header Content-Disposition
                content_disposition = response.headers.get('Content-Disposition', '')
                file_name = 'documento.pdf'
                
                if 'filename=' in content_disposition:
                    file_name = content_disposition.split('filename=')[-1].strip('"\'')
                elif 'filename*=' in content_disposition:
                    # Manejar filename* con encoding
                    match = re.search(r"filename\*=[^']*'[^']*'([^;]+)", content_disposition)
                    if match:
                        file_name = match.group(1)
                
                mime_type = response.headers.get('Content-Type', 'application/octet-stream')
                content = response.content
                
                _logger.debug(
                    "Documento descargado: %s, tamaño: %d bytes, MIME: %s",
                    file_name,
                    len(content),
                    mime_type,
                )
                
                return content, file_name, mime_type
            else:
                _logger.error(
                    "Error al descargar nodo %s. Código: %d, Respuesta: %s",
                    node_id,
                    response.status_code,
                    response.text[:200] if response.text else "Sin texto",
                )
                return None, None, None
                
        except requests.exceptions.RequestException as e:
            _logger.error(
                "Error de conexión al descargar nodo %s: %s",
                node_id,
                str(e),
            )
            return None, None, None

    # =========================================================================
    # MÉTODOS PÚBLICOS DE ACCESO SIMPLIFICADO
    # =========================================================================

    @api.model
    def sync_tasks(self):
        """
        Método público para sincronizar tareas de Alfresco.
        """
        _logger.info("Sincronización manual de tareas iniciada")
        return self._execute_sync()

    @api.model
    def get_user_tasks(self, user_id=None):
        """
        Obtiene las tareas de Alfresco para un usuario específico o el usuario actual.
        """
        if not user_id:
            user_id = self.env.uid
        
        tasks = self.search([("user_id", "=", user_id)])
        _logger.debug(
            "Obtenidas %d tareas para usuario ID: %d",
            len(tasks),
            user_id,
        )
        return tasks

    @api.model
    def get_sync_stats(self):
        """
        Obtiene estadísticas de las tareas sincronizadas.
        """
        total_tasks = self.search_count([])
        tasks_with_activity = self.search_count([("activity_ids", "!=", False)])
        users_with_tasks = len(self.read_group([], ["user_id"], ["user_id"]))
        rejected_tasks = self.search_count([("is_rejected", "=", True)])
        
        stats = {
            "total_tasks": total_tasks,
            "tasks_with_activity": tasks_with_activity,
            "tasks_without_activity": total_tasks - tasks_with_activity,
            "users_with_tasks": users_with_tasks,
            "rejected_tasks": rejected_tasks,
        }
        
        _logger.debug("Estadísticas de sincronización: %s", stats)
        return stats

    # =========================================================================
    # MÉTODOS PRIVADOS DE CONFIGURACIÓN Y OBTENCIÓN DE DATOS
    # =========================================================================

    @api.model
    def _parse_alfresco_datetime(self, datetime_str):
        """
        Convierte una fecha ISO 8601 de Alfresco al formato de Odoo.
        """
        if not datetime_str:
            return False
        
        try:
            match = re.match(r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})', datetime_str)
            if match:
                date_part = match.group(1)
                time_part = match.group(2)
                odoo_datetime = f"{date_part} {time_part}"
                _logger.debug(
                    "Fecha parseada: %s -> %s",
                    datetime_str,
                    odoo_datetime,
                )
                return odoo_datetime
            else:
                _logger.warning(
                    "Formato de fecha no reconocido: %s",
                    datetime_str,
                )
                return False
                
        except Exception as e:
            _logger.warning(
                "Error al parsear fecha '%s': %s",
                datetime_str,
                str(e),
            )
            return False

    @api.model
    def _get_alfresco_config(self):
        """Obtiene la configuración de conexión a Alfresco desde los parámetros del sistema."""
        config = self.env["ir.config_parameter"].sudo()
        url = config.get_param("asi_alfresco_integration.alfresco_server_url")
        user = config.get_param("asi_alfresco_integration.alfresco_username")
        pwd = config.get_param("asi_alfresco_integration.alfresco_password")
        
        _logger.debug(
            "Configuración Alfresco obtenida - URL: %s, Usuario: %s",
            url,
            user,
        )
        
        return url, user, pwd

    @api.model
    def _fetch_alfresco_tasks(self):
        """
        Obtiene todas las tareas desde la API de Alfresco.
        """
        url, user, pwd = self._get_alfresco_config()
        
        if not url or not user or not pwd:
            _logger.warning(
                "Configuración de Alfresco incompleta. "
                "Verifique URL, usuario y contraseña en Ajustes."
            )
            return []

        tasks_endpoint = f"{url}/alfresco/api/-default-/public/workflow/versions/1/tasks"
        all_tasks = []
        skip_count = 0
        max_items = 100
        has_more = True

        _logger.debug("Iniciando obtención de tareas desde Alfresco: %s", tasks_endpoint)

        while has_more:
            try:
                params = {
                    "skipCount": skip_count,
                    "maxItems": max_items,
                }
                
                _logger.debug(
                    "Solicitando tareas - skipCount: %d, maxItems: %d",
                    skip_count,
                    max_items,
                )
                
                response = requests.get(
                    tasks_endpoint,
                    auth=(user, pwd),
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()
                
                data = response.json()
                entries = data.get("list", {}).get("entries", [])
                pagination = data.get("list", {}).get("pagination", {})
                
                _logger.debug(
                    "Respuesta recibida - Tareas en esta página: %d, Total: %d",
                    len(entries),
                    pagination.get("totalItems", 0),
                )
                
                for entry in entries:
                    task_data = entry.get("entry", {})
                    all_tasks.append(task_data)
                
                has_more = pagination.get("hasMoreItems", False)
                skip_count += max_items
                
            except requests.exceptions.RequestException as e:
                _logger.error(
                    "Error al obtener tareas de Alfresco: %s",
                    str(e),
                )
                break

        _logger.info("Total de tareas obtenidas de Alfresco: %d", len(all_tasks))
        return all_tasks

    @api.model
    def _get_users_with_alfresco_mapping(self):
        """
        Obtiene un diccionario de usuarios que tienen configurado su alfresco_user.
        Retorna: {alfresco_user: res.users record}
        """
        users = self.env["res.users"].search([
            ("alfresco_user", "!=", False),
            ("alfresco_user", "!=", ""),
        ])
        
        mapping = {user.alfresco_user: user for user in users}
        
        _logger.debug(
            "Usuarios con mapeo Alfresco: %s",
            list(mapping.keys()),
        )
        
        return mapping

    @api.model
    def _get_activity_type(self):
        """Obtiene o crea el tipo de actividad para tareas de Alfresco."""
        activity_type = self.env.ref(
            "asi_alfresco_tasks.mail_activity_type_alfresco_task",
            raise_if_not_found=False,
        )
        
        if not activity_type:
            activity_type = self.env["mail.activity.type"].search(
                [("name", "=", "Tarea Alfresco")],
                limit=1,
            )
        
        if not activity_type:
            activity_type = self.env["mail.activity.type"].sudo().create({
                "name": "Tarea Alfresco",
                "summary": "Tarea sincronizada desde Alfresco",
                "icon": "fa-tasks",
                "delay_count": 0,
            })
            _logger.info("Tipo de actividad 'Tarea Alfresco' creado")
        
        return activity_type

    def _create_or_update_task_with_activity(self, task_data, odoo_user):
        """
        Crea o actualiza una tarea de Alfresco en Odoo y le asigna una actividad.
        """
        alfresco_task_id = task_data.get("id")

        existing_task = self.search([
            ("alfresco_task_id", "=", alfresco_task_id)
        ], limit=1)

        # Detectar si la tarea es rechazada
        is_rejected = self._detectar_si_es_rechazada(task_data)

        # Obtener el estado actual de Alfresco
        alfresco_state = task_data.get("state", "unclaimed")

        # Determinar si la tarea está completada en Alfresco
        is_completed_in_alfresco = alfresco_state == "completed"

        # Preparar valores de la tarea
        task_vals = {
            "alfresco_task_id": alfresco_task_id,
            "name": task_data.get("name", "Sin nombre"),
            "description": task_data.get("description", ""),
            "assignee": task_data.get("assignee"),
            "state": alfresco_state,
            "priority": task_data.get("priority", 0),
            "process_id": task_data.get("processId"),
            "process_definition_id": task_data.get("processDefinitionId"),
            "activity_definition_id": task_data.get("activityDefinitionId"),
            "form_resource_key": task_data.get("formResourceKey"),
            "started_at": self._parse_alfresco_datetime(task_data.get("startedAt")),
            "due_at": self._parse_alfresco_datetime(task_data.get("dueAt")),
            "user_id": odoo_user.id,
            "is_rejected": is_rejected,
        }

        # Si la tarea está completada en Alfresco, actualizar is_completed en Odoo
        if is_completed_in_alfresco:
            task_vals["is_completed"] = True
            _logger.debug(
                "Tarea %s está completada en Alfresco, marcando como completada en Odoo",
                alfresco_task_id,
            )

        if existing_task:
            # Si la tarea ya existe, actualizar sus valores
            # Pero mantener is_completed si ya estaba completada en Odoo y no está completada en Alfresco
            if not is_completed_in_alfresco and existing_task.is_completed:
                # No sobrescribir is_completed si ya estaba completada en Odoo
                del task_vals["is_completed"]
                _logger.debug(
                    "Manteniendo estado completado en Odoo para tarea %s",
                    alfresco_task_id,
                )

            existing_task.write(task_vals)
            task = existing_task
            _logger.debug(
                "Tarea actualizada: %s para usuario %s (rechazada: %s, estado Alfresco: %s)",
                alfresco_task_id,
                odoo_user.name,
                is_rejected,
                alfresco_state,
            )
        else:
            task = self.create(task_vals)
            _logger.debug(
                "Tarea creada: %s para usuario %s (rechazada: %s, estado Alfresco: %s)",
                alfresco_task_id,
                odoo_user.name,
                is_rejected,
                alfresco_state,
            )

        # Crear actividad solo si la tarea no está completada, no está rechazada
        # y no está ya en estado 'completed' en Alfresco
        if (not task.is_completed and 
            task.state != "completed" and 
            not task.is_rejected):

            existing_activity = self.env["mail.activity"].search([
                ("res_model", "=", "alfresco.task"),
                ("res_id", "=", task.id),
                ("user_id", "=", odoo_user.id),
            ], limit=1)

            if not existing_activity:
                activity_type = self._get_activity_type()

                # Determinar el tipo de actividad basado en si hay documentos
                if task.document_count > 0:
                    summary = f"[FIRMAR] {task.name}"
                else:
                    summary = f"[PROCESAR] {task.name}"

                self.env["mail.activity"].sudo().create({
                    "activity_type_id": activity_type.id,
                    "res_model_id": self.env["ir.model"]._get("alfresco.task").id,
                    "res_id": task.id,
                    "user_id": odoo_user.id,
                    "date_deadline": date.today(),
                    "summary": summary[:100],
                    "note": task.description or "",
                })

                _logger.debug(
                    "Actividad creada para tarea %s, usuario %s",
                    alfresco_task_id,
                    odoo_user.name,
                )
        elif task.is_rejected and not task.is_completed:
            # Si la tarea está rechazada pero no completada, crear actividad de rechazo
            # Solo si no hay una actividad existente de rechazo
            existing_reject_activity = self.env["mail.activity"].search([
                ("res_model", "=", "alfresco.task"),
                ("res_id", "=", task.id),
                ("summary", "ilike", "[RECHAZADA]"),
            ], limit=1)

            if not existing_reject_activity:
                self._crear_actividad_rechazada()
                _logger.debug(
                    "Actividad de rechazo creada para tarea %s",
                    alfresco_task_id,
                )
        elif task.is_rejected or task.state == "completed":
            # Si la tarea está rechazada o completada en Alfresco,
            # marcar cualquier actividad existente como realizada
            task._mark_activities_done()
            _logger.debug(
                "Actividades marcadas como realizadas para tarea %s (rechazada/completada)",
                alfresco_task_id,
            )

        # Sincronizar documentos solo si la tarea no está completada
        if not task.is_completed:
            task._sync_task_documents()
        else:
            _logger.debug(
                "Omitiendo sincronización de documentos para tarea completada %s",
                alfresco_task_id,
            )

        return task

    def _sync_task_documents(self):
        """
        Sincroniza los documentos (items) de la tarea desde Alfresco.
        """
        self.ensure_one()
        
        url, user, pwd = self._get_alfresco_config()
        
        if not url or not user or not pwd:
            return
        
        items_endpoint = f"{url}/alfresco/api/-default-/public/workflow/versions/1/tasks/{self.alfresco_task_id}/items"
        
        _logger.debug(
            "Obteniendo items de tarea %s desde: %s",
            self.alfresco_task_id,
            items_endpoint,
        )
        
        try:
            response = requests.get(
                items_endpoint,
                auth=(user, pwd),
                timeout=30,
            )
            
            if response.status_code != 200:
                _logger.warning(
                    "No se pudieron obtener items de tarea %s. Código: %d",
                    self.alfresco_task_id,
                    response.status_code,
                )
                return
            
            data = response.json()
            entries = data.get("list", {}).get("entries", [])
            
            _logger.debug(
                "Items encontrados para tarea %s: %d",
                self.alfresco_task_id,
                len(entries),
            )
            
            Document = self.env["alfresco.task.document"]
            existing_docs = {doc.node_id: doc for doc in self.document_ids}
            
            for entry in entries:
                item = entry.get("entry", {})
                node_id = item.get("id")
                
                if not node_id:
                    continue
                
                size = item.get("size") or item.get("sizeInBytes") or 0
                
                doc_vals = {
                    "task_id": self.id,
                    "node_id": node_id,
                    "name": item.get("name", "Sin nombre"),
                    "mime_type": item.get("mimeType", ""),
                    "size": size,
                    "created_at": self._parse_alfresco_datetime(item.get("createdAt")),
                    "created_by": item.get("createdBy", ""),
                    "modified_at": self._parse_alfresco_datetime(item.get("modifiedAt")),
                    "modified_by": item.get("modifiedBy", ""),
                }
                
                if node_id in existing_docs:
                    existing_docs[node_id].write(doc_vals)
                else:
                    Document.create(doc_vals)
                
            _logger.debug(
                "Documentos sincronizados para tarea %s",
                self.alfresco_task_id,
            )
            
        except requests.exceptions.RequestException as e:
            _logger.error(
                "Error al obtener items de tarea %s: %s",
                self.alfresco_task_id,
                str(e),
            )

    @api.model
    def _execute_sync(self):
        """
        Ejecuta la sincronización de tareas de Alfresco.
        """
        _logger.info("Ejecutando sincronización de tareas de Alfresco")
        
        user_mapping = self._get_users_with_alfresco_mapping()
        
        if not user_mapping:
            _logger.warning("No hay usuarios con alfresco_user configurado")
            return {
                "success": False,
                "message": "No hay usuarios con alfresco_user configurado",
                "tasks_created": 0,
                "tasks_updated": 0,
                "tasks_rejected": 0,
            }
        
        alfresco_tasks = self._fetch_alfresco_tasks()
        
        if not alfresco_tasks:
            _logger.info("No se encontraron tareas en Alfresco")
            return {
                "success": True,
                "message": "No se encontraron tareas en Alfresco",
                "tasks_created": 0,
                "tasks_updated": 0,
                "tasks_rejected": 0,
            }
        
        tasks_created = 0
        tasks_updated = 0
        tasks_rejected = 0
        tasks_completed = 0
        
        for task_data in alfresco_tasks:
            assignee = task_data.get("assignee")
            
            if not assignee or assignee not in user_mapping:
                _logger.debug(
                    "Tarea %s ignorada - asignado '%s' no mapeado",
                    task_data.get("id"),
                    assignee,
                )
                continue
            
            odoo_user = user_mapping[assignee]
            
            existing = self.search([
                ("alfresco_task_id", "=", task_data.get("id"))
            ], limit=1)
            
            # Detectar si es rechazada
            is_rejected = self._detectar_si_es_rechazada(task_data)
            if is_rejected:
                tasks_rejected += 1
            
            # Contar tareas completadas en Alfresco
            if task_data.get("state") == "completed":
                tasks_completed += 1
            
            self._create_or_update_task_with_activity(task_data, odoo_user)
            
            if existing:
                tasks_updated += 1
            else:
                tasks_created += 1
        
        _logger.info(
            "Sincronización completada - Creadas: %d, Actualizadas: %d, Rechazadas: %d, Completadas en Alfresco: %d",
            tasks_created,
            tasks_updated,
            tasks_rejected,
            tasks_completed,
        )
        
        return {
            "success": True,
            "message": f"Sincronización completada. Creadas: {tasks_created}, Actualizadas: {tasks_updated}, Rechazadas: {tasks_rejected}, Completadas en Alfresco: {tasks_completed}",
            "tasks_created": tasks_created,
            "tasks_updated": tasks_updated,
            "tasks_rejected": tasks_rejected,
            "tasks_completed": tasks_completed,
        }

    @api.model
    def cron_sync_alfresco_tasks(self):
        """
        Método llamado por el cron para sincronizar tareas.
        """
        _logger.info("Cron de sincronización de tareas Alfresco iniciado")
        return self._execute_sync()