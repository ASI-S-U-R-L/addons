# -*- coding: utf-8 -*-

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    credit_card_number = fields.Char(string='Número de Tarjeta de Crédito')
    phone_extra = fields.Char(string='Teléfono Extra')