# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FuelCardLoad(models.Model):
  _name = 'fuel.card.load'
  _description = 'Carga de Tarjeta de Combustible'
  _inherit = ['mail.thread', 'mail.activity.mixin']
  _order = 'date desc, id desc'
  
  name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo'), tracking=True)
  date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
  
  card_id = fields.Many2one('fuel.magnetic.card', string='Tarjeta', required=True, tracking=True,
                           domain="[('state', 'in', ['available', 'assigned'])]")

  carrier_id = fields.Many2one('fuel.carrier', string='Portador de Combustible', required=True, tracking=True,
                              domain="[('id', 'in', carrier_ids)]")
  
  carrier_ids = fields.Many2many(related='card_id.carrier_ids', string='Portadores Disponibles', readonly=True)
  
  initial_balance = fields.Float(string='Saldo Inicial', readonly=True, tracking=True)
  amount = fields.Float(string='Importe', required=True, tracking=True)
  
  final_balance = fields.Float(string='Saldo Final', compute='_compute_final_balance', store=True, tracking=True)
  
  # ELIMINADO: unassigned_id ya no es gestionado directamente por card_load
  # unassigned_id = fields.Many2one('fuel.unassigned', string='Combustible No Asignado', tracking=True,
  #                                domain="[('state', 'in', ['confirmed', 'partially_used']), ('carrier_id', '=', carrier_id)]")
  
  state = fields.Selection([
      ('draft', 'Borrador'),
      ('confirmed', 'Confirmado'),
      ('cancelled', 'Cancelado')
  ], string='Estado', default='draft', tracking=True)
  
  notes = fields.Text(string='Notas')
  
  @api.model
  def create(self, vals):
      if vals.get('name', _('Nuevo')) == _('Nuevo'):
          vals['name'] = self.env['ir.sequence'].next_by_code('fuel.card.load') or _('Nuevo')
      
      if vals.get('card_id'):
          card = self.env['fuel.magnetic.card'].browse(vals['card_id'])
          vals['initial_balance'] = card.current_balance
      
      return super(FuelCardLoad, self).create(vals)
  
  @api.depends('initial_balance', 'amount', 'carrier_id.current_price')
  def _compute_final_balance(self):
      for load in self:
          if load.carrier_id and load.amount:
              load.final_balance = load.initial_balance + (load.amount * load.carrier_id.current_price)
          else:
              load.final_balance = load.initial_balance
  
  @api.onchange('card_id')
  def _onchange_card_id(self):
      if self.card_id:
          self.initial_balance = self.card_id.current_balance
          self.carrier_id = False
          # ELIMINADO: lógica relacionada con unassigned_id
          
          return {
              'domain': {
                  'carrier_id': [('id', 'in', self.card_id.carrier_ids.ids)],
              }
          }
      else:
          self.initial_balance = 0.0
          self.carrier_id = False
          return {
              'domain': {
                  'carrier_id': [('id', '=', False)],
              }
          }
  
  # ELIMINADO: _onchange_carrier_id y _onchange_unassigned_id ya que unassigned_id fue eliminado
  
  @api.constrains('card_id', 'carrier_id')
  def _check_carrier_in_card(self):
      for load in self:
          if load.card_id and load.carrier_id:
              if load.carrier_id not in load.card_id.carrier_ids:
                  raise ValidationError(_(
                      "El portador de combustible '%s' no está asignado a la tarjeta '%s'."
                  ) % (load.carrier_id.name, load.card_id.name))
  
  def action_confirm(self):
      for load in self:
          if load.state == 'draft':
              if not load.card_id.carrier_ids:
                  raise ValidationError(_("La tarjeta seleccionada no tiene portadores de combustible asignados."))
              
              if not load.carrier_id:
                  raise ValidationError(_("Debe seleccionar un portador de combustible."))
              
              if load.carrier_id not in load.card_id.carrier_ids:
                  raise ValidationError(_(
                      "El portador de combustible seleccionado no está asignado a esta tarjeta."
                  ))
              
              # ELIMINADO: Lógica de consumo de combustible no asignado de card_load
              
              charge_value = load.amount * load.carrier_id.current_price
              new_balance = load.card_id.current_balance + charge_value
              load.card_id.write({'current_balance': new_balance})
              
              load.state = 'confirmed'
  
  def action_cancel(self):
      for load in self:
          if load.state == 'confirmed':
              charge_value = load.amount * load.carrier_id.current_price
              if load.card_id.current_balance < charge_value:
                  raise ValidationError(_("No se puede cancelar la carga porque la tarjeta no tiene suficiente saldo para revertir el monto original."))
              
              new_balance = load.card_id.current_balance - charge_value
              load.card_id.write({'current_balance': new_balance})
              
              # ELIMINADO: Lógica de reversión de combustible no asignado de card_load
              
              load.state = 'cancelled'
          elif load.state == 'draft':
              load.state = 'cancelled'
  
  def action_reset_to_draft(self):
      for load in self:
          if load.state == 'cancelled':
              load.state = 'draft'

