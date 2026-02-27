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
        }

    def _authenticate(self):
        config = self._get_api_config()
        url = f"{config['base_url']}/api/token/"
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

    def _get_headers(self, token):
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

    def _api_get(self, path, params=None):
        config = self._get_api_config()
        token = config['token'] or self._authenticate()
        url = f"{config['base_url']}{path}"
        resp = requests.get(url, headers=self._get_headers(token), params=params, timeout=15)
        if resp.status_code == 401:
            token = self._authenticate()
            resp = requests.get(url, headers=self._get_headers(token), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _api_post(self, path, payload):
        config = self._get_api_config()
        token = config['token'] or self._authenticate()
        url = f"{config['base_url']}{path}"
        resp = requests.post(url, headers=self._get_headers(token), json=payload, timeout=15)
        if resp.status_code == 401:
            token = self._authenticate()
            resp = requests.post(url, headers=self._get_headers(token), json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()
