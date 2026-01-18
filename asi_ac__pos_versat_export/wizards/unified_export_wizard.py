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
    _description = 'Wizard para exportación unificada VERSAT desde asientos contables'
    
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
        if not move.ref:
            return False
        
        ref = move.ref.strip()
        
        if '/POS/' in ref:
            return True
        
        if ref.startswith('POS/'):
            return True
            
        if ref.startswith('POS') and any(c.isdigit() for c in ref[3:]):
            return True
            
        return False
    
    def _extract_pos_number(self, move):
        """Extrae el número de pedido POS del campo ref"""
        if not self._is_pos_move(move):
            return None
            
        ref = move.ref.strip()
        
        if '/POS/' in ref:
            ref_parts = ref.split('/')
            if len(ref_parts) >= 3:
                pos_number = ref_parts[2].split()[0]
                return f"PV-{pos_number}"
        
        elif ref.startswith('POS/'):
            pos_number = ref.split('/')[1].split()[0]
            return f"PV-{pos_number}"
            
        elif ref.startswith('POS') and any(c.isdigit() for c in ref[3:]):
            numbers = ''.join(filter(str.isdigit, ref[3:]))
            if numbers:
                return f"PV-{numbers}"
        
        return None
    
    def _get_move_base_name(self, move):
        """Obtiene el nombre base para el asiento (POS o normal)"""
        if self._is_pos_move(move):
            pos_number = self._extract_pos_number(move)
            return f"POS-{pos_number}" if pos_number else f"POS-{move.id}"
        return f"Asiento-{self._sanitize_filename(move.name or f'ID-{move.id}')}"
    
    def _format_importe(self, amount):
        """Formatea el importe: sin decimales si es entero, con 2 decimales si no lo es"""
        if amount == int(amount):
            return f"{int(amount)}"
        else:
            return f"{amount:.2f}"
    
    def _consolidate_pos_moves(self, pos_moves, config):
        """Consolida múltiples asientos POS en documentos totalizados"""
        _logger.info(f"CONSOLIDANDO {len(pos_moves)} asientos POS")
        
        total_efectivo = 0
        total_banco = 0
        total_ventas = 0
        pos_references = []
        fecha_primera = None
        
        for move in pos_moves:
            payment_amounts = self.env['account.move.versat.export']._get_pos_payment_amounts_improved(move, config)
            total_efectivo += payment_amounts['efectivo']
            total_banco += payment_amounts['banco']
            
            total_ventas += move.amount_total
            
            pos_num = self._extract_pos_number(move)
            if pos_num:
                pos_references.append(pos_num)
            
            if not fecha_primera and move.date:
                fecha_primera = move.date
        
        _logger.info(f"TOTALES CONSOLIDADOS - Efectivo: {total_efectivo}, Banco: {total_banco}, Ventas: {total_ventas}")
        
        return {
            'efectivo': total_efectivo,
            'banco': total_banco,
            'ventas': total_ventas,
            'referencias': pos_references,
            'fecha': fecha_primera
        }
    
    def _generate_consolidated_cobros(self, consolidated_data, config):
        """Genera archivos .cyp consolidados para POS"""
        cobros = []
        
        # Cobro consolidado de efectivo
        if consolidated_data['efectivo'] > 0:
            cobro_type = self.env['versat.cobro.type'].search([('tipo_deposito', '=', 'caja')], limit=1)
            if not cobro_type:
                raise UserError(_('No se encontró el tipo de cobro para caja.'))
            
            fecha_emi = consolidated_data['fecha'].strftime('%d/%m/%Y') if consolidated_data['fecha'] else ''
            numero = f"POS-CONSOLIDADO-EFECTIVO"
            
            importe_str = self._format_importe(consolidated_data['efectivo'])
            
            content = f"""Tipo={cobro_type.guid}
Unidad={config.unidad_default}
Numero={numero}
Fechaemi={fecha_emi}
Descripcion=Documento creado desde Punto de Venta
Deposito={config.cuenta_caja_efectivo}
Importe={importe_str}
EntregadoA=
[Contrapartidas]
Concepto=126
Importe={importe_str}
{{
906 |CUP|{importe_str}
}}"""
            
            cobros.append((f"{numero}.cyp", content))
            _logger.info(f"Cobro consolidado efectivo generado: {importe_str}")
        
        # Cobro consolidado de banco
        if consolidated_data['banco'] > 0:
            cobro_type = self.env['versat.cobro.type'].search([('tipo_deposito', '=', 'banco')], limit=1)
            if not cobro_type:
                raise UserError(_('No se encontró el tipo de cobro para banco.'))
            
            fecha_emi = consolidated_data['fecha'].strftime('%d/%m/%Y') if consolidated_data['fecha'] else ''
            numero = f"POS-CONSOLIDADO-BANCO"
            
            importe_str = self._format_importe(consolidated_data['banco'])
            
            content = f"""Tipo={cobro_type.guid}
Unidad={config.unidad_default}
Entidad={config.entidad_default}
Numero={numero}
Fechaemi={fecha_emi}
Descripcion=Documento creado desde Punto de Venta
Deposito={config.cuenta_caja_banco}
Importe={importe_str}
EntregadoA=
[Contrapartidas]
Concepto=126
Importe={importe_str}
{{
906 |CUP|{importe_str}
}}"""
            
            cobros.append((f"{numero}.cyp", content))
            _logger.info(f"Cobro consolidado banco generado: {importe_str}")
        
        return cobros
    
    def _generate_consolidated_aportes(self, consolidated_data, config):
        """Genera archivo .obl con aportes consolidados (1% y 10%) para POS"""
        obligaciones = []
        
        base_ventas = consolidated_data['ventas']
        if base_ventas <= 0:
            return obligaciones
        
        aporte_10 = base_ventas * 0.10
        aporte_1 = base_ventas * 0.01
        
        fecha_emi = consolidated_data['fecha'].strftime('%d/%m/%Y') if consolidated_data['fecha'] else ''
        numero_aporte = "POS-CONSOLIDADO"
        
        # Tipo para aporte 10%
        type_10 = self.env['versat.obligacion.type'].search([('code', '=', '002')], limit=1)
        # Tipo para aporte 1%
        type_1 = self.env['versat.obligacion.type'].search([('code', '=', '003')], limit=1)
        
        content = ""
        
        # Aporte 1% - PRIMERO en el archivo
        if type_1 and aporte_1 > 0:
            content += f"""[Obligacion]
Concepto={type_1.concepto}
Tipo={type_1.guid}
Unidad={config.unidad_default}
Numero={numero_aporte}
Fechaemi={fecha_emi}
Descripcion=APORTE DESARROLLO LOCAL
Fecharec=
ImporteMC={self._format_importe(aporte_1)}
CuentaMC={type_1.cuenta_mc}
[Contrapartidas]
Concepto=114
Importe={self._format_importe(aporte_1)}
{{
836113 |CUP|{self._format_importe(aporte_1)}
}}

"""
        
        # Aporte 10% - SEGUNDO en el archivo
        if type_10 and aporte_10 > 0:
            content += f"""[Obligacion]
Concepto={type_10.concepto}
Tipo={type_10.guid}
Unidad={config.unidad_default}
Numero={numero_aporte}
Fechaemi={fecha_emi}
Descripcion=IMP. 10% VENTAS
Fecharec=
ImporteMC={self._format_importe(aporte_10)}
CuentaMC={type_10.cuenta_mc}
[Contrapartidas]
Concepto=114
Importe={self._format_importe(aporte_10)}
{{
805 |CUP|{self._format_importe(aporte_10)}
}}"""
        
        if content:
            file_name = f"Doc-0-{numero_aporte}-APORTES.obl"
            obligaciones.append((file_name, content.strip()))
            _logger.info(f"Aportes consolidados generados: 1%={self._format_importe(aporte_1)}, 10%={self._format_importe(aporte_10)}")
        
        return obligaciones
    
    def action_export_unified(self):
        """Acción principal de exportación unificada"""
        self.ensure_one()
        
        active_ids = self.env.context.get('active_ids', [])
        _logger.info(f"IDs recibidos en el contexto: {active_ids}")
        
        if not active_ids:
            raise UserError(_('No se han seleccionado asientos contables para exportar.'))
        
        all_moves = self.env['account.move'].browse(active_ids).filtered(lambda m: m.state == 'posted')
        _logger.info(f"Asientos confirmados a procesar: {len(all_moves)}")
        
        if not all_moves:
            raise UserError(_('No se encontraron asientos contables confirmados para exportar.'))
        
        # Separar POS de facturas normales
        pos_moves = all_moves.filtered(lambda m: self._is_pos_move(m))
        factura_moves = all_moves.filtered(lambda m: not self._is_pos_move(m))
        
        _logger.info(f"CLASIFICACION - POS: {len(pos_moves)}, Facturas: {len(factura_moves)}")
        
        config = self._get_config()
        files_data = {}
        
        if pos_moves:
            _logger.info(f"Procesando {len(pos_moves)} asientos POS (CONSOLIDADOS)")
            
            # Consolidar todos los POS
            consolidated_data = self._consolidate_pos_moves(pos_moves, config)
            
            # Generar cobros consolidados
            cobros_consolidados = self._generate_consolidated_cobros(consolidated_data, config)
            
            # Generar aportes consolidados (1% y 10%)
            aportes_consolidados = self._generate_consolidated_aportes(consolidated_data, config)
            
            # Crear carpeta para POS consolidados
            folder_name = f"POS-Consolidado-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            files_data[folder_name] = {
                'obligaciones': aportes_consolidados,
                'cobros': cobros_consolidados
            }
            
            _logger.info(f"Carpeta POS consolidada creada: {folder_name}")
            _logger.info(f"   Obligaciones (aportes): {len(aportes_consolidados)}")
            _logger.info(f"   Cobros: {len(cobros_consolidados)}")
        
        # Procesar facturas normales individualmente
        if factura_moves:
            _logger.info(f"Procesando {len(factura_moves)} facturas normales")
            
            for move in factura_moves:
                folder_name = self._get_move_base_name(move)
                files_data[folder_name] = {
                    'obligaciones': [],
                    'cobros': []
                }
                
                _logger.info(f"Procesando factura: {move.name}")
                
                # Generar documentos para la factura
                account_docs = self.env['account.move.versat.export'].generate_account_documents(move, config)
                
                for file_name, content in account_docs['obligaciones']:
                    files_data[folder_name]['obligaciones'].append((file_name, content))
                    _logger.info(f"   Obligacion generada: {file_name}")
                
                for file_name, content in account_docs['cobros']:
                    files_data[folder_name]['cobros'].append((file_name, content))
                    _logger.info(f"   Cobro generado: {file_name}")
        
        # Verificar resultados
        total_carpetas = len(files_data)
        total_obligaciones = sum(len(data['obligaciones']) for data in files_data.values())
        total_cobros = sum(len(data['cobros']) for data in files_data.values())
        total_documentos = total_obligaciones + total_cobros
        
        _logger.info(f"Exportacion completada: {total_carpetas} carpetas, {total_documentos} documentos totales")
        _logger.info(f"   Obligaciones: {total_obligaciones}")
        _logger.info(f"   Cobros: {total_cobros}")
        
        if total_documentos == 0:
            raise UserError(_('No se generaron archivos para los asientos seleccionados.'))
        
        # Generar ZIP
        zip_data = self._generate_zip_file(files_data)
        file_name = f'versat_export_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.zip'
        attachment = self._create_attachment(zip_data, file_name)
        
        _logger.info(f"Archivo ZIP generado: {file_name}")
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
