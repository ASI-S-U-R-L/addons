# -*- coding: utf-8 -*-
"""
Modelo para gestionar las Entidades Certificadoras (CA) de confianza.
Almacena los certificados .crt que se usarán para validar firmas digitales.
"""
import base64
import logging
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    _logger.warning("Módulo 'cryptography' no disponible.")


class CertificateAuthority(models.Model):
    """
    Modelo para almacenar certificados de Entidades Certificadoras (CA).
    Estos certificados se usan para validar la cadena de confianza de firmas digitales.
    """
    _name = 'asi.certificate.authority'
    _description = 'Entidad Certificadora de Confianza'
    _order = 'sequence, name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre identificativo de la entidad certificadora'
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
        help='Orden de prioridad para la validación'
    )
    
    certificate_file = fields.Binary(
        string='Archivo de Certificado (.crt/.pem/.cer)',
        required=True,
        attachment=True,
        help='Archivo del certificado de la CA en formato PEM o DER'
    )
    
    certificate_filename = fields.Char(
        string='Nombre del archivo'
    )
    
    # Información extraída del certificado
    subject_cn = fields.Char(
        string='Nombre Común (CN)',
        readonly=True,
        help='Common Name del sujeto del certificado'
    )
    
    subject_org = fields.Char(
        string='Organización',
        readonly=True,
        help='Organización del sujeto del certificado'
    )
    
    issuer_cn = fields.Char(
        string='Emisor (CN)',
        readonly=True,
        help='Common Name del emisor del certificado'
    )
    
    serial_number = fields.Char(
        string='Número de Serie',
        readonly=True,
        help='Número de serie del certificado'
    )
    
    valid_from = fields.Datetime(
        string='Válido desde',
        readonly=True,
        help='Fecha de inicio de validez del certificado'
    )
    
    valid_until = fields.Datetime(
        string='Válido hasta',
        readonly=True,
        help='Fecha de expiración del certificado'
    )
    
    is_expired = fields.Boolean(
        string='Expirado',
        compute='_compute_is_expired',
        store=False,
        help='Indica si el certificado ha expirado'
    )
    
    is_self_signed = fields.Boolean(
        string='Autofirmado',
        readonly=True,
        help='Indica si el certificado es autofirmado (CA raíz)'
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True,
        help='Si está desactivado, no se usará para validación'
    )
    
    notes = fields.Text(
        string='Notas',
        help='Notas o comentarios adicionales sobre esta CA'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        help='Compañía a la que pertenece esta CA'
    )

    @api.depends('valid_until')
    def _compute_is_expired(self):
        """Calcula si el certificado ha expirado."""
        now = fields.Datetime.now()
        for record in self:
            if record.valid_until:
                record.is_expired = record.valid_until < now
            else:
                record.is_expired = False

    @api.model_create_multi
    def create(self, vals_list):
        """Extrae información del certificado al crear el registro."""
        for vals in vals_list:
            if vals.get('certificate_file'):
                cert_info = self._extract_certificate_info(vals['certificate_file'])
                vals.update(cert_info)
        return super().create(vals_list)

    def write(self, vals):
        """Actualiza información del certificado si se modifica el archivo."""
        if vals.get('certificate_file'):
            cert_info = self._extract_certificate_info(vals['certificate_file'])
            vals.update(cert_info)
        return super().write(vals)

    def _extract_certificate_info(self, certificate_b64):
        """
        Extrae información del certificado codificado en base64.
        
        Args:
            certificate_b64: Certificado codificado en base64
            
        Returns:
            dict: Información extraída del certificado
        """
        info = {}
        
        if not HAS_CRYPTOGRAPHY:
            _logger.warning("No se puede extraer información: cryptography no disponible")
            return info
        
        try:
            cert_data = base64.b64decode(certificate_b64)
            
            # Intentar cargar como PEM primero
            try:
                certificate = x509.load_pem_x509_certificate(cert_data, default_backend())
            except:
                # Si falla, intentar como DER
                certificate = x509.load_der_x509_certificate(cert_data, default_backend())
            
            # Extraer información del sujeto
            subject = certificate.subject
            for attr in subject:
                if attr.oid == x509.oid.NameOID.COMMON_NAME:
                    info['subject_cn'] = attr.value
                elif attr.oid == x509.oid.NameOID.ORGANIZATION_NAME:
                    info['subject_org'] = attr.value
            
            # Extraer información del emisor
            issuer = certificate.issuer
            for attr in issuer:
                if attr.oid == x509.oid.NameOID.COMMON_NAME:
                    info['issuer_cn'] = attr.value
            
            # Número de serie
            info['serial_number'] = format(certificate.serial_number, 'X')
            
            # Fechas de validez
            not_before = certificate.not_valid_before_utc if hasattr(certificate, 'not_valid_before_utc') else certificate.not_valid_before
            not_after = certificate.not_valid_after_utc if hasattr(certificate, 'not_valid_after_utc') else certificate.not_valid_after
            
            info['valid_from'] = not_before.replace(tzinfo=None)
            info['valid_until'] = not_after.replace(tzinfo=None)
            
            # Verificar si es autofirmado
            info['is_self_signed'] = certificate.subject == certificate.issuer
            
            _logger.info(f"Información extraída del certificado CA: CN={info.get('subject_cn')}")
            
        except Exception as e:
            _logger.error(f"Error extrayendo información del certificado: {e}")
            raise ValidationError(_(
                "No se pudo leer el certificado. Asegúrese de que el archivo sea un "
                "certificado válido en formato PEM (.crt, .pem) o DER (.cer).\n\nError: %s"
            ) % str(e))
        
        return info

    def get_x509_certificate(self):
        """
        Obtiene el objeto x509 del certificado.
        
        Returns:
            x509.Certificate: Objeto certificado o None si hay error
        """
        self.ensure_one()
        
        if not HAS_CRYPTOGRAPHY or not self.certificate_file:
            return None
        
        try:
            cert_data = base64.b64decode(self.certificate_file)
            
            try:
                return x509.load_pem_x509_certificate(cert_data, default_backend())
            except:
                return x509.load_der_x509_certificate(cert_data, default_backend())
                
        except Exception as e:
            _logger.error(f"Error cargando certificado CA {self.name}: {e}")
            return None

    @api.model
    def get_all_active_certificates(self):
        """
        Obtiene todos los certificados CA activos como objetos x509.
        
        Returns:
            list: Lista de tuplas (record, x509_certificate)
        """
        certificates = []
        active_cas = self.search([('active', '=', True)], order='sequence')
        
        for ca in active_cas:
            x509_cert = ca.get_x509_certificate()
            if x509_cert:
                certificates.append((ca, x509_cert))
            else:
                _logger.warning(f"No se pudo cargar certificado CA: {ca.name}")
        
        return certificates

    def action_view_certificate_details(self):
        """Acción para ver los detalles del certificado en una ventana."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detalles del Certificado'),
            'res_model': 'asi.certificate.authority',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
