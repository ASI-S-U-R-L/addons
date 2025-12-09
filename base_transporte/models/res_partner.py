# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Relación con licencias de conducir
    driver_license_ids = fields.One2many(
        'fleet.driver.license', 
        'partner_id', 
        string='Licencias de Conducir',
        help='Licencias de conducir del chofer'
    )

    # Campos computados para información rápida
    driver_license_count = fields.Integer(
        string='Cantidad de Licencias',
        compute='_compute_driver_license_info',
        store=True
    )

    active_licenses_count = fields.Integer(
        string='Licencias Vigentes',
        compute='_compute_driver_license_info',
        store=True
    )

    expired_licenses_count = fields.Integer(
        string='Licencias Vencidas',
        compute='_compute_driver_license_info',
        store=True
    )

    has_expired_licenses = fields.Boolean(
        string='Tiene Licencias Vencidas',
        compute='_compute_driver_license_info',
        store=True
    )

    has_expiring_licenses = fields.Boolean(
        string='Tiene Licencias por Vencer',
        compute='_compute_driver_license_info',
        store=True
    )

    license_types_summary = fields.Char(
        string='Tipos de Licencia',
        compute='_compute_driver_license_info',
        store=True,
        help='Resumen de tipos de licencia vigentes'
    )

    # Campo para identificar si es chofer
    is_driver = fields.Boolean(
        string='Es Chofer',
        compute='_compute_is_driver',
        store=True,
        help='Indica si esta persona es un chofer (tiene licencias o está asignado a vehículos)'
    )

    @api.depends('driver_license_ids', 'driver_license_ids.state', 'driver_license_ids.is_expiring_soon', 'driver_license_ids.license_type')
    def _compute_driver_license_info(self):
        for partner in self:
            licenses = partner.driver_license_ids
            partner.driver_license_count = len(licenses)
            
            active_licenses = licenses.filtered(lambda l: l.state == 'active')
            partner.active_licenses_count = len(active_licenses)
            
            expired_licenses = licenses.filtered(lambda l: l.state == 'expired')
            partner.expired_licenses_count = len(expired_licenses)
            partner.has_expired_licenses = bool(expired_licenses)
            
            expiring_licenses = licenses.filtered(lambda l: l.is_expiring_soon and l.state == 'active')
            partner.has_expiring_licenses = bool(expiring_licenses)
            
            # Resumen de tipos de licencia vigentes
            if active_licenses:
                license_types = active_licenses.mapped('license_type')
                type_names = [dict(active_licenses[0]._fields['license_type'].selection)[lt] for lt in license_types]
                partner.license_types_summary = ', '.join(sorted(set(type_names)))
            else:
                partner.license_types_summary = 'Sin licencias vigentes'

    @api.depends('driver_license_ids')
    def _compute_is_driver(self):
        # También considerar si está asignado como conductor a algún vehículo
        for partner in self:
            has_licenses = bool(partner.driver_license_ids)
            
            # Verificar si está asignado a algún vehículo
            is_vehicle_driver = bool(self.env['fleet.vehicle'].search([
                '|', 
                ('driver_id', '=', partner.id),
                ('future_driver_id', '=', partner.id)
            ], limit=1))
            
            partner.is_driver = has_licenses or is_vehicle_driver

    def action_view_driver_licenses(self):
        """Acción para ver las licencias del chofer"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Licencias de %s') % self.name,
            'res_model': 'fleet.driver.license',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {
                'default_partner_id': self.id,
            }
        }

    def action_add_driver_license(self):
        """Acción para añadir una nueva licencia"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nueva Licencia para %s') % self.name,
            'res_model': 'fleet.driver.license',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            }
        }

    @api.model
    def get_drivers_with_expiring_licenses(self, days=30):
        """Método para obtener choferes con licencias por vencer"""
        return self.search([
            ('has_expiring_licenses', '=', True)
        ])

    def check_license_for_vehicle_type(self, vehicle_custom_type):
        """Verificar si el chofer tiene licencia válida para el tipo de vehículo"""
        self.ensure_one()
        
        # Mapeo de tipos de vehículo a tipos de licencia requeridos
        vehicle_license_mapping = {
            'movil': ['b', 'c'],  # Automóviles o camiones
            'tecnologico': ['c', 'd'],  # Camiones o ómnibus (vehículos especializados)
            'estacionario': [],  # No requiere licencia (generadores/turbinas)
        }
        
        required_licenses = vehicle_license_mapping.get(vehicle_custom_type, [])
        
        if not required_licenses:  # Estacionarios no requieren licencia
            return True
            
        active_licenses = self.driver_license_ids.filtered(lambda l: l.state == 'active')
        driver_license_types = active_licenses.mapped('license_type')
        
        # Verificar si tiene al menos una licencia válida para el tipo de vehículo
        return any(license_type in required_licenses for license_type in driver_license_types)
