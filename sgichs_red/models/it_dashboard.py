# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class ITDashboardNetwork(models.Model):
    """
    Extiende el dashboard base con métricas de red:
    - KPIs de estado de conexión (online/offline/pending/unknown)
    - Conteo de servicios de red
    - Gráficas por estado de conexión y protocolo
    Uso de read_group con '__count' y fallbacks de clave.
    """
    _inherit = 'it.dashboard'

    @api.model
    def get_dashboard_data(self):
        dashboard_data = super(ITDashboardNetwork, self).get_dashboard_data()
        _logger.info("SGICH-RED: Extendiendo datos del dashboard con métricas de red...")

        dashboard_data.setdefault('kpis', {})
        dashboard_data.setdefault('charts', {})
        dashboard_data.setdefault('lists', {})

        try:
            Hardware = self.env['it.asset.hardware']
            Service = self.env['it.asset.network_service'] if 'it.asset.network_service' in self.env else None
            PingHistory = self.env['it.hardware.ping.history'] if 'it.hardware.ping.history' in self.env else None

            # -------------------
            # KPIs
            # -------------------
            # Estados de conexión (sumando online + online_agent como "online" efectivo)
            net_hw_online = Hardware.search_count([('connection_status', 'in', ['online', 'online_agent'])])
            net_hw_offline = Hardware.search_count([('connection_status', 'in', ['offline', 'unreachable'])])
            net_hw_pending_unknown = Hardware.search_count([('connection_status', 'in', ['pending', 'unknown'])])

            network_services_total = Service.search_count([]) if Service else 0

            dashboard_data['kpis'].update({
                'net_hw_online': net_hw_online,
                'net_hw_offline': net_hw_offline,
                'net_hw_pending_unknown': net_hw_pending_unknown,
                'network_services_total': network_services_total,
            })

            # -------------------
            # Charts
            # -------------------
            def _grp_count(d, keys=('__count', 'id_count', 'connection_status_count', 'protocol_count')):
                for k in keys:
                    if k in d:
                        return d[k]
                return 0

            # 1) Hardware por Estado de Conexión
            status_groups = Hardware.read_group(
                domain=[],
                fields=['__count'],
                groupby=['connection_status'],
                lazy=False
            )
            # Mapeo legible de la selección
            st_info = Hardware.fields_get(allfields=['connection_status']).get('connection_status', {})
            st_selection = dict(st_info.get('selection', []))  # p.ej. {'online': 'Online', ...}

            chart_net_status = {
                'labels': [st_selection.get(d.get('connection_status'), d.get('connection_status') or 'Sin estado') for d in status_groups],
                'data': [_grp_count(d) for d in status_groups],
            }

            # 2) Servicios por Protocolo (si el modelo existe)
            chart_net_protocol = {'labels': [], 'data': []}
            if Service:
                proto_groups = Service.read_group(
                    domain=[],
                    fields=['__count'],
                    groupby=['protocol'],
                    lazy=False
                )
                proto_info = Service.fields_get(allfields=['protocol']).get('protocol', {})
                proto_selection = dict(proto_info.get('selection', []))  # {'tcp': 'TCP', ...}

                chart_net_protocol = {
                    'labels': [proto_selection.get(d.get('protocol'), d.get('protocol') or 'Sin protocolo') for d in proto_groups],
                    'data': [_grp_count(d) for d in proto_groups],
                }

            dashboard_data['charts'].update({
                'network_connection_status': chart_net_status,
                'network_service_protocol': chart_net_protocol,
            })

            # -------------------
            # Listas (opcional, útil para futuras vistas)
            # -------------------
            recent_ping_failures = []
            if PingHistory:
                recent_ping_failures = PingHistory.search_read(
                    domain=[('status', 'in', ['offline', 'unreachable'])],
                    fields=['id', 'hardware_id', 'ping_time', 'status', 'response_time_ms'],
                    limit=5,
                    order='ping_time desc'
                )

            dashboard_data['lists'].update({
                'recent_ping_failures': recent_ping_failures
            })

        except Exception:
            _logger.exception("SGICH-RED: Error calculando métricas de red. Se devuelven solo datos del core.")

        _logger.info("SGICH-RED: Datos de red añadidos al dashboard.")
        return dashboard_data