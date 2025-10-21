from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import re

_logger = logging.getLogger(__name__)

class AccountMoveVersatExport(models.Model):
    _name = 'account.move.versat.export'
    _description = 'Funcionalidades de exportación VERSAT para asientos contables'
    
    def _is_pos_move(self, move):
        """Determina si un asiento viene de un pedido POS - CORREGIDO para múltiples formatos"""
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
        """Extrae el número de pedido POS del campo ref - CORREGIDO para múltiples formatos"""
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
            return pos_number or f"POS-{move.id}"
        return move.name or f"ASIENTO-{move.id}"
    
    def _format_importe(self, amount):
        """Formatea el importe: sin decimales si es entero, con 2 decimales si no lo es"""
        if amount == int(amount):
            return f"{int(amount)}"
        else:
            return f"{amount:.2f}"
    
    def _format_cuenta_line(self, cuenta, importe):
        """Formatea la línea de cuenta con espacio EXACTO como VERSAT"""
        cuenta_limpia = cuenta.rstrip()
        
        cuenta_con_espacio = cuenta_limpia + ' '
        formatted_importe = self._format_importe(importe)
        return f"{cuenta_con_espacio}|CUP|{formatted_importe}"
    
    def _get_pos_payment_amounts_improved(self, move, config):
        """Obtiene los montos de pago para asientos POS - VERSIÓN COMPLETAMENTE REVISADA"""
        cash_amount = 0
        bank_amount = 0
    
        _logger.info(f"🔍 INICIANDO ANÁLISIS DETALLADO DEL POS: {move.name}")
        _logger.info(f"   📋 Referencia: {move.ref}")
        _logger.info(f"   💰 Total del asiento: {move.amount_total}")
        _logger.info(f"   🏦 Cuenta caja configurada: {config.cuenta_caja_efectivo}")
        _logger.info(f"   🏦 Cuenta banco configurada: {config.cuenta_caja_banco}")
    
        
    
        lineas_credito = []
        lineas_debito = []
    
        for line in move.line_ids:
            account_code = line.account_id.code or ''
            account_name = (line.account_id.name or '').lower()
        
            _logger.info(f"   📊 Línea: {account_code} | {account_name} | Débito: {line.debit} | Crédito: {line.credit}")
        
            if line.credit > 0:
                lineas_credito.append(line)
                _logger.info(f"   📈 Línea de CRÉDITO: {account_code} - {line.credit}")
        
            if line.debit > 0:
                lineas_debito.append(line)
                _logger.info(f"   📉 Línea de DÉBITO: {account_code} - {line.debit}")
    
        
        linea_ingreso = None
        for line in lineas_credito:
            if line.account_id.code == '906':
                linea_ingreso = line
                _logger.info(f"   ✅ LÍNEA DE INGRESO 906 ENCONTRADA: {line.credit}")
                break
    
        
        if not linea_ingreso and lineas_credito:
            linea_ingreso = lineas_credito[0]
            _logger.info(f"   ℹ️  Usando primera línea de crédito como ingreso: {linea_ingreso.account_id.code} - {linea_ingreso.credit}")
    
        # Procesar líneas de débito (pagos)
        for line in lineas_debito:
            account_code = line.account_id.code or ''
            account_name = (line.account_id.name or '').lower()
        
            
            if account_code == config.cuenta_caja_efectivo.strip():
                cash_amount += line.debit
                _logger.info(f"   ✅✅✅ EFECTIVO DETECTADO por código exacto configurado: {line.debit}")
                continue
        
            if account_code == config.cuenta_caja_banco.strip():
                bank_amount += line.debit
                _logger.info(f"   ✅✅✅ BANCO DETECTADO por código exacto configurado: {line.debit}")
                continue
        
            
            if any(word in account_name for word in ['caja', 'efectivo', 'cash']):
                cash_amount += line.debit
                _logger.info(f"   ✅ EFECTIVO DETECTADO por nombre de cuenta: {line.debit}")
                continue
        
            if any(word in account_name for word in ['banco', 'bank', 'transfer', 'tarjeta', 'card']):
                bank_amount += line.debit
                _logger.info(f"   ✅ BANCO DETECTADO por nombre de cuenta: {line.debit}")
                continue
        
            
            if move.journal_id and 'pos' in move.journal_id.name.lower():
                # En POS, las líneas de débito que no son impuestos suelen ser pagos
                if 'tax' not in account_name and 'impuesto' not in account_name:
                    cash_amount += line.debit
                    _logger.info(f"   ℹ️  EFECTIVO ASUMIDO por débito en POS: {line.debit}")
    
        
        if cash_amount == 0 and bank_amount == 0 and linea_ingreso:
            total_ingreso = linea_ingreso.credit
            _logger.info(f"   ⚠️  No se detectaron pagos específicos, usando ingreso como efectivo: {total_ingreso}")
            cash_amount = total_ingreso
    
        # Validación final
        total_detectado = cash_amount + bank_amount
        if linea_ingreso and abs(total_detectado - linea_ingreso.credit) > 0.01:
            _logger.warning(f"   ⚠️  DISCREPANCIA: Débitos detectados ({total_detectado}) ≠ Crédito ingreso ({linea_ingreso.credit})")
    
        _logger.info(f"💰 RESUMEN FINAL: Efectivo={cash_amount}, Banco={bank_amount}")
        return {
            'efectivo': cash_amount,
            'banco': bank_amount
        }
    
    def _detect_document_types_account(self, move, config):
        """Detecta automáticamente qué tipos de documentos generar - VERSIÓN MEJORADA"""
        document_types = []
    
        _logger.info(f"🔍 INICIANDO DETECCIÓN PARA: {move.name}")
        _logger.info(f"   📋 Referencia: {move.ref}")
        _logger.info(f"   🏷️  Tipo: {move.move_type}")
    
        # Detectar POS
        is_pos = self._is_pos_move(move)
        _logger.info(f"   🎯 Es POS: {is_pos}")
    
        # SOLO facturas generan obligacion_factura
        if move.move_type in ['out_invoice', 'out_refund'] and move.state == 'posted' and not is_pos:
            document_types.append('obligacion_factura')
            _logger.info(f"   ✅ Añadido obligacion_factura para factura")
    
        # Para POS: SIEMPRE buscar cobros
        if is_pos and move.state == 'posted':
            _logger.info(f"   🔍 BUSCANDO PAGOS POS (BÚSQUEDA AGRESIVA)...")
            payment_amounts = self._get_pos_payment_amounts_improved(move, config)
        
            # FORZAR generación de cobro si hay algún monto detectado
            if payment_amounts['efectivo'] > 0:
                document_types.append('cobro_caja')
                _logger.info(f"   ✅✅✅ Añadido cobro_caja (efectivo: {payment_amounts['efectivo']})")
            else:
                _logger.info(f"   ❌ No se añadió cobro_caja (efectivo: 0)")
        
            if payment_amounts['banco'] > 0:
                document_types.append('cobro_banco') 
                _logger.info(f"   ✅✅✅ Añadido cobro_banco (banco: {payment_amounts['banco']})")
            else:
                _logger.info(f"   ❌ No se añadió cobro_banco (banco: 0)")
            
            
            if not any(doc in document_types for doc in ['cobro_caja', 'cobro_banco']) and move.amount_total > 0:
                _logger.info(f"   ⚠️  FORZANDO cobro_caja porque es POS con total > 0")
                document_types.append('cobro_caja')
            
        else:
            # Lógica normal para facturas
            payments = self.env['account.payment'].search([
                ('move_id', '=', move.id),
                ('state', '=', 'posted'),
                ('payment_type', '=', 'inbound')
            ])
        
            for payment in payments:
                if payment.journal_id.type == 'cash':
                    document_types.append('cobro_caja')
                    _logger.info(f"   ✅ Añadido cobro_caja (pago: {payment.amount})")
                elif payment.journal_id.type == 'bank':
                    document_types.append('cobro_banco')
                    _logger.info(f"   ✅ Añadido cobro_banco (pago: {payment.amount})")
    
        # Aportes para POS y facturas
        if (move.move_type == 'out_invoice' and move.state == 'posted') or \
            (is_pos and move.state == 'posted'):
            document_types.append('aporte_ventas')
            _logger.info(f"   ✅ Añadido aporte_ventas")
    
        _logger.info(f"📄 DOCUMENTOS FINALES: {document_types}")
        return document_types
    
    def _generate_obligacion_factura_account(self, move, config):
        """Genera archivo .obl para facturas con formato VERSAT exacto"""
        obligacion_type = self.env['versat.obligacion.type'].search([('code', '=', '001')], limit=1)
        if not obligacion_type:
            raise UserError(_('No se encontró el tipo de obligación para facturas.'))
        
        fecha_emi = move.invoice_date.strftime('%d/%m/%Y') if move.invoice_date else move.date.strftime('%d/%m/%Y') if move.date else ''
        
        # SOLO para facturas (no POS)
        importe_mc = move.amount_residual if move.amount_residual > 0 else move.amount_total
        descripcion = f"Derecho de Cobro de la Factura: {move.name or 'SIN-NUMERO'}"
        numero = move.name or 'SIN-NUMERO'
        
        content = f"""[Obligacion]
Concepto={obligacion_type.concepto}
Tipo={obligacion_type.guid}
Unidad={config.unidad_default}
Entidad={config.entidad_default}
Numero={numero}
Fechaemi={fecha_emi}
Descripcion={descripcion}
Fecharec=
ImporteMC={self._format_importe(importe_mc)}
CuentaMC={obligacion_type.cuenta_mc}
[Contrapartidas]
Concepto={obligacion_type.concepto_contrapartida}
Importe={self._format_importe(importe_mc)}
{{
{self._format_cuenta_line(obligacion_type.cuenta_contrapartida, importe_mc)}
}}"""
        
        return f"Doc-0-{numero}-CUENTAS-X-COBRAR.obl", content
    
    def _generate_cobro_caja_account(self, move, config):
        """Genera archivo .cyp para cobros en caja con formato VERSAT exacto"""
        cobro_type = self.env['versat.cobro.type'].search([('tipo_deposito', '=', 'caja')], limit=1)
        if not cobro_type:
            raise UserError(_('No se encontró el tipo de cobro para caja.'))
    
        # Para POS, obtener monto de las líneas del asiento
        if self._is_pos_move(move):
            
            payment_amounts = self._get_pos_payment_amounts_improved(move, config)
            amount = payment_amounts['efectivo']
            if amount <= 0:
                _logger.info(f"   ❌ No se generó cobro caja para POS {move.name} porque el monto de efectivo es 0")
                return None, None
        
            fecha_emi = move.date.strftime('%d/%m/%Y') if move.date else ''
            pos_number = self._extract_pos_number(move) or f"PV-{move.id}"
        
            # FORMATO EXACTO PARA POS
            content = f"""Tipo={cobro_type.guid}
Unidad={config.unidad_default}
Numero={pos_number}
Fechaemi={fecha_emi}
Descripcion=Documento creado desde Punto de Venta
Deposito={config.cuenta_caja_efectivo}
Importe={self._format_importe(amount)}
EntregadoA=
[Contrapartidas]
Concepto=126
Importe={self._format_importe(amount)}
{{
906 |CUP|{self._format_importe(amount)}
}}"""
        
            return f"Doc-0-{pos_number}-CAJA.cyp", content
        else:
            # Lógica original para contabilidad normal
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
Descripcion=Documento creado desde Punto de Venta
Deposito={config.cuenta_caja_efectivo}
Importe={self._format_importe(payment.amount)}
EntregadoA=
[Contrapartidas]
Concepto={cobro_type.concepto_contrapartida}
Importe={self._format_importe(payment.amount)}
{{
{self._format_cuenta_line(cobro_type.cuenta_contrapartida, payment.amount)}
}}"""
        
            return f"Doc-0-{numero_corto}-CAJA.cyp", content
    
    def _generate_cobro_banco_account(self, move, config):
        """Genera archivo .cyp para cobros en banco con formato VERSAT exacto"""
        cobro_type = self.env['versat.cobro.type'].search([('tipo_deposito', '=', 'banco')], limit=1)
        if not cobro_type:
            raise UserError(_('No se encontró el tipo de cobro para banco.'))
        
        # Para POS, obtener monto de las líneas del asiento
        if self._is_pos_move(move):
            payment_amounts = self._get_pos_payment_amounts_improved(move)
            amount = payment_amounts['banco']
            if amount <= 0:
                _logger.info(f"   ❌ No se generó cobro banco para POS {move.name} porque el monto de banco es 0")
                return None, None
            
            fecha_emi = move.date.strftime('%d/%m/%Y') if move.date else ''
            pos_number = self._extract_pos_number(move) or f"PV-{move.id}"
            
            # FORMATO EXACTO PARA POS
            content = f"""Tipo={cobro_type.guid}
