from odoo import models, fields, api
from datetime import date


class AgingParetoReport(models.TransientModel):
    _name = 'aging.pareto.report'
    _description = 'Informe Pareto y Envejecimiento de Deudas'

    date_to = fields.Date(
        string='Fecha hasta',
        default=lambda self: date.today(),
        required=True,
        help='Fecha límite para considerar las deudas.'
    )

    @api.model
    def _get_domain_base(self, date_to):
        return [
            ('account_type', '=', 'asset_receivable'),
            ('amount_residual', '>', 0),
            ('move_id.state', '=', 'posted'),
            ('date', '<=', date_to),
        ]

    def get_pareto_clients(self):
        self.ensure_one()
        domain = self._get_domain_base(self.date_to)
        aml = self.env['account.move.line'].search(domain)

        deuda_por_cliente = {}
        for line in aml:
            partner = line.partner_id
            if not partner:
                continue
            deuda_por_cliente.setdefault(partner, 0.0)
            deuda_por_cliente[partner] += line.amount_residual

        if not deuda_por_cliente:
            return []

        ordenado = sorted(deuda_por_cliente.items(), key=lambda x: x[1], reverse=True)
        total_deuda = sum(deuda_por_cliente.values())
        acumulado = 0.0
        clientes_pareto = []

        for partner, deuda in ordenado:
            acumulado += deuda
            clientes_pareto.append({
                'partner_name': partner.name,
                'partner_id': partner.id,
                'deuda': deuda,
                'porcentaje': (deuda / total_deuda) * 100 if total_deuda else 0.0,
                'porcentaje_acumulado': (acumulado / total_deuda) * 100 if total_deuda else 0.0,
            })
            if acumulado >= total_deuda * 0.80:
                break

        return clientes_pareto

    def get_aging_clients(self):
        self.ensure_one()
        today = self.date_to or date.today()

        domain = self._get_domain_base(self.date_to) + [
            ('date_maturity', '!=', False),
            ('date_maturity', '<', today),
        ]
        aml = self.env['account.move.line'].search(domain)

        aging_data = {}

        for line in aml:
            partner = line.partner_id
            if not partner:
                continue
            dias = (today - line.date_maturity).days

            if partner.id not in aging_data:
                aging_data[partner.id] = {
                    'partner_name': partner.name,
                    'partner_id': partner.id,
                    'max_dias': dias,
                    'total_dias': dias,
                    'count': 1,
                    'total_vencido': line.amount_residual,
                }
            else:
                data = aging_data[partner.id]
                data['max_dias'] = max(data['max_dias'], dias)
                data['total_dias'] += dias
                data['count'] += 1
                data['total_vencido'] += line.amount_residual

        for data in aging_data.values():
            data['promedio'] = data['total_dias'] / data['count'] if data['count'] else 0.0

        ordenado = sorted(aging_data.values(), key=lambda x: x['max_dias'], reverse=True)
        return ordenado

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref(
            'account_aging_pareto_report.action_report_aging_pareto'
        ).report_action(self)
