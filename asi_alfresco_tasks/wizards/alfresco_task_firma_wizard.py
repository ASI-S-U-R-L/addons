# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import tempfile
import os
import logging
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import json
import requests

_logger = logging.getLogger(__name__)

# Importaciones para firma digital
try:
    from endesive import pdf
    from cryptography.hazmat.primitives.serialization import pkcs12
    HAS_ENDESIVE = True
except ImportError:
    HAS_ENDESIVE = False
    _logger.warning("La biblioteca 'endesive' no está instalada. La funcionalidad de firma no estará disponible.")

# Verificar PyPDF
try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False
    _logger.warning("La biblioteca 'pypdf' no está instalada. La funcionalidad de firma no estará disponible.")


class AlfrescoTaskFirmaWizard(models.TransientModel):
    _name = 'alfresco.task.firma.wizard'
    _description = 'Asistente para Firma Digital de Documentos de Tareas Alfresco'

    # =========================================================================
    # CAMPOS DEL WIZARD
    # =========================================================================
    
    # Relación con la tarea
    task_id = fields.Many2one(
        'alfresco.task',
        string='Tarea Alfresco',
        required=True,
        readonly=True,
    )
    
    # Documentos de la tarea
    document_ids = fields.Many2many(
        'alfresco.task.document',
        string='Documentos a Firmar',
        readonly=True,
    )
    
    document_count = fields.Integer(
        string='Cantidad de Documentos',
        compute='_compute_document_count',
        store=True,
    )
    
    # Campos específicos para la firma
    signature_role = fields.Many2one(
        'document.signature.tag',
        string='Rol para la Firma',
        help='Rol con el que se desea firmar (ej: Aprobado por:, Contabilizado por:, etc.)',
        required=True,
        default=lambda self: self._get_default_signature_role(),
    )
    
    signature_password = fields.Char(
        string='Contraseña del Certificado',
        help='Contraseña del archivo PKCS#12 (.p12)',
    )
    
    signature_position = fields.Selection([
        ('izquierda', 'Izquierda'),
        ('centro_izquierda', 'Centro-Izquierda'),
        ('centro_derecha', 'Centro-Derecha'),
        ('derecha', 'Derecha')
    ],
        string='Posición de la Firma',
        required=True,
        default='derecha',
        help='Posición en la parte inferior de la página donde se colocará la firma',
    )
    
    # Campos temporales para certificado e imagen
    certificate_wizard = fields.Binary(
        string='Certificado (.p12) - Temporal',
        attachment=False,
        help='Certificado temporal para esta sesión de firma',
    )
    
    certificate_wizard_name = fields.Char(
        string='Nombre del Certificado Temporal',
    )
    
    wizard_signature_image = fields.Binary(
        string='Imagen de Firma - Temporal',
        attachment=False,
        help='Imagen temporal para esta sesión de firma',
    )
    
    # Campos informativos sobre el usuario
    has_certificate = fields.Boolean(
        string='Usuario tiene certificado',
        compute='_compute_user_status',
        store=False,
    )
    
    has_password = fields.Boolean(
        string='Usuario tiene contraseña',
        compute='_compute_user_status',
        store=False,
    )
    
    has_image = fields.Boolean(
        string='Usuario tiene imagen',
        compute='_compute_user_status',
        store=False,
    )
    
    # Campos de estado del proceso
    status = fields.Selection([
        ('configuracion', 'Configuración'),
        ('procesando', 'Procesando'),
        ('completado', 'Completado'),
        ('error', 'Error')
    ],
        string='Estado',
        default='configuracion',
        required=True,
    )
    
    message_result = fields.Text(
        string='Resultado del Proceso',
        readonly=True,
    )
    
    documents_processed = fields.Integer(
        string='Documentos Procesados',
        default=0,
    )
    
    documents_with_error = fields.Integer(
        string='Documentos con Error',
        default=0,
    )
    
    signature_opaque_background = fields.Boolean(
        string='Firma con fondo opaco',
        default=False,
        help='Si está marcado, la firma tendrá fondo blanco opaco en lugar de transparente',
    )
    
    sign_all_pages = fields.Boolean(
        string='Firmar todas las páginas',
        default=False,
        help='Si está marcado, se firmará todas las páginas del documento en lugar de solo la última',
    )
    
    show_sign_button = fields.Boolean(
        string='Mostrar Botón Firmar',
        compute='_compute_show_sign_button',
        store=False,
    )
    
    has_password_error = fields.Boolean(
        string='Error de Contraseña',
        default=False,
    )
    
    documents_with_error_ids = fields.Many2many(
        'alfresco.task.document',
        'alfresco_task_firma_wizard_error_rel',
        'wizard_id',
        'document_id',
        string='Documentos con Error',
    )
    
    # =========================================================================
    # MÉTODOS COMPUTADOS
    # =========================================================================
    
    @api.depends('document_ids')
    def _compute_document_count(self):
        for wizard in self:
            wizard.document_count = len(wizard.document_ids)
    
    @api.depends('status', 'documents_with_error')
    def _compute_show_sign_button(self):
        for wizard in self:
            if wizard.status == 'completado' and wizard.documents_with_error == 0:
                wizard.show_sign_button = False
            elif wizard.status in ['completado', 'error'] and wizard.documents_with_error > 0:
                wizard.show_sign_button = True
            else:
                wizard.show_sign_button = True
    
    @api.depends()
    def _compute_user_status(self):
        """Calcula si el usuario ya tiene configuración de firma"""
        for wizard in self:
            user = wizard.env.user
            wizard.has_certificate = bool(user.certificado_firma)
            wizard.has_password = bool(user.contrasena_certificado)
            wizard.has_image = bool(user.imagen_firma)
    
    # =========================================================================
    # MÉTODOS DE CONFIGURACIÓN INICIAL
    # =========================================================================
    
    @api.model
    def default_get(self, fields_list):
        """Valores por defecto para el asistente"""
        res = super(AlfrescoTaskFirmaWizard, self).default_get(fields_list)
        
        user = self.env.user
        
        # Obtener la tarea del contexto
        active_id = self.env.context.get('active_id')
        if active_id:
            task = self.env['alfresco.task'].browse(active_id)
            if task.exists():
                res['task_id'] = task.id
                # Incluir todos los documentos de la tarea
                res['document_ids'] = [(6, 0, task.document_ids.ids)]
        
        # Verificar si el usuario ya tiene configuración
        # y pre-cargar los datos si es necesario
        if user.certificado_firma:
            res['has_certificate'] = True
            _logger.debug("Usuario tiene certificado configurado")
        else:
            res['has_certificate'] = False
        
        if user.contrasena_certificado:
            res['has_password'] = True
            _logger.debug("Usuario tiene contraseña configurada")
        else:
            res['has_password'] = False
        
        if user.imagen_firma:
            res['has_image'] = True
            _logger.debug("Usuario tiene imagen configurada")
        else:
            res['has_image'] = False
        
        return res
    
    @api.model
    def create(self, vals):
        """Sobrescribir create para asegurar que se calculen los campos computados"""
        wizard = super(AlfrescoTaskFirmaWizard, self).create(vals)
        
        # Forzar el cálculo de los campos computados
        wizard._compute_user_status()
        
        return wizard
    
    def _get_default_signature_role(self):
        """Obtiene el primer rol de firma disponible como valor por defecto"""
        signature_role = self.env['document.signature.tag'].search([], limit=1)
        return signature_role.id if signature_role else False
    
    # =========================================================================
    # MÉTODOS PARA OBTENER DATOS DE FIRMA
    # =========================================================================
    
    def _obtener_datos_firma(self):
        """Obtiene los datos de firma priorizando wizard sobre user"""
        user = self.env.user
        
        # Priorizar certificado del wizard, sino usar el del user
        certificado_data = None
        if self.certificate_wizard:
            _logger.debug("Usando certificado del wizard")
            certificado_data = base64.b64decode(self.certificate_wizard)
        elif user.certificado_firma:
            _logger.debug("Usando certificado del usuario")
            certificado_data = base64.b64decode(user.certificado_firma)
        
        if not certificado_data:
            raise UserError(_('Debe proporcionar un certificado .p12 en el wizard o tenerlo configurado en sus preferencias.'))
        
        # Priorizar imagen del wizard, sino usar la del user
        imagen_firma = None
        if self.wizard_signature_image:
            _logger.debug("Usando imagen del wizard")
            imagen_firma = self.wizard_signature_image
        elif user.imagen_firma:
            _logger.debug("Usando imagen del usuario")
            imagen_firma = user.imagen_firma
        
        if not imagen_firma:
            raise UserError(_('Debe proporcionar una imagen de firma en el wizard o tenerla configurada en sus preferencias.'))
        
        # Priorizar contraseña del wizard, sino usar la del user
        contrasena = None
        if self.signature_password and self.signature_password.strip():
            _logger.debug("Usando contraseña del wizard")
            contrasena = self.signature_password.strip()
        elif user.contrasena_certificado:
            _logger.debug("Usando contraseña del usuario")
            contrasena = user.get_contrasena_descifrada()
        
        if not contrasena:
            raise UserError(_('Debe proporcionar la contraseña del certificado.'))
        
        _logger.debug("Datos de firma obtenidos correctamente")
        return certificado_data, imagen_firma, contrasena
    
    # =========================================================================
    # MÉTODOS DE PROCESAMIENTO DE IMÁGENES
    # =========================================================================
    
    def _crear_imagen_firma_con_rol(self, imagen_firma_original, rol):
        """Crea una imagen de firma temporal con el texto del rol"""
        try:
            # Decodificar la imagen original
            imagen_data = base64.b64decode(imagen_firma_original)
            imagen = Image.open(BytesIO(imagen_data))
            
            # Convertir a RGBA si no lo está
            if imagen.mode != 'RGBA':
                imagen = imagen.convert('RGBA')
            
            # Dimensiones originales
            ancho_original, alto_original = imagen.size
            
            # Limitar ancho máximo a 300px manteniendo proporción
            max_ancho = 300
            if ancho_original > max_ancho:
                factor_escala = max_ancho / ancho_original
                nuevo_ancho_img = max_ancho
                nuevo_alto_img = int(alto_original * factor_escala)
                try:
                    # Para versiones nuevas de Pillow (>=8.0.0)
                    imagen = imagen.resize((nuevo_ancho_img, nuevo_alto_img), Image.Resampling.LANCZOS)
                except AttributeError:
                    # Para versiones antiguas de Pillow
                    imagen = imagen.resize((nuevo_ancho_img, nuevo_alto_img), Image.LANCZOS)
                ancho_original, alto_original = nuevo_ancho_img, nuevo_alto_img
            
            # Calcular nuevo alto (agregar espacio para el texto)
            try:
                # Intentar cargar una fuente del sistema
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
            except:
                try:
                    # Fuente alternativa
                    font = ImageFont.truetype("arial.ttf", 10)
                except:
                    # Fuente por defecto
                    font = ImageFont.load_default()
            
            # Texto a agregar
            texto = f"{rol}"
            
            # Calcular dimensiones del texto
            draw_temp = ImageDraw.Draw(imagen)
            bbox = draw_temp.textbbox((0, 0), texto, font=font)
            ancho_texto = bbox[2] - bbox[0]
            alto_texto = bbox[3] - bbox[1]
            
            if texto:
                # Crear nueva imagen con espacio adicional arriba
                margen_texto = 10
                nuevo_alto = alto_original + alto_texto + (margen_texto * 2)
                nuevo_ancho = max(ancho_original, ancho_texto + 20)
                
                if self.signature_opaque_background:
                    # Crear imagen nueva con fondo blanco opaco
                    nueva_imagen = Image.new('RGBA', (nuevo_ancho, nuevo_alto), (255, 255, 255, 255))
                else:
                    # Crear imagen nueva con fondo transparente (comportamiento original)
                    nueva_imagen = Image.new('RGBA', (nuevo_ancho, nuevo_alto), (255, 255, 255, 0))
                
                # Pegar el texto en la parte superior
                draw = ImageDraw.Draw(nueva_imagen)
                x_texto = (nuevo_ancho - ancho_texto) // 2  # Centrar texto
                y_texto = margen_texto
                draw.text((x_texto, y_texto), texto, fill=(0, 0, 0, 255), font=font)
                
                # Pegar la imagen original debajo del texto
                x_imagen = (nuevo_ancho - ancho_original) // 2  # Centrar imagen
                y_imagen = alto_texto + (margen_texto * 2)
                
                if self.signature_opaque_background:
                    # Crear una copia de la imagen original con fondo blanco
                    imagen_con_fondo = Image.new('RGBA', imagen.size, (255, 255, 255, 255))
                    imagen_con_fondo.paste(imagen, (0, 0), imagen if imagen.mode == 'RGBA' else None)
                    nueva_imagen.paste(imagen_con_fondo, (x_imagen, y_imagen))
                else:
                    # Comportamiento original con transparencia
                    nueva_imagen.paste(imagen, (x_imagen, y_imagen), imagen if imagen.mode == 'RGBA' else None)
            else:
                if self.signature_opaque_background:
                    # Crear imagen con fondo blanco opaco
                    nueva_imagen = Image.new('RGBA', imagen.size, (255, 255, 255, 255))
                    nueva_imagen.paste(imagen, (0, 0), imagen if imagen.mode == 'RGBA' else None)
                else:
                    nueva_imagen = imagen
            
            # Guardar en archivo temporal
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            nueva_imagen.save(temp_file, format='PNG')
            temp_file.close()
            
            return temp_file.name, nueva_imagen.size
            
        except Exception as e:
            _logger.error(f"Error creando imagen de firma con rol: {e}")
            raise UserError(_('Error al procesar la imagen de firma: %s') % str(e))
    
    def _calcular_coordenadas_firma(self, page_width, page_height, imagen_width, imagen_height, posicion):
        """Calcula las coordenadas de la firma según la posición seleccionada"""
        margen_inferior = 25
        margen_lateral = 13
        separacion = 5
        ancho = page_width / 4 - 20
        y = margen_inferior
        
        # Calcular nueva altura de imagen
        escala = min(ancho, imagen_width) / max(ancho, imagen_width)
        alto = imagen_height * escala   
        y1 = y + alto 
        
        # Calcular coordenada X según la posición
        xi = margen_lateral
        x1i = xi + ancho
        
        xci = x1i + xi + separacion
        x1ci = xci + ancho
        
        xcd = x1ci + xi + separacion
        x1cd = xcd + ancho
        
        xd = x1cd + xi + separacion
        x1d = xd + ancho
        
        if posicion == 'izquierda':
            x = xi
            x1 = x1i
        elif posicion == 'centro_izquierda':
            x = xci
            x1 = x1ci
        elif posicion == 'centro_derecha':
            x = xcd
            x1 = x1cd
        else:  # derecha
            x = xd
            x1 = x1d
        
        return x, y, x1, y1
    
    # =========================================================================
    # MÉTODO PRINCIPAL DE FIRMA
    # =========================================================================
    
    def action_firmar_documentos(self):
        """Acción principal para firmar todos los documentos seleccionados"""
        self.ensure_one()
        
        _logger.info("Iniciando proceso de firma para tarea: %s", self.task_id.alfresco_task_id)
        
        # Validar bibliotecas necesarias
        if not HAS_ENDESIVE or not HAS_PYPDF:
            self.write({
                'status': 'error',
                'message_result': _('Las bibliotecas necesarias no están instaladas. Por favor, instale "endesive" y "pypdf".')
            })
            return self._recargar_wizard()
        
        # Validar campos obligatorios
        if not self.document_ids:
            raise UserError(_('No hay documentos para firmar.'))
        
        if not self.signature_role:
            raise UserError(_('Debe especificar el rol para la firma.'))
        
        # Determinar qué documentos procesar
        if self.status in ['completado', 'error'] and self.documents_with_error > 0:
            # Solo procesar documentos que tuvieron error
            documentos_a_procesar = self.documents_with_error_ids
            # Limpiar la lista de documentos con error para el nuevo intento
            self.documents_with_error_ids = [(5, 0, 0)]
        else:
            # Procesar todos los documentos
            documentos_a_procesar = self.document_ids
            # Limpiar la lista de documentos con error
            self.documents_with_error_ids = [(5, 0, 0)]
        
        # Cambiar status a procesando
        self.write({
            'status': 'procesando',
            'message_result': 'Iniciando proceso de firma...',
            'documents_processed': 0,
            'documents_with_error': 0,
            'has_password_error': False,
        })
        
        documents_processed = 0
        documents_with_error = 0
        errores_detalle = []
        documentos_con_error = []
        
        try:
            # Obtener datos de firma (prioriza wizard sobre user)
            certificado_data, imagen_firma, contrasena = self._obtener_datos_firma()
            
            # Crear imagen de firma con rol usando los datos obtenidos
            imagen_firma_path, imagen_size = self._crear_imagen_firma_con_rol(
                imagen_firma, 
                self.signature_role.name,
            )
            imagen_width, imagen_height = imagen_size
            
            try:
                # Cargar el certificado PKCS12
                private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                    certificado_data, 
                    contrasena.encode('utf-8')
                )
                
            except ValueError as e:
                error_msg = str(e)
                if "Invalid password or PKCS12 data" in error_msg:
                    self.write({
                        'has_password_error': True,
                        'signature_password': '',  # Limpiar contraseña
                        'status': 'configuracion'  # Volver al estado de configuración
                    })
                    # Limpiar archivo temporal
                    try:
                        os.unlink(imagen_firma_path)
                    except:
                        pass
                    # Mostrar notificación
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Error de Contraseña'),
                            'message': _('La contraseña del certificado PKCS#12 es incorrecta. Por favor, ingrese la contraseña correcta.'),
                            'type': 'warning',
                            'sticky': False,
                        }
                    }
                else:
                    raise Exception(f"Error cargando certificado PKCS#12: {error_msg}")
            
            # Procesar cada documento
            for documento in documentos_a_procesar:
                try:
                    self._firmar_documento_individual(
                        documento, imagen_firma_path, imagen_width, imagen_height,
                        private_key, certificate, additional_certificates
                    )
                    documents_processed += 1
                    
                    # Actualizar progreso
                    self.write({
                        'documents_processed': documents_processed,
                        'message_result': f'Procesando... {documents_processed}/{len(documentos_a_procesar)} documentos completados'
                    })
                    
                except Exception as e:
                    documents_with_error += 1
                    documentos_con_error.append(documento.id)  # Guardar ID del documento con error
                    error_msg = f"Error en {documento.name}: {str(e)}"
                    errores_detalle.append(error_msg)
                    _logger.error(f"Error firmando documento {documento.name}: {e}")
            
            if documentos_con_error:
                self.documents_with_error_ids = [(6, 0, documentos_con_error)]
            
            # Limpiar archivo temporal
            try:
                os.unlink(imagen_firma_path)
            except:
                pass
            
            # Preparar mensaje final
            if documents_with_error == 0:
                mensaje = f'✅ Proceso completado exitosamente!\n\n'
                mensaje += f'📄 {documents_processed} documentos firmados correctamente\n'
                mensaje += 'Los documentos han sido actualizados con una nueva versión firmada en Alfresco'
                estado_final = 'completado'
                
                # Actualizar la tarea en Alfresco a "completed"
                self._actualizar_tarea_completada()
                
            else:
                mensaje = f'⚠️ Proceso completado con errores:\n\n'
                mensaje += f'✅ {documents_processed} documentos firmados correctamente\n'
                mensaje += f'❌ {documents_with_error} documentos con errores\n\n'
                mensaje += 'Errores detallados:\n' + '\n'.join(errores_detalle)
                estado_final = 'error'
            
            self.write({
                'status': estado_final,
                'message_result': mensaje,
                'documents_processed': documents_processed,
                'documents_with_error': documents_with_error,
            })
            
        except Exception as e:
            # Limpiar archivo temporal en caso de error
            try:
                os.unlink(imagen_firma_path)
            except:
                pass
            raise e
        
        return self._recargar_wizard()
    
    def _firmar_documento_individual(self, documento, imagen_firma_path, imagen_width, imagen_height,
                                   private_key, certificate, additional_certificates):
        """Firma un documento individual y lo sube a Alfresco como nueva versión"""
        # Obtener configuración de Alfresco
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')
        
        if not all([url, user, pwd]):
            raise UserError(_('Configuración de Alfresco incompleta'))
        
        # Descargar el documento desde Alfresco
        download_url = f"{url.rstrip('/')}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{documento.node_id}/content"
        
        _logger.debug(
            "Descargando documento para firma: %s desde: %s",
            documento.name,
            download_url,
        )
        
        response = requests.get(download_url, auth=(user, pwd), timeout=30)
        response.raise_for_status()
        
        pdf_contenido = response.content
        
        # Crear archivo temporal para el PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            temp_pdf.write(pdf_contenido)
            temp_pdf_path = temp_pdf.name
        
        try:
            # Leer PDF para obtener dimensiones
            with open(temp_pdf_path, 'rb') as f:
                pdf_reader = PdfReader(f)
                num_paginas = len(pdf_reader.pages)
                last_page = pdf_reader.pages[-1]
                
                # Obtener dimensiones de la página
                if hasattr(last_page, 'mediabox') and last_page.mediabox:
                    page_width = float(last_page.mediabox.width)
                    page_height = float(last_page.mediabox.height)
                else:
                    from reportlab.lib.pagesizes import letter
                    page_width, page_height = letter
            
            # Calcular coordenadas según posición seleccionada
            x, y, x1, y1 = self._calcular_coordenadas_firma(
                page_width, page_height, imagen_width, imagen_height, self.signature_position
            )
            
            # Datos para la firma digital
            date = datetime.now()
            date_str = date.strftime("D:%Y%m%d%H%M%S+00'00'")
            
            if self.sign_all_pages:
                # Firmar todas las páginas
                paginas_a_firmar = list(range(num_paginas))
                _logger.info(f"Firmando todas las páginas del documento: {num_paginas} páginas")
            else:
                # Firmar solo la última página (comportamiento original)
                paginas_a_firmar = [num_paginas - 1]
                _logger.info(f"Firmando solo la última página del documento: página {num_paginas}")
            
            datau = None
            with open(temp_pdf_path, 'rb') as f:
                datau = f.read()
            
            # Procesar cada página a firmar
            for pagina_num in paginas_a_firmar:
                dct = {
                    "aligned": 0,
                    "sigflags": 3,
                    "sigflagsft": 132,
                    "sigpage": pagina_num,
                    "sigbutton": True,
                    "sigfield": f"Signature_{documento.id}_{pagina_num}",
                    "auto_sigfield": True,
                    "sigandcertify": True,
                    "signaturebox": (x, y, x1, y1),
                    "signature_img": imagen_firma_path,
                    "contact": self.env.user.email or '',
                    "location": self.env.user.company_id.city or '',
                    "signingdate": date_str,
                    "reason": f"Firma Digital - {self.signature_role.name}",
                }
                
                # Firmar digitalmente
                datas = pdf.cms.sign(
                    datau,
                    dct,
                    private_key,
                    certificate,
                    additional_certificates,
                    'sha256'
                )
                
                # Actualizar datau con la firma aplicada para la siguiente iteración
                datau = datau + datas
            
            # Crear PDF firmado
            with tempfile.NamedTemporaryFile(delete=False, suffix='_firmado.pdf') as temp_final:
                temp_final.write(datau)
                temp_final_path = temp_final.name
            
            # Leer PDF firmado
            with open(temp_final_path, 'rb') as f:
                pdf_firmado_contenido = f.read()
            
            # Actualizar el documento original con la versión firmada en Alfresco
            self._actualizar_version_firmada_alfresco(documento, pdf_firmado_contenido)
            
            # Limpiar archivos temporales
            for path in [temp_pdf_path, temp_final_path]:
                try:
                    os.unlink(path)
                except:
                    pass
                    
        except Exception as e:
            # Limpiar archivo temporal en caso de error
            try:
                os.unlink(temp_pdf_path)
            except:
                pass
            raise e
    
    def _actualizar_version_firmada_alfresco(self, documento, pdf_firmado_contenido):
        """
        Actualiza el documento en Alfresco con la versión firmada,
        creando una nueva versión del mismo documento
        """
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')
        
        # Actualizar el documento en Alfresco
        update_url = f"{url.rstrip('/')}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{documento.node_id}/content"
        
        _logger.debug(
            "Actualizando documento firmado en Alfresco: %s",
            documento.name,
        )
        
        try:
            response = requests.put(
                update_url,
                headers={"Content-Type": "application/pdf"},
                data=pdf_firmado_contenido,
                auth=(user, pwd),
                timeout=30
            )
            response.raise_for_status()
            
            _logger.info(
                "Documento %s actualizado con versión firmada en Alfresco",
                documento.name,
            )
            
        except requests.exceptions.RequestException as e:
            _logger.error(
                "Error actualizando documento firmado en Alfresco: %s",
                str(e),
            )
            raise UserError(_('Error actualizando el documento firmado en Alfresco: %s') % str(e))
    
    def _actualizar_tarea_completada(self):
        """
        Actualiza el estado de la tarea en Alfresco a 'completed'
        Solo si todos los documentos fueron firmados exitosamente
        """
        task = self.task_id
        
        # Verificar que la tarea no esté ya completada
        if task.is_completed or task.state == 'completed':
            _logger.debug("La tarea ya está completada, no se actualiza")
            return
        
        # Obtener configuración de Alfresco
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('asi_alfresco_integration.alfresco_server_url')
        user = config.get_param('asi_alfresco_integration.alfresco_username')
        pwd = config.get_param('asi_alfresco_integration.alfresco_password')
        
        if not all([url, user, pwd]):
            _logger.warning("Configuración de Alfresco incompleta para actualizar tarea")
            return
        
        # Endpoint para actualizar el estado de la tarea
        task_endpoint = f"{url.rstrip('/')}/alfresco/api/-default-/public/workflow/versions/1/tasks/{task.alfresco_task_id}?select=state"
        
        _logger.debug(
            "Actualizando estado de tarea %s a 'completed' en Alfresco",
            task.alfresco_task_id,
        )
        
        try:
            response = requests.put(
                task_endpoint,
                auth=(user, pwd),
                json={"state": "completed"},
                timeout=30,
                allow_redirects=False,
            )
            
            _logger.debug(
                "Respuesta de actualización de tarea - Código: %d",
                response.status_code,
            )
            
            if response.status_code in [200, 201]:
                # Actualizar el estado de la tarea en Odoo
                task.write({
                    'state': 'completed',
                    'is_completed': True,
                })
                
                # Marcar actividades como realizadas
                task._mark_activities_done()
                
                _logger.info(
                    "Tarea %s marcada como completada en Alfresco",
                    task.alfresco_task_id,
                )
            else:
                _logger.error(
                    "Error al actualizar tarea %s. Código: %d, Respuesta: %s",
                    task.alfresco_task_id,
                    response.status_code,
                    response.text,
                )
                
        except requests.exceptions.RequestException as e:
            _logger.error(
                "Error de conexión al actualizar tarea %s: %s",
                task.alfresco_task_id,
                str(e),
            )
    
    # =========================================================================
    # MÉTODOS AUXILIARES
    # =========================================================================
    
    def _recargar_wizard(self):
        """Método auxiliar para recargar el wizard"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'alfresco.task.firma.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
            'flags': {'mode': 'edit'},
        }
    
    def action_cerrar_wizard(self):
        """Cerrar el wizard y refrescar la vista de la tarea"""
        return {
            'type': 'ir.actions.act_window_close',
        }