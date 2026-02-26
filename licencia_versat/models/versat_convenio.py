# -*- coding: utf-8 -*-
import logging
from odoo import models, fields,api
from .versat_api_mixin import VersatApiMixin

_logger = logging.getLogger(__name__)


class VersatConvenio(models.Model, VersatApiMixin):
    _name = 'versat.convenio'
    _description = 'Convenio Versat'
    _order = 'nombre'

    convenio_id = fields.Char(string='ID Externo', required=True, index=True)
    nombre = fields.Char(string='Nombre')
    cliente_convenio = fields.Char(string='Cliente Convenio')
    ultimo_pago_licencia = fields.Date(string='Último Pago Licencia')
    ultimo_pago_activacion = fields.Date(string='Último Pago Activación')
    ultima_solicitud = fields.Date(string='Última Solicitud')
    active = fields.Boolean(default=True)

    # Usuario final (cargado desde API)
    usuario_final_id_ext = fields.Char(string='ID Usuario Final (externo)')
    usuario_final_nombre = fields.Char(string='Usuario Final')
    usuario_final_email = fields.Char(string='Email Usuario Final')

    _sql_constraints = [
        ('convenio_id_unique', 'UNIQUE(convenio_id)', 'El ID del convenio debe ser único.'),
    ]

    def name_get(self):
        return [(r.id, r.nombre or r.convenio_id) for r in self]

    @api.model
    def sync_from_api(self):
        """Sincroniza convenios desde /api-acceso/registro_venta_externo/"""
        _logger.info("Sincronizando convenios desde Versat API...")
        try:
            data = self._api_get('/api-acceso/registro_venta_externo/', params={'limit': 10000})
        except Exception as e:
            _logger.error("Error al obtener convenios: %s", e)
            raise

        results = data.get('results', [])
        created = 0
        updated = 0

        for item in results:
            convenio_id = item.get('id')
            if not convenio_id:
                continue

            vals = {
                'convenio_id': convenio_id,
                'nombre': item.get('nombre', ''),
                'cliente_convenio': item.get('cliente_convenio', ''),
                'ultimo_pago_licencia': item.get('ultimo_pago_licencia') or False,
                'ultimo_pago_activacion': item.get('ultimo_pago_activacion') or False,
                'ultima_solicitud': item.get('ultima_solicitud') or False,
            }

            existing = self.search([('convenio_id', '=', convenio_id)], limit=1)
            if existing:
                existing.write(vals)
                updated += 1
            else:
                self.create(vals)
                created += 1

        _logger.info("Convenios: %d creados, %d actualizados.", created, updated)
        return {'created': created, 'updated': updated}

    def action_cargar_usuario_final(self):
        """Carga el usuario final desde la API."""
        self.ensure_one()
        try:
            data = self._api_get(
                '/api-acceso/usuario_final/',
                params={'id_convenio': self.convenio_id}
            )
            results = data.get('results', [])
            if results:
                uf = results[0]
                self.write({
                    'usuario_final_id_ext': uf.get('id', ''),
                    'usuario_final_nombre': uf.get('nombre_completo', '') or uf.get('nombre', ''),
                    'usuario_final_email': uf.get('correo', '') or uf.get('email', ''),
                })
            print(self.convenio_id)

        except Exception as e:
            _logger.error("Error al cargar usuario final para convenio %s: %s", self.convenio_id, e)
            raise
