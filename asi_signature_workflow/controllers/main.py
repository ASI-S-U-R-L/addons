# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, content_disposition
import base64
import logging

_logger = logging.getLogger(__name__)

class SignatureWorkflowController(http.Controller):
    
    @http.route('/signature_workflow/download_signed/<int:workflow_id>', type='http', auth='user')
    def download_signed_documents(self, workflow_id, **kwargs):
        """Controlador para mostrar página de descarga de documentos firmados individuales"""
        try:
            workflow = request.env['signature.workflow'].browse(workflow_id)
            
            if not workflow.exists():
                return request.not_found()
            
            # Verificar permisos (solo creador o destinatario pueden descargar)
            if request.env.user not in (workflow.creator_id, workflow.target_user_id_1, workflow.target_user_id_2, workflow.target_user_id_3, workflow.target_user_id_4):
                return request.redirect('/web/login')
            
            if workflow.state != 'completed':
                return request.not_found()
            
            return request.render('asi_signature_workflow.download_signed_documents_page', {
                'workflow': workflow,
                'signed_documents': workflow.document_ids.filtered('is_signed'),
            })
            
        except Exception as e:
            _logger.error(f"Error accediendo a documentos de la solicitud {workflow_id}: {e}")
            return request.not_found()

    @http.route('/signature_workflow/document/<int:document_id>/download', type='http', auth='user')
    def download_single_document(self, document_id, **kwargs):
        """Controlador para descargar un documento individual firmado - SIMPLIFICADO CON LOGS"""
        _logger.info(f"[DESCARGA_SIMPLE] ===== INICIO DESCARGA DOCUMENTO {document_id} =====")
        
        try:
            document = request.env['signature.workflow.document'].browse(document_id)
            _logger.info(f"[DESCARGA_SIMPLE] Documento encontrado: {document.name if document.exists() else 'NO EXISTE'}")
            
            if not document.exists():
                _logger.error(f"[DESCARGA_SIMPLE] Documento {document_id} no existe")
                return request.not_found()
            
            _logger.info(f"[DESCARGA_SIMPLE] Estado firmado: {document.is_signed}")
            _logger.info(f"[DESCARGA_SIMPLE] Alfresco file ID: {document.alfresco_file_id.id if document.alfresco_file_id else 'NINGUNO'}")
            _logger.info(f"[DESCARGA_SIMPLE] PDF content: {'SÍ' if document.pdf_content else 'NO'}")
            
            workflow = document.workflow_id
            _logger.info(f"[DESCARGA_SIMPLE] Workflow: {workflow.name}, Source: {workflow.document_source}")
            
            # Verificar permisos
            if request.env.user not in (workflow.creator_id, workflow.target_user_id_1, workflow.target_user_id_2, workflow.target_user_id_3, workflow.target_user_id_4):
                _logger.error(f"[DESCARGA_SIMPLE] Usuario sin permisos")
                return request.redirect('/web/login')
            
            # SIMPLIFICAR: Solo manejar Alfresco por ahora
            if workflow.document_source == 'alfresco' and document.alfresco_file_id:
                _logger.info(f"[DESCARGA_SIMPLE] Iniciando descarga de Alfresco")
                return self._download_from_alfresco_simple(document.alfresco_file_id, document.name)
            elif document.pdf_content:
                _logger.info(f"[DESCARGA_SIMPLE] Iniciando descarga local")
                return self._download_local_document(document)
            else:
                _logger.error(f"[DESCARGA_SIMPLE] No hay fuente de descarga disponible")
                return request.not_found()
                
        except Exception as e:
            _logger.error(f"[DESCARGA_SIMPLE] Error general: {e}")
            import traceback
            _logger.error(f"[DESCARGA_SIMPLE] Traceback: {traceback.format_exc()}")
            return request.not_found()

    def _download_from_alfresco_simple(self, alfresco_file, document_name):
        """Método simplificado para descargar de Alfresco con logs extensivos"""
        _logger.info(f"[ALFRESCO_SIMPLE] ===== INICIO DESCARGA ALFRESCO =====")
        _logger.info(f"[ALFRESCO_SIMPLE] Archivo: {alfresco_file.name}")
        _logger.info(f"[ALFRESCO_SIMPLE] Node ID: {alfresco_file.alfresco_node_id}")
        _logger.info(f"[ALFRESCO_SIMPLE] Documento: {document_name}")
        
        try:
            config = request.env['ir.config_parameter'].sudo()
            url = config.get_param('asi_alfresco_integration.alfresco_server_url')
            user = config.get_param('asi_alfresco_integration.alfresco_username')
            pwd = config.get_param('asi_alfresco_integration.alfresco_password')
            
            _logger.info(f"[ALFRESCO_SIMPLE] URL: {url}")
            _logger.info(f"[ALFRESCO_SIMPLE] Usuario: {user}")
            _logger.info(f"[ALFRESCO_SIMPLE] Password configurado: {'SÍ' if pwd else 'NO'}")
            
            if not all([url, user, pwd]):
                _logger.error("[ALFRESCO_SIMPLE] Configuración de Alfresco incompleta")
                return request.not_found()
            
            import requests
            
            node_id = alfresco_file.alfresco_node_id
            
            # ESTRATEGIA SIMPLE: Primero intentar obtener información del nodo actual
            node_info_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}"
            _logger.info(f"[ALFRESCO_SIMPLE] Consultando info del nodo: {node_info_url}")
            
            node_response = requests.get(node_info_url, auth=(user, pwd), timeout=30)
            _logger.info(f"[ALFRESCO_SIMPLE] Respuesta info nodo: {node_response.status_code}")
            
            if node_response.status_code == 200:
                node_data = node_response.json()
                _logger.info(f"[ALFRESCO_SIMPLE] Info del nodo: {node_data}")
                
                # Verificar si hay versiones
                if 'entry' in node_data:
                    entry = node_data['entry']
                    version_label = entry.get('properties', {}).get('cm:versionLabel', 'N/A')
                    modified_at = entry.get('modifiedAt', 'N/A')
                    _logger.info(f"[ALFRESCO_SIMPLE] Versión actual: {version_label}, Modificado: {modified_at}")
            
            # ESTRATEGIA SIMPLE: Intentar descargar directamente el nodo actual (debería ser la versión más reciente)
            download_url = f"{url}/alfresco/api/-default-/public/alfresco/versions/1/nodes/{node_id}/content"
            _logger.info(f"[ALFRESCO_SIMPLE] URL de descarga directa: {download_url}")
            
            response = requests.get(download_url, auth=(user, pwd), timeout=30)
            _logger.info(f"[ALFRESCO_SIMPLE] Respuesta descarga: {response.status_code}")
            _logger.info(f"[ALFRESCO_SIMPLE] Headers respuesta: {dict(response.headers)}")
            
            if response.status_code == 200:
                content_length = len(response.content)
                _logger.info(f"[ALFRESCO_SIMPLE] Contenido descargado: {content_length} bytes")
                
                # Limpiar nombre del archivo
                clean_name = document_name
                if clean_name.endswith(' - firmado.pdf'):
                    clean_name = clean_name.replace(' - firmado.pdf', '.pdf')
                elif clean_name.endswith(' - firmado'):
                    clean_name = clean_name.replace(' - firmado', '')
                
                _logger.info(f"[ALFRESCO_SIMPLE] Nombre final: {clean_name}")
                
                # Verificar si el contenido parece ser un PDF
                if response.content.startswith(b'%PDF'):
                    _logger.info("[ALFRESCO_SIMPLE] Contenido verificado como PDF válido")
                else:
                    _logger.warning("[ALFRESCO_SIMPLE] El contenido NO parece ser un PDF válido")
                    _logger.warning(f"[ALFRESCO_SIMPLE] Primeros 100 bytes: {response.content[:100]}")
                
                headers = [
                    ('Content-Type', 'application/pdf'),
                    ('Content-Length', content_length),
                    ('Content-Disposition', f'attachment; filename="{clean_name}"'),
                ]
                
                _logger.info(f"[ALFRESCO_SIMPLE] ===== DESCARGA EXITOSA =====")
                return request.make_response(response.content, headers=headers)
            else:
                _logger.error(f"[ALFRESCO_SIMPLE] Error en descarga: HTTP {response.status_code}")
                _logger.error(f"[ALFRESCO_SIMPLE] Respuesta error: {response.text[:500]}")
                return request.not_found()
                
        except Exception as e:
            _logger.error(f"[ALFRESCO_SIMPLE] Error general: {e}")
            import traceback
            _logger.error(f"[ALFRESCO_SIMPLE] Traceback: {traceback.format_exc()}")
            return request.not_found()

    def _download_local_document(self, document):
        """Descarga un documento local"""
        _logger.info(f"[LOCAL_SIMPLE] Descargando documento local: {document.name}")
        try:
            if not document.pdf_content:
                _logger.error(f"[LOCAL_SIMPLE] Documento {document.id} no tiene contenido PDF")
                return request.not_found()
                
            pdf_content = base64.b64decode(document.pdf_content)
            _logger.info(f"[LOCAL_SIMPLE] Contenido decodificado: {len(pdf_content)} bytes")
            
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(pdf_content)),
                ('Content-Disposition', f'attachment; filename="{document.name}"'),
            ]
            
            return request.make_response(pdf_content, headers=headers)
            
        except Exception as e:
            _logger.error(f"[LOCAL_SIMPLE] Error descargando documento local: {e}")
            return request.not_found()

    @http.route('/signature_workflow/descargar_multiples', type='http', auth='user')
    def descargar_multiples_documentos(self, workflow_id, **kwargs):
        """Controlador que genera una página HTML para descargar múltiples documentos"""
        _logger.info(f"[DESCARGA_MULTIPLE] ===== INICIO DESCARGA MÚLTIPLE =====")
        _logger.info(f"[DESCARGA_MULTIPLE] Workflow ID: {workflow_id}")
        
        try:
            # Obtener el workflow
            workflow = request.env['signature.workflow'].browse(int(workflow_id))
            
            if not workflow.exists():
                _logger.error(f"[DESCARGA_MULTIPLE] Workflow {workflow_id} no existe")
                return request.not_found()
            
            # Verificar permisos (solo creador o destinatario pueden descargar)
            if request.env.user not in (workflow.creator_id, workflow.target_user_id_1, workflow.target_user_id_2, workflow.target_user_id_3, workflow.target_user_id_4):
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
                if original_name.endswith(' - firmado.pdf'):
                    original_name = original_name.replace(' - firmado.pdf', '.pdf')
                elif original_name.endswith(' - firmado'):
                    original_name = original_name.replace(' - firmado', '')
                
                if documento.alfresco_file_id:
                    # Usar URL directa de Alfresco (como los botones individuales exitosos)
                    download_url = f'/alfresco/file/{documento.alfresco_file_id.id}/download'
                    _logger.info(f"[DESCARGA_MULTIPLE] Documento: {original_name} -> URL DIRECTA ALFRESCO: {download_url}")
                else:
                    # Fallback al controlador si no hay archivo de Alfresco
                    download_url = f'/signature_workflow/document/{documento.id}/download'
                    _logger.info(f"[DESCARGA_MULTIPLE] Documento: {original_name} -> URL CONTROLADOR: {download_url}")
                
                download_urls.append({
                    'url': download_url,
                    'name': original_name
                })
            
            import json
            
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
                            console.log('[JS_MULTIPLE] URL DIRECTA ALFRESCO:', downloadInfo.url);
                            
                            setTimeout(function() {{
                                // Marcar como descargando
                                const fileItem = document.getElementById('file_' + index);
                                if (fileItem) {{
                                    fileItem.classList.add('downloading');
                                    console.log('[JS_MULTIPLE] Marcado como descargando:', downloadInfo.name);
                                }}
                                
                                // Usar fetch para descargar DIRECTAMENTE desde Alfresco
                                console.log('[JS_MULTIPLE] Iniciando fetch DIRECTO a Alfresco:', downloadInfo.url);
                                fetch(downloadInfo.url)
                                    .then(function(response) {{
                                        console.log('[JS_MULTIPLE] Respuesta DIRECTA de Alfresco recibida:');
                                        console.log('[JS_MULTIPLE] - Status:', response.status);
                                        console.log('[JS_MULTIPLE] - StatusText:', response.statusText);
                                        console.log('[JS_MULTIPLE] - Headers:', Object.fromEntries(response.headers.entries()));
                                        
                                        if (!response.ok) {{
                                            throw new Error('Error HTTP DIRECTO: ' + response.status + ' - ' + response.statusText);
                                        }}
                                        return response.blob();
                                    }})
                                    .then(function(blob) {{
                                        console.log('[JS_MULTIPLE] Blob DIRECTO de Alfresco recibido:');
                                        console.log('[JS_MULTIPLE] - Tamaño:', blob.size, 'bytes');
                                        console.log('[JS_MULTIPLE] - Tipo:', blob.type);
                                        
                                        // Verificar que el blob no esté vacío
                                        if (blob.size === 0) {{
                                            throw new Error('Blob vacío recibido de Alfresco');
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
                                        
                                        console.log('[JS_MULTIPLE] ===== DESCARGA DIRECTA COMPLETADA =====');
                                        
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
                                        console.error('[JS_MULTIPLE] ===== ERROR EN DESCARGA DIRECTA =====');
                                        console.error('[JS_MULTIPLE] Error:', error);
                                        console.error('[JS_MULTIPLE] Archivo:', downloadInfo.name);
                                        console.error('[JS_MULTIPLE] URL DIRECTA:', downloadInfo.url);
                                        
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
                        console.log('[JS_MULTIPLE] ===== INICIANDO PROCESO DE DESCARGA DIRECTA =====');
                        updateProgress();
                        
                        // Descargar archivos secuencialmente
                        for (let i = 0; i < downloads.length; i++) {{
                            console.log('[JS_MULTIPLE] Procesando descarga DIRECTA', i + 1, 'de', downloads.length);
                            await downloadFile(downloads[i], i);
                        }}
                        
                        // Mostrar completado
                        console.log('[JS_MULTIPLE] ===== TODAS LAS DESCARGAS DIRECTAS COMPLETADAS =====');
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
                        console.log('[JS_MULTIPLE] DOM cargado, iniciando descargas DIRECTAS...');
                        startDownloads();
                    }});
                </script>
            </body>
            </html>
            """
            
            _logger.info(f"[DESCARGA_MULTIPLE] ===== PÁGINA HTML GENERADA CON URLs DIRECTAS =====")
            return request.make_response(html_content, headers=[('Content-Type', 'text/html')])
            
        except Exception as e:
            _logger.error(f"[DESCARGA_MULTIPLE] Error general: {e}")
            import traceback
            _logger.error(f"[DESCARGA_MULTIPLE] Traceback: {traceback.format_exc()}")
            return request.not_found()
