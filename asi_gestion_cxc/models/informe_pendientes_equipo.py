from odoo import api, fields, models, _

class InformePendientesEquipo(models.TransientModel):
    _name = 'informe.pendientes.equipo'
    _description = 'Informe de Pendientes por Equipo de Ventas'
    _order = 'fecha_factura_antigua asc, team_id asc'

    team_id = fields.Many2one('crm.team', string='Equipo de Ventas', required=True)
    total_pendiente = fields.Float(string='Total Pendiente', digits='Account')
    fecha_factura_antigua = fields.Date(string='Factura mÃ¡s Antigua del Equipo')

    @api.model
    def get_data(self):
        \"\"\"Retorna datos agrupados por equipo de ventas, ordenados por fecha de factura mÃ¡s antigua.\"\"\"
        facturas = self.env['account.move'].search([
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
        ])

        datos_por_equipo = {}
        for factura in facturas:
            equipo = factura.partner_id.team_id
            if not equipo:
                continue
            if equipo not in datos_por_equipo:
                datos_por_equipo[equipo] = {
                    'total_pendiente': 0.0,
                    'fecha_factura_antigua': factura.invoice_date or fields.Date.today(),
                }
            datos_por_equipo[equipo]['total_pendiente'] += factura.amount_residual
            if factura.invoice_date and factura.invoice_date < datos_por_equipo[equipo]['fecha_factura_antigua']:
                datos_por_equipo[equipo]['fecha_factura_antigua'] = factura.invoice_date

        resultados = []
        for equipo, vals in datos_por_equipo.items():
            resultados.append({
                'team_id': equipo.id,
                'total_pendiente': vals['total_pendiente'],
                'fecha_factura_antigua': vals['fecha_factura_antigua'],
            })
        resultados.sort(key=lambda x: x['fecha_factura_antigua'])
        return resultados
