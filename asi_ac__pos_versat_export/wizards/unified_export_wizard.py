from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import io
import zipfile
from datetime import datetime
import logging
import re
import os

_logger = logging.getLogger(__name__)

class VersatUnifiedExportWizard(models.TransientModel):
    _name = 'versat.unified.export.wizard'
    _description = 'Wizard para exportación unificada VERSAT desde asientos contables y POS'
    
    def _get_config(self):
        return self.env['versat.finanzas.config'].get_default_config()
    
    def _generate_zip_file(self, files_data):
        """Generar archivo ZIP con estructura de carpetas exacta"""
        if not files_data:
            raise UserError(_('No hay datos para exportar.'))
    
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for folder_name, folder_structure in files_data.items():
                # Carpeta de Obligaciones
                if folder_structure.get('obligaciones'):
                    for file_name, file_content in folder_structure['obligaciones']:
                        full_path = f"{folder_name}/Obligaciones/{file_name}"
                        zip_file.writestr(full_path, file_content.encode('utf-8'))
                
                # Carpeta de Cobros
                if folder_structure.get('cobros'):
                    for file_name, file_content in folder_structure['cobros']:
                        full_path = f"{folder_name}/Cobros/{file_name}"
                        zip_file.writestr(full_path, file_content.encode('utf-8'))

        zip_buffer.seek(0)
        return base64.b64encode(zip_buffer.getvalue())
    
    def _create_attachment(self, zip_data, file_name):
        return self.env['ir.attachment'].create({
            'name': file_name,
            'datas': zip_data,
            'type': 'binary',
            'mimetype': 'application/zip'
        })
    
    def _sanitize_filename(self, name):
        """Limpia el nombre para usarlo como carpeta"""
        return re.sub(r'[^\w\-_.]', '_', name)
    
    def _is_pos_move(self, move):
        """Determina si un asiento viene de un pedido POS"""
        if move.ref and '/POS/' in move.ref:
            return True
        return False
    
    def _extract_pos_number(self, move):
        """Extrae el número de pedido POS del campo ref"""
        if not self._is_pos_move(move):
            return None
            
        ref_parts = move.ref.split('/')
        if len(ref_parts) >= 3:
            pos_number = ref_parts[2].split()[0]
            return f"PV-{pos_number}"
        return None
    
    def _get_move_base_name(self, move):
        """Obtiene el nombre base para el asiento (POS o normal)"""
        if self._is_pos_move(move):
            pos_number = self._extract_pos_number(move)
            return f"POS-{pos_number}" if pos_number else f"POS-{move.id}"
        return f"Asiento-{self._sanitize_filename(move.name or f'ID-{move.id}')}"
    
    def action_export_unified(self):
        """Acción principal de exportación unificada - VERSIÓN FINAL CORREGIDA"""
        self.ensure_one()
        
        # Obtener TODOS los asientos contables seleccionados del contexto
        active_ids = self.env.context.get('active_ids', [])
        _logger.info(f"🔍 IDs recibidos en el contexto: {active_ids}")
        
        if not active_ids:
            raise UserError(_('No se han seleccionado asientos contables para exportar.'))
        
        moves = self.env['account.move'].browse(active_ids).filtered(lambda m: m.state == 'posted')
        _logger.info(f"📊 Asientos confirmados a procesar: {len(moves)}")
        
        if not moves:
            raise UserError(_('No se encontraron asientos contables confirmados para exportar.'))
        
        config = self._get_config()
        files_data = {}
        
        _logger.info(f"🚀 Iniciando exportación de {len(moves)} asientos contables")
        
        for move in moves:
            folder_name = self._get_move_base_name(move)
            files_data[folder_name] = {
                'obligaciones': [],
                'cobros': []
            }
            
            _logger.info(f"📁 Procesando asiento: {move.name} (Carpeta: {folder_name})")
            _logger.info(f"   🔍 Referencia: {move.ref}")
            _logger.info(f"   🏷️  Tipo POS: {self._is_pos_move(move)}")
            
            documents_generated = 0
            
            # Usar la lógica de account_export para generar documentos
            account_docs = self.env['account.move.versat.export'].generate_account_documents(move, config)
            
            # Agregar documentos a la estructura
            for file_name, content in account_docs['obligaciones']:
                files_data[folder_name]['obligaciones'].append((file_name, content))
                documents_generated += 1
                _logger.info(f"   ✅ Obligación generada: {file_name}")
            
            for file_name, content in account_docs['cobros']:
                files_data[folder_name]['cobros'].append((file_name, content))
                documents_generated += 1
                _logger.info(f"   ✅ Cobro generado: {file_name}")
            
            # Si no se generaron documentos, crear archivo informativo
            if documents_generated == 0:
                info_content = f"No se generaron documentos VERSAT para el asiento: {move.name}\n"
                info_content += f"Referencia: {move.ref}\n"
                info_content += f"Fecha: {move.date if move.date else 'N/A'}\n"
                info_content += f"Tipo: {move.move_type}\n"
                info_content += f"Estado: {move.state}\n"
                info_content += f"Es POS: {'Sí' if self._is_pos_move(move) else 'No'}"
                
                files_data[folder_name]['obligaciones'].append(("INFO-SIN-DOCUMENTOS.txt", info_content))
                _logger.info(f"   ℹ️  Sin documentos, agregado archivo informativo")
        
        # Verificar resultados
        total_carpetas = len(files_data)
        total_obligaciones = sum(len(data['obligaciones']) for data in files_data.values())
        total_cobros = sum(len(data['cobros']) for data in files_data.values())
        total_documentos = total_obligaciones + total_cobros
        
        _logger.info(f"🎉 Exportación completada: {total_carpetas} carpetas, {total_documentos} documentos totales")
        _logger.info(f"   📄 Obligaciones: {total_obligaciones}")
        _logger.info(f"   💰 Cobros: {total_cobros}")
        
        if total_documentos == 0:
            raise UserError(_('No se generaron archivos para los asientos seleccionados.'))
        
        # Generar ZIP
        zip_data = self._generate_zip_file(files_data)
        file_name = f'versat_export_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.zip'
        attachment = self._create_attachment(zip_data, file_name)
        
        _logger.info(f"📦 Archivo ZIP generado: {file_name}")
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }