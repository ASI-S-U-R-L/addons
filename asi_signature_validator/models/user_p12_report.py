# -*- coding: utf-8 -*-
"""
Modelo para reportar usuarios con certificados P12 configurados.
Vista puramente informativa para administradores.
"""
from odoo import models, fields, api

class UserP12Report(models.Model):
    """Modelo transient para generar reporte de usuarios con P12."""
    _name = 'asi.user.p12.report'
    _description = 'Reporte de Usuarios con Certificados P12'
    
    user_id = fields.Many2one('res.users', string='Usuario', readonly=True)
    name = fields.Char(string='Nombre', readonly=True)
    email = fields.Char(string='Email', readonly=True)
    has_certificate = fields.Boolean(string='Tiene P12', readonly=True)
    has_password = fields.Boolean(string='Tiene Contraseña', readonly=True)
    has_signature_image = fields.Boolean(string='Tiene Imagen de Firma', readonly=True)
    certificate_date = fields.Datetime(string='Fecha de Configuración', readonly=True)
    
    @api.model
    def get_users_with_p12(self):
        """
        Obtiene todos los usuarios que tienen certificado P12 configurado.
        Returns: Lista de diccionarios con información de usuarios.
        """
        users = self.env['res.users'].sudo().search([
            ('certificado_firma', '!=', False)
        ])
        
        result = []
        for user in users:
            result.append({
                'id': user.id,
                'name': user.name,
                'login': user.login,
                'email': user.email or '',
                'has_certificate': bool(user.certificado_firma),
                'has_password': bool(user.contrasena_certificado),
                'has_signature_image': bool(user.imagen_firma),
                'write_date': user.write_date,
            })
        
        return result
