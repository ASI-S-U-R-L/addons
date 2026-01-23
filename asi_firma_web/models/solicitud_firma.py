# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import base64
import binascii

_logger = logging.getLogger(__name__)

class SolicitudFirma(models.Model):
    _name = 'solicitud.firma'
    _description = 'Solicitud de Firma'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Referencia de Solicitud',
        required=True,
        tracking=True
    )
    
    solicitante_id = fields.Many2one(
        'res.users',
        string='Solicitante',
        default=lambda self: self.env.user,
        required=True,
        tracking=True
    )
    
    documento_id = fields.Many2one(
        'documento.firma',
        string='Documento',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    
    firmante_id = fields.Many2one(
        'res.users',
        string='Firmante',
        required=True,
        tracking=True
    )
    
    estado = fields.Selection([
        ('pendiente', 'Pendiente'),
        ('firmado', 'Firmado'),
        ('rechazado', 'Rechazado'),
        ('vencido', 'Vencido')
    ], string='Estado', default='pendiente', tracking=True)
    
    fecha_solicitud = fields.Datetime(
        string='Fecha de Solicitud',
        default=fields.Datetime.now,
        tracking=True
    )
    
    fecha_respuesta = fields.Datetime(
        string='Fecha de Respuesta'
    )
    
    motivo_rechazo = fields.Text(
        string='Motivo de Rechazo'
    )
    
    # Campos para el flujo de firma
    firma_completada = fields.Boolean(
        string='Firma Completada',
        compute='_compute_firma_completada',
        store=True
    )

    # Campos para múltiples destinatarios
    target_user_id_1 = fields.Many2one('res.users', string='Destinatario 1')
    target_user_id_2 = fields.Many2one('res.users', string='Destinatario 2')
    target_user_id_3 = fields.Many2one('res.users', string='Destinatario 3')
    target_user_id_4 = fields.Many2one('res.users', string='Destinatario 4')

    # Campos para roles de firma
    signature_role_id_1 = fields.Many2one('signature.role', string='Rol de Firma 1')
    signature_role_id_2 = fields.Many2one('signature.role', string='Rol de Firma 2')
    signature_role_id_3 = fields.Many2one('signature.role', string='Rol de Firma 3')
    signature_role_id_4 = fields.Many2one('signature.role', string='Rol de Firma 4')

    # Campos para posiciones de firma
    signature_position_1 = fields.Char(string='Posición de Firma 1')
    signature_position_2 = fields.Char(string='Posición de Firma 2')
    signature_position_3 = fields.Char(string='Posición de Firma 3')
    signature_position_4 = fields.Char(string='Posición de Firma 4')

    # Campos para indicar si cada destinatario ha firmado
    signed_by_user_1 = fields.Boolean(string='Firmado por Destinatario 1', default=False)
    signed_by_user_2 = fields.Boolean(string='Firmado por Destinatario 2', default=False)
    signed_by_user_3 = fields.Boolean(string='Firmado por Destinatario 3', default=False)
    signed_by_user_4 = fields.Boolean(string='Firmado por Destinatario 4', default=False)

    # Campos para fechas de firma
    signed_date_1 = fields.Datetime(string='Fecha de Firma 1')
    signed_date_2 = fields.Datetime(string='Fecha de Firma 2')
    signed_date_3 = fields.Datetime(string='Fecha de Firma 3')
    signed_date_4 = fields.Datetime(string='Fecha de Firma 4')

    # Campo para el índice del destinatario actual
    current_recipient_index = fields.Integer(string='Índice del Destinatario Actual', default=1)

    @api.depends('estado')
    def _compute_firma_completada(self):
        for record in self:
            record.firma_completada = record.estado in ['firmado', 'rechazado', 'vencido']
    
    @api.onchange('documento_id')
    def _onchange_documento_id(self):
        if self.documento_id:
            self.name = f'Solicitud para: {self.documento_id.name}'
    
    def action_firmar_solicitud(self):
        """Acción para firmar la solicitud"""
        self.ensure_one()
        if self.documento_id:
            return self.documento_id.action_firmar_documento()
        else:
            raise UserError(_('No se encontró el documento asociado a esta solicitud.'))

    def _obtener_datos_firma(self):
        """Fallback robusto en la extensión: intenta super(), y si falta la contraseña,
        decodifica manualmente el campo contrasena_certificado desde user.sudo()."""
        user_sudo = self.env.user.sudo()

        # certificado
        certificado_data = None
        if self.documento_id.certificate_wizard:
            try:
                certificado_data = base64.b64decode(self.documento_id.certificate_wizard)
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
        imagen_firma = self.documento_id.wizard_signature_image or getattr(user_sudo, 'imagen_firma', False)
        if not imagen_firma:
            raise UserError(_('Debe proporcionar una imagen de firma en el wizard o tenerla configurada en sus preferencias.'))

        # contraseña: primero intentar wizard, luego get_contrasena_descifrada(), luego decodificar manualmente
        contrasena = None
        if self.documento_id.signature_password and self.documento_id.signature_password.strip():
            contrasena = self.documento_id.signature_password.strip()
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
    
    def action_rechazar_solicitud(self):
        """Rechazar la solicitud de firma"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rechazar Solicitud'),
            'res_model': 'solicitud.firma.rechazo.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_solicitud_id': self.id,
            }
        }
    
    def action_marcar_como_firmado(self):
        """Marcar solicitud como firmada"""
        self.ensure_one()
        self.estado = 'firmado'
        self.fecha_respuesta = fields.Datetime.now()
        
        # Verificar si todas las solicitudes del documento están firmadas
        solicitudes_pendientes = self.documento_id.solicitud_firma_ids.filtered(
            lambda s: s.estado == 'pendiente'
        )
        
        if not solicitudes_pendientes:
            # Todas las solicitudes están completadas, marcar documento como firmado
            documentos_firmados = self.documento_id.documentos_firmados
            filename = self.documento_id.documentos_firmados_filename
            self.documento_id.action_marcar_como_firmado(documentos_firmados, filename)

    def action_firmar_documentos(self):
        """Acción para firmar documentos desde la solicitud"""
        if not self.documento_id.signature_password:
            try:
                user_sudo = self.env.user.sudo()
                if getattr(user_sudo, 'contrasena_certificado', False):
                    raw = user_sudo.contrasena_certificado
                    if isinstance(raw, bytes):
                        try:
                            pwd = raw.decode('utf-8')
                        except Exception:
                            pwd = None
                    else:
                        pwd = raw.decode('utf-8')
                    
                    if pwd:
                        self.documento_id.signature_password = pwd
                        _logger.info("signature_password cargada en wizard desde user.sudo() en action_firmar_documentos")
                    else:
                        _logger.warning("contrasena_certificado está vacía en action_firmar_documentos")
            except Exception as e:
                _logger.exception("Error obteniendo contraseña desde user.sudo() en action_firmar_documentos: %s", e)
        
        _logger.info(f"signature_password: {self.documento_id.signature_password}")
        
        # Llamar a la acción de firma del documento
        return self.documento_id.action_firmar_documento()
    
    def action_marcar_como_rechazado(self, motivo):
        """Marcar solicitud como rechazada"""
        self.ensure_one()
        self.estado = 'rechazado'
        self.fecha_respuesta = fields.Datetime.now()
        self.motivo_rechazo = motivo
        
        # Marcar documento como rechazado si esta solicitud fue rechazada
        self.documento_id.action_rechazar_documento()
    
    def action_vencer_solicitudes(self):
        """Marcar solicitudes como vencidas"""
        solicitudes_vencidas = self.search([
            ('estado', '=', 'pendiente'),
            ('documento_id.fecha_vencimiento', '<', fields.Date.today())
        ])
        solicitudes_vencidas.write({'estado': 'vencido'})
        
        # Marcar documentos como vencidos
        documentos_vencidos = solicitudes_vencidas.mapped('documento_id')
        documentos_vencidos.write({'state': 'vencido'})
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('solicitud.firma') or _('New')
        return super(SolicitudFirma, self).create(vals)