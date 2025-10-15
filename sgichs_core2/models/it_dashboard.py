# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ITDashboard(models.Model):
    """
    Este modelo no almacena datos en la base de datos de forma persistente.
    Su propósito es actuar como un intermediario para que el cliente web (JavaScript)
    pueda solicitar los datos del dashboard a través de una llamada RPC.
    Cada módulo que extienda el dashboard podrá heredar este modelo y añadir
    su propia lógica de recolección de datos.
    """
    _name = 'it.dashboard'
    _description = 'Modelo de Datos para el Dashboard de TI'

    # Este campo es necesario para que el modelo sea válido, pero no se utiliza para almacenar datos.
    name = fields.Char(string="Nombre del Dashboard")

    @api.model
    def get_dashboard_data(self):
        """
        Método principal llamado por RPC desde el cliente para recopilar y
        estructurar todos los datos necesarios para el dashboard base.
        
        La estructura de datos devuelta está diseñada para ser fácilmente extensible.
        Otros módulos (sgichs_hardware, sgichs_software, etc.) podrán heredar este
        método para añadir sus propios KPIs, gráficos y listas.
        
        :return: Un diccionario con los datos del dashboard.
        """
        _logger.info("SGICH-CORE: Recopilando datos para el Dashboard de TI base...")
        
        # El programador que implementa el dashboard base sabe que en el core
        # solo tiene acceso a los modelos de incidentes y backlog.
        Incident = self.env['it.incident']
        Backlog = self.env['it.asset.backlog']

        # --- 1. KPIs (Indicadores Clave de Rendimiento) para las tarjetas ---
        # Se obtienen los datos crudos que solo el core puede proveer.
        high_incidents = Incident.search_count([('severity', '=', 'high'), ('status', '!=', 'closed')])
        medium_incidents = Incident.search_count([('severity', '=', 'medium'), ('status', '!=', 'closed')])
        backlog_count = Backlog.search_count([('status', '=', 'pending')])
        
        # --- 2. Datos para Gráficos ---
        # Gráfico de Incidentes por Severidad (solo abiertos).
        incidents_by_severity = Incident.read_group(
            domain=[('status', '!=', 'closed')], 
            fields=['severity'], 
            groupby=['severity']
        )
        
        # --- 3. Datos para Listas ---
        # Lista de los últimos 5 incidentes de alta severidad no cerrados.
        recent_high_incidents = Incident.search_read(
            domain=[('severity', '=', 'high'), ('status', '!=', 'closed')],
            fields=['id', 'title', 'detection_date', 'status'],
            limit=5, 
            order='detection_date desc'
        )

        # Se empaquetan todos los datos en una estructura organizada.
        # Los módulos que hereden este método añadirán más claves a estos diccionarios.
        dashboard_data = {
            'kpis': {
                'high_incidents': high_incidents,
                'medium_incidents': medium_incidents,
                'backlog_count': backlog_count,
            },
            'charts': {
                'incident_severity': {
                    'labels': [d['severity'] for d in incidents_by_severity],
                    'data': [d['severity_count'] for d in incidents_by_severity]
                },
            },
            'lists': {
                'recent_high_incidents': recent_high_incidents,
            }
        }
        
        _logger.info("SGICH-CORE: Datos del dashboard base recopilados exitosamente.")
        return dashboard_data