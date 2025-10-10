# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)

class ITAssetBacklog(models.Model):
    """
    Hereda el modelo de backlog para añadir la lógica de procesamiento
    de software detectado en los datos en bruto (raw_data).
    """
    _inherit = 'it.asset.backlog'

    # Este campo permite visualizar el software procesado en la vista del backlog.
    software_ids = fields.Many2many(
        'it.asset.software',
        'backlog_software_rel',
        'backlog_id',
        'software_id',
        string='Software Detectado'
    )

    # Sobrescribimos el método _process_incoming_data que ya existe en el core.
    # Esta función se llama automáticamente desde los métodos create() y write() del modelo base.
    def _process_incoming_data(self, vals):
        """
        Hereda el método del core para añadir el procesamiento de software.
        Esta función se ejecuta al crear o actualizar un registro en el backlog.
        """
        # 1. Ejecutar la lógica de los módulos padres (ej: para procesar IPs desde sgichs_core2)
        vals = super()._process_incoming_data(vals)

        # 2. Si no hay 'raw_data' en la petición, no hay nada que procesar.
        if 'raw_data' not in vals or not vals['raw_data']:
            return vals

        try:
            # 3. Cargar el JSON y extraer la lista de programas.
            data = json.loads(vals['raw_data'])
            software_programs = data.get('programas')
            
            # Si la clave "programas" no existe o no es una lista, terminamos.
            if not isinstance(software_programs, list):
                return vals

            software_model = self.env['it.asset.software']
            software_ids = []
            
            _logger.info(f"Procesando {len(software_programs)} programas desde raw_data para backlog '{vals.get('name')}'.")

            for program in software_programs:
                name = program.get('nombre')
                version = program.get('version', 'N/A') # Usamos 'N/A' si no viene versión.

                if not name:
                    continue

                # 4. Lógica "Buscar o Crear" para cada software.
                domain = [('name', '=', name), ('version', '=', version)]
                existing_software = software_model.search(domain, limit=1)
                
                if existing_software:
                    software_ids.append(existing_software.id)
                else:
                    # Si no existe, lo creamos.
                    new_software = software_model.create({
                        'name': name,
                        'version': version,
                        'description': f"Creado automáticamente desde el backlog del activo {vals.get('name')}.",
                        'subtype': 'otros', # Por defecto 'otros', se puede categorizar manualmente después.
                    })
                    software_ids.append(new_software.id)
            
            if software_ids:
                # 5. Usamos el comando (6, 0, ...) para REEMPLAZAR la lista de software
                # por la recién procesada. Esto mantiene los datos siempre actualizados.
                vals['software_ids'] = [(6, 0, software_ids)]

        except json.JSONDecodeError:
            _logger.warning(f"Backlog para '{vals.get('name')}': raw_data no es un JSON válido durante el procesamiento de software.")
        
        return vals