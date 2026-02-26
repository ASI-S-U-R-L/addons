# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.exceptions import UserError
import requests


class VersatConfig(models.Model):
    _name = 'versat.config'
    _description = 'Configuración API Versat'

    api_base_url = fields.Char(
        string='URL Base API',
        default='https://comercializador.versat.cu',
    )
    api_username = fields.Char(string='Usuario API')
    api_password = fields.Char(string='Contraseña API')

    def action_guardar(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('licencia_versat.api_base_url', self.api_base_url or '')
        ICP.set_param('licencia_versat.api_username', self.api_username or '')
        ICP.set_param('licencia_versat.api_password', self.api_password or '')
        # Limpiar token para forzar re-autenticación
        ICP.set_param('licencia_versat.api_token', '')
        ICP.set_param('licencia_versat.api_refresh_token', '')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Configuración guardada',
                'message': 'Las credenciales han sido guardadas correctamente.',
                'sticky': False,
                'type': 'success',
            },
        }

    def action_test_conexion(self):
        self.ensure_one()
        base_url = self.api_base_url or ''
        username = self.api_username or ''
        password = self.api_password or ''
        if not base_url or not username or not password:
            raise UserError('Complete todos los campos antes de probar la conexión.')
        try:
            resp = requests.post(
                f'{base_url}/api/token/',
                json={'username': username, 'password': password},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            ICP = self.env['ir.config_parameter'].sudo()
            ICP.set_param('licencia_versat.api_token', data.get('access', ''))
            ICP.set_param('licencia_versat.api_refresh_token', data.get('refresh', ''))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '¡Conexión exitosa!',
                    'message': 'Token obtenido y guardado correctamente.',
                    'sticky': False,
                    'type': 'success',
                },
            }
        except Exception as e:
            raise UserError(f'Error de conexión: {e}')

    @classmethod
    def _get_or_create_singleton(cls, env):
        """Devuelve el registro único de configuración, creándolo si no existe."""
        config = env['versat.config'].search([], limit=1)
        if not config:
            ICP = env['ir.config_parameter'].sudo()
            config = env['versat.config'].create({
                'api_base_url': ICP.get_param('licencia_versat.api_base_url', 'https://comercializador.versat.cu'),
                'api_username': ICP.get_param('licencia_versat.api_username', ''),
                'api_password': ICP.get_param('licencia_versat.api_password', ''),
            })
        return config
