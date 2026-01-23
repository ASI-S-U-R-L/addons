# -*- coding: utf-8 -*-

import base64
import datetime
import logging
import os
import urllib.parse
import zipfile
from io import BytesIO

from odoo import http, _
from odoo.http import request
from werkzeug.utils import secure_filename

_logger = logging.getLogger(__name__)


def _b64_to_str(value):
    """Normalize binary/base64 values to a base64 *string* (for JSON and data URIs)."""
    if not value:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            return bytes(value).decode('utf-8')
        except Exception:
            return base64.b64encode(bytes(value)).decode('utf-8')
    return str(value)


def _b64_to_bytes(value):
    """Normalize base64 values to bytes for writing into Odoo binary fields."""
    if not value:
        return False
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode('utf-8')
    return False


def _fetch_alfresco_content(alfresco_file):
    """Best-effort fetch for Alfresco content."""
    if not alfresco_file:
        return None
    # In many deployments, recipients don't have direct read access to alfresco.file.
    # We already validate the document belongs to the workflow and the user is a recipient,
    # so using sudo() here is an acceptable tradeoff for preview/download fetch.
    alfresco_file = alfresco_file.sudo()

    # 1) Try known helper methods
    for meth in ('download_file_content', 'get_file_content', 'get_content', 'download_content'):
        if hasattr(alfresco_file, meth):
            try:
                content = getattr(alfresco_file, meth)()

                # Some implementations may return a requests.Response
                if hasattr(content, 'content') and isinstance(getattr(content, 'content', None), (bytes, bytearray)):
                    return content.content

                # Some implementations may return a dict
                if isinstance(content, dict):
                    for k in ('content', 'data', 'file', 'file_content', 'pdf'):
                        if k in content and content[k]:
                            content = content[k]
                            break

                if isinstance(content, (bytes, bytearray)):
                    return bytes(content)

                # Some implementations may return base64 string
                if isinstance(content, str):
                    # Could already be base64 or a text response. Try best-effort base64 decode.
                    try:
                        decoded = base64.b64decode(content)
                        if decoded.startswith(b'%PDF'):
                            return decoded
                    except Exception:
                        pass

                return None
            except Exception:
                _logger.exception('Error obteniendo contenido de Alfresco con %s', meth)

    # 2) Fallback: try common binary fields if present
    for field_name in ('content', 'file_content', 'binary_content', 'data', 'pdf_content'):
        try:
            if field_name in alfresco_file._fields and getattr(alfresco_file, field_name):
                val = getattr(alfresco_file, field_name)
                if isinstance(val, str):
                    try:
                        decoded = base64.b64decode(val)
                        return decoded
                    except Exception:
                        return None
                if isinstance(val, (bytes, bytearray)):
                    return bytes(val)
        except Exception:
            # ignore and keep trying
            continue

    # 3) Last resort: fetch directly from Alfresco using the node id (same approach used in
    # asi_signature_workflow download controller).
    try:
        node_id = None
        for node_field in ('alfresco_node_id', 'alfresco_nodeid', 'node_id'):
            if node_field in alfresco_file._fields and getattr(alfresco_file, node_field):
                node_id = getattr(alfresco_file, node_field)
                break

        if node_id:
            config = request.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            if url and user and pwd:
                import requests
                download_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}/content"
                resp = requests.get(download_url, auth=(user, pwd), timeout=30)
                if resp.status_code == 200 and resp.content:
                    return resp.content
                _logger.warning('No se pudo descargar contenido desde Alfresco (HTTP %s) para node %s', resp.status_code, node_id)
    except Exception:
        _logger.exception('Error obteniendo contenido directamente desde Alfresco')

    return None


def _get_workflow_for_user_recipient(workflow_id):
    """Return workflow if current user is a recipient and workflow is pending (sent)."""
    user = request.env.user
    Workflow = request.env['signature.workflow']
    return Workflow.search([
        ('id', '=', workflow_id),
        ('state', '=', 'sent'),
        '|', '|', '|',
        ('target_user_id_1', '=', user.id),
        ('target_user_id_2', '=', user.id),
        ('target_user_id_3', '=', user.id),
        ('target_user_id_4', '=', user.id),
    ], limit=1)


def _user_missing_signature_profile_fields(user):
    """Return list of missing profile fields required to sign."""
    missing = []
    if not getattr(user, 'certificado_firma', False):
        missing.append('certificado_firma')
    if not getattr(user, 'imagen_firma', False):
        missing.append('imagen_firma')
    if not getattr(user, 'contrasena_certificado', False):
        missing.append('contrasena_certificado')
    return missing


