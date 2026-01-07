from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    trm_qr_code_str = fields.Text(compute="_compute_trm_qr_code_str", store=True, compute_sudo=True)

    def _compute_trm_qr_code_str(self):
        for record in self:
            trm_qr_code_str = False
            bank_account = self.env['account.journal'].search([
                    ('type', '=', 'bank'), ('company_id', '=', record.company_id.id)
                    ]).bank_account_id
            if bank_account:
                document_references = [record.name]
                if document_references:
                    trm_qr_code_str = {'id_transaccion': ', '.join(document_references), 'importe': record.amount_total, 'moneda': record.currency_id.display_name, 'numero_proveedor': bank_account.acc_number, 'version': 1}
            record.trm_qr_code_str = trm_qr_code_str and str(trm_qr_code_str) or False
        
class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    trm_qr_code_str = fields.Text(compute="_compute_trm_qr_code_str", compute_sudo=True)

    def _compute_trm_qr_code_str(self):
        for record in self:
            trm_qr_code_str = False
            bank_account = self.env['account.journal'].search([
                    ('type', '=', 'bank'), ('company_id', '=', record.company_id.id)
                    ]).bank_account_id
            if bank_account:
                document_references = record.sale_order_ids.mapped('name') + record.invoice_ids.mapped('name')
                if document_references:
                    trm_qr_code_str = {'id_transaccion': ', '.join(document_references), 'importe': record.amount, 'moneda': record.currency_id.display_name, 'numero_proveedor': bank_account.acc_number, 'version': 1}
            record.trm_qr_code_str = trm_qr_code_str and str(trm_qr_code_str) or False
