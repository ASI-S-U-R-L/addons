# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import base64

_logger = logging.getLogger(__name__)


class LocalWorkflowWizard(models.TransientModel):
    _name = 'local.workflow.wizard'
    _description = 'Asistente para Iniciar Solicitud de Firma Digital Local'

    # Información básica del flujo
    name = fields.Char(
        string='Nombre de la Solicitud',
        required=True,
        default=lambda self: f'Solicitud de Firma - {fields.Datetime.now().strftime("%Y-%m-%d - %H-%M")}'
    )
    
    # Destinatario 1
    target_user_id_1 = fields.Many2one('res.users', string='Usuario Destinatario 1')
    signature_role_id_1 = fields.Many2one(
        'document.signature.tag',
        string='Rol de Firma 1',
        default=lambda self: self._get_default_signature_role()
    )
    signature_position_1 = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de la Firma 1', default='derecha')
    
    # Destinatario 2
    target_user_id_2 = fields.Many2one('res.users', string='Usuario Destinatario 2')
    signature_role_id_2 = fields.Many2one('document.signature.tag', string='Rol de Firma 2')
    signature_position_2 = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de la Firma 2')
    
    # Destinatario 3
    target_user_id_3 = fields.Many2one('res.users', string='Usuario Destinatario 3')
    signature_role_id_3 = fields.Many2one('document.signature.tag', string='Rol de Firma 3')
    signature_position_3 = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de la Firma 3')
    
    # Destinatario 4
    target_user_id_4 = fields.Many2one('res.users', string='Usuario Destinatario 4')
    signature_role_id_4 = fields.Many2one('document.signature.tag', string='Rol de Firma 4')
    signature_position_4 = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de la Firma 4')
    
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
    
    # Documentos locales
    document_ids = fields.One2many(
        'local.workflow.wizard.document',
        'wizard_id',
        string='Documentos a Firmar'
    )
    document_count = fields.Integer(string='Documentos Seleccionados', compute='_compute_document_count')
    
    # Notas del flujo
    notes = fields.Text(string='Notas de la Solicitud')
    
    # Campos para mostrar información
    target_user_info = fields.Html(string='Información del Usuario', compute='_compute_target_user_info')

    @api.model
    def _get_default_signature_role(self):
        """Obtiene el rol de firma por defecto"""
        return self.env['document.signature.tag'].search([], limit=1)

    @api.depends('document_ids')
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

    @api.depends('target_user_id_1', 'target_user_id_2', 'target_user_id_3', 'target_user_id_4')
    def _compute_target_user_info(self):
        """Muestra información de todos los usuarios destinatarios"""
        for record in self:
            users_info = []
            for i in range(1, 5):
                user = getattr(record, f'target_user_id_{i}')
                if user:
                    role = getattr(record, f'signature_role_id_{i}')
                    position = getattr(record, f'signature_position_{i}')
                    position_label = dict(record._fields['signature_position_1'].selection).get(position, 'No especificada')
                    
                    users_info.append(f"""
                    <div class="mb-2">
                        <strong>Destinatario {i}:</strong> {user.name}<br/>
                        <small>Email: {user.email or 'No especificado'}</small><br/>
                        <small>Rol: {role.name if role else 'No especificado'}</small><br/>
                        <small>Posición: {position_label}</small>
                    </div>
                    """)
            
            if users_info:
                record.target_user_info = f"""
                <div class="alert alert-info">
                    <h5><i class="fa fa-users"></i> Usuarios Destinatarios:</h5>
                    {''.join(users_info)}
                </div>
                """
            else:
                record.target_user_info = False

    @api.constrains('target_user_id_1', 'target_user_id_2', 'target_user_id_3', 'target_user_id_4',
                    'signature_position_1', 'signature_position_2', 'signature_position_3', 'signature_position_4',
                    'signature_role_id_1', 'signature_role_id_2', 'signature_role_id_3', 'signature_role_id_4')
    def _check_no_duplicate_positions_roles(self):
        """Valida que no haya posiciones ni roles duplicados entre destinatarios activos"""
        for record in self:
            active_recipients = []
            positions = []
            roles = []
            
            for i in range(1, 5):
                user = getattr(record, f'target_user_id_{i}')
                if user:
                    active_recipients.append(i)
                    position = getattr(record, f'signature_position_{i}')
                    role = getattr(record, f'signature_role_id_{i}')
                    
                    # Validar posición
                    if position:
                        if position in positions:
                            position_label = dict(record._fields['signature_position_1'].selection).get(position)
                            raise ValidationError(_(
                                f'La posición "{position_label}" está duplicada. '
                                f'Cada destinatario debe tener una posición única.'
                            ))
                        positions.append(position)
                    
                    # Validar rol
                    if role:
                        if role.id in [r.id for r in roles]:
                            raise ValidationError(_(
                                f'El rol "{role.name}" está duplicado. '
                                f'Cada destinatario debe tener un rol único.'
                            ))
                        roles.append(role)

    @api.onchange('target_user_id_1','target_user_id_2','target_user_id_3','target_user_id_4')
    def _onchange_target_user_id_1(self):
        """Set domain to exclude current user"""
        return {
            'domain': {
                'target_user_id_1': [('id', '!=', self.env.user.id), ('id', '!=', self.target_user_id_2.id), ('id', '!=', self.target_user_id_3.id), ('id', '!=', self.target_user_id_4.id), ('active', '=', True)]
            }
        }

    @api.onchange('target_user_id_1','target_user_id_2','target_user_id_3','target_user_id_4')
    def _onchange_target_user_id_2(self):
        """Set domain to exclude current user"""
        return {
            'domain': {
                'target_user_id_2': [('id', '!=', self.env.user.id), ('id', '!=', self.target_user_id_1.id), ('id', '!=', self.target_user_id_3.id), ('id', '!=', self.target_user_id_4.id), ('active', '=', True)]
            }
        }

    @api.onchange('target_user_id_1','target_user_id_2','target_user_id_3','target_user_id_4')
    def _onchange_target_user_id_3(self):
        """Set domain to exclude current user"""
        return {
            'domain': {
                'target_user_id_3': [('id', '!=', self.env.user.id), ('id', '!=', self.target_user_id_1.id), ('id', '!=', self.target_user_id_2.id), ('id', '!=', self.target_user_id_4.id), ('active', '=', True)]
            }
        }

    @api.onchange('target_user_id_1','target_user_id_2','target_user_id_3','target_user_id_4')
    def _onchange_target_user_id_4(self):
        """Set domain to exclude current user"""
        return {
            'domain': {
                'target_user_id_4': [('id', '!=', self.env.user.id), ('id', '!=', self.target_user_id_1.id), ('id', '!=', self.target_user_id_2.id), ('id', '!=', self.target_user_id_3.id), ('active', '=', True)]
            }
        }
    
    @api.onchange('target_user_id_1', 'signature_role_id_1', 'signature_position_1',
                  'target_user_id_2', 'signature_role_id_2', 'signature_position_2',
                  'target_user_id_3', 'signature_role_id_3', 'signature_position_3',
                  'target_user_id_4', 'signature_role_id_4', 'signature_position_4')
    def _onchange_update_target_user_info(self):
        """Actualiza la información de los usuarios destinatarios"""
        self._compute_target_user_info()

    def action_create_workflow(self):
        """Crea el flujo de trabajo con los documentos seleccionados"""
        self.ensure_one()
        
        # Validar que haya al menos un destinatario
        active_users = [
            self.target_user_id_1, self.target_user_id_2,
            self.target_user_id_3, self.target_user_id_4
        ]
        active_users = [u for u in active_users if u]
        
        if not active_users:
            raise UserError(_('Debe especificar al menos un destinatario.'))
        
        # Validar que haya documentos
        if not self.document_ids:
            raise UserError(_('Debe agregar al menos un documento.'))
        
        for i in range(1, 5):
            user = getattr(self, f'target_user_id_{i}')
            if user:
                role = getattr(self, f'signature_role_id_{i}')
                position = getattr(self, f'signature_position_{i}')
                
                if not role:
                    raise UserError(_(f'Debe seleccionar un rol de firma para el destinatario {i}.'))
                if not position:
                    raise UserError(_(f'Debe seleccionar una posición de firma para el destinatario {i}.'))
        
        try:
            # Crear el flujo de trabajo
            workflow_vals = {
                'name': self.name,
                'creator_id': self.env.user.id,
                'notes': self.notes,
                'signature_opaque_background': self.signature_opaque_background,
                'sign_all_pages': self.sign_all_pages,
            }
            
            # Agregar destinatarios
            for i in range(1, 5):
                user = getattr(self, f'target_user_id_{i}')
                if user:
                    workflow_vals[f'target_user_id_{i}'] = user.id
                    workflow_vals[f'signature_role_id_{i}'] = getattr(self, f'signature_role_id_{i}').id
                    workflow_vals[f'signature_position_{i}'] = getattr(self, f'signature_position_{i}')
            
            workflow = self.env['local.workflow'].create(workflow_vals)
            
            # Crear documentos del flujo
            for doc_line in self.document_ids:
                # Crear attachment para el documento original
                attachment = self.env['ir.attachment'].create({
                    'name': doc_line.name,
                    'datas': doc_line.pdf_content,
                    'res_model': 'local.workflow',
                    'res_id': workflow.id,
                    'mimetype': 'application/pdf',
                    'description': f'Documento original de la solicitud {workflow.name}',
                })
                
                # Crear documento del flujo
                self.env['local.workflow.document'].create({
                    'workflow_id': workflow.id,
                    'name': doc_line.name,
                    'attachment_id': attachment.id,
                })
            
            _logger.info(
                f"Flujo de trabajo local {workflow.id} creado con {len(self.document_ids)} documentos "
                f"y {len(active_users)} destinatarios"
            )
            
            workflow.action_send_for_signature()
            
            # Abrir el flujo creado
            return {
                'type': 'ir.actions.act_window',
                'name': _('Solicitud Creada Exitosamente'),
                'res_model': 'local.workflow',
                'res_id': workflow.id,
                'view_mode': 'form',
                'target': 'current',
            }
        
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error inesperado creando la solicitud: {e}")
            raise UserError(_('Error inesperado al crear la solicitud: %s') % str(e))


