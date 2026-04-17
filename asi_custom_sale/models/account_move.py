from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move' 
  
    # Campos personalizados
    reviewed = fields.Boolean(string="Archivada en contabilidad", default=False, readonly=True) 
    review_date = fields.Date(string="Fecha de Revisión", readonly=True)
    customer_signer_id = fields.Many2one(
        'res.partner',
        string="Firmante del Cliente",
        domain="[('can_sign_invoices', '=', True), ('parent_id', '=', partner_id)]",
        help="Persona autorizada para firmar facturas por parte del cliente.")
    amount_in_words = fields.Char(string='Importe en Letras', compute='_compute_amount_in_words', store=True )               
    sale_order_names = fields.Char(
        string="Órdenes de Venta",
        compute="_compute_sale_orders",
        store=True
    )

    analytic_accounts_ids = fields.Many2many(
        'account.analytic.account',
        string='Cuentas Analíticas',
        compute='_compute_analytic_accounts',
        store=True
    )

    gestion_state = fields.Selection([
        ('none', 'Sin gestionar'),
        ('sent_client','Enviada al Cliente'),
        ('received', 'Recibida'),
        ('archived', 'Archivada'),
    ], string="Estado de Gestión", default='none', store=True)

    def _set_gestion_state(self, new_state):
        # Transiciones permitidas
        allowed_transitions = {
            'sent_client': ['none'],
            'received': ['none', 'sent_client'],
            'archived': ['none', 'sent_client', 'received'],
        }

        # Etiquetas legibles para mensajes de error
        state_labels = dict(self._fields['gestion_state'].selection)

        for move in self:
            if move.state != 'posted':
                raise UserError("Solo puedes cambiar el estado de gestión cuando la factura está contabilizada.")

            old_state = move.gestion_state

            # Validación de transición
            if new_state in allowed_transitions:
                if old_state not in allowed_transitions[new_state]:
                    allowed = ", ".join(
                        f"'{state_labels[s]}'" for s in allowed_transitions[new_state]
                    )
                    raise UserError(
                        f"No se puede cambiar el estado a '{state_labels[new_state]}' "
                        f"cuando el estado actual es '{state_labels[old_state]}'.\n\n"
                        f"Estados permitidos para esta transición: {allowed}."
                    )

            # Obtener etiquetas legibles
            old_label = state_labels.get(old_state, old_state)
            new_label = state_labels.get(new_state, new_state)

            # Aplicar cambio
            move.gestion_state = new_state

            # Mensaje en el chatter
            if old_state in (False, 'none'):
                msg = f"Se ha cambiado al estado <b>{new_label}</b> por {self.env.user.name}."
            else:
                msg = (
                    f"El estado de gestión cambió de <b>{old_label}</b> "
                    f"a <b>{new_label}</b> por {self.env.user.name}."
                )

            move.message_post(body=msg)


    def action_set_gestion_state_sent(self):
        self._set_gestion_state('sent_client')

    def action_set_gestion_state_received(self):
        self._set_gestion_state('received')

    def action_set_gestion_state_archived(self):
        self._set_gestion_state('archived')


    @api.depends('invoice_line_ids.analytic_distribution')
    def _compute_analytic_accounts(self):
        for move in self:
            cuentas = self.env['account.analytic.account']

            for line in move.invoice_line_ids:
                if line.analytic_distribution:
                    analytic_ids = [int(x) for x in line.analytic_distribution.keys()]

                    cuentas_linea = self.env['account.analytic.account'].search([
                        ('id', 'in', analytic_ids),
                        ('plan_id.name', '=', 'Empleados')
                    ])

                    cuentas |= cuentas_linea

            move.analytic_accounts_ids = cuentas

    def cron_recompute_analytic_accounts(self):
        # Solo facturas contabilizadas
        moves = self.search([
            ('state', '=', 'posted'),
            ('move_type', 'in', ['out_invoice', 'in_invoice'])
        ])
        moves._compute_analytic_accounts()


    # Método para marcar la factura como revisada
                 
    def mark_as_reviewed(self):
        self.write({
            'reviewed': True,
            'review_date': fields.Datetime.now(),
        })

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            return {
                'domain': {
                    'customer_signer_id': [
                        ('can_sign_invoices', '=', True),
                        ('parent_id', '=', self.partner_id.id)
                    ]
                }
            }
        else:
            return False


    # Restricción para evitar que se marque como revisada una factura no publicada
    @api.constrains('reviewed')
    def _check_reviewed_state(self):
        for move in self:
            if move.reviewed and move.state != 'posted':
                raise ValidationError("Solo se pueden revisar facturas en estado 'Publicado'.")        

      
    @api.depends('amount_total')
    def _compute_amount_in_words(self):
        for move in self:
            amount = abs(move.amount_total)
            currency = move.currency_id
            amount_in_words = currency.amount_to_text(amount) 
            move.amount_in_words = amount_in_words.capitalize()

    @api.depends("invoice_line_ids.sale_line_ids.order_id")
    def _compute_sale_orders(self):
        """Obtiene las órdenes de venta vinculadas a la factura y las une en una cadena separada por comas."""
        for move in self:
            sale_orders = move.invoice_line_ids.mapped("sale_line_ids.order_id.name")
            move.sale_order_names = ", ".join(sale_orders) if sale_orders else ""
 
    def action_recompute_sale_orders(self):
        """Recalcula el campo sale_order_names para todas las facturas existentes."""
        all_moves = self.search([])
        all_moves._compute_sale_orders()
        
    def action_post(self):
        for invoice in self:
            # Verificar si la factura tiene una fecha válida
            if not invoice.invoice_date:
                raise ValidationError("La factura no tiene una fecha válida. Asigna una fecha antes de confirmarla.") 

            # Buscar la última factura confirmada
            last_invoice = self.search(
                [('state', '=', 'posted'), ('move_type', '=', 'out_invoice')],
                order='invoice_date desc',
                limit=1
            )

            # Verificar si hay una factura anterior y si tiene una fecha válida
            if last_invoice and last_invoice.invoice_date:
                if invoice.invoice_date < last_invoice.invoice_date:
                    raise ValidationError("La fecha de la factura debe ser mayor o igual que la fecha de la última factura confirmada.")

        return super(AccountMove, self).action_post()
