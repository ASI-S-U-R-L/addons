# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class ITDashboardSoftware(models.Model):
    """
    Extiende el dashboard base con métricas y gráficas de software.
    - read_group con '__count' y fallback por si el motor devuelve otra clave.
    - Mapeo de etiquetas legibles para fields selection (subtype, os_type).
    - Cálculo de compliance (autorizado/prohibido/gris) basado en listas activas.
    """
    _inherit = 'it.dashboard'

    @api.model
    def get_dashboard_data(self):
        dashboard_data = super(ITDashboardSoftware, self).get_dashboard_data()
        _logger.info("SGICH-SOFTWARE: Extendiendo datos del dashboard con métricas de software...")

        dashboard_data.setdefault('kpis', {})
        dashboard_data.setdefault('charts', {})
        dashboard_data.setdefault('lists', {})

        try:
            Software = self.env['it.asset.software']
            HWList = self.env['it.hw.list'] if 'it.hw.list' in self.env else None

            # -------------------
            # KPIs
            # -------------------
            total_software = Software.search_count([])

            authorized_ids = set()
            prohibited_ids = set()
            if HWList:
                active_black_lists = HWList.search([('type', '=', 'black'), ('active', '=', True)])
                active_white_lists = HWList.search([('type', '=', 'white'), ('active', '=', True)])
                # Uniones de IDs de software (evita duplicados)
                prohibited_ids = set(sid for lst in active_black_lists for sid in lst.software_ids.ids)
                authorized_ids = set(sid for lst in active_white_lists for sid in lst.software_ids.ids)

            authorized_count = len(authorized_ids)
            prohibited_count = len(prohibited_ids)
            gray_count = max(0, total_software - len(authorized_ids | prohibited_ids))

            dashboard_data['kpis'].update({
                'total_software': total_software,
                'software_authorized_count': authorized_count,
                'software_prohibited_count': prohibited_count,
                'software_gray_count': gray_count,
            })

            # -------------------
            # Charts
            # -------------------
            # Utilidades
            def _grp_count(d, keys=('__count', 'id_count', 'subtype_count', 'os_type_count')):
                for k in keys:
                    if k in d:
                        return d[k]
                return 0

            # 1) Software por Subtipo (selection)
            sw_by_subtype = Software.read_group(
                domain=[],
                fields=['__count'],
                groupby=['subtype'],
                lazy=False
            )
            subtype_info = Software.fields_get(allfields=['subtype']).get('subtype', {})
            subtype_selection = dict(subtype_info.get('selection', []))  # {'gestor_bd': 'Gestor de Bases de Datos', ...}

            chart_software_subtype = {
                'labels': [subtype_selection.get(d.get('subtype'), d.get('subtype') or 'Sin subtipo') for d in sw_by_subtype],
                'data': [_grp_count(d) for d in sw_by_subtype],
            }

            # 2) Software por Sistema Operativo (selection)
            sw_by_os = Software.read_group(
                domain=[],
                fields=['__count'],
                groupby=['os_type'],
                lazy=False
            )
            os_info = Software.fields_get(allfields=['os_type']).get('os_type', {})
            os_selection = dict(os_info.get('selection', []))  # {'windows': 'Windows', ...}

            chart_software_os = {
                'labels': [os_selection.get(d.get('os_type'), d.get('os_type') or 'Sin OS') for d in sw_by_os],
                'data': [_grp_count(d) for d in sw_by_os],
            }

            # (Opcional) 3) Cumplimiento (Autorizado/Prohibido/Gris)
            chart_software_compliance = {
                'labels': ['Autorizado', 'Prohibido', 'Zona Gris'],
                'data': [authorized_count, prohibited_count, gray_count],
            }

            dashboard_data['charts'].update({
                'software_subtype': chart_software_subtype,
                'software_os': chart_software_os,
                'software_compliance': chart_software_compliance,  # por si quieres usarlo luego
            })

            # -------------------
            # Listas (útil para futuras tarjetas/listas)
            # -------------------
            # Ejemplo: últimos 5 software creados (si quieres mostrar algo tipo “recientes”)
            recent_software = Software.search_read(
                domain=[],
                fields=['id', 'name', 'version', 'subtype', 'os_type'],
                limit=5,
                order='create_date desc'
            )
            dashboard_data['lists'].update({
                'recent_software': recent_software,
                # (Opcional) IDs para filtrar acciones desde KPIs si luego quieres
                'software_authorized_ids': list(authorized_ids),
                'software_prohibited_ids': list(prohibited_ids),
            })

        except Exception:
            _logger.exception("SGICH-SOFTWARE: Error calculando métricas de software. Se devuelven solo datos del core.")

        _logger.info("SGICH-SOFTWARE: Datos de software añadidos al dashboard.")
        return dashboard_data