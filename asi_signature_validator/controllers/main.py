# -*- coding: utf-8 -*-
"""
Controlador principal para el módulo asi_signature_validator.
Proporciona endpoints para:
- Validación de certificados P12
- Verificación de firmas digitales en PDFs
- Validación de cadena de confianza contra CAs configuradas
"""
import base64
import json
import logging
import re
import tempfile
import os
from datetime import datetime, timezone, timedelta
from io import BytesIO
from werkzeug.utils import secure_filename

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Importaciones para manejo de certificados
try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID, ExtensionOID
    from cryptography.exceptions import InvalidSignature
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    _logger.warning("Módulo 'cryptography' no disponible. La validación de certificados no funcionará.")

# Importaciones para lectura de PDFs y firmas
try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except ImportError:
    try:
        from PyPDF2 import PdfFileReader as PdfReader
        HAS_PYPDF2 = False
    except ImportError:
        HAS_PYPDF2 = False
        _logger.warning("Módulo 'PyPDF2' no disponible. La verificación de PDFs no funcionará.")

# Importaciones para verificación de firmas - asn1crypto
try:
    from asn1crypto import cms, core, pem
    from asn1crypto import tsp
    HAS_ASN1CRYPTO = True
except ImportError:
    HAS_ASN1CRYPTO = False
    _logger.warning("Módulo 'asn1crypto' no disponible. La extracción detallada de firmas puede estar limitada.")

# Intentar importar pyHanko para validación de PDF
try:
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.general import CMSExtractionError
    from pyhanko_certvalidator import ValidationContext
    from pyhanko_certvalidator.errors import PathValidationError, PathBuildingError
    HAS_PYHANKO = True
except ImportError:
    HAS_PYHANKO = False
    _logger.warning("Módulo 'pyhanko' no instalado. Validación de PDF limitada.")


