# -*- coding: utf-8 -*-
"""
Extensión del modelo res.users para agregar campos computados de texto
que muestran "SÍ" o "NO" para la vista administrativa.
"""
from odoo import models, fields, api
import logging
from datetime import datetime, timedelta
import base64

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    """Extiende res.users para agregar campos computados de texto."""
    _inherit = 'res.users'
    
    # Campos computados que devuelven "SÍ" o "NO" como texto
    has_p12_text = fields.Char(
        string='Tiene P12',
        compute='_compute_p12_status_text',
        store=False
    )
    
    has_password_text = fields.Char(
        string='Tiene Contraseña',
        compute='_compute_p12_status_text',
        store=False
    )
    
    has_signature_image_text = fields.Char(
        string='Tiene Imagen de Firma',
        compute='_compute_p12_status_text',
        store=False
    )
    
    @api.depends('certificado_firma', 'contrasena_certificado', 'imagen_firma')
    def _compute_p12_status_text(self):
        """
        Calcula el texto "SÍ" o "NO" para cada campo.
        Usado en la vista administrativa de usuarios con P12.
        """
        for user in self:
            user.has_p12_text = 'SÍ' if user.certificado_firma else 'NO'
            user.has_password_text = 'SÍ' if user.contrasena_certificado else 'NO'
            user.has_signature_image_text = 'SÍ' if user.imagen_firma else 'NO'

    def _cron_check_certificate_expiration(self):
        """
        Método ejecutado por cron diario a las 9 AM.
        Revisa usuarios con P12 y contraseña configurados y notifica
        si su certificado expira hoy o mañana.
        """
        _logger.info("Iniciando verificación diaria de expiración de certificados P12")
        
        # Buscar usuarios con certificado y contraseña configurados
        users_with_p12 = self.search([
            ('certificado_firma', '!=', False),
            ('contrasena_certificado', '!=', False),
            ('email', '!=', False),  # Asegurar que tenga email
        ])
        
        _logger.info(f"Encontrados {len(users_with_p12)} usuarios con P12 y contraseña configurados")
        
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        notified_count = 0
        
        for user in users_with_p12:
            try:
                # Intentar cargar y validar el certificado
                cert_data = base64.b64decode(user.certificado_firma)
                password = user.contrasena_certificado.encode('utf-8')
                
                from cryptography.hazmat.primitives.serialization import pkcs12
                from cryptography.hazmat.backends import default_backend
                
                # Cargar el certificado P12
                private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                    cert_data,
                    password,
                    backend=default_backend()
                )
                
                # Obtener fecha de expiración
                expiration_date = certificate.not_valid_after_utc.date()
                
                _logger.debug(f"Usuario {user.name} ({user.login}): Certificado expira el {expiration_date}")
                
                # Verificar si expira hoy o mañana
                if expiration_date == today or expiration_date == tomorrow:
                    days_remaining = (expiration_date - today).days
                    
                    _logger.info(
                        f"¡ALERTA! Certificado de {user.name} expira en {days_remaining} día(s) "
                        f"(fecha de expiración: {expiration_date})"
                    )
                    
                    # Enviar correo de notificación
                    self._send_expiration_notification(user, expiration_date, days_remaining)
                    notified_count += 1
                    
            except Exception as e:
                _logger.error(
                    f"Error verificando certificado del usuario {user.name} ({user.login}): {str(e)}",
                    exc_info=True
                )
                continue
        
        _logger.info(
            f"Verificación de certificados completada. "
            f"Se enviaron {notified_count} notificaciones de expiración."
        )
        
        return True
    
    def _send_expiration_notification(self, user, expiration_date, days_remaining):
        """
        Envía un correo electrónico al usuario notificando sobre la expiración
        inminente de su certificado P12.
        
        Args:
            user: Objeto del usuario a notificar
            expiration_date: Fecha de expiración del certificado
            days_remaining: Días restantes hasta la expiración
        """
        try:
            # Preparar datos del correo
            expires_today = days_remaining == 0
            expiration_text = "expira hoy" if expires_today else "expirará mañana"
            expiration_date_str = expiration_date.strftime('%d/%m/%Y')
            company_name = user.company_id.name or 'Sistema de Firma Digital'
            email_from = user.company_id.email or 'noreply@example.com'
            
            # Generar HTML del correo
            html_body = f"""
            <div style="margin: 0px; padding: 0px; font-family: Arial, sans-serif;">
                <table border="0" cellpadding="0" cellspacing="0" style="padding-top: 16px; background-color: #F1F1F1; font-family: Arial, sans-serif; color: #454748; width: 100%; border-collapse: separate;">
                    <tr>
                        <td align="center">
                            <table border="0" cellpadding="0" cellspacing="0" width="600" style="padding: 16px; background-color: #FFFFFF; border: 1px solid #DDDDDD; border-radius: 8px;">
                                <!-- Encabezado -->
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <h1 style="color: #E74C3C; margin: 0; font-size: 24px;">
                                            ⚠️ Certificado de Firma Digital por Expirar
                                        </h1>
                                    </td>
                                </tr>
                                
                                <!-- Contenido -->
                                <tr>
                                    <td style="padding: 20px; font-size: 14px; line-height: 1.6;">
                                        <p style="margin: 0 0 15px;">Estimado/a <strong>{user.name}</strong>,</p>
                                        
                                        <p style="margin: 0 0 15px;">
                                            Le informamos que su certificado de firma digital (.p12) configurado en el sistema
                                            <strong style="color: #E74C3C;">{expiration_text}</strong>.
                                        </p>
                                        
                                        <div style="background-color: #FFF3CD; border-left: 4px solid #FFC107; padding: 15px; margin: 20px 0; border-radius: 4px;">
                                            <p style="margin: 0; color: #856404;">
                                                <strong>Fecha de expiración:</strong> {expiration_date_str}<br/>
                                                <strong>Días restantes:</strong> {days_remaining} día(s)
                                            </p>
                                        </div>
                                        
                                        <p style="margin: 0 0 15px;">
                                            Para continuar firmando documentos digitalmente, deberá renovar su certificado
                                            lo antes posible y actualizar su configuración en el sistema.
                                        </p>
                                        
                                        <p style="margin: 0 0 15px;">
                                            <strong>¿Qué debe hacer?</strong>
                                        </p>
                                        <ul style="margin: 0 0 15px; padding-left: 20px;">
                                            <li>Contacte a su autoridad certificadora para renovar su certificado</li>
                                            <li>Una vez renovado, actualice su certificado en la configuración de su perfil</li>
                                            <li>Verifique que el nuevo certificado funciona correctamente</li>
                                        </ul>
                                        
                                        <p style="margin: 20px 0 0;">
                                            Atentamente,<br/>
                                            <strong>{company_name}</strong>
                                        </p>
                                    </td>
                                </tr>
                                
                                <!-- Pie de página -->
                                <tr>
                                    <td style="padding: 20px; background-color: #F8F9FA; border-top: 1px solid #DDDDDD; text-align: center; font-size: 12px; color: #6C757D;">
                                        <p style="margin: 0;">
                                            Este es un mensaje automático. Por favor, no responda a este correo.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </div>
            """
            
            # Crear y enviar el correo usando el objeto mail.mail
            mail_values = {
                'subject': '⚠️ Su certificado de firma digital está por expirar',
                'email_from': email_from,
                'email_to': user.email,
                'body_html': html_body,
                'auto_delete': True,
            }
            
            mail = self.env['mail.mail'].sudo().create(mail_values)
            mail.send()
            
            _logger.info(f"Correo de expiración enviado exitosamente a {user.email}")
            return True
            
        except Exception as e:
            _logger.error(
                f"Error enviando correo de expiración a {user.email}: {str(e)}",
                exc_info=True
            )
            return False
