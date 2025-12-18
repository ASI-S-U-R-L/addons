# -*- coding: utf-8 -*-
"""
Extensión del modelo res.users para agregar campos computados de texto
que muestran "SÍ" o "NO" para la vista administrativa.
"""
from odoo import models, fields, api


class ResUsers(models.Model):
    """Extiende res.users para agregar campos computados de texto."""
    _inherit = 'res.users'
    
    # Campos computados que devuelven "SÍ" o "NO" como texto
    has_p12_text = fields.Char(
        string='Tiene P12',
        compute='_compute_p12_status_text',
        store=False
    )
    
    has_password_text = fields.Char(
        string='Tiene Contraseña',
        compute='_compute_p12_status_text',
        store=False
    )
    
    has_signature_image_text = fields.Char(
        string='Tiene Imagen de Firma',
        compute='_compute_p12_status_text',
        store=False
    )
    
    @api.depends('certificado_firma', 'contrasena_certificado', 'imagen_firma')
    def _compute_p12_status_text(self):
        """
        Calcula el texto "SÍ" o "NO" para cada campo.
        Usado en la vista administrativa de usuarios con P12.
        """
        for user in self:
            user.has_p12_text = 'SÍ' if user.certificado_firma else 'NO'
            user.has_password_text = 'SÍ' if user.contrasena_certificado else 'NO'
            user.has_signature_image_text = 'SÍ' if user.imagen_firma else 'NO'
