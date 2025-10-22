# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class FuelPlan(models.Model):
  _name = 'fuel.plan'
  _description = 'Propuesta de Plan de Combustible'
  _inherit = ['mail.thread', 'mail.activity.mixin']
  _order = 'create_date desc, id desc'

  name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo'), tracking=True)
  date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)

  plan_type = fields.Selection([
      ('all_carriers', 'Todos los Portadores')
  ], string='Tipo de Plan', required=True, default='all_carriers', readonly=True, tracking=True,
     help="El plan de combustible siempre se genera para todos los portadores disponibles.")

  available_fuel = fields.Float(string='Combustible Disponible (L)', compute='_compute_available_fuel', store=True, tracking=True)

  director_id = fields.Many2one('res.users', string='Director para Aprobación', tracking=True,
                               domain=[('groups_id.category_id.name', '=', 'Gestión de Tarjetas de Combustible')],
                               required=True)
  director_comments = fields.Text(string='Comentarios del Director', tracking=True)
  modified_by_director = fields.Boolean(string='Modificado por Director', default=False, tracking=True)
  state = fields.Selection([
      ('draft', 'Borrador'),
      ('pending_approval', 'Pendiente de Aprobación'),
      ('approved', 'Aprobado'),
      ('loaded', 'Cargado'),
      ('rejected', 'Rechazado'),
      ('cancelled', 'Cancelado')
  ], string='Estado', default='draft', tracking=True)

  distribution_ids = fields.One2many('fuel.plan.distribution', 'plan_id', string='Distribución entre Tarjetas')

  total_distributed_amount = fields.Float(
      string='Total Distribuido (L)',
      compute='_compute_total_distributed_amount',
      store=True,
      tracking=True,
      help="Suma total del combustible distribuido en este plan."
  )

  fuel_usage_ids = fields.One2many('fuel.unassigned.usage', 'plan_id', string='Uso de Combustible')

  @api.model
  def create(self, vals):
      if vals.get('name', _('Nuevo')) == _('Nuevo'):
          vals['name'] = self.env['ir.sequence'].next_by_code('fuel.plan') or _('Nuevo')
      return super(FuelPlan, self).create(vals)

  @api.depends('plan_type')
  def _compute_available_fuel(self):
      for plan in self:
          plan.available_fuel = self.env['fuel.unassigned'].get_total_available_fuel()

  @api.depends('distribution_ids.amount')
  def _compute_total_distributed_amount(self):
      for plan in self:
          plan.total_distributed_amount = sum(plan.distribution_ids.mapped('amount'))

  @api.constrains('total_distributed_amount', 'available_fuel')
  def _check_distribution_total(self):
      for plan in self:
          if plan.total_distributed_amount > plan.available_fuel:
              raise ValidationError(_("No puede distribuir más combustible del disponible. Disponible: %s L, Distribuido: %s L") % (plan.available_fuel, plan.total_distributed_amount))

  def action_generate_distribution(self):
      self.ensure_one()
      
      self.distribution_ids.unlink()
      
      if self.available_fuel <= 0:
          raise ValidationError(_("No hay combustible disponible para distribuir."))
      
      self._generate_distribution_all_carriers()
      
      return True

  def action_clear_distribution(self):
      self.ensure_one()
      if self.state == 'draft':
          self.distribution_ids.unlink()
      return True

  def _generate_distribution_all_carriers(self):
      cards = self.env['fuel.magnetic.card'].search([
          ('active', '=', True),
          ('operational_state', 'in', ['available', 'assigned'])
      ])
      
      if not cards:
          raise ValidationError(_("No hay tarjetas activas para distribuir el combustible."))
      
      fuel_by_carrier = self.env['fuel.unassigned'].get_available_fuel_by_carrier()
      
      cards_by_carrier = {}
      for card in cards:
          for card_carrier in card.carrier_ids:
              if card_carrier.id not in cards_by_carrier:
                  cards_by_carrier[card_carrier.id] = []
              cards_by_carrier[card_carrier.id].append(card)
      
      distribution_vals = []
      
      for carrier_id, fuel_info in fuel_by_carrier.items():
          if carrier_id in cards_by_carrier:
              carrier_cards = cards_by_carrier[carrier_id]
              available_amount = fuel_info['total_available']
              
              if available_amount > 0:
                  distributable_cards = [card for card in carrier_cards if carrier_id in card.carrier_ids.ids]
                  if distributable_cards:
                      amount_per_card = available_amount / len(distributable_cards)
                      
                      for card in distributable_cards:
                          distribution_vals.append({
                              'plan_id': self.id,
                              'card_id': card.id,
                              'amount': amount_per_card,
                              'carrier_id': carrier_id,
                          })
    
      if distribution_vals:
          self.env['fuel.plan.distribution'].create(distribution_vals)
      else:
          raise ValidationError(_("No se pudo generar la distribución. Verifique que haya combustible no asignado y tarjetas activas con portadores coincidentes."))

  def action_send_for_approval(self):
      self.ensure_one()
      
      if not self.distribution_ids:
          raise ValidationError(_("No puede enviar un plan sin distribución."))
      
      if not self.director_id:
          raise ValidationError(_("Debe seleccionar un director para la aprobación."))
      
      if self.total_distributed_amount > self.available_fuel:
          raise ValidationError(_("No hay suficiente combustible disponible para la distribución propuesta."))
      
      self.write({'state': 'pending_approval'})
      
      # Crear actividad en el reloj para el director
      self.activity_schedule(
          'mail.mail_activity_data_todo',
          summary=_("Revisar propuesta de plan de combustible"),
          note=_("Por favor, revise la propuesta de plan de combustible %s y apruebe o rechace según corresponda.\n\nReferencia: %s\nFecha: %s\nCombustible a Distribuir: %s litros") % (
              self.name, self.name, self.date, self.total_distributed_amount
          ),
          user_id=self.director_id.id,
          date_deadline=fields.Date.today()
      )
      
      self.message_post(
          body=_("Plan enviado para aprobación al director %s.") % self.director_id.name,
          message_type='notification',
          subtype_xmlid='mail.mt_comment'
      )
      
      return True

  def action_save_director_changes(self):
      self.ensure_one()
      
      current_user = self.env.user
      if current_user.id != self.director_id.id and not current_user.has_group('base.group_system'):
          raise ValidationError(_("Solo el director asignado puede modificar esta propuesta."))
      
      if self.total_distributed_amount > self.available_fuel:
          raise ValidationError(_("No hay suficiente combustible disponible para la distribución modificada."))
      
      self.write({'modified_by_director': True})
      
      self.message_post(
          body=_("El director %s ha realizado modificaciones en la propuesta de plan.") % self.env.user.name,
          message_type='notification',
          subtype_xmlid='mail.mt_comment',
          partner_ids=[self.create_uid.partner_id.id]
      )
      
      # Crear actividad para el creador del plan
      self.activity_schedule(
          'mail.mail_activity_data_todo',
          summary=_("Plan de combustible modificado por director"),
          note=_("El director %s ha realizado modificaciones en su propuesta de plan de combustible %s.") % (
              self.director_id.name, self.name
          ),
          user_id=self.create_uid.id,
          date_deadline=fields.Date.today()
      )
      
      return True

  def action_approve(self):
      self.ensure_one()
      
      if not self.distribution_ids:
          raise ValidationError(_("No puede aprobar un plan sin distribución."))
      
      current_user = self.env.user
      if self.state == 'pending_approval' and current_user.id != self.director_id.id and not current_user.has_group('base.group_system'):
          raise ValidationError(_("Solo el director asignado puede aprobar esta propuesta."))
      
      if self.total_distributed_amount > self.available_fuel:
          raise ValidationError(_("No hay suficiente combustible disponible para aprobar este plan."))
      
      self.write({'state': 'approved'})
      
      message = _("El plan ha sido aprobado por %s. Las tarjetas pueden ser cargadas ahora.") % self.env.user.name
      if self.modified_by_director:
          message += _(" El plan fue modificado por el director antes de ser aprobado.")
      
      self.message_post(
          body=message,
          message_type='notification',
          subtype_xmlid='mail.mt_comment',
          partner_ids=[self.create_uid.partner_id.id]
      )
      
      # Crear actividad para el creador del plan
      self.activity_schedule(
          'mail.mail_activity_data_todo',
          summary=_("Plan de combustible aprobado"),
          note=_("Su propuesta de plan de combustible %s ha sido APROBADA por el director %s.\n\nPuede proceder a cargar las tarjetas.") % (
              self.name, self.director_id.name
          ),
          user_id=self.create_uid.id,
          date_deadline=fields.Date.today()
      )
      
      # Marcar actividad del director como realizada
      activities = self.env['mail.activity'].search([
          ('res_model', '=', 'fuel.plan'),
          ('res_id', '=', self.id),
          ('user_id', '=', self.director_id.id)
      ])
      activities.action_done()
      
      return True

  def action_load_cards(self):
      """
      Carga el combustible en las tarjetas y descuenta del combustible no asignado.
      """
      self.ensure_one()

      if self.state != 'approved':
          raise ValidationError(_("El plan debe estar en estado 'Aprobado' para cargar las tarjetas."))
      
      if not self.distribution_ids:
          raise ValidationError(_("No se puede cargar un plan sin distribución."))

      # Paso 1: Consumir el combustible no asignado del pool general
      # Agrupar la cantidad total a consumir por cada portador
      distributions_by_carrier = {}
      for distribution in self.distribution_ids:
          carrier_id = distribution.carrier_id.id
          if carrier_id not in distributions_by_carrier:
              distributions_by_carrier[carrier_id] = 0.0
          distributions_by_carrier[carrier_id] += distribution.amount
      
      # Consumir el combustible de los registros no asignados
      for carrier_id, amount_needed in distributions_by_carrier.items():
          # Llama al método en fuel.unassigned para consumir la cantidad,
          # que a su vez creará los registros de uso (fuel.unassigned.usage)
          # vinculados a este plan.
          self.env['fuel.unassigned']._consume_fuel_for_carrier(
              carrier_id, amount_needed, 'fuel.plan', self.id
          )

      # Paso 2: Crear y confirmar las cargas de tarjetas
      for distribution in self.distribution_ids:
          load_carrier = distribution.carrier_id 

          # Crear la carga en borrador y luego confirmarla.
          # La carga de tarjeta ya NO gestiona el combustible no asignado.
          # Solo actualiza el saldo de la tarjeta.
          load = self.env['fuel.card.load'].create({
              'name': f"PLAN-{self.name}-{distribution.card_id.name}",
              'date': self.date,
              'card_id': distribution.card_id.id,
              'carrier_id': load_carrier.id,
              'amount': distribution.amount,
              'state': 'draft',
          })
          load.action_confirm() # Confirma la carga para actualizar el saldo de la tarjeta
      
      self.write({'state': 'loaded'})

      self.message_post(
          body=_("El plan ha sido ejecutado y las tarjetas cargadas por %s.") % self.env.user.name,
          message_type='notification',
          subtype_xmlid='mail.mt_comment',
          partner_ids=[self.create_uid.partner_id.id]
      )
      
      return True

  def action_reject(self):
      self.ensure_one()
      
      current_user = self.env.user
      if self.state == 'pending_approval' and current_user.id != self.director_id.id and not current_user.has_group('base.group_system'):
          raise ValidationError(_("Solo el director asignado puede rechazar esta propuesta."))
      
      self.write({'state': 'rejected'})
      
      self.message_post(
          body=_("El plan ha sido rechazado por %s.") % self.env.user.name,
          message_type='notification',
          subtype_xmlid='mail.mt_comment',
          partner_ids=[self.create_uid.partner_id.id]
      )
      
      # Crear actividad para el creador del plan
      self.activity_schedule(
          'mail.mail_activity_data_todo',
          summary=_("Plan de combustible rechazado"),
          note=_("Su propuesta de plan de combustible %s ha sido RECHAZADA por el director %s.\n\nMotivo: %s") % (
              self.name, self.director_id.name, self.director_comments or "Sin comentarios"
          ),
          user_id=self.create_uid.id,
          date_deadline=fields.Date.today()
      )
      
      # Marcar actividad del director como realizada
      activities = self.env['mail.activity'].search([
          ('res_model', '=', 'fuel.plan'),
          ('res_id', '=', self.id),
          ('user_id', '=', self.director_id.id)
      ])
      activities.action_done()
      
      return True

  def action_reset_to_draft(self):
      self.ensure_one()
      
      if self.state in ['rejected', 'pending_approval']:
          self.write({'state': 'draft', 'modified_by_director': False})
      
      return True

  def action_cancel(self):
      self.ensure_one()
      
      if self.state == 'loaded':
          # Revertir el uso de combustible no asignado vinculado a este plan
          # Buscar todos los registros de uso creados por este plan
          usages_to_revert = self.env['fuel.unassigned.usage'].search([
              ('plan_id', '=', self.id),
              ('source_model', '=', 'fuel.plan')
          ])
          
          for usage in usages_to_revert:
              # Llama al método revert_fuel en el registro de combustible no asignado original
              # para disminuir amount_used y actualizar el estado.
              usage.unassigned_id.revert_fuel(usage.amount_used, usage.source_model, usage.source_id)
              # El registro de uso se eliminará dentro de revert_fuel
          
          # Revertir cargas de tarjetas (solo el saldo de la tarjeta)
          card_loads = self.env['fuel.card.load'].search([
              ('name', 'like', f'PLAN-{self.name}-%'),
              ('state', '=', 'confirmed')
          ])
          for load in card_loads:
              load.action_cancel() # Esto solo revertirá el saldo de la tarjeta, no el unassigned fuel.
    
      self.write({'state': 'cancelled'})
      return True

  @api.model
  def get_dashboard_data(self):
      pending_plans = self.search_count([('state', '=', 'pending_approval')])
      
      return {
          'pending_plans': pending_plans,
      }


