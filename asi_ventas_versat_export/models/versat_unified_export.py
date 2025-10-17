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
        """Generar archivo ZIP con estructura plana - SOLO carpeta de asiento y archivos directamente"""
        if not files_data:
            raise UserError(_('No hay datos para exportar.'))
    
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for folder_name, folder_files in files_data.items():
                # Escribir cada archivo directamente en la carpeta del asiento
                for file_name, file_content in folder_files:
                    # Asegurar que file_name sea solo el nombre del archivo, sin rutas
                    clean_file_name = os.path.basename(file_name)
                    # Ruta completa: "NombreCarpeta/NombreArchivo" - sin subcarpetas
                    full_path = f"{folder_name}/{clean_file_name}"
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
    
    def _format_importe(self, amount):
        """Formatea el importe: sin decimales si es entero, con 2 decimales si no lo es"""
        if amount == int(amount):
            return f"{int(amount)}"
        else:
            return f"{amount:.2f}"
    
    def _format_cuenta_line(self, cuenta, importe):
        """Formatea la línea de cuenta con espacios EXACTOS como VERSAT"""
        cuenta_limpia = cuenta.rstrip()
        cuenta_con_espacios = cuenta_limpia + '   '
        formatted_importe = self._format_importe(importe)
        return f"{cuenta_con_espacios}|CUP|{formatted_importe}"
    
    def _detect_document_types(self, move):
        """Detecta automáticamente qué tipos de documentos generar para un asiento"""
        document_types = []
        
        # Detectar facturas de venta (obligaciones)
        if move.move_type in ['out_invoice', 'out_refund'] and move.state == 'posted':
            document_types.append('obligacion_factura')
        
        # Detectar pagos (cobros)
        payments = self.env['account.payment'].search([
            ('move_id', '=', move.id),
            ('state', '=', 'posted'),
            ('payment_type', '=', 'inbound')
        ])
        
        for payment in payments:
            if payment.journal_id.type == 'cash':
                document_types.append('cobro_caja')
            elif payment.journal_id.type == 'bank':
                document_types.append('cobro_banco')
        
        # Detectar base para aportes (ventas del período)
        if move.move_type == 'out_invoice' and move.state == 'posted':
            document_types.append('aporte_ventas')
        
        return document_types
    
    def _generate_obligacion_factura(self, move, config):
        """Genera archivo .obl para facturas con formato VERSAT exacto"""
        obligacion_type = self.env['versat.obligacion.type'].search([('code', '=', '001')], limit=1)
        if not obligacion_type:
            raise UserError(_('No se encontró el tipo de obligación para facturas.'))
        
        fecha_emi = move.invoice_date.strftime('%d/%m/%Y') if move.invoice_date else ''
        importe_mc = move.amount_residual if move.amount_residual > 0 else move.amount_total
        
        content = f"""[Obligacion]
Concepto={obligacion_type.concepto}
Tipo={obligacion_type.guid}
Unidad={config.unidad_default}
Entidad={config.entidad_default}
Numero={move.name or 'SIN-NUMERO'}
Fechaemi={fecha_emi}
Descripcion=Derecho de Cobro de la Factura: {move.name or 'SIN-NUMERO'}
Fecharec=
ImporteMC={self._format_importe(importe_mc)}
CuentaMC={obligacion_type.cuenta_mc}
[Contrapartidas]
Concepto={obligacion_type.concepto_contrapartida}
Importe={self._format_importe(importe_mc)}
{{
{self._format_cuenta_line(obligacion_type.cuenta_contrapartida, importe_mc)}
}}"""
        
        return f"Doc-0-{move.name or 'SIN-NUMERO'}-CUENTAS X COBRAR.obl", content
    
    def _generate_cobro_caja(self, move, config):
        """Genera archivo .cyp para cobros en caja con formato VERSAT exacto"""
        cobro_type = self.env['versat.cobro.type'].search([('tipo_deposito', '=', 'caja')], limit=1)
        if not cobro_type:
            raise UserError(_('No se encontró el tipo de cobro para caja.'))
        
        payment = self.env['account.payment'].search([
            ('move_id', '=', move.id),
            ('journal_id.type', '=', 'cash')
        ], limit=1)
        
        if not payment:
            return None, None
        
        fecha_emi = payment.date.strftime('%d/%m/%Y') if payment.date else ''
        numero_corto = f"O-{payment.id % 100}"
        
        content = f"""Tipo={cobro_type.guid}
Unidad={config.unidad_default}
Numero={numero_corto}
Fechaemi={fecha_emi}
Descripcion=INGRESO DE VENTAS X EFECTIVO
Deposito={config.cuenta_caja_efectivo}
Importe={self._format_importe(payment.amount)}
EntregadoA={payment.partner_id.name or 'ADMIN'}
[Contrapartidas]
Concepto={cobro_type.concepto_contrapartida}
Importe={self._format_importe(payment.amount)}
{{
{self._format_cuenta_line(cobro_type.cuenta_contrapartida, payment.amount)}
}}"""
        
        return f"Doc-0-{numero_corto}-CAJA.cyp", content
    
    def _generate_cobro_banco(self, move, config):
        """Genera archivo .cyp para cobros en banco con formato VERSAT exacto"""
        cobro_type = self.env['versat.cobro.type'].search([('tipo_deposito', '=', 'banco')], limit=1)
        if not cobro_type:
            raise UserError(_('No se encontró el tipo de cobro para banco.'))
        
        payment = self.env['account.payment'].search([
            ('move_id', '=', move.id),
            ('journal_id.type', '=', 'bank')
        ], limit=1)
        
        if not payment:
            return None, None
        
        fecha_emi = payment.date.strftime('%d/%m/%Y') if payment.date else ''
        numero_corto = f"OC-{payment.id % 100}"
        
        content = f"""Tipo={cobro_type.guid}
Unidad={config.unidad_default}
Entidad={config.entidad_default}
Numero={numero_corto}
Fechaemi={fecha_emi}
Descripcion=INGRESO DE VENTAS X TRANSFER MOVIL
Deposito={config.cuenta_caja_banco}
Importe={self._format_importe(payment.amount)}
EntregadoA={payment.partner_id.name or 'ADMIN'}
[Contrapartidas]
Concepto={cobro_type.concepto_contrapartida}
Importe={self._format_importe(payment.amount)}
{{
{self._format_cuenta_line(cobro_type.cuenta_contrapartida, payment.amount)}
}}"""
        
        return f"Doc-0-{numero_corto}-BANCO.cyp", content
    
    def _generate_aporte_ventas(self, move, config):
        """Genera archivos .obl para aportes con formato VERSAT exacto"""
        files = []
        
        if move.move_type != 'out_invoice' or move.state != 'posted':
            return files
        
        base_ventas = move.amount_untaxed_signed
        aporte_10 = base_ventas * 0.10
        aporte_1 = base_ventas * 0.01
        
        fecha_emi = move.invoice_date.strftime('%d/%m/%Y') if move.invoice_date else ''
        periodo = move.invoice_date.strftime('%m%Y') if move.invoice_date else ''
        
        # Aporte 10%
        type_10 = self.env['versat.obligacion.type'].search([('code', '=', '002')], limit=1)
        if type_10 and aporte_10 > 0:
            content_10 = f"""[Obligacion]
Concepto={type_10.concepto}
Tipo={type_10.guid}
Unidad={config.unidad_default}
Numero=AP VENT {periodo}
Fechaemi={fecha_emi}
Descripcion=IMP. 10% VENTAS
Fecharec=
ImporteMC={self._format_importe(aporte_10)}
CuentaMC={type_10.cuenta_mc}
[Contrapartidas]
Concepto={type_10.concepto_contrapartida}
Importe={self._format_importe(aporte_10)}
{{
{self._format_cuenta_line(type_10.cuenta_contrapartida, aporte_10)}
}}"""
            files.append((f"Doc-0-AP-VENT-{periodo}-APORTE-10.obl", content_10))
        
        # Aporte 1%
        type_1 = self.env['versat.obligacion.type'].search([('code', '=', '003')], limit=1)
        if type_1 and aporte_1 > 0:
            content_1 = f"""[Obligacion]
Concepto={type_1.concepto}
Tipo={type_1.guid}
Unidad={config.unidad_default}
Numero=AP VENT {periodo}
Fechaemi={fecha_emi}
Descripcion=APORTE DESARROLLO LOCAL
Fecharec=
ImporteMC={self._format_importe(aporte_1)}
CuentaMC={type_1.cuenta_mc}
[Contrapartidas]
Concepto={type_1.concepto_contrapartida}
Importe={self._format_importe(aporte_1)}
{{
{self._format_cuenta_line(type_1.cuenta_contrapartida, aporte_1)}
}}"""
            files.append((f"Doc-0-AP-VENT-{periodo}-APORTE-1.obl", content_1))
        
        return files
    
    def action_export_unified(self):
        """Acción principal de exportación unificada - VERSIÓN CORREGIDA"""
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
            folder_name = f"Asiento-{self._sanitize_filename(move.name or f'ID-{move.id}')}"
            files_data[folder_name] = []
            
            _logger.info(f"📁 Procesando asiento: {move.name} (Carpeta: {folder_name})")
            
            # Detectar tipos de documentos para ESTE asiento
            document_types = self._detect_document_types(move)
            _logger.info(f"   📄 Tipos detectados: {document_types}")
            
            documents_generated = 0
            
            for doc_type in document_types:
                try:
                    if doc_type == 'obligacion_factura':
                        file_name, content = self._generate_obligacion_factura(move, config)
                        if file_name and content:
                            files_data[folder_name].append((file_name, content))
                            documents_generated += 1
                            _logger.info(f"   ✅ Generado: {file_name}")
                    
                    elif doc_type == 'cobro_caja':
                        file_name, content = self._generate_cobro_caja(move, config)
                        if file_name and content:
                            files_data[folder_name].append((file_name, content))
                            documents_generated += 1
                            _logger.info(f"   ✅ Generado: {file_name}")
                    
                    elif doc_type == 'cobro_banco':
                        file_name, content = self._generate_cobro_banco(move, config)
                        if file_name and content:
                            files_data[folder_name].append((file_name, content))
                            documents_generated += 1
                            _logger.info(f"   ✅ Generado: {file_name}")
                    
                    elif doc_type == 'aporte_ventas':
                        aporte_files = self._generate_aporte_ventas(move, config)
                        for file_name, content in aporte_files:
                            files_data[folder_name].append((file_name, content))
                            documents_generated += 1
                            _logger.info(f"   ✅ Generado: {file_name}")
                            
                except Exception as e:
                    _logger.error(f"❌ Error generando {doc_type} para asiento {move.name}: {str(e)}")
                    continue
            
            # Si no se generaron documentos, crear archivo informativo
            if documents_generated == 0:
                info_content = f"No se generaron documentos VERSAT para el asiento: {move.name}\n"
                info_content += f"Fecha: {move.date if move.date else 'N/A'}\n"
                info_content += f"Tipo: {move.move_type}\n"
                info_content += f"Estado: {move.state}"
                
                files_data[folder_name].append(("INFO-SIN-DOCUMENTOS.txt", info_content))
                _logger.info(f"   ℹ️  Sin documentos, agregado archivo informativo")
        
        # Verificar resultados
        total_carpetas = len(files_data)
        total_documentos = sum(len(archivos) for archivos in files_data.values())
        
        _logger.info(f"🎉 Exportación completada: {total_carpetas} carpetas, {total_documentos} documentos totales")
        
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