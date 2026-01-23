# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import logging

_logger = logging.getLogger(__name__)

class DocumentoFirma(models.Model):
    _name = 'documento.firma'
    _description = 'Documento para Firma'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Nombre del Documento',
        required=True,
        tracking=True
    )
    
    document_file = fields.Binary(
        string='Archivo PDF',
        required=True,
        help='Archivo PDF que será firmado'
    )
    
    document_filename = fields.Char(
        string='Nombre del Archivo'
    )
    
    state = fields.Selection([
        ('borrador', 'Borrador'),
        ('pendiente', 'Pendiente de Firma'),
        ('firmado', 'Firmado'),
        ('rechazado', 'Rechazado'),
        ('vencido', 'Vencido')
    ], string='Estado', default='borrador', tracking=True)
    
    solicitante_id = fields.Many2one(
        'res.users',
        string='Solicitante',
        default=lambda self: self.env.user,
        required=True,
        tracking=True
    )
    
    firmante_ids = fields.Many2many(
        'res.users',
        string='Firmantes',
        help='Usuarios que deben firmar este documento'
    )
    
    fecha_vencimiento = fields.Date(
        string='Fecha de Vencimiento',
        help='Fecha límite para firmar el documento'
    )
    
    motivo = fields.Text(
        string='Motivo/Descripción',
        help='Descripción del documento o motivo de la solicitud'
    )
    
    signature_position = fields.Selection([
        ('derecha', 'Derecha'),
        ('izquierda', 'Izquierda'),
        ('centro', 'Centro')
    ], string='Posición de Firma', default='derecha')
    
    signature_role = fields.Many2one(
        'document.signature.tag',
        string='Rol de Firma'
    )
    
    signature_password = fields.Char(
        string='Contraseña de Certificado'
    )
    
    signature_opaque_background = fields.Boolean(
        string='Fondo Opaco',
        default=False
    )
    
    sign_all_pages = fields.Boolean(
        string='Firmar Todas las Páginas',
        default=False
    )
    
    certificate_wizard = fields.Binary(
        string='Certificado Digital'
    )
    
    certificate_wizard_name = fields.Char(
        string='Nombre del Certificado'
    )
    
    wizard_signature_image = fields.Binary(
        string='Imagen de Firma'
    )
    
    documentos_firmados = fields.Binary(
        string='Documentos Firmados'
    )
    
    documentos_firmados_filename = fields.Char(
        string='Nombre del Archivo Firmado'
    )
    
    # Campos para el flujo de firma
    firma_actual = fields.Integer(
        string='Firma Actual',
        default=1
    )
    
    total_firmas = fields.Integer(
        string='Total de Firmas',
        compute='_compute_total_firmas',
        store=True
    )
    
    porcentaje_firmas = fields.Float(
        string='Porcentaje Firmado',
        compute='_compute_porcentaje_firmas',
        store=True
    )
    
    # Relación con solicitudes de firma
    solicitud_firma_ids = fields.One2many(
        'solicitud.firma',
        'documento_id',
        string='Solicitudes de Firma'
    )

    # Campos para actividades
    activity_ids = fields.One2many(
        'mail.activity',
        'res_id',
        domain=[('res_model', '=', 'documento.firma')],
        string='Actividades'
    )
    
    @api.depends('firmante_ids')
    def _compute_total_firmas(self):
        for record in self:
            record.total_firmas = len(record.firmante_ids)
    
    @api.depends('firma_actual', 'total_firmas')
    def _compute_porcentaje_firmas(self):
        for record in self:
            if record.total_firmas > 0:
                record.porcentaje_firmas = (record.firma_actual / record.total_firmas) * 100
            else:
                record.porcentaje_firmas = 0
    
    @api.onchange('document_file')
    def _onchange_document_file(self):
        if self.document_file and not self.document_filename:
            self.document_filename = 'documento.pdf'
    
    def action_enviar_firma(self):
        """Enviar documento para firma"""
        for record in self:
            if not record.firmante_ids:
                raise UserError(_('Debe seleccionar al menos un firmante.'))
            
            record.state = 'pendiente'
            
            # Crear actividades para cada firmante
            for firmante in record.firmante_ids:
                self.env['mail.activity'].create({
                    'res_model_id': self.env['ir.model']._get('documento.firma').id,
                    'res_id': record.id,
                    'user_id': firmante.id,
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': f'Documento para firmar: {record.name}',
                    'note': f'El documento "{record.name}" está pendiente de su firma.',
                    'date_deadline': record.fecha_vencimiento or fields.Date.today()
                })
    
    def action_firmar_documento(self):
        """Acción para firmar el documento"""
        self.ensure_one()
        
        # Obtener datos de firma
        try:
            certificado_data, imagen_firma, contrasena = self._obtener_datos_firma()
        except UserError as e:
            raise UserError(_('Error al obtener datos de firma: %s') % str(e))
        
        # Llamar al asistente de firma con los datos obtenidos
        return {
            'type': 'ir.actions.act_window',
            'name': _('Firmar Documento'),
            'res_model': 'alfresco.firma.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_document_id': self.id,
                'default_signature_position': self.signature_position,
                'default_signature_role': self.signature_role.id if self.signature_role else False,
                'default_signature_password': contrasena,
                'default_signature_opaque_background': self.signature_opaque_background,
                'default_sign_all_pages': self.sign_all_pages,
                'default_certificate_wizard': base64.b64encode(certificado_data) if certificado_data else False,
                'default_certificate_wizard_name': self.certificate_wizard_name,
                'default_wizard_signature_image': imagen_firma,
                'from_workflow': True,
                'workflow_id': self.id,
                'readonly_signature_config': True,
            }
        }
    
    def _obtener_datos_firma(self):
        """Obtener datos de firma desde el documento o preferencias del usuario"""
        user_sudo = self.env.user.sudo()

        # certificado
        certificado_data = None
        if self.certificate_wizard:
            try:
                certificado_data = base64.b64decode(self.certificate_wizard)
            except Exception:
                certificado_data = None
        else:
            if getattr(user_sudo, 'certificado_firma', False):
                try:
                    certificado_data = base64.b64decode(user_sudo.certificado_firma)
                except Exception:
                    certificado_data = None

        if not certificado_data:
            raise UserError(_('Debe proporcionar un certificado .p12 en el wizard o tenerlo configurado en sus preferencias.'))

        # imagen
        imagen_firma = self.wizard_signature_image or getattr(user_sudo, 'imagen_firma', False)
        if not imagen_firma:
            raise UserError(_('Debe proporcionar una imagen de firma en el wizard o tenerla configurada en sus preferencias.'))

        # contraseña: primero intentar wizard, luego get_contrasena_descifrada(), luego decodificar manualmente
        contrasena = None
        if self.signature_password and self.signature_password.strip():
            contrasena = self.signature_password.strip()
        else:
            # intentar método existente
            try:
                contrasena = user_sudo.get_contrasena_descifrada()
            except Exception:
                contrasena = None

        # 1) intentar método oficial
        try:
            contrasena = user_sudo.get_contrasena_descifrada()
            if contrasena:
                _logger.debug("Contraseña obtenida vía get_contrasena_descifrada()")
        except Exception as e:
            _logger.warning("user_sudo.get_contrasena_descifrada() devolvió False/None o lanzó excepción: %s", e)
            contrasena = None

        # 2) si no hay contraseña, intentar decodificar base64 con padding y urlsafe
        if not contrasena and getattr(user_sudo, 'contrasena_certificado', False):
            raw = user_sudo.contrasena_certificado
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            # limpiar espacios y saltos
            raw_clean = raw.strip().replace('\n', '').replace('\r', '')
            # intentar decodificar directo
            try:
                contrasena = base64.b64decode(raw_clean.encode('utf-8')).decode('utf-8')
                _logger.info("Contraseña recuperada decodificando base64 (direct).")
            except (binascii.Error, Exception):
                # intentar con padding
                try:
                    padded = raw_clean + ('=' * (-len(raw_clean) % 4))
                    contrasena = base64.b64decode(padded.encode('utf-8')).decode('utf-8')
                    _logger.info("Contraseña recuperada decodificando base64 añadiendo padding.")
                except (binascii.Error, Exception):
                    # intentar urlsafe
                    try:
                        contrasena = base64.urlsafe_b64decode(raw_clean.encode('utf-8') + b'=' * (-len(raw_clean) % 4)).decode('utf-8')
                        _logger.info("Contraseña recuperada decodificando base64 urlsafe.")
                    except Exception as e:
                        _logger.warning("No se pudo decodificar manualmente contrasena_certificado: %s", e)
                        contrasena = None
        
        # 3) si sigue sin contraseña, asumir que el valor crudo es la contraseña (compatibilidad)
        if not contrasena and getattr(user_sudo, 'contrasena_certificado', False):
            raw = user_sudo.contrasena_certificado
            if isinstance(raw, bytes):
                try:
                    raw = raw.decode('utf-8')
                except Exception:
                    raw = None
            if raw:
                contrasena = raw
                _logger.info("Usando valor crudo de contrasena_certificado como contraseña (fallback de compatibilidad).")
        
        # 4) si aún no hay contraseña, lanzar UserError
        if not contrasena:
            raise UserError(_('Debe proporcionar la contraseña del certificado.'))
        
        _logger.info(f"Contraseña obtenida: {contrasena}")
        
        return certificado_data, imagen_firma, contrasena
    
    def action_rechazar_documento(self):
        """Rechazar el documento"""
        self.ensure_one()
        self.state = 'rechazado'
        
        # Eliminar actividades pendientes
        activities = self.env['mail.activity'].search([
            ('res_id', '=', self.id),
            ('res_model', '=', 'documento.firma'),
            ('state', '=', 'todo')
        ])
        activities.action_feedback(feedback=_('Documento rechazado'))
    
    def action_marcar_como_firmado(self, documentos_firmados, filename):
        """Marcar documento como firmado"""
        self.ensure_one()
        self.state = 'firmado'
        self.documentos_firmados = documentos_firmados
        self.documentos_firmados_filename = filename
        
        # Eliminar actividades pendientes
        activities = self.env['mail.activity'].search([
            ('res_id', '=', self.id),
            ('res_model', '=', 'documento.firma'),
            ('state', '=', 'todo')
        ])
        activities.action_feedback(feedback=_('Documento firmado exitosamente'))
    
    def action_vencer_documentos(self):
        """Marcar documentos como vencidos"""
        documentos_vencidos = self.search([
            ('state', '=', 'pendiente'),
            ('fecha_vencimiento', '<', fields.Date.today())
        ])
        documentos_vencidos.write({'state': 'vencido'})
        
        # Eliminar actividades de documentos vencidos
        activities = self.env['mail.activity'].search([
            ('res_id', 'in', documentos_vencidos.ids),
            ('res_model', '=', 'documento.firma'),
            ('state', '=', 'todo')
        ])
        activities.action_feedback(feedback=_('Documento vencido'))
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('documento.firma') or _('New')
        return super(DocumentoFirma, self).create(vals)