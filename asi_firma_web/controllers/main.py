
# -*- coding: utf-8 -*-
import logging
from odoo import http, _
from odoo.http import request
import base64
from werkzeug.utils import secure_filename
import urllib.parse
from io import BytesIO
import zipfile
import datetime
import os
_logger = logging.getLogger(__name__)
class FirmaWebController(http.Controller):

    @http.route(['/firmar-documentos'], type='http', auth='user', website=True)
    def form_page(self, **kw):
        try:
            # Obtener etiquetas existentes
            Tag = request.env['document.signature.tag']
            tags = Tag.search([])
            _logger.info(f"Etiquetas de firma encontradas: {len(tags)}")
            # Crear etiquetas por defecto solo si no existen
            if not tags:
                default_tags = [
                    {'name': 'Aprobado por'},
                    {'name': 'Autorizado por'},
                    {'name': 'Elaborado por'},
                    {'name': 'Solicitado por'}
                ]
                for tag_data in default_tags:
                    Tag.create(tag_data)
                tags = Tag.search([])  # Re-obtener después de crear
            
            return request.render('asi_firma_web.firma_form_page', {
                'tags': tags, 
                'message': kw.get('msg')
            })
            
        except Exception as e:
            # Manejo de errores
            return request.render('asi_firma_web.firma_form_page', {
                'tags': [],
                'message': f'Error al cargar el formulario: {str(e)}'
            })

    @http.route(['/firmar-documentos/enviar'], type='http', auth='user', website=True, csrf=False, methods=['POST'])
    def submit(self, **post):
        files = request.httprequest.files
        pdf_files = files.getlist('pdfs')
        if not pdf_files:
            return request.redirect('/firmar-documentos?msg=' + urllib.parse.quote(_('Debes adjuntar al menos un PDF.')))
        # Crear wizard
        vals = {}
        # Campos simples
        vals['signature_position'] = post.get('signature_position') or 'derecha'
        if post.get('signature_role'):
            try:
                vals['signature_role'] = int(post.get('signature_role'))
            except:
                pass
        if post.get('signature_password'):
            vals['signature_password'] = post.get('signature_password')
        if post.get('signature_opaque_background'):
            vals['signature_opaque_background'] = True
        if post.get('sign_all_pages'):
            vals['sign_all_pages'] = True

        # Certificado
        cert = files.get('certificate_wizard')
        if cert and cert.filename:
            vals['certificate_wizard_name'] = secure_filename(cert.filename)
            vals['certificate_wizard'] = base64.b64encode(cert.read())
        # Imagen
        img = files.get('wizard_signature_image')
        if img and img.filename:
            vals['wizard_signature_image'] = base64.b64encode(img.read())

        wizard = request.env['firma.documento.wizard'].create(vals)
        _logger.info(f"Wizard creado: {wizard.id}, vals: {vals}")

        # Crear líneas por cada PDF
        Documento = request.env['documento.firma']
        for f in pdf_files:
            if not f.filename:
                continue
            name = secure_filename(f.filename)
            data = base64.b64encode(f.read())
            doc = Documento.create({
                'wizard_id': wizard.id,
                'document_name': name,
                'pdf_document': data,
            })
            _logger.info(f"Documento creado: {doc.id}, name: {name}")

        # Ejecutar firma
        try:
            _logger.info(f"Llamando action_firmar_documentos para wizard {wizard.id}")
            wizard.action_firmar_documentos()
            _logger.info(f"Después de firma, status: {wizard.status}, documents_processed: {wizard.documents_processed}")
        except Exception as e:
            _logger.error(f"Error en firma: {e}")
            return request.redirect('/firmar-documentos?msg=' + urllib.parse.quote(_('Error en firma: %s') % (str(e)[:80])))

        # Preparar respuesta: si hay ZIP usarlo; si no, si hay un único PDF firmado, devolverlo
        if wizard.zip_signed:
            fname = wizard.zip_name or 'documentos_firmados_%s.zip' % datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            data = base64.b64decode(wizard.zip_signed)
            headers=[('Content-Type','application/zip'),
                     ('Content-Disposition','attachment; filename="%s"' % fname)]
            return request.make_response(data, headers)
        else:
            # buscar firmados individuales
            signed_lines = wizard.document_ids.filtered(lambda d: d.signature_status=='firmado' and d.pdf_signed)
            if len(signed_lines)==1:
                ln = signed_lines[0]
                data = base64.b64decode(ln.pdf_signed)
                # Construir nombre como en el ZIP
                nombre_base, extension = os.path.splitext(ln.document_name or 'documento.pdf')
                if not extension:
                    extension = '.pdf'
                filename = f"{nombre_base} - firmado{extension}"
                headers=[('Content-Type','application/pdf'),
                          ('Content-Disposition','attachment; filename="%s"' % filename)]
                return request.make_response(data, headers)
            elif len(signed_lines)>1:
                # construir zip en memoria
                mem = BytesIO()
                with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for ln in signed_lines:
                        zf.writestr(ln.document_name or 'documento.pdf', base64.b64decode(ln.pdf_signed))
                data = mem.getvalue()
                headers=[('Content-Type','application/zip'),
                         ('Content-Disposition','attachment; filename="documentos_firmados.zip"')]
                return request.make_response(data, headers)
        return request.redirect('/firmar-documentos?msg=' + urllib.parse.quote(_('No se generaron archivos firmados.')))