class FuelPlanDistribution(models.Model):
  _name = 'fuel.plan.distribution'
  _description = 'Distribución del Plan de Combustible'

  plan_id = fields.Many2one('fuel.plan', string='Plan de Combustible', required=True, ondelete='cascade')
  card_id = fields.Many2one('fuel.magnetic.card', string='Tarjeta', required=True)
  amount = fields.Float(string='Importe', required=True)
  carrier_id = fields.Many2one('fuel.carrier', string='Portador', required=True)

  _sql_constraints = [
      ('card_plan_uniq', 'unique(plan_id, card_id)', 'Una tarjeta solo puede aparecer una vez en cada plan!')
  ]

  @api.onchange('card_id')
  def _onchange_card_id(self):
      if self.card_id:
          if len(self.card_id.carrier_ids) == 1:
              self.carrier_id = self.card_id.carrier_ids[0]
          else:
              self.carrier_id = False
      else:
          self.carrier_id = False

  @api.constrains('card_id', 'carrier_id')
  def _check_card_carrier_consistency(self):
      for record in self:
          if not record.card_id or not record.carrier_id:
              continue
          
          if record.carrier_id not in record.card_id.carrier_ids:
              raise ValidationError(_(
                  "El portador '%s' no está asignado a la tarjeta '%s'. "
                  "Por favor, seleccione un portador válido para esta tarjeta."
              ) % (record.carrier_id.name, record.card_id.name))