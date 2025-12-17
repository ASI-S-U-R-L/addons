# -*- coding: utf-8 -*-
import binascii
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import base64

_logger = logging.getLogger(__name__)

class AlfrescoFirmaWizardExtension(models.TransientModel):
    _inherit = 'alfresco.firma.wizard'
    
    from_workflow = fields.Boolean(string='Desde Solicitud de Firma', default=False)
    workflow_id = fields.Many2one('signature.workflow', string='Solicitud de Firma')
    readonly_signature_config = fields.Boolean(string='Configuración de Solo Lectura', default=False)

    @api.model
    def default_get(self, fields_list):
        """Valores por defecto para el asistente (extensión).
        Intenta cargar la contraseña descifrada usando sudo() si el campo está solicitado.
        """
        res = super(AlfrescoFirmaWizardExtension, self).default_get(fields_list)
        
        context = self.env.context
        if context.get('from_workflow') and context.get('workflow_id'):
            workflow = self.env['signature.workflow'].browse(context.get('workflow_id'))
            if workflow.exists():
                res.update({
                    'from_workflow': True,
                    'workflow_id': workflow.id,
                    'readonly_signature_config': context.get('readonly_signature_config', False),
                })
                
                # Solo asignar signature_role si está en la lista de campos solicitados
                if 'signature_role' in fields_list and workflow.signature_role_id:
                    res['signature_role'] = workflow.signature_role_id.id
                
                # Solo asignar signature_position si está en la lista de campos solicitados
                if 'signature_position' in fields_list and workflow.signature_position:
                    res['signature_position'] = workflow.signature_position
                
                if 'signature_opaque_background' in fields_list:
                    res['signature_opaque_background'] = workflow.signature_opaque_background
                
                if 'sign_all_pages' in fields_list:
                    res['sign_all_pages'] = workflow.sign_all_pages
                
                # Intentar cargar la contraseña descifrada del usuario con sudo()
                if 'signature_password' in fields_list:
                    try:
                        user_sudo = self.env.user.sudo()
                        if getattr(user_sudo, 'contrasena_certificado', False):
                            password = user_sudo.get_contrasena_descifrada()
                            if password:
                                res['signature_password'] = password
                                _logger.info("Contraseña del certificado cargada desde el perfil del usuario %s (via sudo)", user_sudo.name)
                            else:
                                _logger.debug("get_contrasena_descifrada devolvió None o cadena vacía para el usuario %s", user_sudo.name)
                        else:
                            _logger.debug("Usuario %s no tiene contrasena_certificado configurada", user_sudo.name)
                    except Exception as e:
                        _logger.warning("No se pudo cargar la contraseña guardada del usuario (default_get extension): %s", e)
                
                _logger.info(
                    "Wizard de Alfresco configurado desde solicitud de firma %s con rol %s y posición %s",
                    workflow.id,
                    workflow.signature_role_id.name if workflow.signature_role_id else 'N/A',
                    workflow.signature_position
                )
        
        return res

    def _obtener_datos_firma(self):
        """Fallback robusto en la extensión: intenta super(), y si falta la contraseña,
        decodifica manualmente el campo contrasena_certificado desde user.sudo()."""
        try:
            return super(AlfrescoFirmaWizardExtension, self)._obtener_datos_firma()
        except UserError as ue:
            # Si el error es por contraseña, intentamos fallback manual
            msg = str(ue or '').lower()
            if 'contraseña' not in msg and 'certificado' not in msg:
                raise

        # reconstruir datos usando sudo y decodificación manual si es necesario
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
        
        _logger.info(f"Contraseña obtenida: {contrasena}, raw: {raw}, raw_clean: {raw_clean}, padded: {padded}, contrasena_certificado: {user_sudo.contrasena_certificado}")
        
        return certificado_data, imagen_firma, contrasena

    def action_firmar_documentos(self):
        if not self.signature_password:
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
                        self.signature_password = pwd
                        _logger.info("signature_password cargada en wizard desde user.sudo() en action_firmar_documentos")
                    else:
                        _logger.warning("contrasena_certificado está vacía en action_firmar_documentos")
            except Exception as e:
                _logger.exception("Error obteniendo contraseña desde user.sudo() en action_firmar_documentos: %s", e)
            
        _logger.info(f"signature_password: {self.signature_password}")

        result = super(AlfrescoFirmaWizardExtension, self).action_firmar_documentos()
        
        if self.from_workflow and self.workflow_id and self.status == 'completado':
            try:
                self.workflow_id.action_mark_as_signed()
                _logger.info(f"Solicitud de firma {self.workflow_id.id} marcada como firmada automáticamente después de firma Alfresco")
            except Exception as e:
                _logger.error(f"Error marcando solicitud como firmada después de firma Alfresco: {e}")
                # No re-lanzar el error para no afectar la firma exitosa
        
        return result

    @api.onchange('signature_role', 'signature_position', 'signature_opaque_background', 'sign_all_pages')
    def _onchange_signature_config(self):
        """Prevenir cambios en configuración cuando viene de solictud de firma"""
        if self.readonly_signature_config and self.from_workflow:
            if self.workflow_id:
                if self.workflow_id.signature_role_id:
                    self.signature_role = self.workflow_id.signature_role_id.id
                if self.workflow_id.signature_position:
                    self.signature_position = self.workflow_id.signature_position
                self.signature_opaque_background = self.workflow_id.signature_opaque_background
                self.sign_all_pages = self.workflow_id.sign_all_pages
                return {
                    'warning': {
                        'title': _('Configuración Bloqueada'),
                        'message': _('La configuración de firma está definida por el creador del solicitud de firma y no puede ser modificada.')
                    }
                }
