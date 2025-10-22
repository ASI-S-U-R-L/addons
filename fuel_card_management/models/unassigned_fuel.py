# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError

import logging

_logger = logging.getLogger(__name__)

class FuelUnassigned(models.Model):
  _name = 'fuel.unassigned'
  _description = 'Combustible No Asignado'
  _inherit = ['mail.thread', 'mail.activity.mixin']
  _order = 'date desc, id desc'
  
  name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo'), tracking=True)
  date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
  
  invoice_id = fields.Many2one('fuel.invoice', string='Factura', required=True, tracking=True)
  
  carrier_id = fields.Many2one('fuel.carrier', string='Portador de Combustible', required=True, tracking=True)
  
  amount = fields.Float(string='Cantidad (L)', required=True, tracking=True)
  amount_used = fields.Float(string='Cantidad Usada (L)', default=0.0, tracking=True)
  amount_available = fields.Float(string='Cantidad Disponible (L)', compute='_compute_amount_available', store=True, tracking=True)
  
  unit_price = fields.Float(string='Precio Unitario', required=True, tracking=True)
  total_amount = fields.Float(string='Importe Total', compute='_compute_total_amount', store=True, tracking=True)
  
  state = fields.Selection([
      ('draft', 'Borrador'),
      ('confirmed', 'Confirmado'),
      ('partially_used', 'Parcialmente Usado'),
      ('fully_used', 'Completamente Usado'),
      ('cancelled', 'Cancelado')
  ], string='Estado', default='draft', tracking=True)
  
  notes = fields.Text(string='Notas')
  
  created_from_invoice = fields.Boolean(string='Creado desde Factura', default=False)
  
  usage_ids = fields.One2many('fuel.unassigned.usage', 'unassigned_id', string='Usos de Combustible')
  
  @api.model
  def create(self, vals):
      if not self.env.context.get('from_invoice_confirmation') and not self.env.user.has_group('base.group_system'):
          raise AccessError(_("No se puede crear combustible no asignado manualmente. "
                            "El combustible no asignado se genera automáticamente al confirmar una factura."))
      
      if vals.get('name', _('Nuevo')) == _('Nuevo'):
          vals['name'] = self.env['ir.sequence'].next_by_code('fuel.unassigned') or _('Nuevo')
      
      if self.env.context.get('from_invoice_confirmation'):
          vals['created_from_invoice'] = True
          
      return super(FuelUnassigned, self).create(vals)
  
  @api.depends('amount', 'amount_used')
  def _compute_amount_available(self):
      for record in self:
          record.amount_available = record.amount - record.amount_used
  
  @api.depends('amount', 'unit_price')
  def _compute_total_amount(self):
      for record in self:
          record.total_amount = record.amount * record.unit_price
  
  @api.constrains('carrier_id')
  def _check_carrier_id(self):
      for record in self:
          if not record.carrier_id:
              raise ValidationError(_("Debe seleccionar un portador de combustible."))
  
  @api.constrains('amount_used', 'amount')
  def _check_amount_used(self):
      for record in self:
          if record.amount_used > record.amount:
              raise ValidationError(_("La cantidad usada no puede ser mayor que la cantidad total."))
          if record.amount_used < 0:
              raise ValidationError(_("La cantidad usada no puede ser negativa."))
  
  def action_confirm(self):
      for record in self:
          if record.state == 'draft':
              record.state = 'confirmed'
  
  def action_cancel(self):
      for record in self:
          if record.state != 'cancelled':
              if record.amount_used > 0:
                  raise ValidationError(_("No se puede cancelar este registro de combustible no asignado porque ya ha sido utilizado. Primero debe revertir sus usos."))
              record.state = 'cancelled'
  
  def action_reset_to_draft(self):
      for record in self:
          if record.state == 'cancelled':
              record.state = 'draft'
  
  def use_fuel(self, amount, source_model=False, source_id=False):
      self.ensure_one()
      
      if self.state not in ['confirmed', 'partially_used']:
          raise ValidationError(_("Solo se puede usar combustible en estado confirmado o parcialmente usado."))
      
      if amount <= 0:
          raise ValidationError(_("La cantidad a usar debe ser mayor que cero."))
      
      if amount > self.amount_available:
          raise ValidationError(_("No hay suficiente combustible disponible. Disponible: %s L, Intentando usar: %s L") % (self.amount_available, amount))
      
      usage_vals = {
          'unassigned_id': self.id,
          'amount_used': amount,
          'date_used': fields.Date.today(),
          'source_model': source_model,
          'source_id': source_id,
      }
      if source_model == 'fuel.plan' and source_id:
          usage_vals['plan_id'] = source_id
      
      self.env['fuel.unassigned.usage'].create(usage_vals)
      
      self.amount_used += amount
      
      if self.amount_used >= self.amount:
          self.state = 'fully_used'
      else:
          self.state = 'partially_used'
      
      _logger.info(f"Combustible no asignado {self.name} usado: {amount}L. Saldo restante: {self.amount_available}L. Estado: {self.state}")
      return True
  
  def revert_fuel(self, amount, source_model=False, source_id=False):
      self.ensure_one()

      if amount <= 0:
          raise ValidationError(_("La cantidad a revertir debe ser mayor que cero."))
      
      if self.amount_used < amount:
          raise ValidationError(_("No se puede revertir más combustible del que se ha usado. Usado: %s L, Intentando revertir: %s L") % (self.amount_used, amount))

      # Buscar y desvincular el registro de uso específico
      # Se busca el registro de uso que coincida con la cantidad y la fuente.
      # Si la cantidad fue dividida en múltiples usos, esto requeriría una lógica más compleja.
      # Por simplicidad, asumimos que revert_fuel se llama con la cantidad exacta de un uso.
      usages_to_revert = self.env['fuel.unassigned.usage'].search([
          ('unassigned_id', '=', self.id),
          ('source_model', '=', source_model),
          ('source_id', '=', source_id),
          ('amount_used', '=', amount) 
      ], limit=1) # Limitar a 1 para evitar revertir múltiples veces el mismo uso si hay duplicados

      if not usages_to_revert:
          _logger.warning(f"No se encontró el registro de uso exacto para revertir en combustible no asignado {self.name} (fuente: {source_model}/{source_id}, cantidad: {amount}).")
          raise ValidationError(_("No se encontró el registro de uso correspondiente para revertir. Verifique la cantidad y la fuente."))
      
      usages_to_revert.unlink() # Eliminar el registro de uso

      self.amount_used -= amount
      
      if self.amount_used == 0:
          self.state = 'confirmed'
      elif self.amount_used < self.amount:
          self.state = 'partially_used'
      
      _logger.info(f"Combustible no asignado {self.name} revertido: {amount}L. Saldo restante: {self.amount_available}L. Estado: {self.state}")
      return True
  
  def _consume_fuel_for_carrier(self, carrier_id, amount_needed, source_model=False, source_id=False):
      """Consumir combustible de un portador específico, creando usage records."""
      unassigned_fuel = self.env['fuel.unassigned'].search([
          ('carrier_id', '=', carrier_id),
          ('state', 'in', ['confirmed', 'partially_used']),
          ('amount_available', '>', 0)
      ], order='date asc')
      
      remaining_amount = amount_needed
      
      for fuel_record in unassigned_fuel:
          if remaining_amount <= 0:
              break
          
          available_in_record = fuel_record.amount_available
          amount_to_use = min(remaining_amount, available_in_record)
          
          fuel_record.use_fuel(amount_to_use, source_model, source_id)
          
          remaining_amount -= amount_to_use
  
      if remaining_amount > 0:
          raise ValidationError(_("No hay suficiente combustible disponible para el portador %s para cubrir la cantidad total requerida.") % 
                              self.env['fuel.carrier'].browse(carrier_id).name)
  
  @api.model
  def get_available_fuel_by_carrier(self, carrier_id=None):
      domain = [('state', 'in', ['confirmed', 'partially_used'])]
      
      if carrier_id:
          domain.append(('carrier_id', '=', carrier_id))
      
      unassigned_records = self.search(domain)
      
      if carrier_id:
          return sum(unassigned_records.mapped('amount_available'))
      else:
          result = {}
          for record in unassigned_records:
              carrier = record.carrier_id
              if carrier.id not in result:
                  result[carrier.id] = {
                      'carrier': carrier,
                      'total_available': 0.0
                  }
              result[carrier.id]['total_available'] += record.amount_available
          
          return result
  
  @api.model
  def get_total_available_fuel(self):
      unassigned_records = self.search([('state', 'in', ['confirmed', 'partially_used'])])
      return sum(unassigned_records.mapped('amount_available'))


