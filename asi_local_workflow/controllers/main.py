# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, content_disposition
import base64
import logging
import json

_logger = logging.getLogger(__name__)


class LocalWorkflowController(http.Controller):
    
    @http.route('/local_workflow/download_signed/<int:workflow_id>', type='http', auth='user')
    def download_signed_documents(self, workflow_id, **kwargs):
        """Controlador para mostrar página de descarga de documentos firmados individuales"""
        try:
            workflow = request.env['local.workflow'].browse(workflow_id)
            
            if not workflow.exists():
                return request.not_found()
            
            # Verificar permisos (solo creador o destinatarios pueden descargar)
            current_user = request.env.user
            allowed_users = [workflow.creator_id]
            
            for i in range(1, 5):
                user = getattr(workflow, f'target_user_id_{i}')
                if user:
                    allowed_users.append(user)
            
            if current_user not in allowed_users:
                return request.redirect('/web/login')
            
            if workflow.state != 'completed':
                return request.not_found()
            
            signed_documents = workflow.document_ids.filtered('is_signed')
            
            return request.make_response(
                self._generate_download_page(workflow, signed_documents),
                headers=[('Content-Type', 'text/html; charset=utf-8')]
            )
            
        except Exception as e:
            _logger.error(f"Error accediendo a documentos de la solicitud {workflow_id}: {e}")
            return request.not_found()

    def _generate_download_page(self, workflow, signed_documents):
        """Genera la página HTML para descarga de documentos"""
        
        # Construir lista de documentos HTML
        documents_html = ""
        for document in signed_documents:
            documents_html += f"""
                <div class="list-group-item d-flex justify-content-between align-items-center">
                    <div>
                        <i class="fa fa-file-pdf-o text-danger"></i>
                        <span class="ml-2">{document.name}</span>
                        <small class="text-muted d-block">
                            Firmado el {document.signed_date or 'N/A'}
                        </small>
                    </div>
                    <a href="/local_workflow/document/{document.id}/download" 
                       class="btn btn-primary btn-sm">
                        <i class="fa fa-download"></i> Descargar
                    </a>
                </div>
            """
        
        # Construir HTML de usuarios destinatarios
        target_users_html = ""
        for i in range(1, 5):
            user = getattr(workflow, f'target_user_id_{i}')
            if user:
                target_users_html += f"<span class='badge badge-secondary mr-1'>{user.name}</span>"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
            <title>Documentos Firmados - {workflow.name}</title>
            <link rel="stylesheet" href="/web/static/lib/bootstrap/css/bootstrap.min.css"/>
            <link rel="stylesheet" href="/web/static/src/legacy/css/font_awesome.css"/>
            <style>
                body {{
                    background-color: #f8f9fa;
                    padding: 20px;
                }}
                .card {{
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    border: none;
                    border-radius: 8px;
                }}
                .card-header {{
                    border-radius: 8px 8px 0 0 !important;
                }}
                .list-group-item {{
                    border-left: none;
                    border-right: none;
                }}
                .list-group-item:first-child {{
                    border-top: none;
                }}
                .list-group-item:last-child {{
                    border-bottom: none;
                }}
                .badge {{
                    font-size: 0.8em;
                }}
            </style>
        </head>
        <body>
            <div class="container mt-4">
                <div class="row justify-content-center">
                    <div class="col-md-10">
                        <div class="card">
                            <div class="card-header bg-success text-white">
                                <h4 class="mb-0">
                                    <i class="fa fa-check-circle"></i> Documentos Firmados Listos
                                </h4>
                            </div>
                            <div class="card-body">
                                <h5>Solicitud de Firma: {workflow.name}</h5>
                                <p class="text-muted">
                                    Creado por: <strong>{workflow.creator_id.name}</strong><br/>
                                    Destinatarios: {target_users_html or 'N/A'}<br/>
                                    Fecha de finalización: {workflow.completed_date or 'N/A'}
                                </p>
                                
                                <hr/>
                                
                                <h6>Documentos disponibles para descarga ({len(signed_documents)}):</h6>
                                <div class="list-group mb-4">
                                    {documents_html}
                                </div>
                                
                                <div class="text-center">
                                    <a href="/local_workflow/descargar_multiples?workflow_id={workflow.id}" 
                                       class="btn btn-success btn-lg">
                                        <i class="fa fa-download"></i> DESCARGAR TODOS LOS DOCUMENTOS
                                    </a>
                                    <p class="text-muted mt-2">
                                        Los documentos se descargarán automáticamente uno por uno
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <script src="/web/static/lib/jquery/jquery.js"></script>
            <script src="/web/static/lib/bootstrap/js/bootstrap.min.js"></script>
        </body>
        </html>
        """
        
        return html_content

    @http.route('/local_workflow/document/<int:document_id>/download', type='http', auth='user')
    def download_single_document(self, document_id, **kwargs):
        """Controlador para descargar un documento individual firmado"""
        _logger.info(f"[DESCARGA_SIMPLE] ===== INICIO DESCARGA DOCUMENTO {document_id} =====")
        
        try:
            document = request.env['local.workflow.document'].browse(document_id)
            _logger.info(f"[DESCARGA_SIMPLE] Documento encontrado: {document.name if document.exists() else 'NO EXISTE'}")
            
            if not document.exists():
                _logger.error(f"[DESCARGA_SIMPLE] Documento {document_id} no existe")
                return request.not_found()
            
            _logger.info(f"[DESCARGA_SIMPLE] Estado firmado: {document.is_signed}")
            _logger.info(f"[DESCARGA_SIMPLE] Attachment ID: {document.attachment_id.id if document.attachment_id else 'NINGUNO'}")
            
            workflow = document.workflow_id
            _logger.info(f"[DESCARGA_SIMPLE] Workflow: {workflow.name}")
            
            # Verificar permisos
            current_user = request.env.user
            allowed_users = [workflow.creator_id]
            
            for i in range(1, 5):
                user = getattr(workflow, f'target_user_id_{i}')
                if user:
                    allowed_users.append(user)
            
            if current_user not in allowed_users:
                _logger.error(f"[DESCARGA_SIMPLE] Usuario sin permisos")
                return request.redirect('/web/login')
            
            if not document.is_signed:
                _logger.error(f"[DESCARGA_SIMPLE] Documento no está firmado")
                return request.not_found()
            
            # Descargar el documento firmado desde attachment
            if document.attachment_id:
                _logger.info(f"[DESCARGA_SIMPLE] Iniciando descarga desde attachment")
                return self._download_from_attachment(document.attachment_id, document.name)
            else:
                _logger.error(f"[DESCARGA_SIMPLE] No hay attachment disponible para descargar")
                return request.not_found()
                
        except Exception as e:
            _logger.error(f"[DESCARGA_SIMPLE] Error general: {e}")
            import traceback
            _logger.error(f"[DESCARGA_SIMPLE] Traceback: {traceback.format_exc()}")
            return request.not_found()

    def _download_from_attachment(self, attachment, document_name):
        """Método para descargar desde attachment con logs extensivos"""
        _logger.info(f"[ATTACHMENT] ===== INICIO DESCARGA ATTACHMENT =====")
        _logger.info(f"[ATTACHMENT] Archivo: {attachment.name}")
        _logger.info(f"[ATTACHMENT] Tamaño: {len(attachment.datas) if attachment.datas else 0} bytes")
        _logger.info(f"[ATTACHMENT] Documento: {document_name}")
        
        try:
            if not attachment.datas:
                _logger.error("[ATTACHMENT] Attachment no tiene datos")
                return request.not_found()
            
            file_content = base64.b64decode(attachment.datas)
            content_length = len(file_content)
            _logger.info(f"[ATTACHMENT] Contenido decodificado: {content_length} bytes")
            
            # Limpiar nombre del archivo
            clean_name = document_name
            if not clean_name.endswith('.pdf'):
                clean_name += '.pdf'
            
            _logger.info(f"[ATTACHMENT] Nombre final: {clean_name}")
            
            # Verificar si el contenido parece ser un PDF
            if file_content.startswith(b'%PDF'):
                _logger.info("[ATTACHMENT] Contenido verificado como PDF válido")
            else:
                _logger.warning("[ATTACHMENT] El contenido NO parece ser un PDF válido")
                _logger.warning(f"[ATTACHMENT] Primeros 100 bytes: {file_content[:100]}")
            
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', content_length),
                ('Content-Disposition', content_disposition(clean_name)),
            ]
            
            _logger.info(f"[ATTACHMENT] ===== DESCARGA EXITOSA =====")
            return request.make_response(file_content, headers=headers)
                
        except Exception as e:
            _logger.error(f"[ATTACHMENT] Error general: {e}")
            import traceback
            _logger.error(f"[ATTACHMENT] Traceback: {traceback.format_exc()}")
            return request.not_found()

    @http.route('/local_workflow/descargar_multiples', type='http', auth='user')
    def descargar_multiples_documentos(self, workflow_id, **kwargs):
        """Controlador que genera una página HTML para descargar múltiples documentos"""
        _logger.info(f"[DESCARGA_MULTIPLE] ===== INICIO DESCARGA MÚLTIPLE =====")
        _logger.info(f"[DESCARGA_MULTIPLE] Workflow ID: {workflow_id}")
        
        try:
            # Obtener el workflow
            workflow = request.env['local.workflow'].browse(int(workflow_id))
            
            if not workflow.exists():
                _logger.error(f"[DESCARGA_MULTIPLE] Workflow {workflow_id} no existe")
                return request.not_found()
            
            # Verificar permisos (solo creador o destinatarios pueden descargar)
            current_user = request.env.user
            allowed_users = [workflow.creator_id]
            
            for i in range(1, 5):
                user = getattr(workflow, f'target_user_id_{i}')
                if user:
                    allowed_users.append(user)
            
            if current_user not in allowed_users:
                _logger.error(f"[DESCARGA_MULTIPLE] Usuario sin permisos")
                return request.redirect('/web/login')
            
            # Obtener documentos firmados
            documents_signed = workflow.document_ids.filtered(lambda d: d.is_signed)
            _logger.info(f"[DESCARGA_MULTIPLE] Documentos firmados encontrados: {len(documents_signed)}")
            
            if not documents_signed:
                _logger.error(f"[DESCARGA_MULTIPLE] No hay documentos firmados")
                return request.not_found()
            
            download_urls = []
            for documento in documents_signed:
                original_name = documento.name
                if not original_name.endswith('.pdf'):
                    original_name += '.pdf'
                
                # Usar URL del controlador de descarga individual
                download_url = f'/local_workflow/document/{documento.id}/download'
                _logger.info(f"[DESCARGA_MULTIPLE] Documento: {original_name} -> URL: {download_url}")
                
                download_urls.append({
                    'url': download_url,
                    'name': original_name
                })
            
            # Crear lista de archivos para el HTML
            file_items_html = ""
            for i, doc in enumerate(download_urls):
                file_items_html += f'<div class="file-item" id="file_{i}">{doc["name"]}</div>\n'
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Descargando documentos...</title>
                <meta charset="utf-8">
                <style>
                    body {{ 
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                        text-align: center; 
                        padding: 50px;
                        background: white;
                        color: #333;
                        margin: 0;
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    .container {{
                        max-width: 600px;
                        background: rgba(255, 255, 255, 0.95);
                        color: #333;
                        padding: 40px;
                        border-radius: 15px;
                        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                        border: 1px solid #e0e0e0;
                    }}
                    .spinner {{
                        border: 4px solid #f3f3f3;
                        border-top: 4px solid #667eea;
                        border-radius: 50%;
                        width: 50px;
                        height: 50px;
                        animation: spin 1s linear infinite;
                        margin: 20px auto;
                    }}
                    @keyframes spin {{
                        0% {{ transform: rotate(0deg); }}
                        100% {{ transform: rotate(360deg); }}
                    }}
                    .success {{
                        color: #28a745;
                        margin-top: 20px;
                        font-size: 18px;
                    }}
                    .progress-bar {{
                        width: 100%;
                        height: 20px;
                        background-color: #e0e0e0;
                        border-radius: 10px;
                        overflow: hidden;
                        margin: 20px 0;
                    }}
                    .progress-fill {{
                        height: 100%;
                        background: linear-gradient(90deg, #667eea, #764ba2);
                        width: 0%;
                        transition: width 0.3s ease;
                    }}
                    .file-list {{
                        text-align: left;
                        margin: 20px 0;
                        max-height: 200px;
                        overflow-y: auto;
                    }}
                    .file-item {{
                        padding: 8px;
                        margin: 4px 0;
                        background: #f8f9fa;
                        border-radius: 5px;
                        border-left: 4px solid #667eea;
                    }}
                    .file-item.downloaded {{
                        background: #d4edda;
                        border-left-color: #28a745;
                    }}
                    .file-item.downloading {{
                        background: #fff3cd;
                        border-left-color: #ffc107;
                    }}
                    .file-item.error {{
                        background: #f8d7da;
                        border-left-color: #dc3545;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>📄 Descargando Documentos Firmados</h2>
                    <div class="spinner" id="spinner"></div>
                    <p id="status">Preparando descarga de {len(download_urls)} documentos...</p>
                    
                    <div class="progress-bar">
                        <div class="progress-fill" id="progress"></div>
                    </div>
                    
                    <div class="file-list" id="fileList">
                        {file_items_html}
                    </div>
                    
                    <div class="success" id="complete" style="display:none;">
                        ✅ ¡Descarga completada!<br>
                        <small>Se han descargado {len(download_urls)} documentos. Puede cerrar esta ventana.</small>
                    </div>
                </div>
                
                <script>
                    const downloads = {json.dumps(download_urls)};
                    let downloaded = 0;
                    
                    console.log('[JS_MULTIPLE] ===== INICIO DESCARGA MÚLTIPLE JS =====');
                    console.log('[JS_MULTIPLE] Total documentos:', downloads.length);
                    console.log('[JS_MULTIPLE] Lista completa:', downloads);
                    
                    function updateProgress() {{
                        const progress = (downloaded / downloads.length) * 100;
                        document.getElementById('progress').style.width = progress + '%';
                        document.getElementById('status').textContent = 
                            'Descargados: ' + downloaded + ' de ' + downloads.length + ' documentos';
                        console.log('[JS_MULTIPLE] Progreso actualizado:', progress + '%');
                    }}
                    
                    function downloadFile(downloadInfo, index) {{
                        return new Promise(function(resolve) {{
                            console.log('[JS_MULTIPLE] ===== INICIANDO DESCARGA', index + 1, '=====');
                            console.log('[JS_MULTIPLE] Archivo:', downloadInfo.name);
                            console.log('[JS_MULTIPLE] URL:', downloadInfo.url);
                            
                            setTimeout(function() {{
                                // Marcar como descargando
                                const fileItem = document.getElementById('file_' + index);
                                if (fileItem) {{
                                    fileItem.classList.add('downloading');
                                    console.log('[JS_MULTIPLE] Marcado como descargando:', downloadInfo.name);
                                }}
                                
                                // Usar fetch para descargar
                                console.log('[JS_MULTIPLE] Iniciando fetch:', downloadInfo.url);
                                fetch(downloadInfo.url)
                                    .then(function(response) {{
                                        console.log('[JS_MULTIPLE] Respuesta recibida:');
                                        console.log('[JS_MULTIPLE] - Status:', response.status);
                                        console.log('[JS_MULTIPLE] - StatusText:', response.statusText);
                                        console.log('[JS_MULTIPLE] - Headers:', Object.fromEntries(response.headers.entries()));
                                        
                                        if (!response.ok) {{
                                            throw new Error('Error HTTP: ' + response.status + ' - ' + response.statusText);
                                        }}
                                        return response.blob();
                                    }})
                                    .then(function(blob) {{
                                        console.log('[JS_MULTIPLE] Blob recibido:');
                                        console.log('[JS_MULTIPLE] - Tamaño:', blob.size, 'bytes');
                                        console.log('[JS_MULTIPLE] - Tipo:', blob.type);
                                        
                                        // Verificar que el blob no esté vacío
                                        if (blob.size === 0) {{
                                            throw new Error('Blob vacío recibido');
                                        }}
                                        
                                        // Crear URL temporal para el blob
                                        const url = window.URL.createObjectURL(blob);
                                        console.log('[JS_MULTIPLE] URL temporal creada:', url);
                                        
                                        // Crear link de descarga
                                        const link = document.createElement('a');
                                        link.href = url;
                                        link.download = downloadInfo.name;
                                        link.style.display = 'none';
                                        
                                        // Agregar al DOM y hacer click
                                        document.body.appendChild(link);
                                        console.log('[JS_MULTIPLE] Link agregado al DOM, haciendo click...');
                                        link.click();
                                        
                                        // Limpiar
                                        setTimeout(function() {{
                                            document.body.removeChild(link);
                                            window.URL.revokeObjectURL(url);
                                            console.log('[JS_MULTIPLE] Link limpiado');
                                        }}, 100);
                                        
                                        console.log('[JS_MULTIPLE] ===== DESCARGA COMPLETADA =====');
                                        
                                        // Marcar como descargado
                                        setTimeout(function() {{
                                            downloaded++;
                                            updateProgress();
                                            
                                            if (fileItem) {{
                                                fileItem.classList.remove('downloading');
                                                fileItem.classList.add('downloaded');
                                            }}
                                            
                                            resolve();
                                        }}, 200);
                                    }})
                                    .catch(function(error) {{
                                        console.error('[JS_MULTIPLE] ===== ERROR EN DESCARGA =====');
                                        console.error('[JS_MULTIPLE] Error:', error);
                                        console.error('[JS_MULTIPLE] Archivo:', downloadInfo.name);
                                        console.error('[JS_MULTIPLE] URL:', downloadInfo.url);
                                        
                                        if (fileItem) {{
                                            fileItem.classList.remove('downloading');
                                            fileItem.classList.add('error');
                                        }}
                                        resolve();
                                    }});
                                
                            }}, index * 1000); // 1 segundo entre descargas
                        }});
                    }}
                    
                    async function startDownloads() {{
                        console.log('[JS_MULTIPLE] ===== INICIANDO PROCESO DE DESCARGA =====');
                        updateProgress();
                        
                        // Descargar archivos secuencialmente
                        for (let i = 0; i < downloads.length; i++) {{
                            console.log('[JS_MULTIPLE] Procesando descarga', i + 1, 'de', downloads.length);
                            await downloadFile(downloads[i], i);
                        }}
                        
                        // Mostrar completado
                        console.log('[JS_MULTIPLE] ===== TODAS LAS DESCARGAS COMPLETADAS =====');
                        document.getElementById('spinner').style.display = 'none';
                        document.getElementById('complete').style.display = 'block';
                        
                        // Auto-cerrar después de 5 segundos
                        setTimeout(function() {{
                            console.log('[JS_MULTIPLE] Auto-cerrando ventana...');
                            window.close();
                        }}, 5000);
                    }}
                    
                    // Iniciar descargas cuando la página esté ready
                    document.addEventListener('DOMContentLoaded', function() {{
                        console.log('[JS_MULTIPLE] DOM cargado, iniciando descargas...');
                        startDownloads();
                    }});
                </script>
            </body>
            </html>
            """
            
            _logger.info(f"[DESCARGA_MULTIPLE] ===== PÁGINA HTML GENERADA =====")
            return request.make_response(html_content, headers=[('Content-Type', 'text/html')])
            
        except Exception as e:
            _logger.error(f"[DESCARGA_MULTIPLE] Error general: {e}")
            import traceback
            _logger.error(f"[DESCARGA_MULTIPLE] Traceback: {traceback.format_exc()}")
            return request.not_found()