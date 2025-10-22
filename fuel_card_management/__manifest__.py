# -*- coding: utf-8 -*-
{
    'name': 'Gestión de Tarjetas Prepagadas de Combustible',
    'version': '1.0',
    'summary': 'Gestión de tarjetas prepagadas de combustible',
    'description': """
        Módulo para gestionar el Registro y Control de Tarjetas Prepagadas de Combustible.
        Incluye funcionalidades para:
        - Gestión de tarjetas magnéticas
        - Control de saldos
        - Facturación de combustible
        - Carga de tarjetas
        - Entrega y devolución de tarjetas
        - Tickets de compra de combustible
        - Ajustes y traspasos de saldo
        - Propuestas de plan de combustible con aprobación del director
    """,
    'category': 'Fleet',
    'author': 'Juan Miguel Zaldivar Gordo',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'account',
        'fleet',
        'mail',
        'base_transporte',
        'fleet_vehicle_log_fuel',
        'web', # Añadido por el uso de componentes de interfaz de usuario
    ],
    'data': [
       
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/cron_data.xml',

        
      
        'views/magnetic_card_views.xml',
        'views/fuel_carrier_views.xml',
        'views/unassigned_fuel_views.xml',
        'views/fuel_invoice_views.xml',
        'views/card_load_views.xml',
        'views/balance_adjustment_views.xml',
        'views/balance_transfer_views.xml',
        'views/fuel_plan_views.xml',
        'views/fleet_vehicle_log_fuel_views_inherit.xml',
     
        'views/fuel_card_balance_report_wizard_views.xml',
        'views/dashboard_views.xml',
        
        
        'report/fuel_consumption_report.xml',
        'report/card_balance_report.xml',
        'report/fuel_card_balance_report.xml',
        'report/fuel_card_balance_report_template.xml',
        'report/report_templates.xml',
        
     
        'views/magnetic_card_views_action.xml',
        'views/card_load_views_action.xml',
        'views/fuel_invoice_views_action.xml',
        'views/unassigned_fuel_views_action.xml',
        'views/balance_adjustment_views_action.xml',
        'views/balance_transfer_views_action.xml',
        'views/fuel_plan_views_action.xml',
        
        # Cargar vistas que referencian acciones
        'views/vehicle_views.xml',
        'views/card_delivery_views.xml',
        
       
        'views/menu_views.xml',
        
       
        'data/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'fuel_card_management/static/src/js/dashboard.js',
            'fuel_card_management/static/src/css/dashboard.css',
        ],
    },
    'qweb': [
        'static/src/xml/dashboard.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