class SignatureValidatorController(http.Controller):
    """
    Controlador para las páginas de validación de certificados y verificación de firmas PDF.
    """

    # =========================================================================
    # MÉTODOS AUXILIARES PARA ENTIDADES CERTIFICADORAS
    # =========================================================================
    
    def _get_configured_cas(self):
        """
        Obtiene todos los certificados CA configurados y activos.
        
        Returns:
            list: Lista de tuplas (record, x509_certificate)
        """
        try:
            CA = request.env['asi.certificate.authority'].sudo()
            return CA.get_all_active_certificates()
        except Exception as e:
            _logger.error(f"Error obteniendo CAs configuradas: {e}")
            return []
    
    # =========================================================================
    # para soportar cadenas con intermedios y verificación criptográfica real
    # =========================================================================
    
    def _verify_certificate_chain(self, certificate, additional_certs=None):
        """
        Verifica la cadena de confianza de un certificado contra las CAs configuradas.
        
        IMPORTANTE: Para que la verificación funcione correctamente, TODAS las CAs
        intermedias de la cadena deben estar configuradas en el sistema, no solo la raíz.
        
        La cadena de confianza funciona así:
        Usuario -> CA Intermedia 1 -> CA Intermedia 2 -> ... -> CA Raíz
        
        Si falta algún eslabón intermedio, la verificación fallará.
        """
        result = {
            'chain_valid': False,
            'chain_verified': False,
            'trusted_ca': None,
            'validation_errors': [],
            'validation_warnings': [],
            'chain_path': [],
            'debug_info': [],
            'missing_ca_hint': None  # Nueva: sugerencia de qué CA falta
        }
        
        if not HAS_CRYPTOGRAPHY:
            result['validation_errors'].append('Módulo cryptography no disponible para verificación de cadena.')
            return result
        
        # Obtener CAs configuradas
        configured_cas = self._get_configured_cas()
        
        if not configured_cas:
            result['validation_warnings'].append(
                'No hay Entidades Certificadoras configuradas en el sistema. '
                'Configure las CAs en Ajustes > Validador de Firmas para habilitar la verificación de cadena de confianza.'
            )
            return result
        
        _logger.info(f"[CHAIN] ========== INICIO VERIFICACIÓN DE CADENA ==========")
        _logger.info(f"[CHAIN] CAs configuradas: {len(configured_cas)}")
        
        # Información del certificado a verificar
        try:
            cert_subject_cn = self._get_cn_from_name(certificate.subject)
            cert_issuer_cn = self._get_cn_from_name(certificate.issuer)
            cert_issuer_full = self._name_to_dict(certificate.issuer)
            
            result['chain_path'].append({
                'type': 'end_entity',
                'subject': cert_subject_cn,
                'issuer': cert_issuer_cn
            })
            
            _logger.info(f"[CHAIN] Certificado: {cert_subject_cn}")
            _logger.info(f"[CHAIN] Emisor (issuer): {cert_issuer_cn}")
            _logger.info(f"[CHAIN] Issuer completo: {cert_issuer_full}")
            
            result['debug_info'].append(f"Certificado: {cert_subject_cn}")
            result['debug_info'].append(f"Emitido por: {cert_issuer_cn}")
            
        except Exception as e:
            result['validation_errors'].append(f'Error leyendo información del certificado: {str(e)}')
            return result
        
        # Listar todas las CAs configuradas para debug
        _logger.info(f"[CHAIN] --- CAs configuradas ---")
        ca_subjects = []
        for ca_record, ca_cert in configured_cas:
            ca_subject_cn = self._get_cn_from_name(ca_cert.subject)
            ca_subject_full = self._name_to_dict(ca_cert.subject)
            ca_subjects.append(ca_subject_cn)
            _logger.info(f"[CHAIN]   - {ca_record.name}: {ca_subject_cn}")
            _logger.info(f"[CHAIN]     Subject completo: {ca_subject_full}")
            result['debug_info'].append(f"CA disponible: {ca_record.name} ({ca_subject_cn})")
        
        # Construir pool de certificados disponibles (intermedios del P12 + CAs configuradas)
        cert_pool = []
        
        # Agregar CAs configuradas al pool
        for ca_record, ca_cert in configured_cas:
            cert_pool.append({
                'cert': ca_cert,
                'name': ca_record.name,
                'subject_cn': self._get_cn_from_name(ca_cert.subject),
                'subject': ca_cert.subject,
                'is_configured_ca': True
            })
        
        # Agregar certificados adicionales del P12 (intermedios)
        if additional_certs:
            _logger.info(f"[CHAIN] Certificados adicionales en P12: {len(additional_certs)}")
            for i, cert in enumerate(additional_certs):
                if cert is not None:
                    inter_cn = self._get_cn_from_name(cert.subject)
                    _logger.info(f"[CHAIN]   - Intermedio P12 {i+1}: {inter_cn}")
                    cert_pool.append({
                        'cert': cert,
                        'name': f'Intermedio P12 ({inter_cn})',
                        'subject_cn': inter_cn,
                        'subject': cert.subject,
                        'is_configured_ca': False
                    })
        else:
            _logger.info(f"[CHAIN] No hay certificados adicionales en el P12")
        
        # =====================================================================
        # ESTRATEGIA 1: Verificación directa contra CAs configuradas
        # =====================================================================
        _logger.info(f"[CHAIN] --- Estrategia 1: Verificación directa ---")
        result['debug_info'].append("--- Verificación directa contra CAs ---")
        
        for ca_record, ca_cert in configured_cas:
            ca_subject_cn = self._get_cn_from_name(ca_cert.subject)
            
            # Comparar issuer del certificado con subject de la CA
            names_match = self._names_match(certificate.issuer, ca_cert.subject)
            _logger.info(f"[CHAIN] Comparando issuer con CA '{ca_record.name}': match={names_match}")
            
            if names_match:
                _logger.info(f"[CHAIN] Nombres coinciden, verificando firma criptográfica...")
                sig_valid, sig_error = self._verify_certificate_signature_detailed(certificate, ca_cert)
                
                if sig_valid:
                    _logger.info(f"[CHAIN] ¡ÉXITO! Firma válida contra CA: {ca_record.name}")
                    result['chain_valid'] = True
                    result['chain_verified'] = True
                    result['trusted_ca'] = {
                        'name': ca_record.name,
                        'subject_cn': ca_record.subject_cn,
                        'organization': ca_record.subject_org
                    }
                    result['chain_path'].append({
                        'type': 'trusted_ca',
                        'subject': ca_subject_cn,
                        'issuer': self._get_cn_from_name(ca_cert.issuer)
                    })
                    result['debug_info'].append(f"VÁLIDO: Firmado directamente por CA '{ca_record.name}'")
                    return result
                else:
                    _logger.warning(f"[CHAIN] Nombres coinciden pero firma inválida: {sig_error}")
                    result['debug_info'].append(f"CA '{ca_record.name}' coincide por nombre pero firma inválida: {sig_error}")
        
        # =====================================================================
        # ESTRATEGIA 2: Construir cadena completa usando pool de certificados
        # =====================================================================
        _logger.info(f"[CHAIN] --- Estrategia 2: Construir cadena completa ---")
        result['debug_info'].append("--- Intentando construir cadena completa ---")
        
        chain_result = self._build_chain_to_root(certificate, cert_pool, configured_cas, result['debug_info'])
        
        if chain_result['success']:
            result['chain_valid'] = True
            result['chain_verified'] = True
            result['trusted_ca'] = chain_result['trusted_ca']
            result['chain_path'].extend(chain_result['chain_path'])
            _logger.info(f"[CHAIN] ¡ÉXITO! Cadena completa verificada")
            return result
        
        # =====================================================================
        # ESTRATEGIA 3: Verificación criptográfica directa (sin comparar nombres)
        # Por si hay diferencias en cómo se codifican los nombres
        # =====================================================================
        _logger.info(f"[CHAIN] --- Estrategia 3: Verificación criptográfica bruta ---")
        result['debug_info'].append("--- Verificación criptográfica sin comparar nombres ---")
        
        for ca_record, ca_cert in configured_cas:
            sig_valid, sig_error = self._verify_certificate_signature_detailed(certificate, ca_cert)
            _logger.info(f"[CHAIN] Verificación bruta contra '{ca_record.name}': válida={sig_valid}")
            
            if sig_valid:
                _logger.info(f"[CHAIN] ¡ÉXITO por verificación bruta! CA: {ca_record.name}")
                result['chain_valid'] = True
                result['chain_verified'] = True
                result['trusted_ca'] = {
                    'name': ca_record.name,
                    'subject_cn': ca_record.subject_cn,
                    'organization': ca_record.subject_org
                }
                result['chain_path'].append({
                    'type': 'trusted_ca',
                    'subject': self._get_cn_from_name(ca_cert.subject),
                    'issuer': self._get_cn_from_name(ca_cert.issuer)
                })
                result['debug_info'].append(f"VÁLIDO: Firma verificada criptográficamente con CA '{ca_record.name}'")
                result['validation_warnings'].append(
                    f"El certificado fue validado por verificación criptográfica directa con '{ca_record.name}', "
                    f"aunque los nombres del emisor no coinciden exactamente."
                )
                return result
        
        # =====================================================================
        # FALLÓ: Generar mensaje de error detallado
        # =====================================================================
        _logger.info(f"[CHAIN] ========== VERIFICACIÓN FALLIDA ==========")
        result['chain_verified'] = True
        
        # Crear mensaje de error detallado
        error_parts = []
        error_parts.append(f'El certificado fue emitido por "{cert_issuer_cn}".')
        
        # Verificar si es un problema de CA intermedia faltante
        issuer_is_configured = any(
            self._get_cn_from_name(ca_cert.subject) == cert_issuer_cn or 
            ca_record.subject_cn == cert_issuer_cn
            for ca_record, ca_cert in configured_cas
        )
        
        if issuer_is_configured:
            error_parts.append(
                f'Esta CA SÍ está configurada, pero la verificación de firma criptográfica falló. '
                f'Esto puede deberse a que el certificado incluye caracteres especiales o codificación diferente en el nombre del emisor.'
            )
        else:
            error_parts.append(f'Esta CA NO está configurada en el sistema.')
            error_parts.append(f'')
            error_parts.append(f'SOLUCIÓN: Debe agregar el certificado de "{cert_issuer_cn}" como Entidad Certificadora en:')
            error_parts.append(f'Ajustes > Validador de Firmas > Entidades Certificadoras')
            error_parts.append(f'')
            error_parts.append(f'CAs actualmente configuradas: {", ".join(ca_subjects)}')
            
            # Guardar hint de CA faltante
            result['missing_ca_hint'] = cert_issuer_cn
        
        result['validation_errors'].append('\n'.join(error_parts))
        
        return result
    
    def _build_chain_to_root(self, certificate, cert_pool, configured_cas, debug_info):
        """
        Intenta construir una cadena desde el certificado hasta una CA raíz de confianza.
        
        Returns:
            dict con 'success', 'trusted_ca', 'chain_path'
        """
        result = {
            'success': False,
            'trusted_ca': None,
            'chain_path': []
        }
        
        current_cert = certificate
        visited = set()
        max_depth = 10
        
        for depth in range(max_depth):
            current_serial = current_cert.serial_number
            if current_serial in visited:
                debug_info.append(f"Ciclo detectado en profundidad {depth}")
                _logger.warning(f"[CHAIN] Ciclo detectado en la cadena")
                break
            visited.add(current_serial)
            
            current_issuer_cn = self._get_cn_from_name(current_cert.issuer)
            _logger.info(f"[CHAIN] Profundidad {depth}: buscando emisor '{current_issuer_cn}'")
            debug_info.append(f"Nivel {depth}: buscando '{current_issuer_cn}'")
            
            # Buscar el emisor en el pool de certificados
            issuer_found = None
            
            for pool_entry in cert_pool:
                pool_cert = pool_entry['cert']
                pool_name = pool_entry['name']
                
                # Comparar nombres
                if self._names_match(current_cert.issuer, pool_cert.subject):
                    _logger.info(f"[CHAIN] Candidato encontrado: {pool_name}")
                    
                    # Verificar firma
                    sig_valid, sig_error = self._verify_certificate_signature_detailed(current_cert, pool_cert)
                    
                    if sig_valid:
                        _logger.info(f"[CHAIN] Firma válida con: {pool_name}")
                        debug_info.append(f"Encontrado y verificado: {pool_name}")
                        
                        result['chain_path'].append({
                            'type': 'intermediate' if not pool_entry['is_configured_ca'] else 'trusted_ca',
                            'subject': pool_entry['subject_cn'],
                            'issuer': self._get_cn_from_name(pool_cert.issuer)
                        })
                        
                        # Si es una CA configurada, hemos terminado
                        if pool_entry['is_configured_ca']:
                            # Buscar el record de la CA
                            for ca_record, ca_cert in configured_cas:
                                if ca_cert == pool_cert:
                                    result['success'] = True
                                    result['trusted_ca'] = {
                                        'name': ca_record.name,
                                        'subject_cn': ca_record.subject_cn,
                                        'organization': ca_record.subject_org
                                    }
                                    _logger.info(f"[CHAIN] Cadena completa hasta CA: {ca_record.name}")
                                    return result
                        
                        issuer_found = pool_cert
                        break
                    else:
                        _logger.warning(f"[CHAIN] Firma inválida con {pool_name}: {sig_error}")
                        debug_info.append(f"Candidato {pool_name} - firma inválida: {sig_error}")
            
            if issuer_found is None:
                _logger.info(f"[CHAIN] No se encontró emisor válido para '{current_issuer_cn}'")
                debug_info.append(f"No se encontró emisor: {current_issuer_cn}")
                break
            
            # Verificar si el emisor encontrado es self-signed (raíz)
            if self._names_match(issuer_found.subject, issuer_found.issuer):
                _logger.info(f"[CHAIN] Encontrado certificado raíz (self-signed)")
                # Verificar si está en las CAs configuradas
                for ca_record, ca_cert in configured_cas:
                    if self._names_match(ca_cert.subject, issuer_found.subject):
                        result['success'] = True
                        result['trusted_ca'] = {
                            'name': ca_record.name,
                            'subject_cn': ca_record.subject_cn,
                            'organization': ca_record.subject_org
                        }
                        return result
                
                debug_info.append(f"Certificado raíz encontrado pero no está en CAs configuradas")
                break
            
            current_cert = issuer_found
        
        return result
    
    def _verify_certificate_signature_detailed(self, certificate, issuer_cert):
        """
        Verifica si un certificado fue firmado por otro certificado.
        
        Returns:
            tuple: (bool válido, str mensaje_error o None)
        """
        try:
            issuer_public_key = issuer_cert.public_key()
            signature = certificate.signature
            tbs_certificate_bytes = certificate.tbs_certificate_bytes
            hash_alg = certificate.signature_hash_algorithm
            
            if hash_alg is None:
                hash_alg = hashes.SHA256()
            
            if isinstance(issuer_public_key, rsa.RSAPublicKey):
                try:
                    issuer_public_key.verify(
                        signature,
                        tbs_certificate_bytes,
                        padding.PKCS1v15(),
                        hash_alg
                    )
                    return True, None
                except InvalidSignature:
                    return False, "Firma RSA inválida"
                except Exception as e:
                    return False, f"Error verificando RSA: {str(e)}"
                    
            elif isinstance(issuer_public_key, ec.EllipticCurvePublicKey):
                try:
                    issuer_public_key.verify(
                        signature,
                        tbs_certificate_bytes,
                        ec.ECDSA(hash_alg)
                    )
                    return True, None
                except InvalidSignature:
                    return False, "Firma ECDSA inválida"
                except Exception as e:
                    return False, f"Error verificando ECDSA: {str(e)}"
            else:
                return False, f"Tipo de clave no soportado: {type(issuer_public_key)}"
                
        except Exception as e:
            return False, f"Error general: {str(e)}"
    
    def _names_match(self, name1, name2):
        """
        Compara dos objetos x509.Name de forma flexible.
        """
        try:
            # Método 1: Comparación directa
            if name1 == name2:
                return True
            
            # Método 2: Comparar CN (commonName)
            cn1 = self._get_cn_from_name(name1)
            cn2 = self._get_cn_from_name(name2)
            
            if cn1 and cn2 and cn1 == cn2:
                return True
            
            # Método 3: Comparar como diccionarios
            dict1 = self._name_to_dict(name1)
            dict2 = self._name_to_dict(name2)
            
            # Comparar elementos clave
            for key in ['CN', 'O', 'C']:
                val1 = dict1.get(key, '').strip()
                val2 = dict2.get(key, '').strip()
                if val1 and val2 and val1 != val2:
                    return False
            
            # Si CN coincide, consideramos match
            if dict1.get('CN') and dict2.get('CN') and dict1.get('CN') == dict2.get('CN'):
                return True
            
            return False
            
        except Exception as e:
            _logger.debug(f"Error comparando nombres: {e}")
            return name1 == name2
    
    def _name_to_dict(self, name):
        """Convierte x509.Name a diccionario."""
        result = {}
        try:
            for attr in name:
                oid = attr.oid
                if oid == NameOID.COMMON_NAME:
                    result['CN'] = attr.value
                elif oid == NameOID.ORGANIZATION_NAME:
                    result['O'] = attr.value
                elif oid == NameOID.COUNTRY_NAME:
                    result['C'] = attr.value
                elif oid == NameOID.ORGANIZATIONAL_UNIT_NAME:
                    result['OU'] = attr.value
                elif oid == NameOID.SERIAL_NUMBER:
                    result['SERIAL'] = attr.value
                else:
                    oid_name = oid._name if hasattr(oid, '_name') else str(oid.dotted_string)
                    result[oid_name] = attr.value
        except:
            pass
        return result
    
    def _name_to_string(self, name):
        """Convierte un x509.Name a string legible."""
        d = self._name_to_dict(name)
        return ", ".join(f"{k}={v}" for k, v in d.items())

    def _get_cn_from_name(self, name):
        """Extrae el Common Name de un x509.Name."""
        try:
            for attr in name:
                if attr.oid == NameOID.COMMON_NAME:
                    return attr.value
        except:
            pass
        return str(name)
    
    # =========================================================================
    # Mantener compatibilidad con método anterior
    # =========================================================================
    def _verify_certificate_signature(self, certificate, issuer_cert):
        """Wrapper para compatibilidad."""
        valid, _ = self._verify_certificate_signature_detailed(certificate, issuer_cert)
        return valid

    # =========================================================================
    # MÉTODOS AUXILIARES PARA CERTIFICADO P12
    # =========================================================================
    
    def _extract_name_info(self, name):
        """Extrae información detallada de un x509.Name."""
        info = {
            'common_name': '',
            'organization': '',
            'organizational_unit': '',
            'country': '',
            'state': '',
            'locality': '',
            'serial_number': '',
            'email': ''
        }
        
        try:
            for attr in name:
                if attr.oid == NameOID.COMMON_NAME:
                    info['common_name'] = attr.value
                elif attr.oid == NameOID.ORGANIZATION_NAME:
                    info['organization'] = attr.value
                elif attr.oid == NameOID.ORGANIZATIONAL_UNIT_NAME:
                    info['organizational_unit'] = attr.value
                elif attr.oid == NameOID.COUNTRY_NAME:
                    info['country'] = attr.value
                elif attr.oid == NameOID.STATE_OR_PROVINCE_NAME:
                    info['state'] = attr.value
                elif attr.oid == NameOID.LOCALITY_NAME:
                    info['locality'] = attr.value
                elif attr.oid == NameOID.SERIAL_NUMBER:
                    info['serial_number'] = attr.value
                elif attr.oid == NameOID.EMAIL_ADDRESS:
                    info['email'] = attr.value
        except Exception as e:
            _logger.error(f"Error extrayendo información del nombre: {e}")
        
        return info
    
    def _build_detailed_validation_result(self, certificate, chain_result, is_expired, now):
        """Construye un resultado detallado de validación con mensajes claros."""
        result = {
            'validation_errors': list(chain_result.get('validation_errors', [])),
            'validation_warnings': list(chain_result.get('validation_warnings', [])),
            'validation_details': [],
            'debug_info': chain_result.get('debug_info', [])
        }
        
        # Agregar errores de expiración
        if is_expired:
            try:
                not_after = certificate.not_valid_after_utc if hasattr(certificate, 'not_valid_after_utc') else certificate.not_valid_after
                if not_after.tzinfo is None:
                    not_after = not_after.replace(tzinfo=timezone.utc)
                days_expired = (now - not_after).days
                result['validation_errors'].append(
                    f'El certificado expiró hace {days_expired} día(s), el {not_after.strftime("%d/%m/%Y")}.'
                )
            except:
                result['validation_errors'].append('El certificado ha expirado.')
        
        # Verificar si está próximo a expirar
        if not is_expired:
            try:
                not_after = certificate.not_valid_after_utc if hasattr(certificate, 'not_valid_after_utc') else certificate.not_valid_after
                if not_after.tzinfo is None:
                    not_after = not_after.replace(tzinfo=timezone.utc)
                days_until = (not_after - now).days
                if days_until <= 30:
                    result['validation_warnings'].append(
                        f'El certificado expirará en {days_until} día(s), el {not_after.strftime("%d/%m/%Y")}.'
                    )
            except:
                pass
        
        # Agregar detalles de la cadena
        if chain_result.get('chain_valid'):
            ca_info = chain_result.get('trusted_ca', {})
            result['validation_details'].append(
                f'Cadena de confianza verificada contra: {ca_info.get("name", "CA")} ({ca_info.get("organization", "")})'
            )
        
        return result

    # =====================================================
    # PÁGINA DE VALIDACIÓN DE CERTIFICADOS P12
    # =====================================================
    
    @http.route(['/validar-certificado'], type='http', auth='user', website=True)
    def certificate_validation_page(self, **kw):
        """
        Renderiza la página de validación de certificados P12.
        Muestra al usuario si tiene un certificado guardado en su perfil.
        """
        try:
            user = request.env.user
            user_has_certificado = bool(user.certificado_firma)
            user_has_password = bool(user.contrasena_certificado)
            
            ca_count = request.env['asi.certificate.authority'].sudo().search_count([('active', '=', True)])
            
            return request.render('asi_signature_validator.certificate_validation_page', {
                'message': kw.get('msg'),
                'user_has_certificado': user_has_certificado,
                'user_has_password': user_has_password,
                'ca_count': ca_count,
            })
        except Exception as e:
            _logger.error(f"Error al cargar página de validación de certificados: {e}")
            return request.render('asi_signature_validator.certificate_validation_page', {
                'message': f'Error al cargar el formulario: {str(e)}',
                'user_has_certificado': False,
                'user_has_password': False,
                'ca_count': 0,
            })

    @http.route(['/validar-certificado/verificar'], type='http', auth='user', website=True, csrf=False, methods=['POST'])
    def validate_certificate(self, **post):
        """
        Endpoint para validar un certificado P12.
        Recibe el archivo P12 y la contraseña, devuelve información del certificado.
        """
        if not HAS_CRYPTOGRAPHY:
            return self._json_error_response(
                'El módulo de criptografía no está instalado en el servidor.',
                status=500
            )
        
        try:
            files = request.httprequest.files
            user = request.env.user
            
            # Determinar origen del certificado y contraseña
            cert_file = files.get('certificate')
            password = post.get('password', '').strip()
            use_profile = post.get('use_profile') == 'true'
            
            cert_data = None
            
            if use_profile and user.certificado_firma:
                try:
                    cert_data = base64.b64decode(user.certificado_firma)
                    _logger.info(f"Usando certificado del perfil del usuario {user.id}")
                except Exception as e:
                    _logger.error(f"Error al decodificar certificado del perfil: {e}")
                    return self._json_error_response('Error al leer el certificado del perfil.')
                
                if not password and user.contrasena_certificado:
                    password = user.get_contrasena_descifrada()
                    _logger.info("Usando contraseña del perfil del usuario")
            elif cert_file and cert_file.filename:
                cert_data = cert_file.read()
                _logger.info(f"Certificado subido: {secure_filename(cert_file.filename)}")
            else:
                return self._json_error_response('Debe proporcionar un archivo de certificado (.p12).')
            
            if not password:
                return self._json_error_response('Debe proporcionar la contraseña del certificado.')
            
            # Validar el certificado
            result = self._validate_p12_certificate(cert_data, password)
            
            return request.make_json_response(result)
            
        except Exception as e:
            _logger.error(f"Error en validación de certificado: {e}")
            return self._json_error_response(f'Error al procesar el certificado: {str(e)}')

    # =====================================================
    # PÁGINA DE VERIFICACIÓN DE FIRMAS EN PDFs
    # =====================================================
    
    @http.route(['/verificar-firmas-pdf'], type='http', auth='user', website=True)
    def pdf_signature_verification_page(self, **kw):
        """
        Renderiza la página de verificación de firmas en PDFs.
        """
        try:
            ca_count = request.env['asi.certificate.authority'].sudo().search_count([('active', '=', True)])
            
            return request.render('asi_signature_validator.pdf_verification_page', {
                'message': kw.get('msg'),
                'ca_count': ca_count,
            })
        except Exception as e:
            _logger.error(f"Error al cargar página de verificación de PDFs: {e}")
            return request.render('asi_signature_validator.pdf_verification_page', {
                'message': f'Error al cargar el formulario: {str(e)}',
                'ca_count': 0,
            })

    @http.route(['/verificar-firmas-pdf/analizar'], type='http', auth='user', website=True, csrf=False, methods=['POST'])
    def analyze_pdf_signatures(self, **post):
        """
        Endpoint para analizar las firmas digitales en uno o varios PDFs.
        """
        try:
            files = request.httprequest.files
            pdf_files = files.getlist('pdfs')
            
            if not pdf_files:
                return self._json_error_response('Debe subir al menos un archivo PDF.')
            
            results = []
            
            for pdf_file in pdf_files:
                if not pdf_file.filename:
                    continue
                    
                filename = secure_filename(pdf_file.filename)
                _logger.info(f"Analizando firmas en: {filename}")
                
                try:
                    pdf_data = pdf_file.read()
                    pdf_result = self._analyze_single_pdf(pdf_data, filename)
                    results.append(pdf_result)
                except Exception as e:
                    _logger.error(f"Error analizando {filename}: {e}", exc_info=True)
                    results.append({
                        'filename': filename,
                        'error': str(e),
                        'has_signatures': False,
                        'signatures': []
                    })
            
            return request.make_json_response({
                'success': True,
                'total_files': len(results),
                'results': results
            })
            
        except Exception as e:
            _logger.error(f"Error en análisis de PDFs: {e}", exc_info=True)
            return self._json_error_response(f'Error al procesar los PDFs: {str(e)}')

    def _analyze_single_pdf(self, pdf_data, filename):
        """
        Analiza un único PDF y extrae información de sus firmas.
        
        Args:
            pdf_data: Bytes del archivo PDF
            filename: Nombre del archivo
            
        Returns:
            dict: Diccionario con información de las firmas encontradas
        """
        try:
            signatures_list = self._extract_pkcs7_signatures_from_pdf(pdf_data)
            
            signatures_grouped = {}
            for sig in signatures_list:
                # Crear clave única basada en firmante, emisor y fechas de validez
                # Asegurarse de que valid_from y valid_until existan y sean comparables
                valid_from = sig.get('valid_from', 'unknown')
                valid_until = sig.get('expiry_date', 'unknown') # Usamos 'expiry_date' como 'valid_until'
                
                sig_key = f"{sig.get('signer', 'unknown')}|{sig.get('issuer', 'unknown')}|{valid_from}|{valid_until}"
                
                if sig_key in signatures_grouped:
                    signatures_grouped[sig_key]['count'] += 1
                else:
                    sig['count'] = 1
                    signatures_grouped[sig_key] = sig
            
            # Convertir de nuevo a lista
            unique_signatures = list(signatures_grouped.values())
            
            _logger.info(f"Se encontraron {len(signatures_list)} firma(s) en {filename} ({len(unique_signatures)} única(s))")
            
            return {
                'filename': filename,
                'has_signatures': len(unique_signatures) > 0,
                'total_signatures': len(signatures_list),
                'unique_signatures': len(unique_signatures),
                'signatures': unique_signatures,
                'error': None
            }
        except Exception as e:
            _logger.error(f"Error analizando PDF {filename}: {e}", exc_info=True)
            return {
                'filename': filename,
                'has_signatures': False,
                'total_signatures': 0,
                'unique_signatures': 0,
                'signatures': [],
                'error': str(e)
            }

    def _extract_pkcs7_signatures_from_pdf(self, pdf_data):
        """
        Extrae firmas PKCS#7/CMS directamente del contenido binario del PDF.
        """
        signatures = []
        seen_hashes = set()
        
        try:
            pdf_str = pdf_data
            sig_pattern = rb'/Type\s*/Sig'
            sig_dict_starts = [m.start() for m in re.finditer(sig_pattern, pdf_str)]
            
            _logger.info(f"Encontrados {len(sig_dict_starts)} objetos /Type /Sig en el PDF")
            
            unique_count = 0
            for idx, pos in enumerate(sig_dict_starts):
                try:
                    _logger.debug(f"Procesando firma potencial #{idx + 1} en posición {pos}")
                    sig_info, pkcs7_hash = self._extract_single_signature(pdf_str, pos, idx + 1)
                    if sig_info and pkcs7_hash:
                        if pkcs7_hash not in seen_hashes:
                            seen_hashes.add(pkcs7_hash)
                            unique_count += 1
                            sig_info['index'] = unique_count
                            sig_info['field_name'] = f'Firma #{unique_count}'
                            signatures.append(sig_info)
                            _logger.info(f"Firma #{unique_count} agregada")
                except Exception as e:
                    _logger.error(f"Error procesando firma #{idx + 1}: {e}", exc_info=True)
            
            if not signatures:
                _logger.info("Intentando método alternativo de búsqueda de PKCS#7...")
                signatures = self._find_pkcs7_structures(pdf_data)
            
        except Exception as e:
            _logger.error(f"Error extrayendo firmas PKCS#7: {e}", exc_info=True)
        
        return signatures

    def _extract_single_signature(self, pdf_data, sig_pos, sig_index):
        """
        Extrae información de una única firma desde la posición dada.
        """
        try:
            search_start = max(0, sig_pos - 3000)
            search_end = min(len(pdf_data), sig_pos + 15000)
            chunk = pdf_data[search_start:search_end]
            
            relative_sig_pos = sig_pos - search_start
            dict_start = chunk.rfind(b'<<', 0, relative_sig_pos + 20)
            
            dict_end = None
            if dict_start != -1:
                nesting = 0
                i = dict_start
                while i < len(chunk) - 1:
                    if chunk[i:i+2] == b'<<':
                        nesting += 1
                        i += 2
                    elif chunk[i:i+2] == b'>>':
                        nesting -= 1
                        if nesting == 0:
                            dict_end = i + 2
                            break
                        i += 2
                    else:
                        i += 1
            
            if dict_start != -1 and dict_end:
                sig_dict_chunk = chunk[dict_start:dict_end]
            else:
                sig_dict_chunk = chunk
            
            contents_pattern = rb'/Contents\s*<([0-9a-fA-F\s]+)>'
            contents_match = re.search(contents_pattern, chunk)
            
            if not contents_match:
                contents_pattern2 = rb'/Contents\s*$$([^$$]*)\)'
                contents_match = re.search(contents_pattern2, chunk)
            
            if not contents_match:
                return None, None
            
            hex_content = contents_match.group(1)
            hex_content = re.sub(rb'\s+', b'', hex_content)
            
            try:
                pkcs7_data = bytes.fromhex(hex_content.decode('ascii'))
            except Exception as e:
                return None, None
            
            import hashlib
            pkcs7_hash = hashlib.sha256(pkcs7_data).hexdigest()
            
            sig_info = self._parse_pkcs7_signature(pkcs7_data, sig_index, sig_dict_chunk)
            return sig_info, pkcs7_hash
            
        except Exception as e:
            _logger.error(f"Error extrayendo firma individual #{sig_index}: {e}", exc_info=True)
            return None, None

    def _find_pkcs7_structures(self, pdf_data):
        """
        Método alternativo: buscar estructuras PKCS#7 directamente en el PDF.
        """
        signatures = []
        
        try:
            signed_data_oid = bytes([0x06, 0x09, 0x2A, 0x86, 0x48, 0x86, 0xF7, 0x0D, 0x01, 0x07, 0x02])
            
            pos = 0
            sig_index = 0
            
            while True:
                pos = pdf_data.find(signed_data_oid, pos)
                if pos == -1:
                    break
                
                sig_index += 1
                
                for offset in range(min(50, pos)):
                    check_pos = pos - offset
                    if check_pos >= 0 and pdf_data[check_pos] == 0x30:
                        try:
                            length, header_len = self._read_asn1_length(pdf_data, check_pos + 1)
                            if length and length > 100:
                                total_len = 1 + header_len + length
                                pkcs7_data = pdf_data[check_pos:check_pos + total_len]
                                
                                sig_info = self._parse_pkcs7_signature(pkcs7_data, sig_index, b'')
                                if sig_info:
                                    signatures.append(sig_info)
                                    break
                        except:
                            continue
                
                pos += 1
                
        except Exception as e:
            _logger.error(f"Error buscando estructuras PKCS#7: {e}", exc_info=True)
        
        return signatures

    def _read_asn1_length(self, data, pos):
        """
        Lee la longitud de un elemento ASN.1 DER.
        """
        if pos >= len(data):
            return None, 0
        
        first_byte = data[pos]
        
        if first_byte < 0x80:
            return first_byte, 1
        elif first_byte == 0x80:
            return None, 0
        else:
            num_bytes = first_byte & 0x7F
            if pos + 1 + num_bytes > len(data):
                return None, 0
            
            length = 0
            for i in range(num_bytes):
                length = (length << 8) | data[pos + 1 + i]
            
            return length, 1 + num_bytes

    def _parse_pkcs7_signature(self, pkcs7_data, sig_index, pdf_chunk):
        """
        Parsea los datos PKCS#7/CMS y extrae información del certificado.
        Incluye verificación de cadena de confianza.
        """
        sig_info = {
            'index': sig_index,
            'field_name': f'Firma #{sig_index}',
            'signer': 'Desconocido',
            'issuer': 'Desconocido',
            'sign_date': None,
            'valid': None,
            'expiry_date': None,
            'valid_from': None,
            'reason': None,
            'location': None,
            'validation_errors': [],
            'validation_warnings': [],
            'chain_valid': None,
            'trusted_ca': None,
            'hash': None  # Añadido para agrupar duplicados
        }
        
        try:
            import hashlib
            sig_info['hash'] = hashlib.sha256(pkcs7_data).hexdigest()
            
            # Extraer metadatos del diccionario PDF
            if pdf_chunk:
                # Razón de la firma
                reason_patterns = [
                    rb'/Reason\s*$$([^$$]*)\)',
                    rb'/Reason\s*<([0-9a-fA-F]+)>',
                ]
                for pattern in reason_patterns:
                    reason_match = re.search(pattern, pdf_chunk)
                    if reason_match:
                        try:
                            raw = reason_match.group(1)
                            if b'<' in pattern:
                                sig_info['reason'] = bytes.fromhex(raw.decode('ascii')).decode('utf-8', errors='ignore')
                            else:
                                sig_info['reason'] = raw.decode('utf-8', errors='ignore')
                            break
                        except:
                            pass
                
                # Ubicación
                location_patterns = [
                    rb'/Location\s*$$([^$$]*)\)',
                    rb'/Location\s*<([0-9a-fA-F]+)>',
                ]
                for pattern in location_patterns:
                    location_match = re.search(pattern, pdf_chunk)
                    if location_match:
                        try:
                            raw = location_match.group(1)
                            if b'<' in pattern:
                                sig_info['location'] = bytes.fromhex(raw.decode('ascii')).decode('utf-8', errors='ignore')
                            else:
                                sig_info['location'] = raw.decode('utf-8', errors='ignore')
                            break
                        except:
                            pass
                
                # Fecha /M
                date_patterns = [
                    (rb"/M\s*$$D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})[^$$]*([+-Z])?(\d{2})?(\d{2})?$", "estándar completo"),
                    (rb"/M\s*$$D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})$$", "estándar sin segundos"),
                    (rb"/M\s*$$D:(\d{4})(\d{2})(\d{2})$$", "estándar solo fecha"),
                    (rb"/M\s*<([0-9a-fA-F]+)>", "hexadecimal"),
                ]
                
                for pattern, pattern_name in date_patterns:
                    date_match = re.search(pattern, pdf_chunk)
                    if date_match:
                        try:
                            groups = date_match.groups()
                            
                            if pattern_name == "hexadecimal":
                                hex_date = groups[0].decode('ascii')
                                date_str = bytes.fromhex(hex_date).decode('utf-8', errors='ignore')
                                inner_match = re.match(r'D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?', date_str)
                                if inner_match:
                                    groups = inner_match.groups()
                                else:
                                    continue
                            
                            year = int(groups[0])
                            month = int(groups[1]) if len(groups) > 1 and groups[1] else 1
                            day = int(groups[2]) if len(groups) > 2 and groups[2] else 1
                            hour = int(groups[3]) if len(groups) > 3 and groups[3] else 0
                            minute = int(groups[4]) if len(groups) > 4 and groups[4] else 0
                            second = int(groups[5]) if len(groups) > 5 and groups[5] else 0
                            
                            sign_dt = datetime(year, month, day, hour, minute, second)
                            
                            # Manejar timezone offset
                            tz_indicator = groups[6] if len(groups) > 6 else None
                            tz_hour = int(groups[7]) if len(groups) > 7 and groups[7] else 0
                            tz_minute = int(groups[8]) if len(groups) > 8 and groups[8] else 0

                            if tz_indicator == '+':
                                offset = timezone(timedelta(hours=tz_hour, minutes=tz_minute))
                            elif tz_indicator == '-':
                                offset = timezone(timedelta(hours=-tz_hour, minutes=-tz_minute))
                            else: # 'Z' or no indicator implies UTC
                                offset = timezone.utc
                            
                            if offset:
                                sign_dt = sign_dt.replace(tzinfo=offset)
                            
                            sig_info['sign_date'] = sign_dt.astimezone(timezone.utc).strftime('%d/%m/%Y %H:%M:%S')
                            break
                        except Exception as e:
                            _logger.debug(f"Error parsing date pattern {pattern_name}: {e}")
                            continue
            
            # Parsear PKCS#7
            content_info = cms.ContentInfo.load(pkcs7_data)
            
            if content_info['content_type'].native != 'signed_data':
                sig_info['validation_errors'].append('El contenido de la firma no es de tipo SignedData.')
                return sig_info
            
            signed_data = content_info['content']
            certificates = signed_data['certificates']
            
            if not certificates:
                sig_info['validation_errors'].append('La firma no contiene certificados embebidos.')
                return sig_info
            
            # Encontrar el certificado del firmante
            cert = None
            additional_certs = []
            signer_infos = signed_data['signer_infos']
            
            if signer_infos and len(signer_infos) > 0:
                signer_info_obj = signer_infos[0]
                sid = signer_info_obj['sid']
                
                if sid.name == 'issuer_and_serial_number':
                    target_serial = sid.chosen['serial_number'].native
                    
                    for cert_choice in certificates:
                        try:
                            c = cert_choice.chosen if hasattr(cert_choice, 'chosen') else cert_choice
                            tbs = c['tbs_certificate']
                            if tbs['serial_number'].native == target_serial:
                                cert = c
                            else:
                                additional_certs.append(c)
                        except:
                            continue
            
            if cert is None:
                for cert_choice in certificates:
                    try:
                        cert = cert_choice.chosen if hasattr(cert_choice, 'chosen') else cert_choice
                        break
                    except:
                        continue
            
            if cert is None:
                sig_info['validation_errors'].append('No se pudo extraer el certificado del firmante.')
                return sig_info
            
            # Extraer información del certificado
            tbs = cert['tbs_certificate']
            
            # Sujeto
            subject = tbs['subject']
            subject_info = self._parse_asn1_name(subject)
            signer_name = subject_info.get('common_name', 
                         subject_info.get('organization', 
                         subject_info.get('serial_number', 'Desconocido')))
            sig_info['signer'] = signer_name
            sig_info['signer_details'] = subject_info
            
            # Emisor
            issuer = tbs['issuer']
            issuer_info = self._parse_asn1_name(issuer)
            issuer_name = issuer_info.get('common_name',
                         issuer_info.get('organization', 'Desconocido'))
            sig_info['issuer'] = issuer_name
            sig_info['issuer_details'] = issuer_info
            
            # Fechas de validez
            validity = tbs['validity']
            not_before = validity['not_before'].native
            not_after = validity['not_after'].native
            
            now = datetime.now(timezone.utc)
            if not_before.tzinfo is None:
                not_before = not_before.replace(tzinfo=timezone.utc)
            if not_after.tzinfo is None:
                not_after = not_after.replace(tzinfo=timezone.utc)
            
            is_expired = now > not_after
            is_not_yet_valid = now < not_before
            is_cert_valid = not_before <= now <= not_after
            
            sig_info['valid_from'] = not_before.strftime('%d/%m/%Y %H:%M:%S')
            sig_info['expiry_date'] = not_after.strftime('%d/%m/%Y %H:%M:%S') # Corregido para que coincida con el uso en _analyze_single_pdf
            sig_info['expired'] = is_expired
            
            if HAS_CRYPTOGRAPHY:
                try:
                    # Reconstruir certificado x509 desde asn1crypto para usar con cryptography
                    cert_der = cert.dump()
                    x509_cert = x509.load_der_x509_certificate(cert_der, default_backend())
                    
                    # Convertir certificados adicionales
                    x509_additional = []
                    for ac in additional_certs:
                        try:
                            ac_der = ac.dump()
                            x509_additional.append(x509.load_der_x509_certificate(ac_der, default_backend()))
                        except:
                            pass
                    
                    chain_result = self._verify_certificate_chain(x509_cert, x509_additional)
                    
                    sig_info['chain_validation'] = {
                        'verified': chain_result.get('chain_verified', False),
                        'valid': chain_result.get('chain_valid', False),
                        'trusted_ca': chain_result.get('trusted_ca'),
                        'chain_path': chain_result.get('chain_path', [])
                    }
                    sig_info['validation_errors'].extend(chain_result.get('validation_errors', []))
                    sig_info['validation_warnings'].extend(chain_result.get('validation_warnings', []))
                    sig_info['debug_info'] = chain_result.get('debug_info', [])
                    
                except Exception as e:
                    _logger.error(f"Error verificando cadena para firma PDF: {e}")
                    sig_info['validation_warnings'].append(f'No se pudo verificar la cadena de confianza: {str(e)}')
            
            if is_expired:
                days_expired = (now - not_after).days
                sig_info['validation_errors'].append(
                    f'El certificado del firmante expiró hace {days_expired} día(s) '
                    f'(fecha de expiración: {not_after.strftime("%d/%m/%Y")}).'
                )
            
            if is_not_yet_valid:
                sig_info['validation_errors'].append(
                    f'El certificado del firmante aún no era válido en el momento de la verificación '
                    f'(válido desde: {not_before.strftime("%d/%m/%Y")}).'
                )
            
            # Determinar validez final de la firma
            has_cas = len(self._get_configured_cas()) > 0
            if has_cas:
                chain_valid = sig_info.get('chain_validation', {}).get('valid', False)
                # La firma es válida si el certificado es válido Y la cadena de confianza es válida
                sig_info['valid'] = is_cert_valid and chain_valid
            else:
                # Si no hay CAs configuradas, solo consideramos la validez del certificado
                sig_info['valid'] = is_cert_valid
            
            # Buscar fecha de firma en atributos
            if signer_infos and len(signer_infos) > 0 and not sig_info['sign_date']:
                signer_info_obj = signer_infos[0]
                signed_attrs = signer_info_obj['signed_attrs']
                
                if signed_attrs:
                    for attr in signed_attrs:
                        if attr['type'].native == 'signing_time':
                            try:
                                signing_time = attr['values'][0].native
                                if signing_time:
                                    if signing_time.tzinfo is None:
                                        signing_time = signing_time.replace(tzinfo=timezone.utc)
                                    sig_info['sign_date'] = signing_time.astimezone(timezone.utc).strftime('%d/%m/%Y %H:%M:%S')
                            except:
                                pass
                            break
                
                # Buscar timestamp
                unsigned_attrs = signer_info_obj['unsigned_attrs']
                if unsigned_attrs and not sig_info['sign_date']:
                    for attr in unsigned_attrs:
                        attr_type = attr['type'].native
                        if attr_type in ('signature_time_stamp_token', 'time_stamp_token'):
                            try:
                                ts_token_data = attr['values'][0].native
                                if isinstance(ts_token_data, bytes):
                                    ts_content_info = cms.ContentInfo.load(ts_token_data)
                                else:
                                    ts_content_info = cms.ContentInfo.load(attr['values'][0].contents)
                                
                                if ts_content_info['content_type'].native == 'signed_data':
                                    ts_signed_data = ts_content_info['content']
                                    ts_content = ts_signed_data['encap_content_info']['content']
                                    if ts_content:
                                        tst_info = tsp.TSTInfo.load(ts_content.native)
                                        gen_time = tst_info['gen_time'].native
                                        if gen_time:
                                            if gen_time.tzinfo is None:
                                                gen_time = gen_time.replace(tzinfo=timezone.utc)
                                            sig_info['sign_date'] = gen_time.astimezone(timezone.utc).strftime('%d/%m/%Y %H:%M:%S')
                                            sig_info['timestamp_authority'] = True
                            except:
                                pass
            
            if not sig_info['sign_date']:
                sig_info['sign_date'] = 'No disponible'
            
            return sig_info
            
        except Exception as e:
            _logger.error(f"Error parseando PKCS#7: {e}", exc_info=True)
            sig_info['validation_errors'].append(f'Error al procesar la firma: {str(e)}')
            return sig_info

    def _parse_asn1_name(self, name):
        """
        Parsea un nombre ASN.1 a un diccionario legible.
        """
        info = {}
        try:
            name_obj = name
            if hasattr(name, 'chosen'):
                name_obj = name.chosen
            
            for rdn in name_obj:
                for name_type_value in rdn:
                    try:
                        oid = name_type_value['type']
                        type_name = oid.human_friendly if hasattr(oid, 'human_friendly') else str(oid.native)
                        value = name_type_value['value'].native
                        
                        key_mapping = {
                            'common_name': 'common_name',
                            'organization_name': 'organization',
                            'organizational_unit_name': 'organizational_unit',
                            'country_name': 'country',
                            'state_or_province_name': 'state',
                            'locality_name': 'locality',
                            'email_address': 'email',
                            'serial_number': 'serial_number',
                            'surname': 'surname',
                            'given_name': 'given_name',
                        }
                        
                        key = key_mapping.get(type_name.lower().replace(' ', '_'), type_name)
                        info[key] = value
                    except:
                        pass
        except Exception as e:
            _logger.error(f"Error parseando nombre ASN.1: {e}")
        
        return info

    # =====================================================
    # MÉTODOS AUXILIARES
    # =====================================================
    
    def _json_error_response(self, message, status=400):
        """
        Genera una respuesta JSON de error consistente.
        """
        _logger.error(f"Error en validador: {message}")
        response = request.make_json_response({
            'success': False,
            'error': message
        }, status=status)
        response.headers['Content-Type'] = 'application/json'
        return response

    # =========================================================================
    # RUTAS WEB
    # =========================================================================
    
    @http.route('/asi/validador', type='http', auth='public', website=True)
    def validator_home(self, **kw):
        """Página principal del validador."""
        ca_count = len(self._get_configured_cas())
        return request.render('asi_signature_validator.validator_home', {
            'ca_count': ca_count
        })
    
    @http.route('/asi/validador/p12', type='http', auth='public', website=True)
    def validator_p12(self, **kw):
        """Página de validación de certificados P12."""
        ca_count = len(self._get_configured_cas())
        return request.render('asi_signature_validator.validator_p12', {
            'ca_count': ca_count
        })
    
    @http.route('/asi/validador/pdf', type='http', auth='public', website=True)
    def validator_pdf(self, **kw):
        """Página de validación de firmas en PDF."""
        ca_count = len(self._get_configured_cas())
        return request.render('asi_signature_validator.validator_pdf', {
            'ca_count': ca_count
        })
    
    @http.route('/asi/validador/validate_p12', type='json', auth='public', methods=['POST'])
    def validate_p12(self, **kw):
        """Endpoint AJAX para validar certificado P12."""
        try:
            file_data = kw.get('file_data')
            password = kw.get('password', '')
            
            if not file_data:
                return {'success': False, 'error': 'No se recibió el archivo'}
            
            # Decodificar archivo base64
            if ',' in file_data:
                file_data = file_data.split(',')[1]
            
            cert_data = base64.b64decode(file_data)
            result = self._validate_p12_certificate(cert_data, password)
            
            return result
            
        except Exception as e:
            _logger.exception("Error validando P12")
            return {'success': False, 'error': f'Error procesando el archivo: {str(e)}'}
    
    @http.route('/asi/validador/validate_pdf', type='json', auth='public', methods=['POST'])
    def validate_pdf(self, **kw):
        """Endpoint AJAX para validar firmas en PDF."""
        try:
            file_data = kw.get('file_data')
            
            if not file_data:
                return {'success': False, 'error': 'No se recibió el archivo'}
            
            if ',' in file_data:
                file_data = file_data.split(',')[1]
            
            pdf_data = base64.b64decode(file_data)
            result = self._validate_pdf_signatures(pdf_data)
            
            return result
            
        except Exception as e:
            _logger.exception("Error validando PDF")
            return {'success': False, 'error': f'Error procesando el archivo: {str(e)}'}
    
    # =========================================================================
    # VALIDACIÓN DE CERTIFICADOS P12
    # =========================================================================
    
    def _validate_p12_certificate(self, cert_data, password):
        """Valida un certificado P12 y extrae su información."""
        try:
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                cert_data,
                password.encode('utf-8'),
                default_backend()
            )
            
            if certificate is None:
                return {
                    'success': False,
                    'error': 'El archivo P12 no contiene un certificado válido.',
                    'validation_errors': ['El archivo P12 no contiene un certificado que se pueda extraer.']
                }
            
            # Extraer información del certificado
            subject = certificate.subject
            issuer = certificate.issuer
            
            subject_info = self._extract_name_info(subject)
            issuer_info = self._extract_name_info(issuer)
            
            # Fechas de validez
            not_before = certificate.not_valid_before_utc if hasattr(certificate, 'not_valid_before_utc') else certificate.not_valid_before
            not_after = certificate.not_valid_after_utc if hasattr(certificate, 'not_valid_after_utc') else certificate.not_valid_after
            
            now = datetime.now(timezone.utc)
            if not_before.tzinfo is None:
                not_before = not_before.replace(tzinfo=timezone.utc)
            if not_after.tzinfo is None:
                not_after = not_after.replace(tzinfo=timezone.utc)
            
            is_expired = now > not_after
            is_not_yet_valid = now < not_before
            is_time_valid = not_before <= now <= not_after
            days_until_expiry = (not_after - now).days if not is_expired else 0
            
            serial_number = format(certificate.serial_number, 'X')
            
            _logger.info(f"[P12] Certificado: {subject_info.get('common_name')}")
            _logger.info(f"[P12] Emisor: {issuer_info.get('common_name')}")
            _logger.info(f"[P12] Certificados adicionales en P12: {len(additional_certs) if additional_certs else 0}")
            
            if additional_certs:
                for i, ac in enumerate(additional_certs):
                    if ac:
                        ac_cn = self._get_cn_from_name(ac.subject)
                        ac_issuer = self._get_cn_from_name(ac.issuer)
                        _logger.info(f"[P12] Adicional {i+1}: {ac_cn} (emitido por: {ac_issuer})")
            
            chain_result = self._verify_certificate_chain(certificate, additional_certs)
            
            validation_result = self._build_detailed_validation_result(
                certificate, chain_result, is_expired, now
            )
            
            is_chain_valid = chain_result.get('chain_valid', False)
            has_cas_configured = len(self._get_configured_cas()) > 0
            
            if has_cas_configured:
                is_valid = is_time_valid and is_chain_valid
            else:
                is_valid = is_time_valid
            
            return {
                'success': True,
                'valid': is_valid,
                'expired': is_expired,
                'not_yet_valid': is_not_yet_valid,
                'password_correct': True,
                'certificate_info': {
                    'subject': subject_info,
                    'issuer': issuer_info,
                    'serial_number': serial_number,
                    'not_before': not_before.strftime('%d/%m/%Y %H:%M:%S'),
                    'not_after': not_after.strftime('%d/%m/%Y %H:%M:%S'),
                    'days_until_expiry': days_until_expiry,
                },
                'chain_validation': {
                    'verified': chain_result.get('chain_verified', False),
                    'valid': chain_result.get('chain_valid', False),
                    'trusted_ca': chain_result.get('trusted_ca'),
                    'chain_path': chain_result.get('chain_path', [])
                },
                'validation_errors': validation_result['validation_errors'],
                'validation_warnings': validation_result['validation_warnings'],
                'validation_details': validation_result['validation_details'],
                'debug_info': validation_result.get('debug_info', [])  # Incluir debug info
            }
            
        except ValueError as e:
            error_str = str(e).lower()
            if 'password' in error_str or 'mac' in error_str or 'decrypt' in error_str:
                return {
                    'success': False,
                    'error': 'Contraseña incorrecta o archivo corrupto.',
                    'password_correct': False,
                    'validation_errors': ['La contraseña proporcionada no es correcta para este certificado P12.']
                }
            return {
                'success': False,
                'error': f'Error al leer el certificado: {str(e)}',
                'validation_errors': [f'No se pudo procesar el archivo P12: {str(e)}']
            }
        except Exception as e:
            _logger.exception("Error validando P12")
            return {
                'success': False,
                'error': f'Error inesperado: {str(e)}',
                'validation_errors': [f'Error interno al procesar el certificado: {str(e)}']
            }
    
    # =========================================================================
    # VALIDACIÓN DE FIRMAS EN PDF
    # =========================================================================
    
    def _validate_pdf_signatures(self, pdf_data):
        """Valida las firmas digitales en un documento PDF."""
        if not HAS_PYHANKO:
            return self._validate_pdf_basic(pdf_data)
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(pdf_data)
                tmp_path = tmp.name
            
            try:
                with open(tmp_path, 'rb') as f:
                    reader = PdfFileReader(f)
                    
                    sig_fields = reader.embedded_signatures
                    
                    if not sig_fields:
                        return {
                            'success': True,
                            'has_signatures': False,
                            'message': 'El documento PDF no contiene firmas digitales.',
                            'signatures': []
                        }
                    
                    signatures = []
                    
                    for sig in sig_fields:
                        sig_info = self._extract_signature_info_pyhanko(sig)
                        signatures.append(sig_info)
                    
                    all_valid = all(s.get('valid', False) for s in signatures)
                    
                    return {
                        'success': True,
                        'has_signatures': True,
                        'signature_count': len(signatures),
                        'all_valid': all_valid,
                        'signatures': signatures
                    }
                    
            finally:
                os.unlink(tmp_path)
                
        except Exception as e:
            _logger.exception("Error validando PDF")
            return {
                'success': False,
                'error': f'Error al procesar el PDF: {str(e)}',
                'validation_errors': [f'No se pudo analizar el documento PDF: {str(e)}']
            }
    
    def _extract_signature_info_pyhanko(self, sig):
        """Extrae información de una firma usando pyHanko."""
        info = {
            'valid': False,
            'signer': {},
            'issuer': {},
            'timestamp': None,
            'validation_errors': [],
            'validation_warnings': [],
            'chain_validation': {
                'verified': False,
                'valid': False,
                'trusted_ca': None,
                'chain_path': []
            },
            'debug_info': []
        }
        
        try:
            # Extraer información del certificado del firmante
            try:
                signer_cert = sig.signer_cert
                if signer_cert:
                    info['signer'] = self._extract_name_info(signer_cert.subject)
                    info['issuer'] = self._extract_name_info(signer_cert.issuer)
                    
                    # Verificar cadena de confianza
                    try:
                        # Obtener certificados adicionales de la firma
                        additional_certs = []
                        if hasattr(sig, 'other_embedded_certs'):
                            additional_certs = list(sig.other_embedded_certs)
                        
                        chain_result = self._verify_certificate_chain(signer_cert, additional_certs)
                        info['chain_validation'] = {
                            'verified': chain_result.get('chain_verified', False),
                            'valid': chain_result.get('chain_valid', False),
                            'trusted_ca': chain_result.get('trusted_ca'),
                            'chain_path': chain_result.get('chain_path', [])
                        }
                        info['validation_errors'].extend(chain_result.get('validation_errors', []))
                        info['validation_warnings'].extend(chain_result.get('validation_warnings', []))
                        info['debug_info'] = chain_result.get('debug_info', [])
                        
                    except Exception as e:
                        _logger.debug(f"Error verificando cadena de firma PDF: {e}")
                        info['validation_warnings'].append(f'No se pudo verificar la cadena de confianza: {str(e)}')
                    
            except Exception as e:
                _logger.debug(f"Error extrayendo certificado del firmante: {e}")
                info['validation_errors'].append(f'Error extrayendo información del firmante: {str(e)}')
            
            # Intentar validar la firma
            try:
                # Adaptar para que `validate_pdf_signature` reciba los datos correctos
                # pyHanko espera un path o un PdfFileReader
                
                # Usamos el reader ya creado
                # La validación directa del objeto `sig` puede ser insuficiente
                # Validamos el documento completo
                
                # Obtenemos el ValidationContext para pasar CAs configuradas
                configured_cas = self._get_configured_cas()
                trusted_certs = [cert for _, cert in configured_cas]
                validation_context = ValidationContext(trust_roots=trusted_certs)
                
                # Llamar a validate_pdf_signature con el PdfFileReader y el contexto
                status = validate_pdf_signature(sig, reader=reader, validation_context=validation_context)
                
                info['valid'] = status.intact and status.valid
                info['intact'] = status.intact
                info['signature_valid'] = status.valid
                
                if hasattr(status, 'timestamp') and status.timestamp:
                    info['timestamp'] = status.timestamp.strftime('%d/%m/%Y %H:%M:%S')
                
                if not status.intact:
                    info['validation_errors'].append('El documento ha sido modificado después de firmarse.')
                
                if not status.valid:
                    info['validation_errors'].append('La firma criptográfica no es válida.')
                    
            except PathValidationError as e:
                info['valid'] = False
                info['validation_errors'].append(f'Error validando la cadena de certificados: {str(e)}')
            except PathBuildingError as e:
                info['valid'] = False
                info['validation_errors'].append(f'No se pudo construir la cadena de certificados: {str(e)}')
            except CMSExtractionError as e:
                info['valid'] = False
                info['validation_errors'].append(f'Error al extraer la firma CMS: {str(e)}')
            except Exception as e:
                _logger.debug(f"Error en validación pyHanko: {e}")
                # Si falla la validación de pyhanko pero tenemos info del cert, 
                # marcar como firma presente pero no verificada completamente
                if info['signer']:
                    info['validation_warnings'].append(f'Validación parcial: {str(e)}')
                else:
                    info['validation_errors'].append(f'Error de validación: {str(e)}')
            
            # Determinar validez final considerando cadena de confianza
            has_cas = len(self._get_configured_cas()) > 0
            if has_cas:
                chain_valid = info['chain_validation'].get('valid', False)
                # La firma es válida si la verificación de pyHanko es válida Y la cadena de confianza es válida
                info['valid'] = info.get('valid', False) and chain_valid
            else:
                # Si no hay CAs configuradas, solo consideramos la validez intrínseca de la firma
                info['valid'] = info.get('valid', False)
            
        except Exception as e:
            _logger.exception("Error procesando firma")
            info['validation_errors'].append(f'Error procesando la firma: {str(e)}')
        
        return info
    
    def _validate_pdf_basic(self, pdf_data):
        """Validación básica de PDF sin pyHanko."""
        try:
            pdf_content = pdf_data.decode('latin-1')
            
            has_sig_field = '/Sig' in pdf_content or '/Type /Sig' in pdf_content
            has_pkcs7 = 'pkcs7' in pdf_content.lower() or '/SubFilter' in pdf_content
            
            if has_sig_field or has_pkcs7:
                return {
                    'success': True,
                    'has_signatures': True,
                    'message': 'El documento parece contener firmas digitales, pero se requiere el módulo pyHanko para validación completa.',
                    'signatures': [],
                    'validation_warnings': ['Instale pyHanko para validación detallada de firmas PDF.']
                }
            else:
                return {
                    'success': True,
                    'has_signatures': False,
                    'message': 'El documento PDF no parece contener firmas digitales.',
                    'signatures': []
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Error analizando el PDF: {str(e)}',
                'validation_errors': [f'No se pudo analizar el documento: {str(e)}']
            }
