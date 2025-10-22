# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FuelInvoice(models.Model):
    _name = 'fuel.invoice'
    _description = 'Factura de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo'), tracking=True)
    invoice_number = fields.Char(string='Número de Factura', required=True, tracking=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    
    carrier_id = fields.Many2one('fuel.carrier', string='Portador de Combustible', required=True, tracking=True)
    
    amount = fields.Float(string='Cantidad (L)', required=True, tracking=True)
    unit_price = fields.Float(string='Precio Unitario', compute='_compute_unit_price', store=True, readonly=True, tracking=True)
    total_amount = fields.Float(string='Importe Total', compute='_compute_total_amount', store=True, readonly=True, tracking=True)
    
    account_invoice_id = fields.Many2one('account.move', string='Factura Contable', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    unassigned_ids = fields.One2many('fuel.unassigned', 'invoice_id', string='Combustible No Asignado')
    unassigned_amount = fields.Float(string='Cantidad No Asignada (L)', compute='_compute_unassigned_amount', store=True)
    
    notes = fields.Text(string='Notas')
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('fuel.invoice') or _('Nuevo')
        return super(FuelInvoice, self).create(vals)
    
    @api.depends('carrier_id')
    def _compute_unit_price(self):
        """Calcula automáticamente el precio unitario basado en el portador seleccionado"""
        for invoice in self:
            if invoice.carrier_id:
                invoice.unit_price = invoice.carrier_id.current_price
            else:
                invoice.unit_price = 0.0
    
    @api.depends('amount', 'unit_price')
    def _compute_total_amount(self):
        """Calcula automáticamente el importe total (cantidad × precio unitario)"""
        for invoice in self:
            invoice.total_amount = invoice.amount * invoice.unit_price
    
    @api.depends('unassigned_ids.amount', 'unassigned_ids.state')
    def _compute_unassigned_amount(self):
        for invoice in self:
            invoice.unassigned_amount = sum(invoice.unassigned_ids.filtered(lambda u: u.state == 'confirmed').mapped('amount'))
    
    @api.onchange('carrier_id')
    def _onchange_carrier_id(self):
        """Actualiza el precio unitario cuando se cambia el portador"""
        if self.carrier_id:
            self.unit_price = self.carrier_id.current_price
    
    @api.constrains('amount')
    def _check_amount(self):
        for invoice in self:
            if invoice.amount <= 0:
                raise ValidationError(_("La cantidad debe ser mayor que cero."))
    
    @api.constrains('carrier_id')
    def _check_carrier_id(self):
        for invoice in self:
            if not invoice.carrier_id:
                raise ValidationError(_("Debe seleccionar un portador de combustible."))
    
    def action_confirm(self):
        for invoice in self:
            if invoice.state == 'draft':
                if not invoice.carrier_id:
                    raise ValidationError(_("Debe seleccionar un portador de combustible antes de confirmar."))
                
                invoice.state = 'confirmed'
                
                # Crear automáticamente un registro de combustible no asignado
                self.env['fuel.unassigned'].with_context(from_invoice_confirmation=True).create({
                    'invoice_id': invoice.id,
                    'carrier_id': invoice.carrier_id.id,
                    'date': invoice.date,
                    'amount': invoice.amount,
                    'unit_price': invoice.unit_price,
                    'state': 'confirmed',
                })
    
    def action_cancel(self):
        for invoice in self:
            if invoice.state != 'cancelled':
                # Verificar si hay combustible no asignado que ya ha sido utilizado
                if invoice.unassigned_amount < invoice.amount:
                    raise ValidationError(_("No puede cancelar esta factura porque parte del combustible ya ha sido asignado."))
                
                invoice.state = 'cancelled'
                
                # Cancelar registros de combustible no asignado
                invoice.unassigned_ids.filtered(lambda u: u.state != 'cancelled').write({'state': 'cancelled'})
    
    def action_reset_to_draft(self):
        for invoice in self:
            if invoice.state == 'cancelled':
                invoice.state = 'draft'
