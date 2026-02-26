# -*- coding: utf-8 -*-
import requests
import logging

_logger = logging.getLogger(__name__)


class VersatApiMixin:
    """Mixin con utilidades para llamadas a la API de Versat."""

    def _get_api_config(self):
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'base_url': ICP.get_param('licencia_versat.api_base_url', 'https://comercializador.versat.cu'),
            'username': ICP.get_param('licencia_versat.api_username', ''),
            'password': ICP.get_param('licencia_versat.api_password', ''),
            'token': ICP.get_param('licencia_versat.api_token', ''),
            'refresh_token': ICP.get_param('licencia_versat.api_refresh_token', ''),
        }

    def _authenticate(self):
        """Obtiene un nuevo token de acceso y lo guarda en parámetros."""
        config = self._get_api_config()
        url = f"{config['base_url']}/api/token/"
        try:
            resp = requests.post(url, json={
                'username': config['username'],
                'password': config['password'],
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            ICP = self.env['ir.config_parameter'].sudo()
            ICP.set_param('licencia_versat.api_token', data.get('access', ''))
            ICP.set_param('licencia_versat.api_refresh_token', data.get('refresh', ''))
            return data.get('access', '')
        except Exception as e:
            _logger.error("Error autenticando con Versat API: %s", e)
            raise

    def _get_headers(self, token=None):
        if not token:
            config = self._get_api_config()
            token = config['token']
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

    def _api_get(self, path, params=None):
        """GET con reintento de autenticación si el token expira."""
        config = self._get_api_config()
        token = config['token']
        if not token:
            token = self._authenticate()

        url = f"{config['base_url']}{path}"
        resp = requests.get(url, headers=self._get_headers(token), params=params, timeout=15)

        if resp.status_code == 401:
            _logger.info("Token expirado, re-autenticando...")
            token = self._authenticate()
            resp = requests.get(url, headers=self._get_headers(token), params=params, timeout=15)

        resp.raise_for_status()
        return resp.json()

    def _api_post(self, path, payload):
        """POST con reintento de autenticación si el token expira."""
        config = self._get_api_config()
        token = config['token']
        if not token:
            token = self._authenticate()

        url = f"{config['base_url']}{path}"
        resp = requests.post(url, headers=self._get_headers(token), json=payload, timeout=15)

        if resp.status_code == 401:
            _logger.info("Token expirado, re-autenticando...")
            token = self._authenticate()
            resp = requests.post(url, headers=self._get_headers(token), json=payload, timeout=15)

        resp.raise_for_status()
        return resp.json()