class LocalWorkflowWizardDocument(models.TransientModel):
    _name = 'local.workflow.wizard.document'
    _description = 'Documento Temporal para Wizard de Flujo Local'

    wizard_id = fields.Many2one('local.workflow.wizard', string='Wizard', required=True, ondelete='cascade')
    name = fields.Char(string='Nombre del Documento', required=True)
    pdf_content = fields.Binary(string='Contenido PDF', required=True, attachment=False)
    pdf_filename = fields.Char(string='Nombre del Archivo')
    
    # Información del archivo
    file_size = fields.Char(string='Tamaño', compute='_compute_file_info')

    @api.depends('pdf_content')
    def _compute_file_info(self):
        for record in self:
            if record.pdf_content:
                try:
                    size_bytes = len(base64.b64decode(record.pdf_content))
                    if size_bytes < 1024:
                        record.file_size = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        record.file_size = f"{size_bytes / 1024:.1f} KB"
                    else:
                        record.file_size = f"{size_bytes / (1024 * 1024):.1f} MB"
                except:
                    record.file_size = "N/A"
            else:
                record.file_size = "N/A"

    @api.onchange('pdf_content')
    def _onchange_pdf_content(self):
        """Actualiza el nombre del documento basado en el archivo"""
        if self.pdf_content and self.pdf_filename and not self.name:
            self.name = self.pdf_filename
