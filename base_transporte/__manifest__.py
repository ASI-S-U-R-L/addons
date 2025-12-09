# -*- coding: utf-8 -*-
{
    'name': 'Fleet Vehicle Custom Fields',
    'version': '16.0.1.0.0',
    'category': 'Human Resources/Fleet',
    'summary': 'Extensión del módulo Fleet con campos personalizados para tipos de vehículos, consumo y gestión de licencias de conducir',
    'description': """
        Este módulo extiende el módulo Fleet base de Odoo añadiendo:
        - Tipos de vehículos: Móvil, Tecnológico, Estacionario
        - Gestión de tipos de consumo según el tipo de vehículo
        - Capacidad de tanques (simple o doble)
        - Control de combustible inicial
        - Índice de consumo de fábrica
        - Gestión completa de licencias de conducir para choferes
        - Múltiples licencias por chofer con diferentes tipos
        - Control de vencimientos y estados de licencias
        - Validaciones de compatibilidad chofer-vehículo
    """,
    'author': 'ASI S.U.R.L.',
    'website': 'https://www.asisurl.cu',
    'depends': ['fleet'],
    'data': [
        'security/ir.model.access.csv',
        'data/fleet_driver_license_cron.xml',
        'views/fleet_driver_license_views.xml',
        'views/res_partner_views.xml',
        'views/fleet_vehicle_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
