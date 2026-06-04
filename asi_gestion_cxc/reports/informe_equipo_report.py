from odoo import models, api

class InformePendientesEquipoReport(models.AbstractModel):
    _name = 'report.asi_gestion_cxc.reporte_pendientes_equipo'
    _description = 'Reporte de Pendientes por Equipo de Ventas'

    @api.model
    def _get_report_values(self, docids, data=None):
        informe = self.env['informe.pendientes.equipo']
        datos = informe.get_data()
        total_general = sum(d['total_pendiente'] for d in datos)
        return {
            'doc_ids': docids,
            'doc_model': 'informe.pendientes.equipo',
            'data': datos,
            'total_general': total_general,
        }
