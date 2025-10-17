# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import base64
from datetime import timedelta

_logger = logging.getLogger(__name__)


class LocalWorkflow(models.Model):
    _name = 'local.workflow'
    _description = 'Solicitud de Firma Digital Local'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Nombre de la Solicitud', required=True, tracking=True)
    creator_id = fields.Many2one('res.users', string='Creador', required=True, 
                                 default=lambda self: self.env.user, readonly=True)
    
    # Destinatario 1
    target_user_id_1 = fields.Many2one('res.users', string='Destinatario 1', tracking=True)
    signature_role_id_1 = fields.Many2one('document.signature.tag', string='Rol de Firma 1')
    signature_position_1 = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de Firma 1')
    signed_by_user_1 = fields.Boolean(string='Firmado por Usuario 1', default=False, readonly=True)
    signed_date_1 = fields.Datetime(string='Fecha Firma Usuario 1', readonly=True)
    
    # Destinatario 2
    target_user_id_2 = fields.Many2one('res.users', string='Destinatario 2', tracking=True)
    signature_role_id_2 = fields.Many2one('document.signature.tag', string='Rol de Firma 2')
    signature_position_2 = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de Firma 2')
    signed_by_user_2 = fields.Boolean(string='Firmado por Usuario 2', default=False, readonly=True)
    signed_date_2 = fields.Datetime(string='Fecha Firma Usuario 2', readonly=True)
    
    # Destinatario 3
    target_user_id_3 = fields.Many2one('res.users', string='Destinatario 3', tracking=True)
    signature_role_id_3 = fields.Many2one('document.signature.tag', string='Rol de Firma 3')
    signature_position_3 = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de Firma 3')
    signed_by_user_3 = fields.Boolean(string='Firmado por Usuario 3', default=False, readonly=True)
    signed_date_3 = fields.Datetime(string='Fecha Firma Usuario 3', readonly=True)
    
    # Destinatario 4
    target_user_id_4 = fields.Many2one('res.users', string='Destinatario 4', tracking=True)
    signature_role_id_4 = fields.Many2one('document.signature.tag', string='Rol de Firma 4')
    signature_position_4 = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de Firma 4')
    signed_by_user_4 = fields.Boolean(string='Firmado por Usuario 4', default=False, readonly=True)
    signed_date_4 = fields.Datetime(string='Fecha Firma Usuario 4', readonly=True)
    
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
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('signed', 'Firmado'),
        ('completed', 'Completado'),
        ('cancelled', 'Cancelado'),
        ('rejected', 'Rechazado')
    ], string='Estado', default='draft', required=True, tracking=True)
    
    # Documentos del flujo
    document_ids = fields.One2many('local.workflow.document', 'workflow_id', string='Documentos')
    document_count = fields.Integer(string='Cantidad de Documentos', compute='_compute_document_count')
    
    # Fechas importantes
    sent_date = fields.Datetime(string='Fecha de Envío', readonly=True)
    signed_date = fields.Datetime(string='Fecha de Firma', readonly=True)
    completed_date = fields.Datetime(string='Fecha de Finalización', readonly=True)
    rejection_date = fields.Datetime(string='Fecha de Rechazo', readonly=True)
    
    # Notas y observaciones
    notes = fields.Text(string='Notas')
    signature_notes = fields.Text(string='Notas de Firma', readonly=True)
    rejection_notes = fields.Text(string='Motivo del Rechazo', readonly=True)

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
            
            # Obtener destinatarios activos con sus datos
            recipients = []
            for i in range(1, 5):
                user = getattr(record, f'target_user_id_{i}')
                role = getattr(record, f'signature_role_id_{i}')
                position = getattr(record, f'signature_position_{i}')
                
                if user:
                    # Validar que si hay usuario, también haya rol y posición
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
            
            # Validar que no se repitan posiciones
            positions = [r['position'] for r in recipients]
            if len(positions) != len(set(positions)):
                raise ValidationError(_('Las posiciones de firma no pueden repetirse entre destinatarios.'))
            
            # Validar que no se repitan roles
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
                'date_deadline': fields.Date.today() + timedelta(days=7),
            })
            _logger.info(f"Actividad de firma creada para usuario {recipient_data['user'].name} (destinatario {recipient_data['index']}) en solicitud {self.id}")
        except Exception as e:
            _logger.error(f"Error creando actividad de firma: {e}")

    def _send_signature_request_notification(self):
        """Crea notificaciones internas para todos los destinatarios"""
        self.ensure_one()
        
        recipients = self._get_active_recipients()
        
        for recipient in recipients:
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

    def action_send_for_signature(self):
        """Envía la solicitud de firma a los destinatarios"""
        self.ensure_one()
        
        if not self.document_ids:
            raise UserError(_('Debe agregar al menos un documento antes de enviar la solicitud.'))
        
        recipients = self._get_active_recipients()
        if not recipients:
            raise UserError(_('Debe especificar al menos un destinatario.'))
        
        self.write({
            'state': 'sent',
            'sent_date': fields.Datetime.now()
        })
        
        for recipient in recipients:
            self._create_signature_activity(recipient)
        
        self._send_signature_request_notification()
        
        recipient_names = ', '.join([r['user'].name for r in recipients])
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Solicitud enviada exitosamente a: {recipient_names}',
                'type': 'success',
            }
        }

    def action_sign_documents(self):
        """Abre el wizard de firma para el usuario actual"""
        self.ensure_one()
        
        if self.state != 'sent':
            raise UserError(_('Solo se pueden firmar solicitudes en estado "Enviado".'))
        
        recipient_data = self._get_current_user_recipient_data()
        if not recipient_data:
            raise UserError(_('Usted no es un destinatario de esta solicitud de firma.'))
        
        if recipient_data['signed']:
            raise UserError(_('Usted ya ha firmado esta solicitud.'))
        
        # Preparar documentos para el wizard de firma
        documents_to_sign = []
        for doc in self.document_ids:
            if doc.attachment_id:
                documents_to_sign.append((0, 0, {
                    'document_name': doc.name,
                    'pdf_content': doc.attachment_id.datas,
                }))
        
        if not documents_to_sign:
            raise UserError(_('No hay documentos disponibles para firmar.'))
        
        # Crear wizard de firma
        wizard = self.env['firma.documento.wizard'].create({
            'from_workflow': True,
            'workflow_id': self.id,
            'readonly_signature_config': True,
            'signature_role': recipient_data['role'].id,
            'signature_position': recipient_data['position'],
            'signature_opaque_background': self.signature_opaque_background,
            'sign_all_pages': self.sign_all_pages,
            'document_ids': documents_to_sign,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Firmar Documentos'),
            'res_model': 'firma.documento.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'from_workflow': True,
                'workflow_id': self.id,
                'readonly_signature_config': True,
            }
        }

    def action_mark_as_signed(self):
        """Marca la solicitud como firmada por el usuario actual"""
        self.ensure_one()
        
        recipient_data = self._get_current_user_recipient_data()
        if not recipient_data:
            _logger.warning(f"Usuario {self.env.user.name} intentó marcar como firmado pero no es destinatario")
            return
        
        # Marcar como firmado
        setattr(self, f'signed_by_user_{recipient_data["index"]}', True)
        setattr(self, f'signed_date_{recipient_data["index"]}', fields.Datetime.now())
        
        self.message_post(
            body=_('Documentos firmados por %s') % self.env.user.name,
            subject=_('Documentos Firmados')
        )
        
        # Verificar si todos los destinatarios han firmado
        all_signed = all([
            getattr(self, f'signed_by_user_{r["index"]}')
            for r in self._get_active_recipients()
        ])
        
        if all_signed:
            self.write({
                'state': 'signed',
                'signed_date': fields.Datetime.now()
            })
            
            # Notificar al creador
            self.message_post(
                body=_('Todos los destinatarios han firmado los documentos.'),
                subject=_('Firma Completada'),
                partner_ids=[self.creator_id.partner_id.id],
                message_type='notification',
            )
        
        _logger.info(f"Solicitud {self.id} marcada como firmada por usuario {recipient_data['index']}")

    def action_mark_as_completed(self):
        """Marca la solicitud como completada"""
        self.ensure_one()
        
        if self.state != 'signed':
            raise UserError(_('Solo se pueden completar solicitudes en estado "Firmado".'))
        
        # Verificar que todos los documentos estén firmados
        unsigned_docs = self.document_ids.filtered(lambda d: not d.is_signed)
        if unsigned_docs:
            raise UserError(_('Hay documentos sin firmar. No se puede completar la solicitud.'))
        
        self.write({
            'state': 'completed',
            'completed_date': fields.Datetime.now()
        })
        
        self.message_post(
            body=_('Solicitud de firma completada exitosamente'),
            subject=_('Solicitud Completada')
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Solicitud completada exitosamente'),
                'type': 'success',
            }
        }

    def action_reject_workflow(self):
        """Abre el wizard para rechazar la solicitud"""
        self.ensure_one()
        
        if self.state != 'sent':
            raise UserError(_('Solo se pueden rechazar solicitudes en estado "Enviado".'))
        
        recipient_data = self._get_current_user_recipient_data()
        if not recipient_data:
            raise UserError(_('Solo los destinatarios pueden rechazar la solicitud.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rechazar Solicitud'),
            'res_model': 'local.workflow.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_workflow_id': self.id}
        }

    def _process_rejection(self, rejection_notes):
        """Procesa el rechazo de la solicitud"""
        self.ensure_one()
        
        self.write({
            'state': 'rejected',
            'rejection_date': fields.Datetime.now(),
            'rejection_notes': rejection_notes
        })
        
        # Notificar al creador
        self.message_post(
            body=_(
                'Solicitud rechazada por %s<br/>'
                '<b>Motivo:</b> %s'
            ) % (self.env.user.name, rejection_notes),
            subject=_('Solicitud Rechazada'),
            partner_ids=[self.creator_id.partner_id.id],
            message_type='notification',
        )
        
        _logger.info(f"Solicitud {self.id} rechazada por {self.env.user.name}")

    def action_send_reminder(self):
        """Envía recordatorio a los destinatarios que no han firmado"""
        self.ensure_one()
        
        if self.state != 'sent':
            raise UserError(_('Solo se pueden enviar recordatorios para solicitudes en estado "Enviado".'))
        
        pending_recipients = [
            r for r in self._get_active_recipients()
            if not r['signed']
        ]
        
        if not pending_recipients:
            raise UserError(_('Todos los destinatarios ya han firmado.'))
        
        for recipient in pending_recipients:
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
                    'partner_ids': [(4, recipient['user'].partner_id.id)],
                    'author_id': self.creator_id.partner_id.id,
                })
            except Exception as e:
                _logger.error(f"Error enviando recordatorio a destinatario {recipient['index']}: {e}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Recordatorio enviado a {len(pending_recipients)} destinatario(s)',
                'type': 'success',
            }
        }

    def action_download_all_signed(self):
        """Redirige a la página de descarga de documentos firmados"""
        self.ensure_one()
        
        if self.state != 'completed':
            raise UserError(_('Solo se pueden descargar documentos de solicitudes completadas.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/local_workflow/download_signed/{self.id}',
            'target': 'self',
        }


class LocalWorkflowDocument(models.Model):
    _name = 'local.workflow.document'
    _description = 'Documento de la Solicitud de Firma Local'

    workflow_id = fields.Many2one('local.workflow', string='Flujo', required=True, ondelete='cascade')
    name = fields.Char(string='Nombre del Documento', required=True)
    
    # Attachment original
    attachment_id = fields.Many2one('ir.attachment', string='Documento Original', ondelete='restrict')
    
    # Attachment firmado
    signed_attachment_id = fields.Many2one('ir.attachment', string='Documento Firmado', ondelete='restrict')
    
    # Estado del documento
    is_signed = fields.Boolean(string='Firmado', default=False, readonly=True)
    signed_date = fields.Datetime(string='Fecha de Firma', readonly=True)
    
    # Información del archivo
    file_size = fields.Char(string='Tamaño', compute='_compute_file_info')
    mimetype = fields.Char(string='Tipo MIME', related='attachment_id.mimetype', readonly=True)

    @api.depends('attachment_id', 'signed_attachment_id')
    def _compute_file_info(self):
        for record in self:
            attachment = record.signed_attachment_id or record.attachment_id
            if attachment and attachment.file_size:
                size_bytes = attachment.file_size
                if size_bytes < 1024:
                    record.file_size = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    record.file_size = f"{size_bytes / 1024:.1f} KB"
                else:
                    record.file_size = f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                record.file_size = "N/A"

    def action_download_document(self):
        """Descarga el documento firmado"""
        self.ensure_one()
        
        if not self.is_signed or not self.signed_attachment_id:
            raise UserError(_('El documento no está firmado aún.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.signed_attachment_id.id}?download=true',
            'target': 'self',
        }

    def action_preview_document(self):
        """Previsualiza el documento"""
        self.ensure_one()
        
        attachment = self.signed_attachment_id or self.attachment_id
        if not attachment:
            raise UserError(_('No hay documento disponible para previsualizar.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}',
            'target': 'new',
        }
