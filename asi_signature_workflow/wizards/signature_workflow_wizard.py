# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class SignatureWorkflowWizard(models.TransientModel):
    _name = 'signature.workflow.wizard'
    _description = 'Asistente para Iniciar Solicitud de Firma Digital'

    # Información básica del flujo
    name = fields.Char(string='Nombre de la Solicitud', 
                      default=lambda self: f'Solicitud de Firma - {fields.Datetime.now().strftime("%Y-%m-%d - %H-%M")}')
    
    # Destinatario 1
    target_user_id_1 = fields.Many2one('res.users', string='Usuario Destinatario 1')
    signature_role_id_1 = fields.Many2one('document.signature.tag', string='Rol de Firma 1',
                                          default=lambda self: self._get_default_signature_role())
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
    
    # Campos de compatibilidad (deprecados pero mantenidos)
    target_user_id = fields.Many2one('res.users', string='Usuario Destinatario (Deprecado)', 
                                    compute='_compute_legacy_fields', store=False)
    signature_role_id = fields.Many2one('document.signature.tag', string='Rol de Firma (Deprecado)',
                                       compute='_compute_legacy_fields', store=False)
    signature_position = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ], string='Posición de la Firma (Deprecado)', compute='_compute_legacy_fields', store=False)
    
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
    
    # Selección del origen de documentos
    document_source = fields.Selection([
        ('local', 'Documentos Locales'),
        ('alfresco', 'Documentos de Alfresco')
    ], string='Origen de Documentos')
    
    # Documentos seleccionados
    selected_document_ids = fields.Many2many('signature.workflow.document.temp', 
                                           string='Documentos Seleccionados')
    document_count = fields.Integer(string='Documentos Seleccionados', 
                                  compute='_compute_document_count')
    
    # Notas del flujo
    notes = fields.Text(string='Notas de la Solicitud',)
    
    # Validaciones de configuración
    has_alfresco_config = fields.Boolean(string='Alfresco Configurado', 
                                       compute='_compute_alfresco_config')
    
    # Campos para mostrar información
    target_user_info = fields.Html(string='Información del Usuario', 
                                 compute='_compute_target_user_info')

    @api.depends('selected_document_ids')
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.selected_document_ids)

    @api.depends()
    def _compute_alfresco_config(self):
        """Verifica si Alfresco está configurado"""
        for record in self:
            config = self.env['ir.config_parameter'].sudo()
            
            _logger.info("[ALFRESCO_CONFIG] Checking Alfresco configuration...")
            
            url_params = [
                'asi_alfresco_integration.alfresco_server_url',
                'alfresco.server_url',
                'alfresco_server_url'
            ]
            user_params = [
                'asi_alfresco_integration.alfresco_username', 
                'alfresco.username',
                'alfresco_username'
            ]
            pwd_params = [
                'asi_alfresco_integration.alfresco_password',
                'alfresco.password', 
                'alfresco_password'
            ]
            
            url = None
            user = None
            pwd = None
            
            # Try to find URL parameter
            for param in url_params:
                url = config.get_param(param)
                if url:
                    _logger.info("[ALFRESCO_CONFIG] Found URL with param: %s = %s", param, url)
                    break
            
            # Try to find username parameter
            for param in user_params:
                user = config.get_param(param)
                if user:
                    _logger.info("[ALFRESCO_CONFIG] Found username with param: %s = %s", param, user)
                    break
            
            # Try to find password parameter
            for param in pwd_params:
                pwd = config.get_param(param)
                if pwd:
                    _logger.info("[ALFRESCO_CONFIG] Found password with param: %s = [HIDDEN]", param)
                    break
            
            _logger.info("[ALFRESCO_CONFIG] Final values - URL: %s, User: %s, Password: %s", bool(url), bool(user), bool(pwd))
            
            has_config = bool(url and user and pwd)
            _logger.info("[ALFRESCO_CONFIG] Configuration check result: %s", has_config)
            
            record.has_alfresco_config = has_config

    @api.depends('target_user_id_1', 'signature_role_id_1', 'signature_position_1')
    def _compute_legacy_fields(self):
        """Mantiene compatibilidad con campos antiguos usando el primer destinatario"""
        for record in self:
            record.target_user_id = record.target_user_id_1
            record.signature_role_id = record.signature_role_id_1
            record.signature_position = record.signature_position_1

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
                    users_info.append(f"""
                    <div class="mb-2">
                        <strong>Destinatario {i}:</strong> {user.name}<br/>
                        <small>Email: {user.email or 'No especificado'}</small><br/>
                        <small>Rol: {role.name if role else 'No especificado'}</small><br/>
                        <small>Posición: {dict(record._fields['signature_position_1'].selection).get(position, 'No especificada')}</small>
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
                            raise ValidationError(_(
                                f'La posición "{dict(record._fields["signature_position_1"].selection).get(position)}" '
                                f'está duplicada. Cada destinatario debe tener una posición única.'
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

    @api.onchange('document_source')
    def _onchange_document_source(self):
        """Validar configuración cuando se cambia el origen"""
        self._compute_alfresco_config()
        if self.document_source == 'alfresco' and not self.has_alfresco_config:
            return {
                'warning': {
                    'title': _('Configuración Requerida'),
                    'message': _('Alfresco no está configurado. Por favor, configure la integración con Alfresco en Configuración > Técnico > Parámetros del Sistema.')
                }
            }

    def open_document_selection(self):
        """Abre el wizard de selección de documentos directamente"""
        self.ensure_one()
        
        _logger.info("[v0] open_document_selection called for wizard ID: %s", self.id)
        _logger.info("[v0] Current document_source: %s", self.document_source)
        _logger.info("[v0] Current target_user_id_1: %s", self.target_user_id_1.id if self.target_user_id_1 else None)
        
        # Validate required fields
        if not self.target_user_id_1:
            raise UserError(_('Debe seleccionar un usuario destinatario.'))
        
        if not self.signature_role_id_1:
            raise UserError(_('Debe seleccionar un rol de firma.'))
        
        if not self.document_source:
            raise UserError(_('Debe seleccionar un origen de documentos.'))
        
        if self.document_source == 'alfresco' and not self.has_alfresco_config:
            raise UserError(_('Alfresco no está configurado correctamente.'))
        
        # Create the PDF selection wizard
        _logger.info("[v0] Creating PdfSelectionWizard with selection_type: %s", self.document_source)
        
        try:
            pdf_wizard = self.env['pdf.selection.wizard'].create({
                'workflow_wizard_id': self.id,
                'selection_type': self.document_source,
            })
            _logger.info("[v0] Created PdfSelectionWizard with ID: %s", pdf_wizard.id)
        except Exception as e:
            _logger.error("[v0] Error creating PdfSelectionWizard: %s", str(e))
            raise UserError(_('Error al crear el asistente de selección: %s') % str(e))
        
        # Return action to open the PDF selection wizard
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Seleccionar Documentos PDF',
            'res_model': 'pdf.selection.wizard',
            'res_id': pdf_wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_selection_type': self.document_source,
                'workflow_wizard_id': self.id,
            }
        }
        
        _logger.info("[v0] Returning action: %s", action)
        return action

    def create_workflow(self):
        """Crea la solicitud de firma final con múltiples destinatarios"""
        self.ensure_one()
        
        if not self.target_user_id_1:
            raise UserError(_('Debe seleccionar al menos un usuario destinatario.'))
        
        for i in range(1, 5):
            user = getattr(self, f'target_user_id_{i}')
            if user:
                role = getattr(self, f'signature_role_id_{i}')
                position = getattr(self, f'signature_position_{i}')
                
                if not role:
                    raise UserError(_(f'Debe seleccionar un rol de firma para el destinatario {i}.'))
                if not position:
                    raise UserError(_(f'Debe seleccionar una posición de firma para el destinatario {i}.'))
        
        if not self.document_source:
            raise UserError(_('Debe seleccionar un origen de documentos.'))
        
        if not self.selected_document_ids:
            raise UserError(_('Debe seleccionar al menos un documento.'))
        
        try:
            workflow_vals = {
                'name': self.name,
                'creator_id': self.env.user.id,
                'signature_opaque_background': self.signature_opaque_background,
                'sign_all_pages': self.sign_all_pages,
                'document_source': self.document_source,
                'notes': self.notes,
            }
            
            # Agregar destinatarios y sus configuraciones
            for i in range(1, 5):
                user = getattr(self, f'target_user_id_{i}')
                if user:
                    workflow_vals[f'target_user_id_{i}'] = user.id
                    workflow_vals[f'signature_role_id_{i}'] = getattr(self, f'signature_role_id_{i}').id
                    workflow_vals[f'signature_position_{i}'] = getattr(self, f'signature_position_{i}')
            
            workflow = self.env['signature.workflow'].create(workflow_vals)
            
            # Crear documentos del flujo
            for temp_doc in self.selected_document_ids:
                doc_vals = {
                    'workflow_id': workflow.id,
                    'name': temp_doc.name,
                }
                
                if self.document_source == 'alfresco':
                    doc_vals['alfresco_file_id'] = temp_doc.alfresco_file_id.id
                else:
                    doc_vals.update({
                        'pdf_content': temp_doc.pdf_content,
                        'pdf_filename': temp_doc.pdf_filename,
                    })
                
                self.env['signature.workflow.document'].create(doc_vals)
            
            workflow.action_send_for_signature()
            
            return {
                'type': 'ir.actions.act_window',
                'name': 'Solicitud Creada Exitosamente',
                'res_model': 'signature.workflow',
                'res_id': workflow.id,
                'view_mode': 'form',
                'target': 'current',
            }
                
        except UserError:
            raise
        except Exception as e:
            _logger.error(f"Error inesperado creando la solicitud: {e}")
            raise UserError(_('Error inesperado al crear la solicitud: %s') % str(e))

    def _get_default_signature_role(self):
        """Get the first available signature role as default"""
        role = self.env['document.signature.tag'].search([], limit=1)
        return role.id if role else False

    def _process_alfresco_signature(self):
        """Procesa la firma de documentos de Alfresco"""
        alfresco_files = self.selected_document_ids.mapped('alfresco_file_id')
        
        # Crear wizard de firma de Alfresco con configuración fija del flujo
        wizard = self.env['alfresco.firma.wizard'].create({
            'file_ids': [(6, 0, alfresco_files.ids)],
            'signature_role': self.signature_role_id.id,
            'signature_position': self.signature_position,
            'signature_opaque_background': self.signature_opaque_background,
            'sign_all_pages': self.sign_all_pages,
        })
        
        # Hacer campos de rol y posición de solo lectura para el destinatario
        return {
            'type': 'ir.actions.act_window',
            'name': 'Firmar Documentos de la Solicitud',
            'res_model': 'alfresco.firma.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'workflow_id': self.id,
                'from_workflow': True,
                'readonly_signature_config': True,  # Indicar que la configuración es de solo lectura
            }
        }

    def _process_local_signature(self):
        """Procesa la firma de documentos locales"""
        # Crear documentos temporales para el wizard de firma local
        document_lines = []
        for doc in self.selected_document_ids:
            document_lines.append((0, 0, {
                'document_name': doc.name,
                'pdf_document': doc.pdf_content,
            }))
        
        # Crear wizard de firma local con configuración fija del flujo
        wizard = self.env['firma.documento.wizard'].create({
            'document_ids': document_lines,
            'signature_role': self.signature_role_id.id,
            'signature_position': self.signature_position,
            'signature_opaque_background': self.signature_opaque_background,
            'sign_all_pages': self.sign_all_pages,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Firmar Documentos de la Solicitud',
            'res_model': 'firma.documento.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'workflow_id': self.id,
                'from_workflow': True,
                'readonly_signature_config': True,  # Indicar que la configuración es de solo lectura
            }
        }

class SignatureWorkflowDocumentTemp(models.TransientModel):
    _name = 'signature.workflow.document.temp'
    _description = 'Documento Temporal para la Solicitud de Firma'

    name = fields.Char(string='Nombre', required=True)
    
    # Para documentos locales
    pdf_content = fields.Binary(string='Contenido PDF')
    pdf_filename = fields.Char(string='Nombre del Archivo')
    
    # Para documentos de Alfresco
    alfresco_file_id = fields.Many2one('alfresco.file', string='Archivo de Alfresco')
    
    # Información adicional
    file_size = fields.Char(string='Tamaño', compute='_compute_file_info')
    file_type = fields.Char(string='Tipo', compute='_compute_file_info')

    @api.depends('pdf_content', 'alfresco_file_id')
    def _compute_file_info(self):
        for record in self:
            if record.alfresco_file_id:
                record.file_size = record.alfresco_file_id.file_size_human
                record.file_type = 'Alfresco PDF'
            elif record.pdf_content:
                import base64
                try:
                    size_bytes = len(base64.b64decode(record.pdf_content))
                    if size_bytes < 1024:
                        record.file_size = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        record.file_size = f"{size_bytes / 1024:.1f} KB"
                    else:
                        record.file_size = f"{size_bytes / (1024 * 1024):.1f} MB"
                    record.file_type = 'PDF Local'
                except:
                    record.file_size = "N/A"
                    record.file_type = 'PDF Local'
            else:
                record.file_size = "N/A"
                record.file_type = "Desconocido"
