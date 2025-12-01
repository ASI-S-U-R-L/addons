# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class FleetDriverLicense(models.Model):
    _name = 'fleet.driver.license'
    _description = 'Licencia de Conducir'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'partner_id, license_type, issue_date desc'
    _rec_name = 'display_name'

    # Relación con el chofer (res.partner)
    partner_id = fields.Many2one(
        'res.partner', 
        string='Chofer', 
        required=True, 
        ondelete='cascade',
        help='Chofer propietario de esta licencia',
        tracking=True
    )

    # Información básica de la licencia
    license_number = fields.Char(
        string='Número de Licencia', 
        required=True,
        help='Número único de la licencia de conducir',
        tracking=True
    )

    license_type = fields.Selection([
        ('a', 'Tipo A - Motocicletas'),
        ('b', 'Tipo B - Automóviles'),
        ('c', 'Tipo C - Camiones'),
        ('d', 'Tipo D - Ómnibus'),
        ('e', 'Tipo E - Articulados'),
        ('f', 'Tipo F - Maquinaria Agrícola'),
        ('g', 'Tipo G - Maquinaria de Construcción'),
    ], string='Tipo de Licencia', required=True, help='Categoría de la licencia de conducir', tracking=True)

    # Fechas importantes
    issue_date = fields.Date(
        string='Fecha de Emisión', 
        required=True,
        default=fields.Date.today,
        help='Fecha en que fue emitida la licencia',
        tracking=True
    )

    expiry_date = fields.Date(
        string='Fecha de Vencimiento', 
        required=True,
        help='Fecha de vencimiento de la licencia',
        tracking=True
    )

    # Estado de la licencia
    state = fields.Selection([
        ('active', 'Vigente'),
        ('expired', 'Vencida'),
        ('suspended', 'Suspendida'),
        ('revoked', 'Revocada'),
    ], string='Estado', default='active', required=True, tracking=True)

    # Información adicional
    issuing_authority = fields.Char(
        string='Autoridad Emisora',
        help='Entidad que emitió la licencia'
    )

    restrictions = fields.Text(
        string='Restricciones',
        help='Restricciones específicas de esta licencia'
    )

    notes = fields.Text(
        string='Observaciones',
        help='Notas adicionales sobre la licencia'
    )

    # Campos computados
    display_name = fields.Char(
        string='Nombre para Mostrar',
        compute='_compute_display_name',
        store=True
    )

    days_to_expiry = fields.Integer(
        string='Días para Vencer',
        compute='_compute_days_to_expiry',
        store=True,
        help='Días restantes hasta el vencimiento'
    )

    is_expired = fields.Boolean(
        string='Está Vencida',
        compute='_compute_is_expired',
        store=True
    )

    is_expiring_soon = fields.Boolean(
        string='Vence Pronto',
        compute='_compute_is_expiring_soon',
        store=True,
        help='Vence en los próximos 30 días'
    )

    # Campos relacionados para facilitar búsquedas
    partner_name = fields.Char(
        related='partner_id.name',
        string='Nombre del Chofer',
        store=True
    )

    @api.depends('license_number', 'license_type', 'partner_id.name')
    def _compute_display_name(self):
        for record in self:
            license_type_name = dict(record._fields['license_type'].selection).get(record.license_type, '')
            record.display_name = f"{record.license_number} - {license_type_name} ({record.partner_id.name or 'Sin Chofer'})"

    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        today = date.today()
        for record in self:
            if record.expiry_date:
                delta = record.expiry_date - today
                record.days_to_expiry = delta.days
            else:
                record.days_to_expiry = 0

    @api.depends('expiry_date', 'state')
    def _compute_is_expired(self):
        today = date.today()
        for record in self:
            if record.expiry_date and record.expiry_date < today:
                record.is_expired = True
                if record.state == 'active':
                    record.state = 'expired'
            else:
                record.is_expired = False

    @api.depends('days_to_expiry')
    def _compute_is_expiring_soon(self):
        for record in self:
            record.is_expiring_soon = 0 <= record.days_to_expiry <= 30

    @api.constrains('license_number', 'partner_id', 'license_type')
    def _check_unique_license_per_type(self):
        for record in self:
            existing = self.search([
                ('license_number', '=', record.license_number),
                ('license_type', '=', record.license_type),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValidationError(
                    _('Ya existe una licencia con el número %s del tipo %s.') % 
                    (record.license_number, dict(record._fields['license_type'].selection)[record.license_type])
                )

    @api.constrains('issue_date', 'expiry_date')
    def _check_dates(self):
        for record in self:
            if record.issue_date and record.expiry_date:
                if record.expiry_date <= record.issue_date:
                    raise ValidationError(
                        _('La fecha de vencimiento debe ser posterior a la fecha de emisión.')
                    )

    @api.model
    def _cron_update_expired_licenses(self):
        """Cron job para actualizar automáticamente el estado de licencias vencidas"""
        today = date.today()
        expired_licenses = self.search([
            ('expiry_date', '<', today),
            ('state', '=', 'active')
        ])
        if expired_licenses:
            expired_licenses.write({'state': 'expired'})
            return len(expired_licenses)
        return 0

    def action_view_partner_licenses(self):
        """Acción para ver todas las licencias del chofer"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Licencias de %s') % self.partner_id.name,
            'res_model': 'fleet.driver.license',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id)],
            'context': {
                'default_partner_id': self.partner_id.id,
            }
        }

    def action_renew_license(self):
        """Acción para renovar una licencia"""
        self.ensure_one()
        if self.state != 'expired':
            raise ValidationError(_('Solo se pueden renovar licencias vencidas.'))
        
        # Crear wizard para renovación (se puede implementar más adelante)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Renovar Licencia'),
            'res_model': 'fleet.driver.license',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_license_type': self.license_type,
                'default_license_number': self.license_number,
                'default_issuing_authority': self.issuing_authority,
            }
        }

    def action_suspend_license(self):
        """Acción para suspender una licencia"""
        self.ensure_one()
        self.state = 'suspended'
        # Crear mensaje en el chatter
        self.message_post(
            body=_('Licencia suspendida por el usuario %s') % self.env.user.name,
            message_type='notification'
        )

    def action_activate_license(self):
        """Acción para activar una licencia suspendida"""
        self.ensure_one()
        if self.is_expired:
            raise ValidationError(_('No se puede activar una licencia vencida. Debe renovarla primero.'))
        self.state = 'active'
        # Crear mensaje en el chatter
        self.message_post(
            body=_('Licencia activada por el usuario %s') % self.env.user.name,
            message_type='notification'
        )
