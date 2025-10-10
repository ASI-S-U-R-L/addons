# addons\sgichs_core2\models\it_asset_backlog.py:
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json # Importante añadir json
import logging

_logger = logging.getLogger(__name__)

class ITAssetBacklog(models.Model):
    _name = 'it.asset.backlog'
    _description = 'Backlog de Activos de TI'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- CAMPOS ---
    name = fields.Char(
        string='Identificador Único',
        required=True,
        tracking=True,
        help="Identificador único del activo (ej. S/N de Placa Base o MAC)."
    )
    description = fields.Text(string='Nombre Descriptivo')
    type = fields.Selection(
        selection=[
            ('hardware', 'Hardware'),
            ('software', 'Software'),
            ('network', 'Red'),
            ('unknown', 'Desconocido'),
        ],
        string='Tipo Detectado',
        required=True,
        default='unknown',
        tracking=True
    )
    raw_data = fields.Text(string="Datos en Bruto (JSON)")
    status = fields.Selection(
        [('pending', 'Pendiente de Aprobación'),
         ('processed', 'Procesado'),
         ('ignored', 'Ignorado')],
        default='pending',
        string="Estado"
    )

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'El identificador único para un activo en el backlog ya existe!')
    ]
    
    # --- LÓGICA DE PROCESAMIENTO ---
    
    def _process_incoming_data(self, vals):
        """
        Procesa el JSON de raw_data para poblar los campos relacionales
        como IPs y Componentes antes de guardar el registro.
        Esta función será llamada desde create() y write().
        """
        if 'raw_data' in vals and vals['raw_data']:
            try:
                data = json.loads(vals['raw_data'])
                
                # --- Procesar IPs si el módulo de red está instalado ---
                if hasattr(self, 'ip_ids') and 'red' in data:
                    ip_address_model = self.env['it.ip.address']
                    ip_ids = []
                    
                    for net_interface in data.get('red', []):
                        ip_str = net_interface.get('ip')
                        if ip_str:
                            # Buscar o crear la dirección IP
                            ip_record = ip_address_model.search([('address', '=', ip_str)], limit=1)
                            if not ip_record:
                                ip_record = ip_address_model.create({'address': ip_str})
                            ip_ids.append(ip_record.id)
                    
                    if ip_ids:
                        # Usamos (6, 0, ...) para reemplazar las IPs existentes por las nuevas
                        vals['ip_ids'] = [(6, 0, ip_ids)]
                        _logger.info(f"Backlog para '{vals.get('name')}': IPs procesadas: {ip_ids}")

                # --- Aquí se añade la lógica para componentes, software, etc. ---
                # Ejemplo para componentes (si sgichs_hardware está instalado)
                # if hasattr(self, 'components_ids') and 'componentes' in data:
                #     ... (lógica similar a la de IPs)
                # Nota: Solo si se decide hacer el agente "tonto" para que toda la logica de procesamiento se mantenga en odoo

            except json.JSONDecodeError:
                _logger.warning(f"Backlog para '{vals.get('name')}': raw_data no es un JSON válido.")

        return vals

    @api.model
    def create(self, vals):
        """
        Sobrescritura para implementar "Upsert" y procesar datos entrantes.
        """
        # 1. Procesar los datos para rellenar campos relacionales (IPs, etc.)
        vals = self._process_incoming_data(vals)

        # 2. Lógica "Upsert"
        unique_id = vals.get('name')
        if unique_id:
            existing_record = self.search([('name', '=', unique_id)], limit=1)
            if existing_record:
                _logger.info(f"Backlog: Se encontró un registro existente para '{unique_id}'. Actualizando.")
                existing_record.write(vals)
                return existing_record
        
        _logger.info(f"Backlog: Creando nuevo registro para '{unique_id or 'N/A'}'.")
        return super(ITAssetBacklog, self).create(vals)

    def write(self, vals):
        """
        Sobrescritura para procesar datos entrantes en las actualizaciones.
        """
        # Procesar los datos para rellenar campos relacionales ANTES de escribir
        vals = self._process_incoming_data(vals)
        return super(ITAssetBacklog, self).write(vals)

    # --- MÉTODOS DE ACCIÓN ---
    def action_approve(self):
        raise NotImplementedError(_("La lógica de aprobación no está implementada en el core. Instale el módulo correspondiente (ej. sgichs_hardware)."))

    def action_ignore(self):
        self.write({'status': 'ignored'})