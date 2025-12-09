from odoo import http
from odoo.http import request, content_disposition
import base64
import logging
import tempfile
import os
from io import BytesIO
import json

_logger = logging.getLogger(__name__)

class FirmaDigitalController(http.Controller):
    
    @http.route('/firma_digital/descargar_pdf', type='http', auth='user')
    def descargar_pdf_firmado(self, pdf_id, **kwargs):
        """Controlador para descargar el PDF firmado (compatibilidad)"""
        try:
            # Obtener el registro del wizard temporal
            firma_wizard = request.env['firma.documento.wizard'].browse(int(pdf_id))
            
            if not firma_wizard.pdf_signed:
                return request.not_found()
            
            # Obtener el nombre original del documento
            nombre_original = firma_wizard.document_name or 'documento.pdf'
            nombre_base, extension = os.path.splitext(nombre_original)
            nombre_firmado = f"{nombre_base}{extension}"
            
            # Preparar la respuesta HTTP con el PDF
            pdf_content = base64.b64decode(firma_wizard.pdf_signed)
            pdfhttpheaders = [
                ('Content-Type', 'application/pdf'),  # Usar application/pdf para PDFs
                ('Content-Length', len(pdf_content)),
                ('Content-Disposition', f'attachment; filename="{nombre_firmado}"'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Pragma', 'no-cache'),
                ('Expires', '0')
            ]
            return request.make_response(pdf_content, headers=pdfhttpheaders)
            
        except Exception as e:
            _logger.error(f"Error al descargar el PDF firmado: {e}")
            return request.not_found()

    @http.route('/firma_digital/descargar_zip', type='http', auth='user')
    def descargar_zip_firmados(self, wizard_id, **kwargs):
        """Controlador para descargar el ZIP con documentos firmados"""
        try:
            # Obtener el registro del wizard
            wizard = request.env['firma.documento.wizard'].browse(int(wizard_id))
            
            if not wizard.zip_signed:
                return request.not_found()
            
            # Preparar la respuesta HTTP con el ZIP
            zip_content = base64.b64decode(wizard.zip_signed)
            zip_headers = [
                ('Content-Type', 'application/zip'),
                ('Content-Length', len(zip_content)),
                ('Content-Disposition', content_disposition(wizard.zip_name))
            ]
            return request.make_response(zip_content, headers=zip_headers)
            
        except Exception as e:
            _logger.error(f"Error al descargar el ZIP firmado: {e}")
            return request.not_found()

    @http.route('/firma_digital/descargar_individual', type='http', auth='user')
    def descargar_documento_individual(self, documento_id, **kwargs):
        """Controlador para descargar un documento individual firmado"""
        try:
            # Obtener el documento
            documento = request.env['documento.firma'].browse(int(documento_id))
            
            if not documento.pdf_signed:
                return request.not_found()
            
            # Obtener el nombre como en el ZIP
            nombre_base, extension = os.path.splitext(documento.document_name)
            if not extension:
                extension = '.pdf'
            nombre_firmado = f"{nombre_base} - firmado{extension}"
            
            # Preparar la respuesta HTTP con el PDF - FORZAR DESCARGA
            pdf_content = base64.b64decode(documento.pdf_signed)
            pdf_headers = [
                ('Content-Type', 'application/pdf'),  # Usar application/pdf para PDFs
                ('Content-Length', len(pdf_content)),
                ('Content-Disposition', f'attachment; filename="{nombre_firmado}"'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Pragma', 'no-cache'),
                ('Expires', '0'),
                ('X-Content-Type-Options', 'nosniff')  # Evitar que el navegador detecte el tipo
            ]
            return request.make_response(pdf_content, headers=pdf_headers)
            
        except Exception as e:
            _logger.error(f"Error al descargar el documento individual: {e}")
            return request.not_found()

    @http.route('/firma_digital/descargar_multiples', type='http', auth='user')
    def descargar_multiples_documentos(self, wizard_id, **kwargs):
        """Controlador que genera una página HTML para descargar múltiples documentos"""
        try:
            # Obtener el wizard
            wizard = request.env['firma.documento.wizard'].browse(int(wizard_id))
            
            # Obtener documentos firmados
            documents_signed = wizard.document_ids.filtered(lambda d: d.signature_status == 'firmado' and d.pdf_signed)
            
            if not documents_signed:
                return request.not_found()
            
            # Crear lista de URLs de descarga
            download_urls = []
            for documento in documents_signed:
                download_urls.append({
                    'url': f'/firma_digital/descargar_individual?documento_id={documento.id}',
                    'name': documento.document_name
                })
            
            # Crear lista de archivos para el HTML
            file_items_html = ""
            for i, doc in enumerate(download_urls):
                file_items_html += f'<div class="file-item" id="file_{i}">{doc["name"]}</div>\n'
            
            # Crear página HTML con JavaScript para descargas automáticas
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
                    
                    function updateProgress() {{
                        const progress = (downloaded / downloads.length) * 100;
                        document.getElementById('progress').style.width = progress + '%';
                        document.getElementById('status').textContent = 
                            'Descargados: ' + downloaded + ' de ' + downloads.length + ' documentos';
                    }}
                    
                    function downloadFile(downloadInfo, index) {{
                        return new Promise(function(resolve) {{
                            setTimeout(function() {{
                                // Marcar como descargando
                                const fileItem = document.getElementById('file_' + index);
                                if (fileItem) {{
                                    fileItem.classList.add('downloading');
                                }}
                                
                                // Usar fetch para descargar sin abrir
                                fetch(downloadInfo.url)
                                    .then(function(response) {{
                                        if (!response.ok) {{
                                            throw new Error('Error en la descarga');
                                        }}
                                        return response.blob();
                                    }})
                                    .then(function(blob) {{
                                        // Crear URL temporal para el blob
                                        const url = window.URL.createObjectURL(blob);
                                        
                                        // Crear link de descarga
                                        const link = document.createElement('a');
                                        link.href = url;
                                        link.download = downloadInfo.name;
                                        link.style.display = 'none';
                                        
                                        // Agregar al DOM y hacer click
                                        document.body.appendChild(link);
                                        link.click();
                                        
                                        // Limpiar
                                        document.body.removeChild(link);
                                        window.URL.revokeObjectURL(url);
                                        
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
                                        console.error('Error descargando:', error);
                                        if (fileItem) {{
                                            fileItem.classList.remove('downloading');
                                            fileItem.style.background = '#f8d7da';
                                            fileItem.style.borderLeftColor = '#dc3545';
                                        }}
                                        resolve();
                                    }});
                                
                            }}, index * 1000); // 1 segundo entre descargas
                        }});
                    }}
                    
                    async function startDownloads() {{
                        updateProgress();
                        
                        // Descargar archivos secuencialmente
                        for (let i = 0; i < downloads.length; i++) {{
                            await downloadFile(downloads[i], i);
                        }}
                        
                        // Mostrar completado
                        document.getElementById('spinner').style.display = 'none';
                        document.getElementById('complete').style.display = 'block';
                        
                        // Auto-cerrar después de 5 segundos
                        setTimeout(function() {{
                            window.close();
                        }}, 5000);
                    }}
                    
                    // Iniciar descargas cuando la página esté ready
                    document.addEventListener('DOMContentLoaded', startDownloads);
                </script>
            </body>
            </html>
            """
            
            return request.make_response(html_content, headers=[('Content-Type', 'text/html')])
            
        except Exception as e:
            _logger.error(f"Error en descarga múltiple: {e}")
            return request.not_found()