class FirmaWebController(http.Controller):

    # ------------------------------------------------------------
    # APIs (website split view)
    # ------------------------------------------------------------

    @http.route(['/api/workflow-data/<int:workflow_id>'], type='http', auth='user', methods=['GET'])
    def get_workflow_data(self, workflow_id, **kw):
        """API para el split-view: devuelve preview + permisos/turno + config (solo lectura)."""
        try:
            workflow = _get_workflow_for_user_recipient(workflow_id)
            if not workflow:
                return request.make_json_response({'success': False, 'error': 'Solicitud no encontrada o sin acceso.'})

            recipient_data = workflow._get_current_user_recipient_data() if hasattr(workflow, '_get_current_user_recipient_data') else None
            can_sign = False
            already_signed = False
            is_turn = False
            reason = None
            signature_role_id = None
            signature_position = None

            if not recipient_data:
                reason = 'No eres destinatario de esta solicitud.'
            else:
                already_signed = bool(recipient_data.get('signed'))
                role = recipient_data.get('role')
                signature_role_id = role.id if role else None
                signature_position = recipient_data.get('position')

                if already_signed:
                    reason = 'Ya firmaste esta solicitud.'
                else:
                    is_turn = bool(workflow._is_user_current_recipient()) if hasattr(workflow, '_is_user_current_recipient') else True
                    if not is_turn:
                        current = workflow._get_current_active_recipient() if hasattr(workflow, '_get_current_active_recipient') else None
                        if current and current.get('user'):
                            reason = f"No es tu turno. Turno actual: {current['user'].name}"
                        else:
                            reason = 'No es tu turno de firmar.'
                    else:
                        can_sign = True

            # Documentos disponibles (metadata) + preview del primer documento
            documents = []
            document_data = None
            document_name = None
            document_id = None
            if workflow.document_ids:
                for d in workflow.document_ids:
                    documents.append({
                        'id': d.id,
                        'name': d.name,
                        'is_signed': bool(getattr(d, 'is_signed', False)),
                        'has_alfresco': bool(getattr(d, 'alfresco_file_id', False)),
                    })

                first_doc = workflow.document_ids[0]
                document_id = first_doc.id
                document_name = first_doc.name
                if first_doc.pdf_content:
                    document_data = _b64_to_str(first_doc.pdf_content)
                elif getattr(first_doc, 'alfresco_file_id', False):
                    content = _fetch_alfresco_content(first_doc.alfresco_file_id)
                    if content:
                        document_data = base64.b64encode(content).decode('utf-8')
                        document_name = first_doc.alfresco_file_id.name or document_name

            user = request.env.user
            missing_profile_fields = _user_missing_signature_profile_fields(user)
            return request.make_json_response({
                'success': True,
                'workflow_id': workflow_id,
                'workflow_name': workflow.name,
                'document_id': document_id,
                'document_name': document_name,
                'document_data': document_data,
                # Compatibilidad (legacy)
                'document_names': [d.name for d in workflow.document_ids],
                # Nuevo: lista de documentos para selector en UI
                'documents': documents,
                'signature_role_id': signature_role_id,
                'signature_position': signature_position,
                'signature_opaque_background': bool(getattr(workflow, 'signature_opaque_background', False)),
                'sign_all_pages': bool(getattr(workflow, 'sign_all_pages', False)),
                'user_has_certificado': bool(user.certificado_firma),
                'user_has_imagen': bool(user.imagen_firma),
                'user_has_password': bool(user.contrasena_certificado),
                'profile_complete': not missing_profile_fields,
                'missing_profile_fields': missing_profile_fields,
                'can_sign': can_sign,
                'already_signed': already_signed,
                'is_turn': is_turn,
                'reason': reason,
            })
        except Exception as e:
            _logger.exception('Error obteniendo datos del workflow')
            return request.make_json_response({'success': False, 'error': str(e)})

    @http.route(['/api/workflow-document-preview/<int:workflow_id>/<int:document_id>'], type='http', auth='user', methods=['GET'])
    def get_workflow_document_preview(self, workflow_id, document_id, **kw):
        """Devuelve el base64 del PDF del documento seleccionado (para previsualización)."""
        try:
            workflow = _get_workflow_for_user_recipient(workflow_id)
            if not workflow:
                return request.make_json_response({'success': False, 'error': 'Solicitud no encontrada o sin acceso.'})

            doc = workflow.document_ids.filtered(lambda d: d.id == document_id)
            if not doc:
                return request.make_json_response({'success': False, 'error': 'Documento no encontrado en la solicitud.'})

            doc = doc[0]
            pdf_b64 = None
            name = doc.name

            if doc.pdf_content:
                pdf_b64 = _b64_to_str(doc.pdf_content)
            elif getattr(doc, 'alfresco_file_id', False):
                content = _fetch_alfresco_content(doc.alfresco_file_id)
                if content:
                    pdf_b64 = base64.b64encode(content).decode('utf-8')
                    name = doc.alfresco_file_id.name or name

            preview_url = None
            if not pdf_b64 and getattr(doc, 'alfresco_file_id', False):
                preview_url = f"/alfresco/file/{doc.alfresco_file_id.id}/download"

            if not pdf_b64 and not preview_url:
                return request.make_json_response({'success': False, 'error': 'No se pudo obtener el contenido del documento.'})

            return request.make_json_response({
                'success': True,
                'workflow_id': workflow_id,
                'document_id': doc.id,
                'document_name': name,
                'document_data': pdf_b64,
                'preview_url': preview_url,
            })
        except Exception as e:
            _logger.exception('Error obteniendo preview del documento')
            return request.make_json_response({'success': False, 'error': str(e)})

    @http.route(['/api/workflow-sign/<int:workflow_id>'], type='http', auth='user', website=True, methods=['POST'])
    def sign_workflow_ajax(self, workflow_id, **post):
        """Firma documentos del workflow desde la bandeja (AJAX).

        - Usa credenciales del perfil (res.users) si están completas.
        - Si faltan, exige que el usuario las proporcione y puede guardarlas si save_to_profile=true.
        - Prioriza alfresco.firma.wizard cuando hay documentos en Alfresco.
        """
        try:
            user = request.env.user
            workflow = _get_workflow_for_user_recipient(workflow_id)
            if not workflow:
                return request.make_json_response({'success': False, 'error': 'Solicitud no encontrada o sin acceso.'}, status=404)

            recipient_data = workflow._get_current_user_recipient_data() if hasattr(workflow, '_get_current_user_recipient_data') else None
            if not recipient_data:
                return request.make_json_response({'success': False, 'error': 'No eres destinatario de esta solicitud.'}, status=403)
            if recipient_data.get('signed'):
                return request.make_json_response({'success': False, 'error': 'Ya firmaste esta solicitud.'}, status=400)
            if hasattr(workflow, '_is_user_current_recipient') and not workflow._is_user_current_recipient():
                current = workflow._get_current_active_recipient() if hasattr(workflow, '_get_current_active_recipient') else None
                msg = 'No es tu turno de firmar.'
                if current and current.get('user'):
                    msg = f"No es tu turno. Turno actual: {current['user'].name}"
                return request.make_json_response({'success': False, 'error': msg}, status=400)

            files = request.httprequest.files
            cert_file = files.get('certificate_wizard')
            img_file = files.get('wizard_signature_image')
            pwd = (post.get('signature_password') or '').strip()
            save_to_profile = str(post.get('save_to_profile') or '').lower() in ('true', '1', 'yes', 'on')

            missing_profile = _user_missing_signature_profile_fields(user)
            missing_needed = []
            if 'certificado_firma' in missing_profile and not (cert_file and cert_file.filename):
                missing_needed.append('certificado_firma')
            if 'imagen_firma' in missing_profile and not (img_file and img_file.filename):
                missing_needed.append('imagen_firma')
            if 'contrasena_certificado' in missing_profile and not pwd:
                missing_needed.append('contrasena_certificado')

            if missing_needed:
                return request.make_json_response({
                    'success': False,
                    'code': 'MISSING_CREDENTIALS',
                    'missing_fields': missing_needed,
                    'error': 'Faltan datos de firma. Completa los campos requeridos.'
                }, status=400)

            # Guardar en perfil si aplica (solo lo que venga en esta petición)
            if save_to_profile:
                write_vals = {}
                if cert_file and cert_file.filename:
                    cert_bytes = cert_file.read()
                    write_vals.update({
                        'certificado_firma': base64.b64encode(cert_bytes),
                        'nombre_certificado': secure_filename(cert_file.filename)
                    })
                if img_file and img_file.filename:
                    img_bytes = img_file.read()
                    write_vals.update({'imagen_firma': base64.b64encode(img_bytes)})
                if pwd:
                    write_vals.update({'contrasena_certificado': pwd})
                if write_vals:
                    user.write(write_vals)

                # IMPORTANTE: si leímos los streams para guardar, necesitamos volver a ponerlos para el wizard
                # (en caso de que el usuario no tenga perfil completo y dependamos del archivo de esta petición).
                # Re-leer desde los valores guardados si corresponde.
                if cert_file and cert_file.filename:
                    # user.certificado_firma queda disponible
                    cert_file = None
                if img_file and img_file.filename:
                    img_file = None
                if pwd:
                    # queda en user.contrasena_certificado (cifrada), pero el wizard puede usar get_contrasena_descifrada
                    pwd = ''

            role = recipient_data.get('role')
            position = recipient_data.get('position') or 'derecha'

            # Determinar si hay documentos en Alfresco (sin asumir que el módulo esté instalado)
            alfresco_files = False
            if workflow.document_ids:
                try:
                    _ = request.env['alfresco.file']
                    alfresco_files = workflow.document_ids.mapped('alfresco_file_id')
                    alfresco_files = alfresco_files.filtered(lambda f: getattr(f, 'alfresco_node_id', False) and (f.name or '').lower().endswith('.pdf'))
                except KeyError:
                    alfresco_files = False

            if alfresco_files:
                # Wizard Alfresco
                try:
                    Wizard = request.env['alfresco.firma.wizard']
                except Exception:
                    return request.make_json_response({'success': False, 'error': 'No está instalado el asistente de firma para Alfresco.'}, status=500)

                wvals = {
                    'file_ids': [(6, 0, alfresco_files.ids)],
                    'signature_role': role.id if role else False,
                    'signature_position': position,
                    'signature_opaque_background': bool(getattr(workflow, 'signature_opaque_background', False)),
                    'sign_all_pages': bool(getattr(workflow, 'sign_all_pages', False)),
                }

                # Enviar temporales SOLO si el usuario los proporciona en esta sesión.
                # Si el usuario tiene perfil completo, el wizard los toma de res.users.
                if cert_file and cert_file.filename:
                    cert_bytes = cert_file.read()
                    wvals['certificate_wizard'] = base64.b64encode(cert_bytes)
                    wvals['certificate_wizard_name'] = secure_filename(cert_file.filename)
                if img_file and img_file.filename:
                    img_bytes = img_file.read()
                    wvals['wizard_signature_image'] = base64.b64encode(img_bytes)
                if pwd:
                    wvals['signature_password'] = pwd

                # Campos extendidos por asi_signature_workflow (si existen)
                if 'from_workflow' in Wizard._fields:
                    wvals['from_workflow'] = True
                if 'workflow_id' in Wizard._fields:
                    wvals['workflow_id'] = workflow.id
                if 'readonly_signature_config' in Wizard._fields:
                    wvals['readonly_signature_config'] = True

                wizard = Wizard.create(wvals)
                wizard.action_firmar_documentos()

            else:
                # Fallback: firma local con PDFs embebidos en workflow.document_ids
                Wizard = request.env['firma.documento.wizard']
                wvals = {
                    'signature_role': role.id if role else False,
                    'signature_position': position,
                    'signature_opaque_background': bool(getattr(workflow, 'signature_opaque_background', False)),
                    'sign_all_pages': bool(getattr(workflow, 'sign_all_pages', False)),
                }
                if cert_file and cert_file.filename:
                    cert_bytes = cert_file.read()
                    wvals['certificate_wizard'] = base64.b64encode(cert_bytes)
                    wvals['certificate_wizard_name'] = secure_filename(cert_file.filename)
                if img_file and img_file.filename:
                    img_bytes = img_file.read()
                    wvals['wizard_signature_image'] = base64.b64encode(img_bytes)
                if pwd:
                    wvals['signature_password'] = pwd
                if 'from_workflow' in Wizard._fields:
                    wvals['from_workflow'] = True
                if 'workflow_id' in Wizard._fields:
                    wvals['workflow_id'] = workflow.id
                if 'readonly_signature_config' in Wizard._fields:
                    wvals['readonly_signature_config'] = True

                wizard = Wizard.create(wvals)
                for doc in workflow.document_ids:
                    pdf_b64 = doc.pdf_content
                    if not pdf_b64 and getattr(doc, 'alfresco_file_id', False):
                        content = _fetch_alfresco_content(doc.alfresco_file_id)
                        if content:
                            pdf_b64 = base64.b64encode(content)
                    if not pdf_b64:
                        continue
                    wizard.document_ids.create({
                        'wizard_id': wizard.id,
                        'document_name': doc.name or 'documento.pdf',
                        'pdf_document': _b64_to_bytes(pdf_b64),
                    })
                if not wizard.document_ids:
                    return request.make_json_response({'success': False, 'error': 'No se pudieron cargar documentos válidos para firmar.'}, status=400)
                wizard.action_firmar_documentos()

            # El workflow se actualiza por el hook de asi_signature_workflow
            return request.make_json_response({
                'success': True,
                'message': 'Firma procesada. La solicitud avanzó según el flujo.',
                'workflow_id': workflow.id,
                'workflow_state': workflow.state,
            })

        except Exception as e:
            _logger.exception('Error firmando workflow desde bandeja (AJAX)')
            return request.make_json_response({'success': False, 'error': str(e)}, status=500)

    @http.route(['/api/solicitudes-pendientes'], type='json', auth='user')
    def get_solicitudes_pendientes(self, **kw):
        """API opcional: lista pendientes del usuario."""
        try:
            user = request.env.user
            workflows = request.env['signature.workflow'].search([
                ('state', '=', 'sent'),
                '|', '|', '|',
                ('target_user_id_1', '=', user.id),
                ('target_user_id_2', '=', user.id),
                ('target_user_id_3', '=', user.id),
                ('target_user_id_4', '=', user.id),
            ])

            solicitudes_data = []
            for w in workflows:
                signed_documents = w.get_signed_documents_download_urls() if hasattr(w, 'get_signed_documents_download_urls') else []
                solicitudes_data.append({
                    'id': w.id,
                    'name': w.name,
                    'documento': ', '.join([d.name for d in w.document_ids]) if w.document_ids else '',
                    'solicitante': w.creator_id.name if w.creator_id else '',
                    'fecha': w.sent_date.strftime('%Y-%m-%d %H:%M') if getattr(w, 'sent_date', False) else '',
                    'state': w.state,
                    'documentos_firmados': signed_documents,
                })

            return {'success': True, 'solicitudes': solicitudes_data}
        except Exception as e:
            _logger.exception('Error al obtener solicitudes pendientes')
            return {'success': False, 'error': str(e)}

    # ------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------

    @http.route(['/bandeja-entrada'], type='http', auth='user', website=True)
    def bandeja_entrada(self, **kw):
        """Bandeja split-view."""
        try:
            user = request.env.user
            msg = request.params.get('msg') or kw.get('msg')

            pending = request.env['signature.workflow'].search([
                ('state', '=', 'sent'),
                '|', '|', '|',
                ('target_user_id_1', '=', user.id),
                ('target_user_id_2', '=', user.id),
                ('target_user_id_3', '=', user.id),
                ('target_user_id_4', '=', user.id),
            ])
            created = request.env['signature.workflow'].search([('creator_id', '=', user.id)])

            pendientes = []
            for w in pending:
                pendientes.append({
                    'workflow': w,
                    'documentos_firmados': w.get_signed_documents_download_urls() if hasattr(w, 'get_signed_documents_download_urls') else [],
                })

            creadas = []
            for w in created:
                creadas.append({
                    'workflow': w,
                    'documentos_firmados': w.get_signed_documents_download_urls() if hasattr(w, 'get_signed_documents_download_urls') else [],
                })

            return request.render('asi_firma_web.bandeja_entrada_page', {
                'solicitudes_pendientes': pendientes,
                'solicitudes_creadas': creadas,
                'user': user,
                'message': msg,
            })
        except Exception as e:
            _logger.exception('Error en bandeja de entrada')
            return request.render('asi_firma_web.bandeja_entrada_page', {
                'solicitudes_pendientes': [],
                'solicitudes_creadas': [],
                'user': request.env.user,
                'error': f'Error al cargar la bandeja de entrada: {str(e)}',
                'message': request.params.get('msg')
            })

    @http.route(['/firmar-documentos'], type='http', auth='user', website=True, methods=['GET'])
    def firmar_documentos(self, **kw):
        """Firma ad-hoc desde el sitio web (no workflow)."""
        user = request.env.user
        msg = request.params.get('msg') or kw.get('msg')
        tags = request.env['document.signature.tag'].search([])

        return request.render('asi_firma_web.firma_form_page', {
            'tags': tags,
            'message': msg,
            'user_has_certificado': bool(user.certificado_firma),
            'user_has_imagen': bool(user.imagen_firma),
            'user_has_password': bool(user.contrasena_certificado),
            'workflow_id': False,
        })

    @http.route(['/firmar-documentos/workflow/<int:workflow_id>'], type='http', auth='user', website=True)
    def firmar_workflow(self, workflow_id, **kw):
        """Formulario web para firmar documentos de un workflow (mismo control de turno que asi_signature_workflow)."""
        try:
            workflow = _get_workflow_for_user_recipient(workflow_id)
            if not workflow:
                return request.redirect('/bandeja-entrada?msg=' + urllib.parse.quote(_('Solicitud no encontrada o sin acceso.')))

            # Lógica oficial del workflow
            recipient_data = workflow._get_current_user_recipient_data() if hasattr(workflow, '_get_current_user_recipient_data') else None
            if not recipient_data:
                return request.redirect('/bandeja-entrada?msg=' + urllib.parse.quote(_('No eres destinatario de esta solicitud.')))

            if recipient_data.get('signed'):
                return request.redirect('/bandeja-entrada?msg=' + urllib.parse.quote(_('Ya firmaste esta solicitud.')))

            if hasattr(workflow, '_is_user_current_recipient') and not workflow._is_user_current_recipient():
                current = workflow._get_current_active_recipient() if hasattr(workflow, '_get_current_active_recipient') else None
                msg = _('No es tu turno de firmar.')
                if current and current.get('user'):
                    msg = _(f"No es tu turno. Turno actual: {current['user'].name}")
                return request.redirect('/bandeja-entrada?msg=' + urllib.parse.quote(msg))

            role = recipient_data.get('role')
            signature_role_id = role.id if role else None
            signature_position = recipient_data.get('position')

            # Preview del primer documento
            document_data = None
            document_name = None
            if workflow.document_ids:
                first_doc = workflow.document_ids[0]
                document_name = first_doc.name
                if first_doc.pdf_content:
                    document_data = _b64_to_str(first_doc.pdf_content)
                elif getattr(first_doc, 'alfresco_file_id', False):
                    content = _fetch_alfresco_content(first_doc.alfresco_file_id)
                    if content:
                        document_data = base64.b64encode(content).decode('utf-8')
                        document_name = first_doc.alfresco_file_id.name or document_name

            user = request.env.user
            tags = request.env['document.signature.tag'].search([])

            return request.render('asi_firma_web.firma_form_page', {
                'tags': tags,
                'message': kw.get('msg') or request.params.get('msg'),
                'user_has_certificado': bool(user.certificado_firma),
                'user_has_imagen': bool(user.imagen_firma),
                'user_has_password': bool(user.contrasena_certificado),
                # workflow context
                'workflow_id': workflow_id,
                'workflow': workflow,
                'workflow_documents': workflow.document_ids,
                'document_data': document_data,
                'document_name': document_name,
                'signature_role_id': signature_role_id,
                'signature_position': signature_position,
                'signature_opaque_background': bool(getattr(workflow, 'signature_opaque_background', False)),
                'sign_all_pages': bool(getattr(workflow, 'sign_all_pages', False)),
            })
        except Exception as e:
            _logger.exception('Error al cargar formulario de firma para workflow')
            return request.redirect('/bandeja-entrada?msg=' + urllib.parse.quote(_('Error al cargar el formulario: %s') % str(e)))

    # ------------------------------------------------------------
    # Actions (POST)
    # ------------------------------------------------------------

    @http.route(['/firmar-documentos/enviar'], type='http', auth='user', website=True, methods=['POST'])
    def submit(self, **post):
        """Firma desde website. Si viene workflow_id, aplica la misma lógica de asi_signature_workflow."""
        try:
            user = request.env.user
            files = request.httprequest.files
            workflow_id = post.get('workflow_id')

            # ------------------------------------------------
            # Workflow signing (NO confiar en PDF/rol/posición del cliente)
            # ------------------------------------------------
            if workflow_id:
                workflow = _get_workflow_for_user_recipient(int(workflow_id))
                if not workflow:
                    return self._error_response(_('Solicitud no encontrada o sin acceso.'), status=404)

                recipient_data = workflow._get_current_user_recipient_data() if hasattr(workflow, '_get_current_user_recipient_data') else None
                if not recipient_data:
                    return self._error_response(_('No eres destinatario de esta solicitud.'), status=403)

                if recipient_data.get('signed'):
                    return self._error_response(_('Ya firmaste esta solicitud.'), status=400)

                if hasattr(workflow, '_is_user_current_recipient') and not workflow._is_user_current_recipient():
                    current = workflow._get_current_active_recipient() if hasattr(workflow, '_get_current_active_recipient') else None
                    msg = _('No es tu turno de firmar.')
                    if current and current.get('user'):
                        msg = _(f"No es tu turno. Turno actual: {current['user'].name}")
                    return self._error_response(msg, status=400)

                role = recipient_data.get('role')
                position = recipient_data.get('position')

                wizard_vals = {
                    'signature_role': role.id if role else False,
                    'signature_position': position or 'derecha',
                    'signature_opaque_background': bool(getattr(workflow, 'signature_opaque_background', False)),
                    'sign_all_pages': bool(getattr(workflow, 'sign_all_pages', False)),
                    # Important: let asi_signature_workflow hook update the workflow
                    'from_workflow': True,
                    'workflow_id': workflow.id,
                }

                # Certificado: archivo subido > perfil
                cert_file = files.get('certificate_wizard')
                if cert_file and cert_file.filename:
                    cert_bytes = cert_file.read()
                    wizard_vals['certificate_wizard'] = base64.b64encode(cert_bytes)
                    wizard_vals['certificate_wizard_name'] = secure_filename(cert_file.filename)
                elif user.certificado_firma:
                    wizard_vals['certificate_wizard'] = user.certificado_firma
                    wizard_vals['certificate_wizard_name'] = user.nombre_certificado or 'certificado.p12'
                else:
                    return self._error_response(_('Debes subir tu certificado (.p12) o guardarlo en tu perfil.'), status=400)

                # Imagen: archivo subido > perfil
                img_file = files.get('wizard_signature_image')
                if img_file and img_file.filename:
                    img_bytes = img_file.read()
                    wizard_vals['wizard_signature_image'] = base64.b64encode(img_bytes)
                elif user.imagen_firma:
                    wizard_vals['wizard_signature_image'] = user.imagen_firma
                else:
                    return self._error_response(_('Debes subir tu imagen de firma o guardarla en tu perfil.'), status=400)

                # Password: input > perfil
                password = (post.get('signature_password') or '').strip()
                if password:
                    wizard_vals['signature_password'] = password
                elif user.contrasena_certificado:
                    # No copiar la contraseña cifrada al wizard.
                    # El wizard tomará la del perfil y la descifrará (get_contrasena_descifrada).
                    pass
                else:
                    return self._error_response(_('Debes ingresar la contraseña del certificado.'), status=400)

                wizard = request.env['firma.documento.wizard'].create(wizard_vals)

                # Documentos (server-side)
                if not workflow.document_ids:
                    return self._error_response(_('No se encontraron documentos en la solicitud.'), status=400)

                for doc in workflow.document_ids:
                    pdf_b64 = doc.pdf_content
                    if not pdf_b64 and getattr(doc, 'alfresco_file_id', False):
                        content = _fetch_alfresco_content(doc.alfresco_file_id)
                        if content:
                            pdf_b64 = base64.b64encode(content)
                    if not pdf_b64:
                        continue

                    wizard.document_ids.create({
                        'wizard_id': wizard.id,
                        'document_name': doc.name or (doc.alfresco_file_id.name if getattr(doc, 'alfresco_file_id', False) else 'documento.pdf'),
                        'pdf_document': _b64_to_bytes(pdf_b64),
                    })

                if not wizard.document_ids:
                    return self._error_response(_('No se pudieron cargar documentos válidos para firmar.'), status=400)

                wizard.action_firmar_documentos()

                # El workflow se actualiza por el hook de asi_signature_workflow
                return request.redirect('/bandeja-entrada?msg=' + urllib.parse.quote(_('Firma procesada. La solicitud avanzó según el flujo.')))

            # ------------------------------------------------
            # Ad-hoc signing (subiendo PDFs)
            # ------------------------------------------------
            pdf_files = files.getlist('pdfs')
            if not pdf_files:
                return request.redirect('/firmar-documentos?msg=' + urllib.parse.quote(_('Debes adjuntar al menos un PDF.')))

            vals = {
                'signature_position': post.get('signature_position') or 'derecha',
                'signature_opaque_background': bool(post.get('signature_opaque_background')),
                'sign_all_pages': bool(post.get('sign_all_pages')),
            }
            if post.get('signature_role'):
                try:
                    vals['signature_role'] = int(post.get('signature_role'))
                except Exception:
                    pass

            # Certificado
            cert_file = files.get('certificate_wizard')
            if cert_file and cert_file.filename:
                cert_bytes = cert_file.read()
                vals['certificate_wizard_name'] = secure_filename(cert_file.filename)
                vals['certificate_wizard'] = base64.b64encode(cert_bytes)

                if post.get('save_to_profile') == 'true':
                    user.write({
                        'certificado_firma': base64.b64encode(cert_bytes),
                        'nombre_certificado': secure_filename(cert_file.filename)
                    })
            elif user.certificado_firma:
                vals['certificate_wizard'] = user.certificado_firma
                vals['certificate_wizard_name'] = user.nombre_certificado or 'certificado.p12'
            else:
                return self._error_response(_('Debes adjuntar tu certificado (.p12).'), status=400)

            # Imagen
            img_file = files.get('wizard_signature_image')
            if img_file and img_file.filename:
                img_bytes = img_file.read()
                vals['wizard_signature_image'] = base64.b64encode(img_bytes)
                if post.get('save_to_profile') == 'true':
                    user.write({'imagen_firma': base64.b64encode(img_bytes)})
            elif user.imagen_firma:
                vals['wizard_signature_image'] = user.imagen_firma
            else:
                return self._error_response(_('Debes adjuntar tu imagen de firma.'), status=400)

            # Password
            password = (post.get('signature_password') or '').strip()
            if password:
                vals['signature_password'] = password
                if post.get('save_to_profile') == 'true':
                    user.write({'contrasena_certificado': password})
            elif user.contrasena_certificado:
                # No copiar la contraseña cifrada al wizard.
                # El wizard la obtiene y descifra desde el perfil del usuario.
                pass
            else:
                return self._error_response(_('Debes ingresar la contraseña del certificado.'), status=400)

            # Document lines
            document_lines = []
            for f in pdf_files:
                if not getattr(f, 'filename', None):
                    continue
                name = secure_filename(f.filename)
                data = base64.b64encode(f.read())
                document_lines.append((0, 0, {'document_name': name, 'pdf_document': data}))

            if not document_lines:
                return self._error_response(_('No se recibieron PDFs válidos.'), status=400)

            vals['document_ids'] = document_lines
            wizard = request.env['firma.documento.wizard'].create(vals)

            try:
                wizard.action_firmar_documentos()
            except Exception as e:
                _logger.exception('Error en firma ad-hoc')
                return self._error_response(_('Error al firmar documentos: %s') % str(e), status=500)

            # Respuesta: ZIP o PDF
            if wizard.zip_signed:
                fname = wizard.zip_name or 'documentos_firmados_%s.zip' % datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                data = base64.b64decode(wizard.zip_signed)
                headers = [('Content-Type', 'application/zip'), ('Content-Disposition', 'attachment; filename="%s"' % fname)]
                response = request.make_response(data, headers)
                response.headers['X-Form-Reset'] = 'success'
                return response

            signed_lines = wizard.document_ids.filtered(lambda d: d.signature_status in ('firmado', 'signed') and d.pdf_signed)
            if len(signed_lines) == 1:
                ln = signed_lines[0]
                data = base64.b64decode(ln.pdf_signed)
                nombre_base, extension = os.path.splitext(ln.document_name or 'documento.pdf')
                if not extension:
                    extension = '.pdf'
                filename = f"{nombre_base} - firmado{extension}"
                headers = [('Content-Type', 'application/pdf'), ('Content-Disposition', 'attachment; filename="%s"' % filename)]
                response = request.make_response(data, headers)
                response.headers['X-Form-Reset'] = 'success'
                return response

            if len(signed_lines) > 1:
                mem = BytesIO()
                with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for ln in signed_lines:
                        zf.writestr(ln.document_name or 'documento.pdf', base64.b64decode(ln.pdf_signed))
                data = mem.getvalue()
                headers = [('Content-Type', 'application/zip'), ('Content-Disposition', 'attachment; filename="documentos_firmados.zip"')]
                response = request.make_response(data, headers)
                response.headers['X-Form-Reset'] = 'success'
                return response

            # Fallback
            ok_count = len(wizard.document_ids.filtered(lambda d: d.signature_status in ('firmado', 'signed')))
            if ok_count:
                return request.redirect('/firmar-documentos?msg=' + urllib.parse.quote(_('Documentos firmados exitosamente (%s).') % ok_count))
            return request.redirect('/firmar-documentos?msg=' + urllib.parse.quote(_('No se generaron archivos firmados.')))

        except Exception as e:
            _logger.exception('Error procesando firma web')
            return self._error_response(_('Error procesando la firma: %s') % str(e), status=500)

    @http.route(['/firmar-documentos/guardar-perfil'], type='http', auth='user', website=True, methods=['POST'])
    def save_to_profile(self, **post):
        """Guardar certificado/imagen/password en el perfil del usuario (endpoint AJAX)."""
        try:
            user = request.env.user
            files = request.httprequest.files

            cert = files.get('certificate_wizard')
            if cert and cert.filename:
                cert_bytes = cert.read()
                user.write({
                    'certificado_firma': base64.b64encode(cert_bytes),
                    'nombre_certificado': secure_filename(cert.filename)
                })

            img = files.get('wizard_signature_image')
            if img and img.filename:
                img_bytes = img.read()
                user.write({'imagen_firma': base64.b64encode(img_bytes)})

            pwd = (post.get('signature_password') or '').strip()
            if pwd:
                user.write({'contrasena_certificado': pwd})

            return request.make_json_response({'success': True, 'message': 'Datos guardados exitosamente en tu perfil'})
        except Exception as e:
            _logger.exception('Error al guardar en perfil')
            return request.make_json_response({'success': False, 'message': f'Error al guardar datos: {str(e)}'})

    def _error_response(self, message, status=500):
        """Helper para errores consistentes."""
        if request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = request.make_json_response({'error': str(message)}, status=status)
            response.headers['Content-Type'] = 'application/json'
            return response
        return request.redirect('/firmar-documentos?msg=' + urllib.parse.quote(_(str(message))))

    # ------------------------------------------------------------
    # Convenience routes used by older UI
    # ------------------------------------------------------------

    @http.route(['/bandeja-entrada/firmar/<int:workflow_id>'], type='http', auth='user', website=True)
    def firmar_solicitud_bandeja(self, workflow_id, **kw):
        return request.redirect(f'/firmar-documentos/workflow/{workflow_id}')

    @http.route(['/bandeja-entrada/rechazar/<int:workflow_id>'], type='http', auth='user', website=True, methods=['GET', 'POST'])
    def rechazar_solicitud_bandeja(self, workflow_id, **kw):
        """Rechazo web con motivo, usando la misma lógica del workflow."""
        workflow = _get_workflow_for_user_recipient(workflow_id)
        if not workflow:
            return request.redirect('/bandeja-entrada?msg=' + urllib.parse.quote(_('Solicitud no encontrada o sin acceso.')))

        if request.httprequest.method == 'GET':
            return request.render('asi_firma_web.workflow_reject_page', {
                'workflow': workflow,
                'workflow_id': workflow_id,
                'message': request.params.get('msg'),
            })

        # POST
        try:
            recipient_data = workflow._get_current_user_recipient_data() if hasattr(workflow, '_get_current_user_recipient_data') else None
            if not recipient_data:
                return request.redirect('/bandeja-entrada?msg=' + urllib.parse.quote(_('No eres destinatario de esta solicitud.')))

            if recipient_data.get('signed'):
                return request.redirect('/bandeja-entrada?msg=' + urllib.parse.quote(_('Ya firmaste esta solicitud.')))

            if hasattr(workflow, '_is_user_current_recipient') and not workflow._is_user_current_recipient():
                current = workflow._get_current_active_recipient() if hasattr(workflow, '_get_current_active_recipient') else None
                msg = _('No es tu turno de rechazar.')
                if current and current.get('user'):
                    msg = _(f"No es tu turno. Turno actual: {current['user'].name}")
                return request.redirect('/bandeja-entrada?msg=' + urllib.parse.quote(msg))

            reason = (kw.get('reason') or '').strip()
            if not reason:
                return request.redirect(f'/bandeja-entrada/rechazar/{workflow_id}?msg=' + urllib.parse.quote(_('Debes indicar el motivo del rechazo.')))

            if hasattr(workflow, '_process_rejection'):
                workflow._process_rejection(reason)
            else:
                # Fallback (menos ideal)
                workflow.message_post(body=_('Rechazado desde web: %s') % reason)
                workflow.write({'state': 'rejected'})

            return request.redirect('/bandeja-entrada?msg=' + urllib.parse.quote(_('Solicitud rechazada exitosamente.')))
        except Exception as e:
            _logger.exception('Error al rechazar solicitud')
            return request.redirect('/bandeja-entrada?msg=' + urllib.parse.quote(_('Error al procesar el rechazo: %s') % str(e)))
