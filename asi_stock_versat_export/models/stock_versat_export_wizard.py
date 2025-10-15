# -*- coding: utf-8 -*-

import base64
import io
import zipfile
import re
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class StockVersatExportWizard(models.TransientModel):
    _name = 'stock.versat.export.wizard'
    _description = 'Stock VERSAT Export Wizard'

    picking_ids = fields.Many2many(
        'stock.picking',
        string='Transferencias de Stock',
        required=True,
        help='Transferencias de stock para exportar al formato VERSAT'
    )
    
    export_file = fields.Binary(
        string='Archivo de Exportación',
        readonly=True,
        help='Archivo ZIP que contiene todos los archivos .mvt'
    )
    
    export_filename = fields.Char(
        string='Nombre del Archivo',
        readonly=True,
        help='Nombre del archivo ZIP de exportación'
    )
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('done', 'Completado'),
    ], default='draft', string='Estado')

    @api.model
    def default_get(self, fields_list):
        """Obtener los pickings seleccionados del contexto"""
        res = super().default_get(fields_list)
        
        if self.env.context.get('active_model') == 'stock.picking' and self.env.context.get('active_ids'):
            picking_ids = self.env.context.get('active_ids')
            res['picking_ids'] = [(6, 0, picking_ids)]
            
        return res

    def _validate_pickings(self):
        """Validación básica - Mantener para compatibilidad"""
        if not self.picking_ids:
            raise UserError(_('No se han seleccionado transferencias para exportar.'))
    
    def _validate_pickings_state(self, pickings):
        """Validaciones específicas para pickings en estado realizado"""
        if not pickings:
            return
        
        # Verificar que todos los pickings tengan el mismo tipo de operación
        operation_types = pickings.mapped('picking_type_id.code')
        if len(set(operation_types)) > 1:
            raise UserError(_(
                'Todas las transferencias seleccionadas deben ser del mismo tipo de operación. '
                'Tipos de operación encontrados: %s'
            ) % ', '.join(set(operation_types)))
        
        # Validar que los tipos de operación tengan concepto VERSAT configurado
        missing_config = pickings.filtered(
            lambda p: not p.picking_type_id.versat_concept
        )
        if missing_config:
            picking_types = missing_config.mapped('picking_type_id.name')
            raise UserError(_(
                'Los siguientes tipos de operación no tienen concepto VERSAT configurado:\n'
                '%s\n\n'
                'Por favor, configure los conceptos VERSAT en: '
                'Almacén → Configuración → Tipos de Operación'
            ) % '\n'.join(set(picking_types)))

    def _get_versat_concept(self, picking):
        """Obtener el concepto VERSAT desde la configuración del tipo de operación"""
        if not picking.picking_type_id.versat_concept:
            raise UserError(_(
                'El tipo de operación "%s" no tiene concepto VERSAT configurado. '
                'Por favor, configure el concepto en los tipos de operación.'
            ) % picking.picking_type_id.name)
        
        return picking.picking_type_id.versat_concept

    def _get_warehouse_code(self, picking):
        """Obtener el código del almacén (2 dígitos numéricos)"""
        warehouse = picking.picking_type_id.warehouse_id
        if warehouse and warehouse.code:
            # Extraer solo números y tomar últimos 2 dígitos
            numbers = re.findall(r'\d+', warehouse.code)
            if numbers:
                return numbers[-1][-2:].zfill(2)
        return '01'  # Default a 01 si no hay código

    def _get_sequence_number(self, picking):
        """Obtener el número de secuencia del documento (sin ceros a la izquierda)"""
        if picking.name:
            numbers = re.findall(r'\d+', picking.name)
            if numbers:
                return numbers[-1]  # Sin zfill
        return '1'

    def _format_date(self, date_obj):
        """Formatear fecha para VERSAT (dd/mm/yyyy para contenido)"""
        if isinstance(date_obj, str):
            date_obj = fields.Datetime.from_string(date_obj)
        return date_obj.strftime('%d/%m/%Y')

    def _get_document_account(self, concept):
        """Obtener la cuenta principal del documento según el concepto VERSAT"""
        account_map = {
            '202': '699010 2',    # Compras
            '2100': '814',        # Ventas
            '203': '699020 2',    # Transferencias recibidas
            '2102': '699020 2',   # Transferencias enviadas
            '2107': '699010 2',   # Devoluciones
            '3116': '814',        # Ventas POS
            '3118': '814',        # Salidas
            '3119': '814',        # Entradas
        }
        return account_map.get(concept, '814')

    def _format_entity(self, partner):
        """Formatear entidad para VERSAT"""
        code = partner.ref or '0000'
        name = partner.name or ''
        state = partner.state_id.name or ''
        country = partner.country_id.name or 'CUBA'
        
        return f'{code}|{name}||||||||{state}|{country}|'

    def _get_source_warehouse(self, picking):
        """Obtener código de almacén de origen (2 dígitos)"""
        if picking.location_id.warehouse_id:
            code = picking.location_id.warehouse_id.code
            numbers = re.findall(r'\d+', code)
            if numbers:
                return numbers[-1][-2:].zfill(2)
        return '01'

    def _get_dest_warehouse(self, picking):
        """Obtener código de almacén de destino (2 dígitos)"""  
        if picking.location_dest_id.warehouse_id:
            code = picking.location_dest_id.warehouse_id.code
            numbers = re.findall(r'\d+', code)
            if numbers:
                return numbers[-1][-2:].zfill(2)
        return '01'

    def _get_num_ctrl(self, picking, concept):
        """Obtener el NumCtrl basado en el concepto VERSAT"""
        sequence_number = self._get_sequence_number(picking)
        
        num_ctrl_map = {
            '202': f'COMP/{sequence_number}',
            '2100': f'VTA/{sequence_number}',
            '203': f'TR/{sequence_number}',
            '2102': f'TE/{sequence_number}',
            '2107': f'DCOMP/{sequence_number}',
            '3116': f'SAL/{sequence_number}',
            '3118': f'SAL/{sequence_number}',
            '3119': f'ENT/{sequence_number}',
        }
        
        return num_ctrl_map.get(concept, picking.origin or picking.name)

    def _generate_mvt_content(self, picking):
        """Generar contenido .mvt para VERSAT según especificaciones"""
        concept = self._get_versat_concept(picking)
        warehouse_code = self._get_warehouse_code(picking)
        sequence_number = self._get_sequence_number(picking)
        date_str = self._format_date(picking.date_done or picking.scheduled_date)
        
        lines = []
        
        # SECCIÓN [Documento]
        lines.append('[Documento]')
        lines.append(f'Concepto={concept}')
        lines.append(f'Almacen={warehouse_code}')
        lines.append(f'Numero={sequence_number}')
        
        num_ctrl = self._get_num_ctrl(picking, concept)
        lines.append(f'NumCtrl={num_ctrl}')
        lines.append(f'Fecha={date_str}')
        
        cuenta_mn = self._get_document_account(concept)
        lines.append(f'CuentaMN={cuenta_mn}')
        
        # Descripción según tipo de operación
        if concept in ['202', '2107', '3119']:
            product_names = picking.move_ids_without_package.mapped('product_id.name')
            total_qty = sum(picking.move_ids_without_package.mapped('quantity_done'))
            if concept == '202':
                descripcion = f"COMPRA DE {', '.join(product_names[:2])}."  # Máximo 2 productos
            elif concept == '2107':
                descripcion = f"Devolucion de {total_qty} {product_names[0] if product_names else 'productos'}."
            else:  # 3119
                descripcion = ""  
        else:
            descripcion = ""  # Vacío para otros conceptos
        
        lines.append(f'Descripcion={descripcion}')
        
        # Entidad para conceptos que lo requieren
        if picking.partner_id and concept in ['202', '2100', '2107']:
            entidad = self._format_entity(picking.partner_id)
            lines.append(f'Entidad={entidad}')
        
        # Campos específicos por operación
        if concept == '202':  # Compra
            lines.append(f'Factura={picking.origin or "S/F"}')
            lines.append('Moneda=PESOS CUBANO')
            lines.append('Recargo=0')
            lines.append('Descuento=0')
            lines.append('Servicios=0')
        
        elif concept == '203':  # Transferencia recibida
            source_wh = self._get_source_warehouse(picking)
            lines.append(f'AlmacenTrans={source_wh}')
            lines.append(f'NumeroTrans={sequence_number}')  # Usar mismo número
            lines.append(f'FechaTrans={date_str}')
        
        elif concept == '2102':  # Transferencia enviada
            dest_wh = self._get_dest_warehouse(picking)
            lines.append(f'AlmacenDestino={dest_wh}')

        # Línea en blanco entre secciones
        
        # SECCIÓN [Ubicacion]
        lines.append('[Ubicacion]')
        for move in picking.move_ids_without_package.filtered(lambda m: m.state == 'done'):
            product = move.product_id
            product_code = product.default_code or product.barcode or 'SINCODIGO'
            product_name = product.name
            
            # UNIDAD DE MEDIDA SIEMPRE 'U'
            uom = 'U'
            
            # Cuenta fija 189 para ubicación según especificaciones
            product_account = '189'
            ubicacion_line = f'{product_code}|{product_name}|{uom}|{product_account}|||||0'
            lines.append(ubicacion_line)
        
        lines.append('')
        
        # SECCIÓN [Movimientos]
        lines.append('[Movimientos]')
        for move in picking.move_ids_without_package.filtered(lambda m: m.state == 'done'):
            product = move.product_id
            product_code = product.default_code or product.barcode or 'SINCODIGO'
            
            # UNIDAD DE MEDIDA SIEMPRE 'U'
            uom = 'U'
            
            quantity = move.quantity_done or move.product_uom_qty
            
            # Formatear cantidades y precios (mantener decimales si existen)
            unit_price = product.standard_price or 0.0
            total_amount = quantity * unit_price
            
            # Calcular existencia final en ubicación de destino
            final_stock_qty = product.with_context(
                location=move.location_dest_id.id
            ).qty_available
            
            # Formatear números (eliminar .0 si es entero)
            quantity_str = str(quantity).rstrip('0').rstrip('.') if quantity % 1 == 0 else str(quantity)
            unit_price_str = str(unit_price).rstrip('0').rstrip('.') if unit_price % 1 == 0 else str(unit_price)
            total_amount_str = str(total_amount).rstrip('0').rstrip('.') if total_amount % 1 == 0 else str(total_amount)
            final_stock_str = str(final_stock_qty).rstrip('0').rstrip('.') if final_stock_qty % 1 == 0 else str(final_stock_qty)
            
            movimiento_line = f'{product_code}|{uom}|{quantity_str}|{unit_price_str}|{total_amount_str}|0|0|{final_stock_str}'
            lines.append(movimiento_line)
        
        return '\n'.join(lines)

    def _generate_filename(self, picking):
        """Generar nombre de archivo .mvt según especificaciones"""
        concept = self._get_versat_concept(picking)
        warehouse_code = self._get_warehouse_code(picking)
        sequence_number = self._get_sequence_number(picking)
        date_str = (picking.date_done or picking.scheduled_date).strftime('%d-%m-%Y')
        
        filename = f'{concept}-Mov {sequence_number} Alm {warehouse_code} De {date_str}.mvt'
        return filename

    def action_export(self):
        """Acción principal para exportar los pickings - Solo exporta los realizados"""
        if not self.picking_ids:
            raise UserError(_('No se han seleccionado transferencias para exportar.'))
        
        # Filtrar solo las transferencias en estado 'done'
        done_pickings = self.picking_ids.filtered(lambda p: p.state == 'done')
        not_done_pickings = self.picking_ids.filtered(lambda p: p.state != 'done')
        
        if not done_pickings:
            raise UserError(_(
                'No hay transferencias en estado "Realizado" para exportar. '
                'Todas las transferencias seleccionadas deben estar realizadas.'
            ))
        
        # Validaciones solo para las transferencias realizadas
        self._validate_pickings_state(done_pickings)
        
        zip_buffer = io.BytesIO()
        exported_count = 0
        error_messages = []
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for picking in done_pickings:
                try:
                    mvt_content = self._generate_mvt_content(picking)
                    filename = self._generate_filename(picking)
                    zip_file.writestr(filename, mvt_content.encode('utf-8'))
                    exported_count += 1
                    
                except Exception as e:
                    error_msg = f'{picking.name}: {str(e)}'
                    error_messages.append(error_msg)
        
        zip_buffer.seek(0)
        zip_data = zip_buffer.read()
        zip_buffer.close()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f'VERSAT_Export_{timestamp}.zip'
        
        self.write({
            'export_file': base64.b64encode(zip_data),
            'export_filename': zip_filename,
            'state': 'done',
        })
        
        # Construir mensaje informativo
        message_parts = []
        
        if exported_count > 0:
            message_parts.append(_(
                '✅ Se exportaron exitosamente <strong>%d</strong> transferencias.'
            ) % exported_count)
        
        if not_done_pickings:
            not_done_names = ', '.join(not_done_pickings.mapped('name'))
            message_parts.append(_(
                '⚠️ Se omitieron <strong>%d</strong> transferencias no realizadas: %s'
            ) % (len(not_done_pickings), not_done_names))
        
        if error_messages:
            message_parts.append(_(
                '❌ Errores en <strong>%d</strong> transferencias realizadas'
            ) % len(error_messages))
            for error in error_messages:
                message_parts.append(f'   • {error}')
        
        full_message = '\n'.join(message_parts)
        
        # Mostrar notificación
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Exportación Completada'),
                'message': full_message,
                'sticky': False,
                'type': 'info' if not_done_pickings or error_messages else 'success',
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': self._name,
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'new',
                    'views': [(False, 'form')],
            }
            },
        }

    def action_download(self):
        """Acción para descargar el archivo ZIP"""
        if not self.export_file:
            raise UserError(_('No hay archivo de exportación disponible.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=stock.versat.export.wizard&id={self.id}&field=export_file&download=true&filename={self.export_filename}',
            'target': 'self',
        }