from odoo import models, fields, api

class VersatObligacionType(models.Model):
    """Tipos de Obligación para exportación .obl"""
    _name = 'versat.obligacion.type'
    _description = 'Tipos de Obligación VERSAT'
    
    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código VERSAT', required=True)
    concepto = fields.Char(string='Concepto', required=True)
    guid = fields.Char(string='GUID', required=True)
    cuenta_mc = fields.Char(string='Cuenta MC', required=True)
    concepto_contrapartida = fields.Char(string='Concepto Contrapartida', required=True)
    cuenta_contrapartida = fields.Char(string='Cuenta Contrapartida', required=True)
    active = fields.Boolean(string='Activo', default=True)
    config_id = fields.Many2one('versat.finanzas.config', string='Configuración')
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'El código VERSAT debe ser único')
    ]

class VersatCobroType(models.Model):
    """Tipos de Cobro para exportación .cyp"""
    _name = 'versat.cobro.type'
    _description = 'Tipos de Cobro VERSAT'
    
    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código VERSAT', required=True)
    guid = fields.Char(string='GUID', required=True)
    concepto_contrapartida = fields.Char(string='Concepto Contrapartida', required=True)
    cuenta_contrapartida = fields.Char(string='Cuenta Contrapartida', required=True)
    tipo_deposito = fields.Selection([
        ('caja', 'Caja'),
        ('banco', 'Banco')
    ], string='Tipo de Depósito', required=True)
    active = fields.Boolean(string='Activo', default=True)
    config_id = fields.Many2one('versat.finanzas.config', string='Configuración')
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'El código VERSAT debe ser único')
    ]

class VersatFinanzasConfig(models.Model):
    """Configuración general para exportaciones financieras"""
    _name = 'versat.finanzas.config'
    _description = 'Configuración VERSAT Finanzas'
    
    name = fields.Char(string='Nombre', default='Configuración VERSAT Finanzas')
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    
    # Configuraciones generales
    unidad_default = fields.Char(string='Unidad por Defecto', required=True, default='01')
    entidad_default = fields.Char(string='Entidad por Defecto', required=True, default='01')
    
    # Cuentas por defecto
    cuenta_ingreso_efectivo = fields.Char(string='Cuenta Ingreso Efectivo', default='906')
    cuenta_caja_efectivo = fields.Char(string='Cuenta Caja Efectivo', default='4')
    cuenta_caja_banco = fields.Char(string='Cuenta Caja Banco', default='9233129970040454')
    
    # Configuración de aportes
    cuenta_aporte_10_ventas = fields.Char(string='Cuenta Aporte 10% Ventas', default='4410001')
    cuenta_costo_aporte_10 = fields.Char(string='Cuenta Costo Aporte 10%', default='805')
    cuenta_aporte_1_desarrollo = fields.Char(string='Cuenta Aporte 1% Desarrollo', default='44100160001')
    cuenta_costo_aporte_1 = fields.Char(string='Cuenta Costo Aporte 1%', default='836113')
    
    # Tipos preconfigurados
    obligacion_type_ids = fields.One2many('versat.obligacion.type', 'config_id', string='Tipos de Obligación')
    cobro_type_ids = fields.One2many('versat.cobro.type', 'config_id', string='Tipos de Cobro')

    @api.model
    def get_default_config(self):
        """Obtener o crear configuración por defecto"""
        config = self.search([], limit=1)
        if not config:
            config = self.create({})
        return config