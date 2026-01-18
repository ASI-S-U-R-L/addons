from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PosOrderVersatExport(models.Model):
    _name = 'pos.order.versat.export'
    _description = 'Funcionalidades de exportación VERSAT para pedidos POS'
    
    def _get_pos_move(self, pos_order):
        """Obtiene el asiento contable asociado a un pedido POS"""
        if pos_order.account_move:
            return pos_order.account_move
        
        # Buscar asientos por referencia
        moves = self.env['account.move'].search([
            ('ref', 'ilike', f'/POS/{pos_order.id}'),
            ('state', '=', 'posted')
        ])
        
        return moves[0] if moves else None
    
    def _generate_pos_cobro_caja(self, pos_order, config, amount):
        """Genera archivo .cyp para cobros en caja desde POS"""
        cobro_type = self.env['versat.cobro.type'].search([('tipo_deposito', '=', 'caja')], limit=1)
        if not cobro_type:
            raise UserError(_('No se encontró el tipo de cobro para caja.'))
        
        fecha_emi = pos_order.date_order.strftime('%d/%m/%Y') if pos_order.date_order else ''
        pos_number = f"PV-{pos_order.id}"
        
        content = f"""Tipo={cobro_type.guid}
Unidad={config.unidad_default}
Numero={pos_number}
Fechaemi={fecha_emi}
Descripcion=Documento creado desde Punto de Venta
Deposito={config.cuenta_caja_efectivo}
Importe={self._format_importe(amount)}
EntregadoA=
[Contrapartidas]
Concepto={cobro_type.concepto_contrapartida}
Importe={self._format_importe(amount)}
{{
{self._format_cuenta_line(cobro_type.cuenta_contrapartida, amount)}
}}"""
        
        return f"Doc-0-{pos_number}-CAJA.cyp", content
    
    def _generate_pos_cobro_banco(self, pos_order, config, amount):
        """Genera archivo .cyp para cobros en banco desde POS"""
        cobro_type = self.env['versat.cobro.type'].search([('tipo_deposito', '=', 'banco')], limit=1)
        if not cobro_type:
            raise UserError(_('No se encontró el tipo de cobro para banco.'))
        
        fecha_emi = pos_order.date_order.strftime('%d/%m/%Y') if pos_order.date_order else ''
        pos_number = f"PV-{pos_order.id}"
        
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
Concepto={cobro_type.concepto_contrapartida}
Importe={self._format_importe(amount)}
{{
{self._format_cuenta_line(cobro_type.cuenta_contrapartida, amount)}
}}"""
        
        return f"Doc-0-{pos_number}-BANCO.cyp", content
    
    def _generate_pos_aporte_ventas(self, pos_order, config):
        """Genera archivo .obl para aportes desde POS"""
        base_ventas = pos_order.amount_total
        aporte_10 = base_ventas * 0.10
        aporte_1 = base_ventas * 0.01
        
        fecha_emi = pos_order.date_order.strftime('%d/%m/%Y') if pos_order.date_order else ''
        pos_number = f"PV-{pos_order.id}"
        
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
Numero={pos_number}
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
}}

"""
        
        # Aporte 10% - SEGUNDO en el archivo
        if type_10 and aporte_10 > 0:
            content += f"""[Obligacion]
Concepto={type_10.concepto}
Tipo={type_10.guid}
Unidad={config.unidad_default}
Numero={pos_number}
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
        
        if content:
            file_name = f"Doc-0-{pos_number}-APORTES.obl"
            return [(file_name, content.strip())]
        
        return []
    
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
    
    def _detect_payment_methods_pos(self, pos_order):
        """Detecta los métodos de pago utilizados en el pedido POS"""
        payment_methods = {
            'efectivo': 0,
            'banco': 0
        }
        
        for payment in pos_order.payment_ids:
            if payment.payment_method_id.is_cash_count:
                payment_methods['efectivo'] += payment.amount
            else:
                payment_methods['banco'] += payment.amount
        
        return payment_methods
    
    def generate_pos_documents(self, pos_order, config):
        """Genera todos los documentos para un pedido POS"""
        documents = {
            'obligaciones': [],
            'cobros': []
        }
        
        # Generar documentos de cobro según métodos de pago
        payment_methods = self._detect_payment_methods_pos(pos_order)
        
        # Cobro en efectivo
        if payment_methods['efectivo'] > 0:
            file_name, content = self._generate_pos_cobro_caja(pos_order, config, payment_methods['efectivo'])
            if file_name and content:
                documents['cobros'].append((file_name, content))
        
        # Cobro en banco
        if payment_methods['banco'] > 0:
            file_name, content = self._generate_pos_cobro_banco(pos_order, config, payment_methods['banco'])
            if file_name and content:
                documents['cobros'].append((file_name, content))
        
        # Generar obligaciones de aportes
        aporte_files = self._generate_pos_aporte_ventas(pos_order, config)
        for file_name, content in aporte_files:
            documents['obligaciones'].append((file_name, content))
        
        return documents