Unidad={config.unidad_default}
Entidad={config.entidad_default}
Numero={pos_number}
Fechaemi={fecha_emi}
Descripcion=Documento creado desde Punto de Venta
Deposito={config.cuenta_caja_banco}
Importe={self._format_importe(amount)}
EntregadoA=
[Contrapartidas]
Concepto=126
Importe={self._format_importe(amount)}
{{
906 |CUP|{self._format_importe(amount)}
}}"""
            
            return f"Doc-0-{pos_number}-BANCO.cyp", content
        else:
            # Lógica original para contabilidad normal
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
Descripcion=Documento creado desde Punto de Venta
Deposito={config.cuenta_caja_banco}
Importe={self._format_importe(payment.amount)}
EntregadoA=
[Contrapartidas]
Concepto={cobro_type.concepto_contrapartida}
Importe={self._format_importe(payment.amount)}
{{
{self._format_cuenta_line(cobro_type.cuenta_contrapartida, payment.amount)}
}}"""
            
            return f"Doc-0-{numero_corto}-BANCO.cyp", content
    
    def _generate_aporte_ventas_account(self, move, config):
        """Genera archivo .obl para aportes con formato VERSAT exacto (AMBOS en mismo archivo)"""
        if (move.move_type != 'out_invoice' and not self._is_pos_move(move)) or move.state != 'posted':
            return []
        
        # Para POS, usar el total del asiento
        if self._is_pos_move(move):
            base_ventas = move.amount_total
        else:
            base_ventas = move.amount_untaxed_signed
            
        aporte_10 = base_ventas * 0.10
        aporte_1 = base_ventas * 0.01
        
        fecha_emi = move.invoice_date.strftime('%d/%m/%Y') if move.invoice_date else move.date.strftime('%d/%m/%Y') if move.date else ''
        
        # Para POS, usar número POS, para contabilidad normal usar número de factura
        if self._is_pos_move(move):
            pos_number = self._extract_pos_number(move) or f"PV-{move.id}"
            numero_aporte = pos_number
        else:
            numero_aporte = move.name or f"F-{move.id}"
        
        # Tipo para aporte 10%
        type_10 = self.env['versat.obligacion.type'].search([('code', '=', '002')], limit=1)
        # Tipo para aporte 1%
        type_1 = self.env['versat.obligacion.type'].search([('code', '=', '003')], limit=1)
        
        content = ""
        
        # Aporte 1% - PRIMERO en el archivo (como en el ejemplo)
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
            return [(file_name, content.strip())]
        
        return []
    
    def generate_account_documents(self, move, config):
        """Genera todos los documentos para un asiento contable - CORREGIDA para POS"""
        documents = {
            'obligaciones': [],
            'cobros': []
        }
        
        # Detectar tipos de documentos
        doc_types = self._detect_document_types_account(move, config)
        _logger.info(f"📄 Tipos de documentos detectados para {move.name}: {doc_types}")
        
        for doc_type in doc_types:
            try:
                if doc_type == 'obligacion_factura':
                    # SOLO generar para facturas, NO para POS
                    if not self._is_pos_move(move):
                        file_name, content = self._generate_obligacion_factura_account(move, config)
                        if file_name and content:
                            documents['obligaciones'].append((file_name, content))
                            _logger.info(f"   ✅ Generado obligacion_factura: {file_name}")
                    else:
                        _logger.info(f"   ⏭️  Saltando obligacion_factura para POS")
                
                elif doc_type == 'cobro_caja':
                    file_name, content = self._generate_cobro_caja_account(move, config)
                    if file_name and content:
                        documents['cobros'].append((file_name, content))
                        _logger.info(f"   ✅ Generado cobro_caja: {file_name}")
                
                elif doc_type == 'cobro_banco':
                    file_name, content = self._generate_cobro_banco_account(move, config)
                    if file_name and content:
                        documents['cobros'].append((file_name, content))
                        _logger.info(f"   ✅ Generado cobro_banco: {file_name}")
                
                elif doc_type == 'aporte_ventas':
                    aporte_files = self._generate_aporte_ventas_account(move, config)
                    for file_name, content in aporte_files:
                        documents['obligaciones'].append((file_name, content))
                        _logger.info(f"   ✅ Generado aporte_ventas: {file_name}")
                        
            except Exception as e:
                _logger.error(f"❌ Error generando {doc_type} para asiento {move.name}: {str(e)}")
                continue
        
        return documents