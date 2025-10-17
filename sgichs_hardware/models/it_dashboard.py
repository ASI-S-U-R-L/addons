# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class ITDashboardHardware(models.Model):
    """
    Extiende los datos del dashboard base con métricas de hardware y componentes.
    Se cuida que:
    - Nunca rompa el RPC (try/except).
    - Se usen campos existentes en los modelos provistos.
    - Las agrupaciones (read_group) sean robustas usando 'id:count'.
    """
    _inherit = 'it.dashboard'

    @api.model
    def get_dashboard_data(self):
        # 1) Traer datos del core
        dashboard_data = super(ITDashboardHardware, self).get_dashboard_data()
        _logger.info("SGICH-HARDWARE: Extendiendo datos del dashboard con métricas de hardware...")

        # Asegurar estructura base siempre presente
        dashboard_data.setdefault('kpis', {})
        dashboard_data.setdefault('charts', {})
        dashboard_data.setdefault('lists', {})

        try:
            Hardware = self.env['it.asset.hardware']
            Component = self.env['it.component']

            # -------------------
            # KPIs de Hardware
            # -------------------
            total_hardware = Hardware.search_count([])

            # No existe 'connection_status' en it.asset.hardware; usamos métricas reales:
            # - HW con componentes (tiene al menos un componente relacionado)
            # - HW sin componentes (relación vacía)
            hw_with_components = Hardware.search_count([('components_ids', '!=', False)])
            hw_without_components = Hardware.search_count([('components_ids', '=', False)])

            # -------------------
            # KPIs de Componentes
            # -------------------
            total_components = Component.search_count([])
            components_assigned = Component.search_count([('hardware_id', '!=', False)])
            components_available = Component.search_count([('hardware_id', '=', False), ('status', '=', 'operational')])
            components_maintenance = Component.search_count([('status', '=', 'maintenance')])
            components_failed = Component.search_count([('status', '=', 'failed')])

            dashboard_data['kpis'].update({
                'total_hardware': total_hardware,
                'hw_with_components_count': hw_with_components,
                'hw_without_components_count': hw_without_components,

                'total_components': total_components,
                'components_assigned': components_assigned,
                'components_available': components_available,
                'components_maintenance': components_maintenance,
                'components_failed': components_failed,
            })

            # -------------------
            # Charts
            # -------------------
            # 1) Activos por Tipo (subtype: selection)
            #    - Usamos id:count para consistencia.
            #    - Mapeamos el valor técnico ('pc') a la etiqueta ('PC').
            assets_by_type = Hardware.read_group(
                domain=[],
                fields=['id:count'],
                groupby=['subtype'],
                lazy=False
            )
            # Mapeo de etiqueta legible del selection
            subtype_field_info = Hardware.fields_get(allfields=['subtype']).get('subtype', {})
            subtype_selection = dict(subtype_field_info.get('selection', []))  # {'pc': 'PC', ...}

            chart_asset_type = {
                'labels': [
                    subtype_selection.get(d.get('subtype'), d.get('subtype') or 'Sin subtipo')
                    for d in assets_by_type
                ],
                'data': [d.get('id_count', 0) for d in assets_by_type],
            }

            # 2) Componentes por Subtipo (subtype_id: many2one)
            components_by_subtype = Component.read_group(
                domain=[],
                fields=['id:count'],
                groupby=['subtype_id'],
                lazy=False
            )
            chart_component_subtype = {
                'labels': [d['subtype_id'][1] if d.get('subtype_id') else 'Sin Subtipo' for d in components_by_subtype],
                'data': [d.get('id_count', 0) for d in components_by_subtype],
            }

            dashboard_data['charts'].update({
                'asset_type': chart_asset_type,
                'component_subtype': chart_component_subtype,
            })

            # -------------------
            # Listas
            # -------------------
            # Componentes disponibles (no asignados) y operativos: muestra info útil.
            available_components = Component.search_read(
                domain=[('hardware_id', '=', False), ('status', '=', 'operational')],
                fields=['id', 'model', 'manufacturer', 'subtype_id', 'status'],
                limit=5,
                order='model asc'
            )
            dashboard_data['lists'].update({
                'available_components': available_components
            })

        except Exception:
            # Si algo falla aquí, al menos mantenemos vivo el dashboard base.
            _logger.exception("SGICH-HARDWARE: Error calculando métricas de hardware. Se devuelven solo datos del core.")

        _logger.info("SGICH-HARDWARE: Datos de hardware añadidos al dashboard.")
        return dashboard_data