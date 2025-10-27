# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'
    
    def print_ticket_direct(self, ticket_type):
        """Impresión directa usando IoT del POS"""
        self.ensure_one()
    
        _logger.info(f"Impresión directa para {ticket_type} - Sesión: {self.name}")
    
        # Verificar configuración IoT
        if not self.config_id.iface_print_via_proxy:
            _logger.warning("IoT no configurado - usando PDF")
            return False
    
        try:
            # Generar contenido según el tipo
            content_generators = {
            'merchandise': self._generate_merchandise_ticket_content,
            'shift_balance': self._generate_shift_balance_ticket_content,
            'coins': self._generate_coins_ticket_content,
            }
        
            if ticket_type in content_generators:
                ticket_content = content_generators[ticket_type]()
            
                # Odoo se encarga de la comunicación con IoT Box
                # La IoT Box maneja el formato y envío a la impresora física
                self.env['pos.config']._print_ticket_via_proxy(ticket_content)
            
                _logger.info(f"✅ Ticket {ticket_type} enviado vía IoT")
                return True
            
        except Exception as e:
            _logger.error(f"Error en impresión IoT: {str(e)}")
    
        return False

    def action_merchandise_sales_report(self):
        """Acción para mostrar el reporte de ventas por mercancías"""
        self.ensure_one()
        
        # Crear el wizard para el reporte
        wizard = self.env['pos.merchandise.report.wizard'].create({
            'session_id': self.id,
            'date_start': self.start_at,
            'date_stop': self.stop_at or fields.Datetime.now(),
        })
        
        return {
            'name': _('Ventas por Mercancías'),
            'type': 'ir.actions.act_window',
            'res_model': 'pos.merchandise.report.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }


    def _generate_merchandise_report_on_close(self):
        """Genera el reporte de mercancías al cerrar la sesión"""
        self.ensure_one()
        
        if self.state == 'closed':
            # Crear datos para el reporte
            report_data = self._prepare_merchandise_report_data()
            
            # Generar el reporte PDF
            report = self.env.ref('asi_pos_reports.action_report_pos_merchandise_sales')
            pdf_content, _ = report._render_qweb_pdf([self.id], data=report_data)
            
            # Si hay impresora Epson conectada, intentar imprimir
            self._try_print_to_epson_printer(report_data)
            
            return True

    def _prepare_merchandise_report_data(self):
        """Prepara los datos para el reporte de mercancías"""
        self.ensure_one()
        
        # Debug: Log para verificar que se está llamando el método
        _logger.info(f"Preparando datos de reporte para sesión: {self.name}")
        
        # Obtener órdenes de la sesión
        orders = self.order_ids.filtered(lambda o: o.state in ['paid', 'done', 'invoiced'])
        _logger.info(f"Órdenes encontradas: {len(orders)}")
        
        if not orders:
            _logger.warning(f"No se encontraron órdenes pagadas en la sesión {self.name}")
            return {
                'session_name': self.name,
                'session_date': self.start_at,
                'user_name': self.user_id.name,
                'categories_data': {},
                'total_amount': 0.0,
            }
        
        # Agrupar productos por categoría
        categories_data = {}
        total_amount = 0.0
        
        for order in orders:
            _logger.info(f"Procesando orden: {order.name} con {len(order.lines)} líneas")
            for line in order.lines:
                # Obtener categoría (primero POS, luego producto, luego sin categoría)
                category = line.product_id.pos_categ_id
                if not category:
                    category = line.product_id.categ_id
                
                category_name = category.name if category else 'Sin Categoría'
                
                if category_name not in categories_data:
                    categories_data[category_name] = []
                
                # Buscar si el producto ya existe en la categoría
                existing_product = None
                for product_data in categories_data[category_name]:
                    if product_data['product_id'] == line.product_id.id:
                        existing_product = product_data
                        break
                
                line_total = line.qty * line.price_unit
                total_amount += line_total
                
                if existing_product:
                    existing_product['quantity'] += line.qty
                    existing_product['total_amount'] += line_total
                else:
                    categories_data[category_name].append({
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.name,
                        'quantity': line.qty,
                        'price_unit': line.price_unit,
                        'total_amount': line_total,
                    })
        
        _logger.info(f"Categorías procesadas: {list(categories_data.keys())}")
        _logger.info(f"Total amount: {total_amount}")
        
        return {
            'session_name': self.name,
            'session_date': self.start_at,
            'user_name': self.user_id.name,
            'categories_data': categories_data,
            'total_amount': total_amount,
        }

    def get_merchandise_report_simple_data(self):
        """Método alternativo más simple para obtener datos del reporte"""
        self.ensure_one()
        
        _logger.info(f"=== MÉTODO SIMPLE - Sesión: {self.name} ===")
        
        # Obtener órdenes pagadas
        orders = self.order_ids.filtered(lambda o: o.state in ['paid', 'done', 'invoiced'])
        _logger.info(f"Órdenes pagadas encontradas: {len(orders)}")
        
        result = {
            'session_name': self.name,
            'session_date': self.start_at,
            'user_name': self.user_id.name,
            'orders_data': [],
            'total_amount': 0.0,
        }
        
        for order in orders:
            order_data = {
                'order_name': order.name,
                'lines': []
            }
            
            for line in order.lines:
                category = line.product_id.pos_categ_id or line.product_id.categ_id
                category_name = category.name if category else 'Sin Categoría'
                line_total = line.qty * line.price_unit
                result['total_amount'] += line_total
                
                line_data = {
                    'product_name': line.product_id.name,
                    'category_name': category_name,
                    'quantity': line.qty,
                    'price_unit': line.price_unit,
                    'total': line_total,
                }
                order_data['lines'].append(line_data)
            
            if order_data['lines']:  # Solo agregar órdenes con líneas
                result['orders_data'].append(order_data)
        
        _logger.info(f"Datos preparados - Total: {result['total_amount']}, Órdenes con líneas: {len(result['orders_data'])}")
        return result

    def get_merchandise_report_grouped_data(self):
        """Método que agrupa los productos por categoría para el reporte mejorado"""
        self.ensure_one()
        
        _logger.info(f"=== MÉTODO AGRUPADO - Sesión: {self.name} ===")
        
        # Obtener órdenes pagadas
        orders = self.order_ids.filtered(lambda o: o.state in ['paid', 'done', 'invoiced'])
        _logger.info(f"Órdenes pagadas encontradas: {len(orders)}")
        
        categories_data = {}
        total_amount = 0.0
        total_orders = len(orders)
        
        for order in orders:
            for line in order.lines:
                # Obtener categoría
                category = line.product_id.pos_categ_id or line.product_id.categ_id
                category_name = category.name if category else 'Sin Categoría'
                
                # Inicializar categoría si no existe
                if category_name not in categories_data:
                    categories_data[category_name] = []
                
                # Buscar si el producto ya existe en la categoría
                existing_product = None
                for product_data in categories_data[category_name]:
                    if product_data['product_id'] == line.product_id.id:
                        existing_product = product_data
                        break
                
                line_total = line.qty * line.price_unit
                total_amount += line_total
                
                if existing_product:
                    # Sumar cantidad y total si el producto ya existe
                    existing_product['quantity'] += line.qty
                    existing_product['total_amount'] += line_total
                    
                    # Recalcular precio promedio - VALIDAR DIVISIÓN POR CERO
                    if existing_product['quantity'] != 0:
                        existing_product['price_unit'] = existing_product['total_amount'] / existing_product['quantity']
                    else:
                        # Si la cantidad es 0 (por reembolsos), mantener el precio original
                        existing_product['price_unit'] = line.price_unit
                        _logger.warning(f"Cantidad cero detectada para producto {line.product_id.name} - manteniendo precio original")
                else:
                    # Agregar nuevo producto
                    categories_data[category_name].append({
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.name,
                        'quantity': line.qty,
                        'price_unit': line.price_unit,
                        'total_amount': line_total,
                    })
        
        # Filtrar productos con cantidad 0 o negativa (resultado de reembolsos completos)
        filtered_categories_data = {}
        for category_name, products in categories_data.items():
            filtered_products = []
            for product in products:
                if product['quantity'] > 0:  # Solo incluir productos con cantidad positiva
                    filtered_products.append(product)
                else:
                    _logger.info(f"Producto filtrado por cantidad <= 0: {product['product_name']} (Qty: {product['quantity']})")
            
            if filtered_products:  # Solo incluir categorías que tengan productos
                filtered_categories_data[category_name] = filtered_products
        
        # Ordenar categorías alfabéticamente
        filtered_categories_data = dict(sorted(filtered_categories_data.items()))
        
        # Ordenar productos dentro de cada categoría alfabéticamente
        for category_name in filtered_categories_data:
            filtered_categories_data[category_name] = sorted(
                filtered_categories_data[category_name], 
                key=lambda x: x['product_name']
            )
        
        _logger.info(f"Datos agrupados - Categorías: {list(filtered_categories_data.keys())}, Total: {total_amount}")
        
        return {
            'session_name': self.name,
            'session_date': self.start_at,
            'session_close_date': self.stop_at,
            'user_name': self.user_id.name,
            'categories_data': filtered_categories_data,
            'total_amount': total_amount,
            'total_orders': total_orders,
        }

    def _try_print_to_epson_printer(self, report_data):
        """Intenta imprimir en impresora Epson si está disponible"""
        try:
            # Verificar si hay impresora configurada
            if self.config_id.iface_print_via_proxy:
                # Generar contenido para ticket
                ticket_content = self._generate_ticket_content(report_data)
                
                # Aquí se podría implementar la comunicación con la impresora Epson
                # Por ahora solo registramos en el log
                _logger.info(f"Imprimiendo ticket de mercancías para sesión {self.name}")
                _logger.info(f"Contenido del ticket:\n{ticket_content}")
                
        except Exception as e:
            _logger.warning(f"Error al imprimir en impresora Epson: {str(e)}")

    def _generate_ticket_content(self, report_data):
        """Genera el contenido del ticket en formato texto"""
        content = []
        content.append("VENTAS POR MERCANCÍAS")
        content.append("================================")
        content.append(f"Sesión: {self.name}")
        content.append(f"Fecha: {report_data['session_date'].strftime('%d/%m/%Y %H:%M')}")
        if self.stop_at:
            content.append(f"Cierre: {self.stop_at.strftime('%d/%m/%Y %H:%M')}")
        content.append(f"Usuario: {report_data['user_name']}")
        content.append("================================")
        
        for category_name, products in report_data['categories_data'].items():
            content.append(f"\n{category_name.upper()}")
            for product in products:
                qty = int(product['quantity'])
                name = product['product_name']
                total = product['total_amount']
                content.append(f"{qty} x {name} ${total:.2f}")
        
        content.append("================================")
        content.append(f"TOTAL ${report_data['total_amount']:.2f}")
        content.append("================================")
        
        return "\n".join(content)

    def _get_shift_balance_data(self):
        """Prepara los datos para el reporte de Balance de Turno"""
        self.ensure_one()
        
        # Obtener órdenes pagadas de la sesión
        orders = self.order_ids.filtered(lambda o: o.state in ['paid', 'done', 'invoiced'])
        
        # Calcular montos por método de pago
        payment_methods = {}
        total_payments = 0.0
        cash_total = 0.0
        
        for order in orders:
            for payment in order.payment_ids:
                method_name = payment.payment_method_id.name
                amount = payment.amount
                
                if method_name not in payment_methods:
                    payment_methods[method_name] = 0.0
                
                payment_methods[method_name] += amount
                total_payments += amount
                
                # Identificar pagos en efectivo
                if payment.payment_method_id.is_cash_count:
                    cash_total += amount
        
        # Convertir payment_methods a lista para el template
        payment_methods_list = [
            {'name': name, 'amount': amount} 
            for name, amount in payment_methods.items()
        ]
        
        # Calcular balance de apertura y cierre
        opening_balance = self.cash_register_balance_start or 0.0
        closing_balance = self.cash_register_balance_end_real or 0.0
        
        # Calcular efectivo (diferencia entre cierre e inicio)
        cash_amount = cash_total
        
        # Otros cálculos (por ahora en 0, se pueden implementar según necesidad)
        other_income = 0.0
        expenses = 0.0
        debts = 0.0
        service = 0.0
        discount = sum(order.amount_total - order.amount_paid for order in orders if order.amount_total > order.amount_paid)
        returns = sum(abs(order.amount_total) for order in self.order_ids.filtered(lambda o: o.amount_total < 0))
        
        # Calcular balance
        balance = cash_amount + other_income - expenses
        
        # Calcular balance final y restante
        final_balance = opening_balance  # El efectivo que queda después del retiro (igual al inicial)
        remaining = balance - cash_amount  # Balance - Retiro
        
        company = self.company_id
        company_address = f"{company.street or ''} {company.street2 or ''}, {company.city or ''}, {company.state_id.name or ''} {company.zip or ''}".strip()
        company_phone = company.phone or ''
        pos_name = self.config_id.name
        
        return {
            'session_name': self.name,
            'date': self.start_at.strftime('%d/%m/%Y') if self.start_at else '',
            'user_name': self.user_id.name,
            'empresa_name': company.name,
            'company_name': pos_name,
            'company_address': company_address,
            'company_phone': company_phone,
            'start_date': self.start_at.strftime('%d/%m/%Y %H:%M') if self.start_at else '',
            'end_date': self.stop_at.strftime('%d/%m/%Y %H:%M') if self.stop_at else 'En curso',
            'opening_balance': opening_balance,
            'cash_amount': cash_amount,
            'other_income': other_income,
            'expenses': expenses,
            'balance': balance,
            'payment_methods': payment_methods_list,
            'debts': debts,
            'service': service,
            'discount': discount,
            'returns': returns,
            'final_balance': final_balance,
            'remaining': remaining,
            'total': total_payments,
        }

    def _get_coins_data(self):
        """Prepara los datos para el reporte de Monedas"""
        self.ensure_one()
        
        _logger.info("="*80)
        _logger.info(f"[COINS REPORT] Sesión: {self.name} | Estado: {self.state}")
        
        opening_balance = self.cash_register_balance_start or 0.0
        
        # Calcular total de efectivo manejado (pagos en efectivo de todas las órdenes)
        orders = self.order_ids.filtered(lambda o: o.state in ['paid', 'done', 'invoiced'])
        cash_total = 0.0
        
        _logger.info(f"[COINS REPORT] Órdenes pagadas encontradas: {len(orders)}")
        
        for order in orders:
            for payment in order.payment_ids:
                if payment.payment_method_id.is_cash_count:
                    cash_total += payment.amount
                    _logger.info(f"[COINS REPORT]   Pago en efectivo: {payment.amount} (Orden: {order.name})")
        
        # Retiro = Total efectivo manejado - Efectivo de apertura
        withdrawal = 0.0
        
        if self.cash_real_transaction < 0: withdrawal = -1 * self.cash_real_transaction
        
        ending_cash = self.cash_register_balance_end_real
        
        _logger.info(f"[COINS REPORT] Balance apertura: {opening_balance}")
        _logger.info(f"[COINS REPORT] Total efectivo manejado: {cash_total}")
        _logger.info(f"[COINS REPORT] Retiro calculado: {withdrawal}")
        _logger.info(f"[COINS REPORT] Balance final: {ending_cash}")
        _logger.info(f"[COINS REPORT] Transaccion total: {self.cash_real_transaction}")
        
        company = self.company_id
        company_address = f"{company.street or ''} {company.street2 or ''}, {company.city or ''}, {company.state_id.name or ''} {company.zip or ''}".strip()
        company_phone = company.phone or ''
        pos_name = self.config_id.name
        
        result = {
            'session_name': self.name,
            'date': self.start_at.strftime('%d/%m/%Y') if self.start_at else '',
            'user_name': self.user_id.name,
            'empresa_name': company.name,
            'company_name': pos_name,
            'company_address': company_address,
            'company_phone': company_phone,
            'start_date': self.start_at.strftime('%d/%m/%Y %H:%M') if self.start_at else '',
            'end_date': self.stop_at.strftime('%d/%m/%Y %H:%M') if self.stop_at else 'En curso',
            'opening_balance': opening_balance,
            'withdrawal': withdrawal,
            'ending_cash': ending_cash,
        }
        
        _logger.info(f"[COINS REPORT] Resultado final - Apertura: {opening_balance} | Retiro: {withdrawal}")
        _logger.info("="*80)
        
        return result
