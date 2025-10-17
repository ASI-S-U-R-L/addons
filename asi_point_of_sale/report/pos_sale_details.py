# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from decimal import Decimal, ROUND_HALF_UP


_logger = logging.getLogger(__name__)

class ReportSaleDetails(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'
    
    

    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False):      
        """ Sobrescribimos este método para agregar información de costos y ganancias """
        _logger.debug("Iniciando get_sale_details con parámetros: date_start=%s, date_stop=%s, config_ids=%s, session_ids=%s", 
                     date_start, date_stop, config_ids, session_ids)
        
        '''def truncate(numero, decimales = 0):
            """ Función interna para evitar el uso de una dependencia externa para redondear truncando. """
            multiplicador = 10**decimales
            if (numero-trunc(numero))*100 == 0:
                return numero
            return int(numero*multiplicador) / multiplicador  '''
        
        res = super(ReportSaleDetails, self).get_sale_details(date_start, date_stop, config_ids, session_ids)
        
        _logger.debug("Resultado original de get_sale_details: %s", res)
        
        orders = self.env['pos.order'].search([
            ('state', 'in', ['paid', 'invoiced', 'done']),
            ('date_order', '>=', date_start),
            ('date_order', '<=', date_stop)
        ])
        
        if config_ids:
            orders = orders.filtered(lambda o: o.config_id.id in config_ids)
        if session_ids:
            orders = orders.filtered(lambda o: o.session_id.id in session_ids)
        
        _logger.debug("Órdenes encontradas: %s", orders)
        
        # Modificamos la lista de productos para incluir información de costos
        products_with_cost = []
        total_cost = 0.0
        total_cost_subtotal = 0.0
        total_profit = 0.0
        total_profit_with_tax = 0.0
        
        # Obtener el total de impuestos
        total_taxes = sum(tax['tax_amount'] for tax in res.get('taxes', []))
        _logger.debug("Total de impuestos: %s", total_taxes)
        
        for product_item in res.get('products', []):
            product = self.env['product.product'].browse(product_item.get('product_id'))
            cost = product.standard_price or 0.0
            quantity = int(product_item.get('quantity', 0.0))
            price_unit = product_item.get('price_unit', 0.0)
            discount = product_item.get('discount', 0.0)
        
            # Calculamos el precio x cantidad (con descuento)
            descuento = (discount/100*price_unit*quantity)
            price_quantity = round(price_unit * quantity - descuento, 2)
        
            # Calculamos con descuento aplicado
            cost_subtotal = round(cost * quantity, 2)
            price_subtotal = round(quantity * price_unit * (1 - (discount or 0.0) / 100.0), 2)
            profit = round(price_subtotal - cost_subtotal, 2)
        
            # Calculamos la proporción de impuestos para este producto
            # Asumimos que los impuestos se distribuyen proporcionalmente al precio de venta
            product_ratio = price_subtotal / res.get('total_paid', 1.0)
            product_taxes = round(total_taxes * product_ratio, 2)
        
            # Ganancia incluyendo impuestos
            profit_with_tax = round(profit + product_taxes, 2)
        
            cost= round(cost,2)
            cost = Decimal(str(cost)) 
            cost = cost.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            
            cost_subtotal= round(cost_subtotal,2)
            cost_subtotal = Decimal(str(cost_subtotal))
            cost_subtotal = cost_subtotal.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            
            price_quantity= round(price_quantity,2)
            price_quantity = Decimal(str(price_quantity))
            price_quantity = price_quantity.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            
            profit= round(profit,2)
            profit = Decimal(str(profit))
            profit = profit.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            
            profit_with_tax= round(profit_with_tax,2)
            profit_with_tax = Decimal(str(profit_with_tax))
            profit_with_tax = profit_with_tax.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            
            price_unit = Decimal(str(price_unit))
            price_unit = price_unit.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            
            quantity = Decimal(str(quantity))
            quantity = quantity.quantize(Decimal("0"), rounding=ROUND_HALF_UP)
        
            product_item.update({
                'quantity': quantity,
                'price_unit': price_unit,
                'cost': cost,
                'cost_subtotal': cost_subtotal,
                'price_quantity': price_quantity,
                'profit': profit,
                'profit_with_tax': profit_with_tax,
            })
        
            products_with_cost.append(product_item)
            total_cost += float(cost)
            total_cost_subtotal += float(cost_subtotal)
            total_profit += float(profit)
            total_profit_with_tax += float(profit_with_tax)
            
        total_cost = Decimal(str(round(total_cost, 2)))
        total_cost = total_cost.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        
        total_cost_subtotal = Decimal(str(round(total_cost_subtotal, 2)))
        total_cost_subtotal = total_cost_subtotal.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        
        total_profit = Decimal(str(round(total_profit, 2)))
        total_profit = total_profit.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        
        total_profit_with_tax = Decimal(str(round(total_profit_with_tax, 2)))
        total_profit_with_tax = total_profit_with_tax.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    
        res['products'] = products_with_cost
        res['total_cost'] = total_cost
        res['total_cost_subtotal'] = total_cost_subtotal
        res['total_profit'] = total_profit
        res['total_profit_with_tax'] = total_profit_with_tax
    
        _logger.debug("Resultado final de get_sale_details: %s", res)
        
        return res

    @api.model
    def _get_report_values(self, docids, data=None):
        """Sobrescribimos este método para asegurarnos de que formatLang esté disponible"""
        _logger.debug("Iniciando _get_report_values con parámetros: docids=%s, data=%s", docids, data)
        
        data = dict(data or {})
        # initialize data keys with their value if provided, else None
        data.update({
            'session_ids': data.get('session_ids') or (docids if not data.get('config_ids') and not data.get('date_start') and not data.get('date_stop') else None),
            'config_ids': data.get('config_ids'),
            'date_start': data.get('date_start'),
            'date_stop': data.get('date_stop'),
            'inicio': data.get('inicio')  # Agregar el campo inicio igual que en el módulo de inventario
        })
        
        # Obtener los objetos de configuración de POS en lugar de solo los IDs
        if data.get('config_ids'):
            configs = self.env['pos.config'].browse(data['config_ids'])
            data['config_ids'] = configs  # Pasar los objetos completos
        else:
            # Si no hay config_ids específicos, obtener todos los puntos de venta
            configs = self.env['pos.config'].search([])
            data['config_ids'] = configs
        
        data.update(self.get_sale_details(data['date_start'], data['date_stop'], configs.ids, data['session_ids']))
        
        # Asegurarnos de que formatLang esté disponible
        if not data.get('formatLang'):
            data['formatLang'] = lambda *args, **kwargs: self.env['ir.qweb.field.monetary'].value_to_html(args[0], kwargs)
        
        _logger.debug("Resultado final de _get_report_values: %s", data)
        
        return data
