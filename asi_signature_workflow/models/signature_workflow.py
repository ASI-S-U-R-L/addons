# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

class SignatureWorkflow(models.Model):
    _name = 'signature.workflow'
    _description = 'Solicitud de Firma Digital'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Nombre de la Solicitud', required=True)
    creator_id = fields.Many2one('res.users', string='Creador', required=True, default=lambda self: self.env.user)
    
    target_user_id_1 = fields.Many2one('res.users', string='Destinatario 1')
    signature_role_id_1 = fields.Many2one('document.signature.tag', string='Rol de Firma 1')
    signature_position_1 = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de Firma 1')
    signed_by_user_1 = fields.Boolean(string='Firmado por Usuario 1', default=False)
    signed_date_1 = fields.Datetime(string='Fecha Firma Usuario 1')
    
    target_user_id_2 = fields.Many2one('res.users', string='Destinatario 2')
    signature_role_id_2 = fields.Many2one('document.signature.tag', string='Rol de Firma 2')
    signature_position_2 = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de Firma 2')
    signed_by_user_2 = fields.Boolean(string='Firmado por Usuario 2', default=False)
    signed_date_2 = fields.Datetime(string='Fecha Firma Usuario 2')
    
    target_user_id_3 = fields.Many2one('res.users', string='Destinatario 3')
    signature_role_id_3 = fields.Many2one('document.signature.tag', string='Rol de Firma 3')
    signature_position_3 = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de Firma 3')
    signed_by_user_3 = fields.Boolean(string='Firmado por Usuario 3', default=False)
    signed_date_3 = fields.Datetime(string='Fecha Firma Usuario 3')
    
    target_user_id_4 = fields.Many2one('res.users', string='Destinatario 4')
    signature_role_id_4 = fields.Many2one('document.signature.tag', string='Rol de Firma 4')
    signature_position_4 = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de Firma 4')
    signed_by_user_4 = fields.Boolean(string='Firmado por Usuario 4', default=False)
    signed_date_4 = fields.Datetime(string='Fecha Firma Usuario 4')
    
    current_recipient_index = fields.Integer(
        string='Índice del Destinatario Actual',
        default=1,
        help='Indica qué destinatario tiene actualmente el turno de firmar (1-4)'
    )
    
    # Campos deprecados (mantener por compatibilidad)
    target_user_id = fields.Many2one('res.users', string='Usuario Destinatario (Deprecado)')
    signature_role_id = fields.Many2one('document.signature.tag', string='Rol de Firma (Deprecado)')
    signature_position = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de la Firma (Deprecado)')
    
    signature_opaque_background = fields.Boolean(
        string='Firma con fondo opaco',
        default=False,
        help='Si está marcado, la firma tendrá fondo blanco opaco en lugar de transparente'
    )
    
    sign_all_pages = fields.Boolean(
        string='Firmar todas las páginas',
        default=False,
        help='Si está marcado, se firmará todas las páginas del documento en lugar de solo la última'
    )
    
    document_source = fields.Selection([
        ('local', 'Documentos Locales'),
        ('alfresco', 'Documentos de Alfresco')
    ], string='Origen de Documentos', required=True)
    
    destination_folder_id = fields.Many2one(
        'alfresco.folder',
        string='Carpeta de Destino',
        help='Carpeta en Alfresco donde se moverán los documentos firmados al completar el flujo'
    )
    destination_folder_path = fields.Char(
        string='Ruta de Carpeta de Destino',
        compute='_compute_destination_folder_path'
    )
    
    documents_moved = fields.Boolean(
        string='Documentos Movidos',
        default=False,
        help='Indica si los documentos ya fueron movidos a la carpeta de destino'
    )
    move_status = fields.Text(
        string='Estado del Movimiento',
        help='Detalle del estado del movimiento de documentos'
    )
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('signed', 'Firmado'),
        ('moving', 'Moviendo Documentos'),  # Nuevo estado para proceso de movimiento
        ('completed', 'Completado'),
        ('cancelled', 'Cancelado'),
        ('rejected', 'Rechazado')
    ], string='Estado', default='draft', required=True, tracking=True)
    
    # Documentos del flujo
    document_ids = fields.One2many('signature.workflow.document', 'workflow_id', string='Documentos')
    document_count = fields.Integer(string='Cantidad de Documentos', compute='_compute_document_count')
    
    alfresco_folder_id = fields.Many2one('alfresco.folder', string='Carpeta de la Solicitud en Alfresco', readonly=True)
    
    # Fechas importantes
    sent_date = fields.Datetime(string='Fecha de Envío')
    signed_date = fields.Datetime(string='Fecha de Firma')
    completed_date = fields.Datetime(string='Fecha de Finalización')
    rejection_date = fields.Datetime(string='Fecha de Rechazo', readonly=True)
    
    # Notas y observaciones
    notes = fields.Text(string='Notas')
    signature_notes = fields.Text(string='Notas de Firma', readonly=True)
    rejection_notes = fields.Text(string='Motivo del Rechazo', readonly=True)

    @api.depends('destination_folder_id')
    def _compute_destination_folder_path(self):
        for record in self:
            if record.destination_folder_id:
                record.destination_folder_path = record.destination_folder_id.complete_path or record.destination_folder_id.name
            else:
                record.destination_folder_path = ''

    @api.depends('document_ids')
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

    @api.constrains('target_user_id_1', 'target_user_id_2', 'target_user_id_3', 'target_user_id_4',
                    'signature_role_id_1', 'signature_role_id_2', 'signature_role_id_3', 'signature_role_id_4',
                    'signature_position_1', 'signature_position_2', 'signature_position_3', 'signature_position_4')
    def _check_unique_positions_and_roles(self):
        """Valida que no se repitan posiciones ni roles entre destinatarios activos"""
        for record in self:
            active_users = [record.target_user_id_1, record.target_user_id_2, 
                          record.target_user_id_3, record.target_user_id_4]
            active_users = [u for u in active_users if u]
            
            if not active_users:
                raise ValidationError(_('Debe especificar al menos un destinatario para la solicitud de firma.'))
            
            recipients = []
            for i in range(1, 5):
                user = getattr(record, f'target_user_id_{i}')
                role = getattr(record, f'signature_role_id_{i}')
                position = getattr(record, f'signature_position_{i}')
                
                if user:
                    if not role or not position:
                        raise ValidationError(_(
                            f'El destinatario {i} debe tener rol y posición de firma asignados.'
                        ))
                    
                    recipients.append({
                        'index': i,
                        'user': user,
                        'role': role,
                        'position': position
                    })
            
            positions = [r['position'] for r in recipients]
            if len(positions) != len(set(positions)):
                raise ValidationError(_('Las posiciones de firma no pueden repetirse entre destinatarios.'))
            
            roles = [r['role'].id for r in recipients]
            if len(roles) != len(set(roles)):
                raise ValidationError(_('Los roles de firma no pueden repetirse entre destinatarios.'))

    def _get_active_recipients(self):
        """Retorna lista de destinatarios activos con sus datos"""
        self.ensure_one()
        recipients = []
        
        for i in range(1, 5):
            user = getattr(self, f'target_user_id_{i}')
            if user:
                recipients.append({
                    'index': i,
                    'user': user,
                    'role': getattr(self, f'signature_role_id_{i}'),
                    'position': getattr(self, f'signature_position_{i}'),
                    'signed': getattr(self, f'signed_by_user_{i}'),
                    'signed_date': getattr(self, f'signed_date_{i}')
                })
        
        return recipients

    def _get_current_active_recipient(self):
        """Obtiene el destinatario que tiene actualmente el turno de firmar"""
        self.ensure_one()
        recipients = self._get_active_recipients()
        
        for recipient in recipients:
            if recipient['index'] == self.current_recipient_index:
                return recipient
        
        return None

    def _is_user_current_recipient(self, user_id=None):
        """Verifica si el usuario dado (o el actual) es el destinatario activo"""
        self.ensure_one()
        
        if user_id is None:
            user_id = self.env.user.id
        
        current_recipient = self._get_current_active_recipient()
        if current_recipient and current_recipient['user'].id == user_id:
            return True
        return False

    def _get_current_user_recipient_data(self):
        """Obtiene los datos del destinatario para el usuario actual"""
        self.ensure_one()
        current_user = self.env.user
        
        for i in range(1, 5):
            user = getattr(self, f'target_user_id_{i}')
            if user == current_user:
                return {
                    'index': i,
                    'user': user,
                    'role': getattr(self, f'signature_role_id_{i}'),
                    'position': getattr(self, f'signature_position_{i}'),
                    'signed': getattr(self, f'signed_by_user_{i}'),
                    'signed_date': getattr(self, f'signed_date_{i}')
                }
        
        return None

    @api.model
    def create(self, vals):
        """Override create para subir documentos locales a Alfresco automáticamente"""
        workflow = super(SignatureWorkflow, self).create(vals)
        
        if workflow.document_source == 'local' and workflow.document_ids:
            workflow._upload_local_documents_to_alfresco()
        
        return workflow

    def _upload_local_documents_to_alfresco(self):
        """Sube documentos locales a la ruta específica en Alfresco"""
        self.ensure_one()
        
        if self.document_source != 'local':
            return
        
        try:
            workflow_folder = self._create_workflow_folder_in_alfresco()
            if not workflow_folder:
                raise UserError(_('No se pudo crear la carpeta de la solicitud en Alfresco'))
            
            uploaded_count = 0
            failed_count = 0
            
            for doc in self.document_ids.filtered(lambda d: d.pdf_content and not d.alfresco_file_id):
                alfresco_file = self._upload_document_to_workflow_folder(doc, workflow_folder)
                if alfresco_file:
                    doc.write({
                        'alfresco_file_id': alfresco_file.id,
                        'download_url': f'/alfresco/file/{alfresco_file.id}/download'
                    })
                    uploaded_count += 1
                    _logger.info(f"Documento {doc.name} subido a Alfresco en carpeta de la solicitud")
                else:
                    failed_count += 1
                    _logger.error(f"Error subiendo documento {doc.name} a Alfresco")
            
            if uploaded_count == 0 and failed_count > 0:
                raise UserError(_('No se pudo subir ningún documento a Alfresco. Verifique la configuración.'))
            elif failed_count > 0:
                _logger.warning(f"Se subieron {uploaded_count} documentos exitosamente, {failed_count} fallaron")
            
            _logger.info(f"Documentos locales de la solicitud {self.id} subidos exitosamente a Alfresco ({uploaded_count}/{uploaded_count + failed_count})")
            
        except Exception as e:
            _logger.error(f"Error subiendo documentos locales de la solicitud {self.id}: {e}")
            raise UserError(_('Error subiendo documentos a Alfresco: %s') % str(e))

    def _create_workflow_folder_in_alfresco(self):
        """Crea la carpeta de la solicitud en la ruta /Sites/Flujos/<usuario>/<nombre_flujo>/"""
        self.ensure_one()
        
        try:
            config = self.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            repo_id = config.get_param('asi_alfresco_integration.alfresco_repo_id', '-root-')
            
            if not all([url, user, pwd]):
                raise UserError(_('Configuración de Alfresco incompleta'))
            
            import requests
            import json
            
            sites_folder = self._get_or_create_alfresco_folder('Sites', repo_id, None)
            if not sites_folder:
                raise UserError(_('No se pudo crear carpeta Sites'))
            
            flujos_folder = self._get_or_create_alfresco_folder('Flujos', sites_folder.node_id, sites_folder)
            if not flujos_folder:
                raise UserError(_('No se pudo crear carpeta Flujos'))
            
            user_folder_name = self.creator_id.login
            user_folder = self._get_or_create_alfresco_folder(user_folder_name, flujos_folder.node_id, flujos_folder)
            if not user_folder:
                raise UserError(_('No se pudo crear carpeta del usuario'))
            
            workflow_folder_name = self.name
            workflow_folder = self._get_or_create_alfresco_folder(workflow_folder_name, user_folder.node_id, user_folder)
            if not workflow_folder:
                raise UserError(_('No se pudo crear carpeta de la solicitud'))
            
            self.write({'alfresco_folder_id': workflow_folder.id})
            
            _logger.info(f"Carpeta de la solicitud creada en: /Sites/Flujos/{user_folder_name}/{workflow_folder_name}/")
            return workflow_folder
            
        except Exception as e:
            _logger.error(f"Error creando carpeta de la solicitud en Alfresco: {e}")
            raise UserError(_('Error creando carpeta en Alfresco: %s') % str(e))

    def _get_or_create_alfresco_folder(self, folder_name, parent_node_id, parent_folder):
        """Obtiene o crea una carpeta en Alfresco"""
        try:
            existing_folder = self.env['alfresco.folder'].search([
                ('name', '=', folder_name),
                ('parent_id', '=', parent_folder.id if parent_folder else False)
            ], limit=1)
            
            if existing_folder:
                return existing_folder
            
            config = self.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            
            import requests
            import json
            
            search_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{parent_node_id}/children"
            search_params = {
                'where': f"(nodeType='cm:folder' AND name='{folder_name}')",
                'maxItems': 1
            }
            
            search_response = requests.get(
                search_url,
                params=search_params,
                auth=(user, pwd),
                timeout=30
            )
            
            if search_response.status_code == 200:
                search_data = search_response.json()
                if search_data.get('list', {}).get('entries'):
                    folder_info = search_data['list']['entries'][0]['entry']
                    existing_folder = self.env['alfresco.folder'].create({
                        'name': folder_name,
                        'node_id': folder_info['id'],
                        'parent_id': parent_folder.id if parent_folder else False,
                        'is_persistent': True,
                        'sync_status': 'synced',
                        'last_sync': fields.Datetime.now(),
                    })
                    _logger.info(f"Carpeta existente {folder_name} sincronizada desde Alfresco")
                    return existing_folder
            
            create_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{parent_node_id}/children"
            folder_data = {
                "name": folder_name,
                "nodeType": "cm:folder",
                "properties": {
                    "cm:title": folder_name,
                    "cm:description": f"Carpeta para solicitudes de firma - {folder_name}"
                }
            }
            
            response = requests.post(
                create_url,
                json=folder_data,
                auth=(user, pwd),
                timeout=30
            )
            
            if response.status_code == 201:
                folder_info = response.json()['entry']
                
                new_folder = self.env['alfresco.folder'].create({
                    'name': folder_name,
                    'node_id': folder_info['id'],
                    'parent_id': parent_folder.id if parent_folder else False,
                    'is_persistent': True,
                    'sync_status': 'synced',
                    'last_sync': fields.Datetime.now(),
                })
                
                _logger.info(f"Carpeta {folder_name} creada exitosamente en Alfresco")
                return new_folder
            elif response.status_code == 409:
                _logger.info(f"Carpeta {folder_name} ya existe en Alfresco (409), buscando...")
                
                search_response_retry = requests.get(
                    search_url,
                    params=search_params,
                    auth=(user, pwd),
                    timeout=30
                )
                
                if search_response_retry.status_code == 200:
                    search_data_retry = search_response_retry.json()
                    if search_data_retry.get('list', {}).get('entries'):
                        folder_info = search_data_retry['list']['entries'][0]['entry']
                        existing_folder = self.env['alfresco.folder'].create({
                            'name': folder_name,
                            'node_id': folder_info['id'],
                            'parent_id': parent_folder.id if parent_folder else False,
                            'is_persistent': True,
                            'sync_status': 'synced',
                            'last_sync': fields.Datetime.now(),
                        })
                        _logger.info(f"Carpeta existente {folder_name} encontrada y sincronizada después de 409")
                        return existing_folder
                
                _logger.error(f"No se pudo encontrar carpeta {folder_name} después de error 409")
                return False
            else:
                _logger.error(f"Error creando carpeta {folder_name} en Alfresco: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            _logger.error(f"Error obteniendo/creando carpeta {folder_name}: {e}")
            return False

    def _upload_document_to_workflow_folder(self, document, workflow_folder):
        """Sube un documento a la carpeta de la solicitud en Alfresco"""
        try:
            config = self.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            
            import requests
            import base64
            import json
            from datetime import datetime
            
            pdf_data = base64.b64decode(document.pdf_content)
            
            upload_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{workflow_folder.node_id}/children"
            
            files = {
                'filedata': (document.name, pdf_data, 'application/pdf')
            }
            
            properties = {
                'cm:title': document.name,
                'cm:description': f'Documento de la solicitud: {self.name}',
                'cm:author': self.creator_id.name,
                'asi:workflow_id': str(self.id),
                'asi:workflow_name': self.name,
                'asi:upload_date': fields.Datetime.now().isoformat()
            }
            
            data = {
                'name': document.name,
                'nodeType': 'cm:content',
                'properties': json.dumps(properties)
            }
            
            _logger.info(f"Subiendo documento {document.name} a carpeta {workflow_folder.node_id}")
            
            response = requests.post(
                upload_url,
                files=files,
                data=data,
                auth=(user, pwd),
                timeout=60
            )
            
            _logger.info(f"Respuesta de Alfresco para {document.name}: Status {response.status_code}")
            
            if response.status_code in [201, 409]:
                if response.status_code == 201:
                    try:
                        response_data = response.json()
                        _logger.info(f"Datos de respuesta completos para {document.name}: {response_data}")
                        
                        if 'entry' in response_data and response_data['entry'] and 'id' in response_data['entry']:
                            file_id = response_data['entry']['id']
                            _logger.info(f"ID real obtenido de respuesta: {file_id}")
                        else:
                            file_id = f"workflow-{self.id}-{document.name.replace(' ', '_').replace('.', '_')}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            _logger.warning(f"Respuesta vacía de Alfresco, usando ID ficticio: {file_id}")
                    except:
                        file_id = f"workflow-{self.id}-{document.name.replace(' ', '_').replace('.', '_')}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        _logger.warning(f"Error parseando respuesta, usando ID ficticio: {file_id}")
                else:
                    file_id = f"existing-{self.id}-{document.name.replace(' ', '_').replace('.', '_')}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    _logger.info(f"Archivo ya existe (409), usando ID ficticio: {file_id}")
                
                alfresco_file = self.env['alfresco.file'].create({
                    'name': document.name,
                    'folder_id': workflow_folder.id,
                    'alfresco_node_id': file_id,
                    'mime_type': 'application/pdf',
                    'file_size': len(pdf_data),
                    'modified_at': fields.Datetime.now(),
                })
                
                _logger.info(f"Documento {document.name} procesado exitosamente con ID: {file_id} (Status: {response.status_code})")
                return alfresco_file
                
            else:
                _logger.error(f"Error subiendo documento {document.name}: {response.status_code} - {response.text}")
                try:
                    error_data = response.json()
                    _logger.error(f"Detalles del error: {error_data}")
                except:
                    _logger.error(f"No se pudo parsear respuesta de error como JSON")
                return False
                
        except Exception as e:
            _logger.error(f"Excepción subiendo documento {document.name}: {e}")
            import traceback
            _logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def action_send_for_signature(self):
        """Envía la solicitud para firma - solo al primer destinatario (flujo secuencial)"""
        self.ensure_one()
        if not self.document_ids:
            raise UserError(_('Debe agregar al menos un documento a la solicitud.'))
        
        recipients = self._get_active_recipients()
        if not recipients:
            raise UserError(_('Debe especificar al menos un destinatario para la solicitud.'))
        
        if self.document_source == 'local':
            local_docs_without_alfresco = self.document_ids.filtered(lambda d: not d.alfresco_file_id)
            if local_docs_without_alfresco:
                self._upload_local_documents_to_alfresco()
                local_docs_with_alfresco = self.document_ids.filtered(lambda d: d.alfresco_file_id)
                if not local_docs_with_alfresco:
                    raise UserError(_('No se pudo subir ningún documento a Alfresco. Verifique la configuración.'))
                elif len(local_docs_with_alfresco) < len(self.document_ids):
                    failed_docs = self.document_ids.filtered(lambda d: not d.alfresco_file_id)
                    _logger.warning(f"Algunos documentos no se subieron: {failed_docs.mapped('name')}")
        
        # Establecer el primer destinatario como activo
        self.write({
            'state': 'sent',
            'sent_date': fields.Datetime.now(),
            'current_recipient_index': recipients[0]['index']  # Primer destinatario
        })
        
        # Solo crear actividad para el PRIMER destinatario (flujo secuencial)
        first_recipient = recipients[0]
        self._create_signature_activity(first_recipient)
        
        # Solo enviar notificación al PRIMER destinatario
        self._send_signature_request_notification_to_recipient(first_recipient)
        
        _logger.info(f"[SEQUENTIAL] Solicitud {self.id} enviada al primer destinatario: {first_recipient['user'].name}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Solicitud enviada al primer destinatario: {first_recipient["user"].name}',
                'type': 'success',
            }
        }

    def _create_signature_activity(self, recipient_data):
        """Crea una actividad para un destinatario específico cuando se envía la solicitud"""
        self.ensure_one()
        
        try:
            activity_type = self.env.ref('mail.mail_activity_data_todo')
            
            self.env['mail.activity'].create({
                'activity_type_id': activity_type.id,
                'summary': f'Firma requerida: {self.name}',
                'note': f'''
                <p>Se requiere su firma para los siguientes documentos:</p>
                <ul>
                    {''.join([f'<li>{doc.name}</li>' for doc in self.document_ids])}
                </ul>
                <p><strong>Rol de firma asignado:</strong> {recipient_data['role'].name}</p>
                <p><strong>Posición de firma:</strong> {dict(self._fields['signature_position_1'].selection)[recipient_data['position']]}</p>
                <p><strong>Enviado por:</strong> {self.creator_id.name}</p>
                {f'<p><strong>Notas:</strong> {self.notes}</p>' if self.notes else ''}
                ''',
                'res_model_id': self.env['ir.model']._get(self._name).id,
                'res_id': self.id,
                'user_id': recipient_data['user'].id,
                'date_deadline': fields.Date.today(),
            })
            _logger.info(f"Actividad de firma creada para usuario {recipient_data['user'].name} (destinatario {recipient_data['index']}) en solicitud {self.id}")
        except Exception as e:
            _logger.error(f"Error creando actividad de firma: {e}")

    def _send_signature_request_notification_to_recipient(self, recipient):
        """Crea notificación interna para un destinatario específico"""
        self.ensure_one()
        
        try:
            self.env['mail.message'].create({
                'subject': f'Nueva solicitud de firma: {self.name}',
                'body': f'''
                <p>Se ha creado una nueva solicitud de firma que requiere su atención:</p>
                <ul>
                    <li><strong>Solicitud de firma:</strong> {self.name}</li>
                    <li><strong>Creado por:</strong> {self.creator_id.name}</li>
                    <li><strong>Documentos:</strong> {self.document_count} archivo(s)</li>
                    <li><strong>Su rol de firma:</strong> {recipient['role'].name}</li>
                    <li><strong>Su posición:</strong> {dict(self._fields['signature_position_1'].selection)[recipient['position']]}</li>
                </ul>
                {f'<p><strong>Notas:</strong> {self.notes}</p>' if self.notes else ''}
                <p>Por favor, acceda la solicitud para revisar y firmar los documentos.</p>
                ''',
                'message_type': 'notification',
                'model': self._name,
                'res_id': self.id,
                'partner_ids': [(4, recipient['user'].partner_id.id)],
                'author_id': self.creator_id.partner_id.id,
            })
            _logger.info(f"Notificación interna de solicitud creada para destinatario {recipient['index']} en solicitud {self.id}")
        except Exception as e:
            _logger.error(f"Error creando notificación interna de solicitud para destinatario {recipient['index']}: {e}")

    def _send_signature_request_notification(self):
        """Crea notificaciones internas para todos los destinatarios - DEPRECADO para flujo secuencial"""
        self.ensure_one()
        
        recipients = self._get_active_recipients()
        
        for recipient in recipients:
            self._send_signature_request_notification_to_recipient(recipient)

    def action_reject_workflow(self):
        """Acción para que un usuario destinatario rechace la solicitud"""
        self.ensure_one()
        
        recipient_data = self._get_current_user_recipient_data()
        if not recipient_data:
            raise UserError(_('Solo los usuarios destinatarios pueden rechazar esta solicitud.'))
        
        if not self._is_user_current_recipient():
            raise UserError(_('No es su turno de firmar. Debe esperar a que los destinatarios anteriores completen su firma.'))
        
        if self.state != 'sent':
            raise UserError(_('Esta solicitud no está disponible para rechazo.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rechazar Solicitud de Firma',
            'res_model': 'signature.workflow.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workflow_id': self.id,
            }
        }

    def _process_rejection(self, rejection_notes):
        """Procesa el rechazo de la solicitud con las notas proporcionadas"""
        self.ensure_one()
        
        recipient_data = self._get_current_user_recipient_data()
        rejecting_user = recipient_data['user'] if recipient_data else self.env.user
        
        self.write({
            'state': 'rejected',
            'rejection_date': fields.Datetime.now(),
            'rejection_notes': f"Rechazado por {rejecting_user.name}:\n{rejection_notes}"
        })
        
        activities = self.env['mail.activity'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
            ('state', '!=', 'done')
        ])
        
        if activities:
            activities.action_done()
            _logger.info(f"Actividades completadas después del rechazo de la solicitud {self.id}")
        
        self.env['mail.activity'].create({
            'activity_type_id': self.env.ref('mail.mail_activity_data_warning').id,
            'summary': f'Solicitud rechazada: {self.name}',
            'note': f'''
            <p>Su solicitud de firma ha sido rechazada por <strong>{rejecting_user.name}</strong></p>
            <p><strong>Motivo del rechazo:</strong></p>
            <div style="background-color: #ffebee; padding: 10px; border-radius: 5px; border-left: 4px solid #f44336; margin: 10px 0;">
                <p>{rejection_notes}</p>
            </div>
            <p>Puede revisar la solicitud y crear una nueva si es necesario.</p>
            ''',
            'res_model_id': self.env['ir.model']._get(self._name).id,
            'res_id': self.id,
            'user_id': self.creator_id.id,
            'date_deadline': fields.Date.today(),
        })
        
        self._send_rejection_notification(rejecting_user)
        
        _logger.info(f"Solicitud {self.id} rechazado por {rejecting_user.name}")

    def _send_rejection_notification(self, rejecting_user):
        """Crea notificación interna de rechazo"""
        self.ensure_one()
        
        try:
            self.env['mail.message'].create({
                'subject': f'Solicitud rechazada: {self.name}',
                'body': f'''
                <p>Su solicitud de firma ha sido rechazada:</p>
                <ul>
                    <li><strong>Solicitud de firma:</strong> {self.name}</li>
                    <li><strong>Rechazado por:</strong> {rejecting_user.name}</li>
                    <li><strong>Fecha de rechazo:</strong> {self.rejection_date}</li>
                </ul>
                <div style="background-color: #ffebee; padding: 10px; border-radius: 5px; border-left: 4px solid #f44336; margin: 10px 0;">
                    <p><strong>Motivo del rechazo:</strong></p>
                    <p>{self.rejection_notes}</p>
                </div>
                <p>Puede revisar la solicitud y crear una nueva si es necesario.</p>
                ''',
                'message_type': 'notification',
                'model': self._name,
                'res_id': self.id,
                'partner_ids': [(4, self.creator_id.partner_id.id)],
                'author_id': rejecting_user.partner_id.id,
            })
            _logger.info(f"Notificación interna de rechazo creada para solicitud {self.id}")
        except Exception as e:
            _logger.error(f"Error creando notificación interna de rechazo: {e}")

    def action_mark_as_completed(self):
        """Acción manual para marcar la solicitud como completada"""
        self.ensure_one()
        
        if self.state not in ['signed', 'completed']:
            raise UserError(_('Solo se pueden completar solicitudes que estén firmadas.'))
        
        self.write({
            'state': 'completed',
            'completed_date': fields.Datetime.now()
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Solicitud marcada como completada',
                'type': 'success',
            }
        }

    def action_sign_documents(self):
        """Abre el wizard de firma de documentos para el destinatario activo"""
        self.ensure_one()
        
        recipient_data = self._get_current_user_recipient_data()
        if not recipient_data:
            raise UserError(_('Solo los usuarios destinatarios pueden firmar.'))
        
        if recipient_data['signed']:
            raise UserError(_('Usted ya ha firmado estos documentos.'))

        if self.state != 'sent':
            raise UserError(_('Esta solicitud no está disponible para firma.'))
        
        if not self._is_user_current_recipient():
            current_recipient = self._get_current_active_recipient()
            if current_recipient:
                raise UserError(_(
                    f'No es su turno de firmar. Actualmente es el turno de: {current_recipient["user"].name}. '
                    f'Debe esperar a que complete su firma.'
                ))
            else:
                raise UserError(_('No es su turno de firmar.'))
        
        return self._process_alfresco_signature(recipient_data)

    def _process_local_signature(self, recipient_data):
        """Procesa la firma de documentos locales usando el wizard local"""
        local_documents = self.document_ids.filtered(lambda d: d.pdf_content)
        
        if not local_documents:
            raise UserError(_('No hay documentos locales disponibles para firmar.'))
        
        _logger.info(f"Procesando firma local de {len(local_documents)} documentos para destinatario {recipient_data['index']}")
        
        wizard = self.env['firma.documento.wizard'].create({
            'signature_role': recipient_data['role'].id,
            'signature_position': recipient_data['position'],
            'signature_opaque_background': self.signature_opaque_background,
            'sign_all_pages': self.sign_all_pages,
            'from_workflow': True,
            'workflow_id': self.id,
        })
        
        for doc in local_documents:
            wizard.document_ids.create({
                'wizard_id': wizard.id,
                'document_name': doc.name,
                'pdf_document': doc.pdf_content,
            })
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Firmar Documentos de la Solicitud - {recipient_data["user"].name}',
            'res_model': 'firma.documento.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'workflow_id': self.id,
                'from_workflow': True,
                'recipient_index': recipient_data['index'],
            }
        }

    def _process_alfresco_signature(self, recipient_data):
        """Procesa la firma de documentos de Alfresco"""
        alfresco_files = self.document_ids.mapped('alfresco_file_id').filtered(lambda f: f)
        
        if not alfresco_files and self.alfresco_folder_id:
            _logger.info(f"No se encontraron archivos de Alfresco asignados, buscando en carpeta {self.alfresco_folder_id.name}")
            
            document_names = self.document_ids.mapped('name')
            for doc_name in document_names:
                matching_files = self.env['alfresco.file'].search([
                    ('folder_id', '=', self.alfresco_folder_id.id),
                    ('name', '=', doc_name)
                ])
                if matching_files:
                    alfresco_files |= matching_files[0]
                    _logger.info(f"Encontrado archivo {doc_name} en Alfresco")
                    
                    doc = self.document_ids.filtered(lambda d: d.name == doc_name)
                    if doc:
                        doc[0].write({'alfresco_file_id': matching_files[0].id})
        
        if not alfresco_files and self.alfresco_folder_id:
            _logger.info(f"Buscando todos los archivos PDF en carpeta de la solicitud {self.alfresco_folder_id.name}")
            all_pdf_files = self.env['alfresco.file'].search([
                ('folder_id', '=', self.alfresco_folder_id.id),
                ('name', 'ilike', '%.pdf')
            ])
            
            if all_pdf_files:
                alfresco_files = all_pdf_files
                _logger.info(f"Encontrados {len(all_pdf_files)} archivos PDF en la carpeta de la solicitud")
                
                for doc in self.document_ids.filtered(lambda d: not d.alfresco_file_id):
                    matching_file = all_pdf_files.filtered(lambda f: f.name == doc.name)
                    if matching_file:
                        doc.write({'alfresco_file_id': matching_file[0].id})
        
        if not alfresco_files:
            error_msg = f'No hay archivos de Alfresco disponibles para firmar.'
            if self.alfresco_folder_id:
                error_msg += f' Carpeta de la solicitud: {self.alfresco_folder_id.name}'
            else:
                error_msg += ' No se encontró carpeta de la solicitud en Alfresco.'
            
            _logger.warning(error_msg)
            raise UserError(_(error_msg))
        
        _logger.info(f"Procesando firma de {len(alfresco_files)} archivos de Alfresco para destinatario {recipient_data['index']}")
        
        wizard = self.env['alfresco.firma.wizard'].create({
            'file_ids': [(6, 0, alfresco_files.ids)],
            'signature_role': recipient_data['role'].id,
            'signature_position': recipient_data['position'],
            'signature_opaque_background': self.signature_opaque_background,
            'sign_all_pages': self.sign_all_pages,
            'from_workflow': True,
            'workflow_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Firmar Documentos de la Solicitud - {recipient_data["user"].name}',
            'res_model': 'alfresco.firma.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'workflow_id': self.id,
                'from_workflow': True,
                'recipient_index': recipient_data['index'],
            }
        }

    def action_mark_as_signed(self):
        """Marca la solicitud como firmada por el usuario actual y activa el siguiente destinatario"""
        self.ensure_one()
        
        recipient_data = self._get_current_user_recipient_data()
        if not recipient_data:
            raise UserError(_('Solo los usuarios destinatarios pueden marcar como firmado.'))
        
        if recipient_data['signed']:
            _logger.warning(f"Usuario {recipient_data['user'].name} ya había firmado la solicitud {self.id}")
            return True

        if self.state != 'sent':
            raise UserError(_('Esta solicitud no está disponible para firma.'))
        
        # 1. Marcar usuario como firmado
        field_name = f'signed_by_user_{recipient_data["index"]}'
        date_field_name = f'signed_date_{recipient_data["index"]}'
        
        self.write({
            field_name: True,
            date_field_name: fields.Datetime.now()
        })
        
        _logger.info(f"[SIGN] Usuario {recipient_data['user'].name} (destinatario {recipient_data['index']}) marcó como firmado la solicitud {self.id}")
        
        # 2. Completar actividad del usuario SIN enviar correos
        try:
            activities = self.env['mail.activity'].sudo().search([
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('user_id', '=', recipient_data['user'].id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
                ('state', '!=', 'done')
            ])
            
            if activities:
                activities.unlink()
                _logger.info(f"[SIGN] Actividad eliminada para usuario {recipient_data['user'].name}")
            else:
                _logger.warning(f"[SIGN] No se encontró actividad pendiente para usuario {recipient_data['user'].name}")
        except Exception as e:
            _logger.error(f"[SIGN] Error eliminando actividad: {e}")
        
        # 3. Refrescar datos
        self.invalidate_cache()
        self = self.browse(self.id)
        
        # 4. Verificar si todos firmaron
        recipients = self._get_active_recipients()
        all_signed = all(r['signed'] for r in recipients)
        
        _logger.info(f"[SIGN] Estado de firmas: {[(r['user'].name, r['signed']) for r in recipients]}")
        _logger.info(f"[SIGN] Todos firmaron: {all_signed}")
        
        if all_signed:
            _logger.info(f"[SIGN] Todos firmaron - Procesando finalización de la solicitud {self.id}")
            
            try:
                # 5. Marcar TODOS los documentos como firmados
                for doc in self.document_ids:
                    update_vals = {
                        'is_signed': True,
                        'signed_date': fields.Datetime.now()
                    }
                    
                    if doc.alfresco_file_id:
                        update_vals['download_url'] = f'/alfresco/file/{doc.alfresco_file_id.id}/download'
                    
                    doc.write(update_vals)
                    _logger.info(f"[SIGN] Documento {doc.name} marcado como firmado")
                
                if self.destination_folder_id:
                    _logger.info(f"[SIGN] Iniciando movimiento de documentos a carpeta destino: {self.destination_folder_id.name}")
                    self.write({'state': 'moving'})
                    self._move_documents_to_destination()
                else:
                    # Sin carpeta de destino, completar directamente
                    self.write({
                        'state': 'completed',
                        'signed_date': fields.Datetime.now(),
                        'completed_date': fields.Datetime.now()
                    })
                
                _logger.info(f"[SIGN] Solicitud {self.id} procesada exitosamente")
                
                # 7. Crear actividad simple para el creador SIN enviar correos
                try:
                    signed_users = ', '.join([r['user'].name for r in recipients])
                    
                    self.env['mail.activity'].sudo().create({
                        'activity_type_id': self.env.ref('mail.mail_activity_data_call').id,
                        'summary': f'Solicitud de Firma completada: {self.name}',
                        'note': f'Todos los destinatarios han firmado: {signed_users}',
                        'res_model_id': self.env['ir.model']._get(self._name).id,
                        'res_id': self.id,
                        'user_id': self.creator_id.id,
                        'date_deadline': fields.Date.today(),
                    })
                    _logger.info(f"[SIGN] Actividad de completado creada para creador")
                except Exception as e:
                    _logger.error(f"[SIGN] Error creando actividad de completado: {e}")
                
            except Exception as e:
                _logger.error(f"[SIGN] Error en proceso de finalización: {e}")
                import traceback
                _logger.error(f"[SIGN] Traceback: {traceback.format_exc()}")
                raise
        else:
            next_recipient = self._get_next_recipient()
            if next_recipient:
                _logger.info(f"[SEQUENTIAL] Activando siguiente destinatario: {next_recipient['user'].name} (índice {next_recipient['index']})")
                
                # Actualizar índice del destinatario actual
                self.write({'current_recipient_index': next_recipient['index']})
                
                # Crear actividad y enviar notificación al siguiente destinatario
                self._create_signature_activity(next_recipient)
                self._send_signature_request_notification_to_recipient(next_recipient)
                
                # Notificar al creador sobre el avance
                self._send_partial_signature_notification(
                    recipient_data, 
                    [r['user'].name for r in recipients if not r['signed']]
                )
            else:
                pending_users = [r['user'].name for r in recipients if not r['signed']]
                _logger.info(f"[SIGN] Firma registrada. Pendientes: {', '.join(pending_users)}")
        
        return True

    def _get_next_recipient(self):
        """Obtiene el siguiente destinatario que debe firmar"""
        self.ensure_one()
        recipients = self._get_active_recipients()
        
        # Buscar el primer destinatario que no haya firmado
        for recipient in recipients:
            if not recipient['signed']:
                return recipient
        
        return None

    def _move_documents_to_destination(self):
        """Mueve los documentos firmados a la carpeta de destino en Alfresco"""
        self.ensure_one()
        
        if not self.destination_folder_id:
            _logger.warning(f"[MOVE] No hay carpeta de destino configurada para la solicitud {self.id}")
            return
        
        try:
            config = self.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            
            if not all([url, user, pwd]):
                raise UserError(_('Configuración de Alfresco incompleta para mover documentos'))
            
            import requests
            import json
            
            target_parent_id = self.destination_folder_id.node_id
            moved_count = 0
            failed_count = 0
            move_details = []
            
            for doc in self.document_ids.filtered(lambda d: d.alfresco_file_id):
                try:
                    node_id = doc.alfresco_file_id.alfresco_node_id
                    
                    if not node_id:
                        _logger.warning(f"[MOVE] Documento {doc.name} no tiene node_id de Alfresco")
                        failed_count += 1
                        move_details.append(f"ERROR: {doc.name} - Sin node_id")
                        continue
                    
                    # API de Alfresco para mover nodo
                    move_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}/move"
                    
                    move_data = {
                        "targetParentId": target_parent_id
                    }
                    
                    _logger.info(f"[MOVE] Moviendo documento {doc.name} (node: {node_id}) a carpeta {target_parent_id}")
                    
                    response = requests.post(
                        move_url,
                        json=move_data,
                        auth=(user, pwd),
                        headers={'Content-Type': 'application/json'},
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        _logger.info(f"[MOVE] Documento {doc.name} movido exitosamente")
                        
                        # Actualizar el registro del archivo en Odoo
                        doc.alfresco_file_id.write({
                            'folder_id': self.destination_folder_id.id
                        })
                        
                        # Marcar documento como movido
                        doc.write({
                            'moved_to_destination': True,
                            'move_date': fields.Datetime.now()
                        })
                        
                        moved_count += 1
                        move_details.append(f"OK: {doc.name}")
                    else:
                        error_msg = f"Error {response.status_code}"
                        try:
                            error_data = response.json()
                            if 'error' in error_data:
                                error_msg = error_data['error'].get('briefSummary', error_msg)
                        except:
                            pass
                        
                        _logger.error(f"[MOVE] Error moviendo {doc.name}: {error_msg}")
                        failed_count += 1
                        move_details.append(f"ERROR: {doc.name} - {error_msg}")
                        
                except Exception as e:
                    _logger.error(f"[MOVE] Excepción moviendo documento {doc.name}: {e}")
                    failed_count += 1
                    move_details.append(f"ERROR: {doc.name} - {str(e)}")
            
            # Actualizar estado del flujo
            move_status = f"Movidos: {moved_count}, Fallidos: {failed_count}\n" + "\n".join(move_details)
            
            self.write({
                'documents_moved': moved_count > 0,
                'move_status': move_status,
                'state': 'completed',
                'signed_date': fields.Datetime.now(),
                'completed_date': fields.Datetime.now()
            })
            
            _logger.info(f"[MOVE] Proceso completado para solicitud {self.id}: {moved_count} movidos, {failed_count} fallidos")
            
            if failed_count > 0:
                _logger.warning(f"[MOVE] Algunos documentos no se pudieron mover. Detalles: {move_status}")
            
        except Exception as e:
            _logger.error(f"[MOVE] Error general moviendo documentos de la solicitud {self.id}: {e}")
            import traceback
            _logger.error(f"[MOVE] Traceback: {traceback.format_exc()}")
            
            # Marcar como completado pero con error en movimiento
            self.write({
                'documents_moved': False,
                'move_status': f"Error general: {str(e)}",
                'state': 'completed',
                'signed_date': fields.Datetime.now(),
                'completed_date': fields.Datetime.now()
            })

    def _send_partial_signature_notification(self, signed_recipient, pending_users):
        """Notifica al creador que un usuario ha firmado pero aún faltan otros"""
        self.ensure_one()
        
        try:
            self.env['mail.message'].create({
                'subject': f'Firma parcial completada: {self.name}',
                'body': f'''
                <p><strong>{signed_recipient['user'].name}</strong> ha firmado los documentos de la solicitud.</p>
                <ul>
                    <li><strong>Solicitud:</strong> {self.name}</li>
                    <li><strong>Fecha de firma:</strong> {fields.Datetime.now()}</li>
                </ul>
                <p><strong>Usuarios pendientes de firma:</strong></p>
                <ul>
                    {''.join([f'<li>{user}</li>' for user in pending_users])}
                </ul>
                <p>La solicitud se completará automáticamente cuando todos los destinatarios hayan firmado.</p>
                ''',
                'message_type': 'notification',
                'model': self._name,
                'res_id': self.id,
                'partner_ids': [(4, self.creator_id.partner_id.id)],
                'author_id': signed_recipient['user'].partner_id.id,
            })
            _logger.info(f"Notificación de firma parcial enviada para la solicitud {self.id}")
        except Exception as e:
            _logger.error(f"Error enviando notificación de firma parcial: {e}")

    def _process_signed_documents(self):
        """Procesa documentos firmados actualizando URLs de descarga y marcándolos como firmados"""
        self.ensure_one()
        
        _logger.info(f"[PROCESS_SIGNED] Procesando documentos de la solicitud {self.id}")
        _logger.info(f"[PROCESS_SIGNED] Total documentos: {len(self.document_ids)}")
        
        for doc in self.document_ids:
            _logger.info(f"[PROCESS_SIGNED] Procesando documento: {doc.name} (ID: {doc.id})")
            _logger.info(f"[PROCESS_SIGNED] - Tiene alfresco_file_id: {bool(doc.alfresco_file_id)}")
            _logger.info(f"[PROCESS_SIGNED] - Estado actual is_signed: {doc.is_signed}")
            
            update_vals = {
                'is_signed': True,
                'signed_date': fields.Datetime.now()
            }
            
            if doc.alfresco_file_id:
                update_vals['download_url'] = f'/alfresco/file/{doc.alfresco_file_id.id}/download'
                _logger.info(f"[PROCESS_SIGNED] - Actualizando URL de descarga: {update_vals['download_url']}")
            
            doc.write(update_vals)
            _logger.info(f"[PROCESS_SIGNED] - Documento {doc.name} marcado como firmado")
        
        unsigned_docs = self.document_ids.filtered(lambda d: not d.is_signed)
        if unsigned_docs:
            _logger.error(f"[PROCESS_SIGNED] ERROR: Documentos sin marcar como firmados: {unsigned_docs.mapped('name')}")
        else:
            _logger.info(f"[PROCESS_SIGNED] Todos los documentos ({len(self.document_ids)}) marcados como firmados correctamente")

    def get_signed_documents_download_urls(self):
        """Obtiene las URLs de descarga de todos los documentos firmados"""
        self.ensure_one()
        urls = []
        
        for doc in self.document_ids.filtered('is_signed'):
            if doc.alfresco_file_id:
                download_url = f"/alfresco/file/{doc.alfresco_file_id.id}/download"
            else:
                download_url = f"/signature_workflow/document/{doc.id}/download"
            
            full_url = f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}{download_url}"
            urls.append({
                'name': doc.name,
                'url': full_url,
                'signed_date': doc.signed_date
            })
        
        return urls

    def _send_completion_notification(self):
        """Crea notificación interna de finalización"""
        self.ensure_one()
        
        recipients = self._get_active_recipients()
        signed_users = ', '.join([r['user'].name for r in recipients])
        
        try:
            self.env['mail.message'].create({
                'subject': f'Documentos firmados disponibles: {self.name}',
                'body': f'''
                <p>Su solicitud de firma digital ha sido completado exitosamente:</p>
                <ul>
                    <li><strong>Solicitud:</strong> {self.name}</li>
                    <li><strong>Firmado por:</strong> {signed_users}</li>
                    <li><strong>Documentos:</strong> {self.document_count} archivo(s) firmados</li>
                    <li><strong>Fecha:</strong> {self.completed_date}</li>
                    <li><strong>Carpeta Alfresco:</strong> /Sites/Flujos/{self.creator_id.login}/{self.name}/</li>
                </ul>
                <p>Los documentos firmados están disponibles para descarga individual desde la solicitud.</p>
                ''',
                'message_type': 'notification',
                'model': self._name,
                'res_id': self.id,
                'partner_ids': [(4, self.creator_id.partner_id.id)],
                'author_id': self.env.user.partner_id.id,
            })
            
            activities = self.env['mail.activity'].search([
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id)
            ])
            
            if activities:
                activities.action_done()
            
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_call').id,
                'summary': f'Documentos firmados disponibles: {self.name}',
                'note': f'''
                <p>Los documentos de la solicitud han sido firmados por todos los destinatarios y están listos para descarga.</p>
                <p><strong>Firmantes:</strong> {signed_users}</p>
                <p><strong>Documentos:</strong> {self.document_count} archivo(s)</p>
                <p><strong>Carpeta:</strong> /Sites/Flujos/{self.creator_id.login}/{self.name}/</p>
                <p>Acceda a la solicitud para descargar los documentos firmados individualmente.</p>
                ''',
                'res_model_id': self.env['ir.model']._get(self._name).id,
                'res_id': self.id,
                'user_id': self.creator_id.id,
                'date_deadline': fields.Date.today(),
            })
            
            _logger.info(f"Notificación interna de finalización creada para la solicitud {self.id}")
            
        except Exception as e:
            _logger.error(f"Error creando notificación interna de finalización: {e}")

    def action_send_reminder(self):
        """Envía recordatorio al destinatario activo actual"""
        self.ensure_one()
        
        if self.state != 'sent':
            raise UserError(_('Solo se pueden enviar recordatorios para las solicitudes enviadas.'))
        
        current_recipient = self._get_current_active_recipient()
        if not current_recipient:
            raise UserError(_('No hay destinatario activo para enviar recordatorio.'))
        
        try:
            self.env['mail.message'].create({
                'subject': f'Recordatorio: Firma Pendiente - {self.name}',
                'body': f'''
                <p><strong>Recordatorio:</strong> Tiene pendiente la firma de documentos.</p>
                <ul>
                    <li><strong>Solicitud:</strong> {self.name}</li>
                    <li><strong>Enviado:</strong> {self.sent_date}</li>
                    <li><strong>Documentos:</strong> {self.document_count} archivo(s)</li>
                </ul>
                <p>Por favor, acceda al sistema para completar la firma.</p>
                ''',
                'message_type': 'notification',
                'model': self._name,
                'res_id': self.id,
                'partner_ids': [(4, current_recipient['user'].partner_id.id)],
                'author_id': self.creator_id.partner_id.id,
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Recordatorio enviado a {current_recipient["user"].name}',
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error(f"Error enviando recordatorio: {e}")
            raise UserError(_('Error enviando recordatorio: %s') % str(e))

    def action_download_all_signed(self):
        """Acción para descargar todos los documentos firmados individualmente"""
        self.ensure_one()
        
        documents_signed = self.document_ids.filtered(lambda d: d.is_signed)
        
        if not documents_signed:
            raise UserError(_('No hay documentos firmados para descargar.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/signature_workflow/descargar_multiples?workflow_id={self.id}',
            'target': 'new',
        }

    def _get_signed_local_wizard(self):
        """Obtiene el wizard de firma local asociado a esta solicitud"""
        if not self.sent_date:
            _logger.warning(f"Solicitud de firma {self.id} no tiene fecha de envío")
            return False
            
        recent_wizards = self.env['firma.documento.wizard'].search([
            ('create_date', '>=', self.sent_date),
            ('create_uid', '=', self.target_user_id.id),
            ('from_workflow', '=', True),
            ('workflow_id', '=', self.id)
        ], order='create_date desc', limit=1)
        
        if recent_wizards:
            return recent_wizards[0]
        
        fallback_wizards = self.env['firma.documento.wizard'].search([
            ('create_date', '>=', self.sent_date),
            ('create_uid', '=', self.target_user_id.id)
        ], order='create_date desc', limit=5)
        
        for wizard in fallback_wizards:
            wizard_doc_names = set(wizard.document_ids.mapped('document_name'))
            workflow_doc_names = set(self.document_ids.mapped('name'))
            
            if wizard_doc_names == workflow_doc_names:
                _logger.info(f"Encontrado wizard {wizard.id} por coincidencia de nombres para la solicitud {self.id}")
                return wizard
        
        _logger.warning(f"No se encontró wizard de firma para la solicitud {self.id}")
        return False

    def unlink(self):
        """Sobrescribe unlink para permitir eliminación solo al creador o administrador"""
        for record in self:
            if self.env.user.has_group('base.group_system'):
                continue
            
            if record.creator_id != self.env.user:
                raise UserError(_(
                    'Solo el creador de la solicitud (%s) puede eliminar este registro. '
                    'Usuario actual: %s'
                ) % (record.creator_id.name, self.env.user.name))
        
        return super(SignatureWorkflow, self).unlink()


class SignatureWorkflowDocument(models.Model):
    _name = 'signature.workflow.document'
    _description = 'Documento de la Solicitud de Firma'

    workflow_id = fields.Many2one('signature.workflow', string='Flujo', required=True, ondelete='cascade')
    name = fields.Char(string='Nombre del Documento', required=True)
    
    pdf_content = fields.Binary(string='Contenido PDF')
    pdf_filename = fields.Char(string='Nombre del Archivo')
    
    alfresco_file_id = fields.Many2one('alfresco.file', string='Archivo de Alfresco')
    
    download_url = fields.Char(string='URL de Descarga')
    
    is_signed = fields.Boolean(string='Firmado', default=False)
    signed_date = fields.Datetime(string='Fecha de Firma')
    
    moved_to_destination = fields.Boolean(string='Movido a Destino', default=False)
    move_date = fields.Datetime(string='Fecha de Movimiento')

    def action_download_document(self):
        """Descarga el documento firmado directamente desde Alfresco (última versión)"""
        self.ensure_one()
        
        _logger.info(f"[DOWNLOAD_DOC] ===== INICIO DESCARGA DOCUMENTO {self.id} =====")
        _logger.info(f"[DOWNLOAD_DOC] Documento: {self.name}")
        _logger.info(f"[DOWNLOAD_DOC] Firmado: {self.is_signed}")
        _logger.info(f"[DOWNLOAD_DOC] Alfresco file ID: {self.alfresco_file_id.id if self.alfresco_file_id else 'NINGUNO'}")
        
        if not self.is_signed:
            _logger.warning(f"[DOWNLOAD_DOC] Documento {self.name} no está firmado")
            raise UserError(_('El documento no está firmado aún.'))
        
        if not self.alfresco_file_id:
            _logger.error(f"[DOWNLOAD_DOC] No hay archivo de Alfresco asociado")
            raise UserError(_('No se encontró el archivo en Alfresco.'))
        
        download_url = f'/alfresco/file/{self.alfresco_file_id.id}/download'
        _logger.info(f"[DOWNLOAD_DOC] Descargando directamente desde Alfresco: {download_url}")
        
        return {
            'type': 'ir.actions.act_url',
            'url': download_url,
            'target': 'self',
        }
