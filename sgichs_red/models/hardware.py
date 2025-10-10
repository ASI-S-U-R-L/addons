# -*- coding: utf-8 -*-
from odoo import models, fields, api
import os
import shlex
import subprocess
import re
import logging
import requests

_logger = logging.getLogger(__name__)

class Hardware(models.Model):
    _inherit = 'it.asset.hardware'

    ip_ids = fields.Many2many(
        'it.ip.address',
        'hardware_ip_rel',
        'hardware_id',
        'ip_id',
        string='Direcciones IP'
    )
    connection_status = fields.Selection(
        selection_add=[
            ('online_agent', 'Online (Vía Agente)'),
        ],
        selection=[
            ('online', 'Online'),
            ('online_agent', 'Online (Vía Agente)'),
            ('offline', 'Offline'),
            ('unreachable', 'Inalcanzable'),
            ('pending', 'Pendiente'),
            ('unknown', 'Desconocido'),
        ],
        string='Estado de Conexión',
        default='pending',
        readonly=True,
        tracking=True
    )
    last_ping_time = fields.Datetime(string='Último Ping', readonly=True)
    ping_history_ids = fields.One2many(
        'it.hardware.ping.history',
        'hardware_id',
        string='Historial de Ping'
    )
    agent_listener_port = fields.Integer(string="Puerto del Agente", default=9191, required=True)

    def _get_first_ip(self):
        self.ensure_one()
        return self.ip_ids[0].address if self.ip_ids else None

    def _do_ping(self, ip_address):
        """
        Lógica de ping HÍBRIDA. Primero intenta el ping tradicional (ICMP)
        y si falla, intenta contactar al agente vía HTTP.
        """
        # --- 1. Intento de Ping Tradicional (ICMP) ---
        try:
            param = '-n 1 -w 2000' if os.name == 'nt' else '-c 1 -W 2'
            command = f"ping {param} {shlex.quote(ip_address)}"
            output = subprocess.check_output(
                command, 
                shell=True, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True, 
                timeout=3
            )
            
            if "TTL=" in output or "ttl=" in output:
                time_match = re.search(r'time[=<>](\d+\.?\d*)', output)
                response_time = float(time_match.group(1)) if time_match else 0.0
                _logger.info(f"Ping ICMP a {ip_address} exitoso. Tiempo: {response_time}ms")
                return 'online', response_time
            
            primary_status = 'unreachable'
        except subprocess.CalledProcessError:
            primary_status = 'offline'
        except Exception as e:
            _logger.error(f"Error desconocido en ping ICMP a {ip_address}: {str(e)}")
            primary_status = 'unknown'

        _logger.warning(f"Ping ICMP a {ip_address} falló (estado: {primary_status}). Intentando ping vía agente...")

        # --- 2. Intento de Ping Vía Agente (HTTP) ---
        agent_port = self.agent_listener_port or 9191
        agent_url = f"http://{ip_address}:{agent_port}/status"
        
        try:
            response = requests.get(agent_url, timeout=5) # Timeout de 5 segundos
            if response.status_code == 200 and response.json().get('status') == 'active':
                _logger.info(f"✅ Ping VÍA AGENTE a {agent_url} exitoso.")
                return 'online_agent', 0.0 # El tiempo de respuesta no es comparable al de ICMP
        except requests.RequestException as e:
            _logger.error(f"❌ Ping VÍA AGENTE a {agent_url} falló: {e}")
            # El estado primario (offline/unreachable) se mantiene.
        
        # --- 3. Devolver resultado final ---
        return primary_status, 0.0

    def update_connection_status(self):
        for device in self:
            ip_address = device._get_first_ip()
            if not ip_address:
                device.connection_status = 'unknown'
                continue

            status, response_time = device._do_ping(ip_address)
            
            device.write({
                'connection_status': status,
                'last_ping_time': fields.Datetime.now(),
            })

            self.env['it.hardware.ping.history'].create({
                'hardware_id': device.id,
                'status': status,
                'response_time_ms': response_time,
            })

    def action_manual_ping(self):
        self.ensure_one()
        self.update_connection_status()
        
    def action_ping_device(self):
        self.ensure_one()
        ip_address = self._get_first_ip()
        
        if not ip_address:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error de Ping',
                    'message': 'El dispositivo no tiene direcciones IP configuradas',
                    'type': 'danger',
                    'sticky': False,
                }
            }

        status, response_time = self._do_ping(ip_address)
        
        # Traducir estados a mensajes amigables
        status_messages = {
            'online': f"¡Conexión exitosa (ICMP)! El dispositivo respondió en {response_time} ms",
            'online_agent': "¡Conexión exitosa (Vía Agente)! El agente está activo en el equipo.",
            'offline': "El dispositivo no respondió (offline)",
            'unreachable': "Dispositivo inalcanzable (posible problema de red)",
            'unknown': "Error desconocido al intentar el ping"
        }
        
        message = status_messages.get(status, f"Estado desconocido: {status}")
        notification_type = 'success' if status in ['online', 'online_agent'] else 'danger'
        
        # Crear registro de historial
        self.env['it.hardware.ping.history'].create({
            'hardware_id': self.id,
            'status': status,
            'response_time_ms': response_time,
        })
        
        # Actualizar estado del dispositivo
        self.write({
            'connection_status': status,
            'last_ping_time': fields.Datetime.now(),
        })
        
        # Mostrar notificación
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Resultado del Ping Híbrido',
                'message': f"{self.name} ({ip_address}): {message}",
                'type': notification_type,
                'sticky': True,  # Permanece visible hasta que el usuario la cierre
            }
        }    

    @api.model
    def cron_ping_devices(self):
        _logger.info("Iniciando tarea programada: Ping a dispositivos de TI...")
        devices_to_ping = self.search([('status', '=', 'active')])
        devices_to_ping.update_connection_status()
        _logger.info(f"Ping completado para {len(devices_to_ping)} dispositivos.")