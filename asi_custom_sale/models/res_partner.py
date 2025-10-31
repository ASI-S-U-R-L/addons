from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    reeup_code = fields.Char(string='Código REEUP')
    commercial_registration_number = fields.Char(string='Número de Registro Comercial')
    subordination = fields.Char(string='Subordinación')
    accreditation_data = fields.Text(string='Datos de Acreditación')
    can_sign_invoices = fields.Boolean(string='Puede Firmar Facturas')  
    accreditation_sign_invoices_data = fields.Text(string='Datos de Acreditación para firmar facturas')
    bank_accounts = fields.Text(compute='_compute_bank_accounts', store=True)
    asi_contract = fields.Char('Contract')
    team_id = fields.Many2one(
        comodel_name="helpdesk.ticket.team",
        string="Zona",
    )

    @api.depends('bank_ids','bank_ids.acc_holder_name','bank_ids.currency_id','bank_ids.acc_number')
    def _compute_bank_accounts(self):
        for partner in self:
            bank_accounts = []
            for bank in partner.bank_ids:
                bank_account = f"No: {bank.acc_number}, Bco: {bank.bank_id.name}, Titular: {bank.acc_holder_name} Moneda: {bank.currency_id.name}"
                bank_accounts.append(bank_account)
            partner.bank_accounts = ',- '.join(bank_accounts)
            
    @api.constrains('can_sign_invoices', 'accreditation_sign_invoices_data')
    def _check_accreditation_sign_invoices_data(self):
        for record in self:
            if record.can_sign_invoices and not record.accreditation_sign_invoices_data:
                raise ValidationError(
                    "El campo 'Datos de Acreditación para firmar facturas' es obligatorio cuando 'Puede Firmar Facturas' está activado."
                )

    @api.onchange('can_sign_invoices')
    def _onchange_can_sign_invoices(self):
        if self.can_sign_invoices and not self.accreditation_sign_invoices_data:
            return {
                'warning': {
                    'title': "Advertencia",
                    'message': "El campo 'Datos de Acreditación para firmar facturas' es obligatorio cuando 'Puede Firmar Facturas' está activado.",
                }
            }            