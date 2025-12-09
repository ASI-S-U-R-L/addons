from odoo import models, fields, api, _
import base64
import logging

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    certificado_firma = fields.Binary(string='Certificado de Firma Digital (.p12)', attachment=True, help='Archivo .p12 para firma digital')
    nombre_certificado = fields.Char(string='Nombre del Certificado', help='Nombre del archivo del certificado')
    imagen_firma = fields.Binary(string='Imagen de Firma', attachment=True, help='Imagen que se utilizará para firmar documentos')
    contrasena_certificado = fields.Char(string='Contraseña del Certificado', help='Contraseña del certificado .p12 (se almacena de forma cifrada)')
    
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            args = ['|', '|', ('login', operator, name), ('name', operator, name), ('email', operator, name)] + args
        return self._search(args, limit=limit, access_rights_uid=name_get_uid)
    
    def _cifrar_contrasena(self, contrasena):
        """Cifra la contraseña usando base64 (método básico)"""
        if not contrasena:
            return False
        import base64
        return base64.b64encode(contrasena.encode('utf-8')).decode('utf-8')

    def _descifrar_contrasena(self, contrasena_cifrada):
        """Descifra la contraseña"""
        if not contrasena_cifrada:
            return False
        import base64
        try:
            return base64.b64decode(contrasena_cifrada.encode('utf-8')).decode('utf-8')
        except:
            return False

    def write(self, vals):
        """Cifrar la contraseña antes de guardar"""
        if 'contrasena_certificado' in vals and vals['contrasena_certificado']:
            vals['contrasena_certificado'] = self._cifrar_contrasena(vals['contrasena_certificado'])
        return super(ResUsers, self).write(vals)

    def get_contrasena_descifrada(self):
        """Obtiene la contraseña descifrada"""
        self.ensure_one()
        return self._descifrar_contrasena(self.contrasena_certificado)