class FuelUnassignedUsage(models.Model):
  _name = 'fuel.unassigned.usage'
  _description = 'Uso de Combustible No Asignado'
  _order = 'date_used desc, id desc'
  
  unassigned_id = fields.Many2one('fuel.unassigned', string='Combustible No Asignado', required=True, ondelete='cascade')
  
  plan_id = fields.Many2one('fuel.plan', string='Plan de Combustible', ondelete='cascade')
  source_model = fields.Char(string='Modelo Origen', help="Modelo del registro que usó el combustible (ej. 'fuel.plan', 'fuel.card.load')")
  source_id = fields.Integer(string='ID Origen', help="ID del registro que usó el combustible")

  amount_used = fields.Float(string='Cantidad Usada (L)', required=True)
  date_used = fields.Date(string='Fecha de Uso', required=True)
  
  carrier_id = fields.Many2one('fuel.carrier', string='Portador', related='unassigned_id.carrier_id', store=True)
  
  @api.constrains('amount_used')
  def _check_amount_used(self):
      for record in self:
          if record.amount_used <= 0:
              raise ValidationError(_("La cantidad usada debe ser mayor que cero."))
  
  def name_get(self):
      result = []
      for record in self:
          name = f"{record.amount_used}L"
          if record.source_model and record.source_id:
              if record.source_model == 'fuel.plan':
                  plan = self.env['fuel.plan'].browse(record.source_id)
                  name = f"Plan {plan.name} - {name}"
              elif record.source_model == 'fuel.card.load':
                  load = self.env['fuel.card.load'].browse(record.source_id)
                  name = f"Carga {load.name} - {name}"
              else:
                  name = f"{record.source_model} ID {record.source_id} - {name}"
          result.append((record.id, name))
      return result

