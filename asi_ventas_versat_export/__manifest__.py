{
    'name': 'VERSAT Finanzas Exports',
    'version': '16.0.3.0.0',
    'category': 'Accounting',
    'summary': 'Exportación unificada de documentos financieros a VERSAT desde asientos contables',
    'description': """
        Módulo para exportar documentos financieros de Odoo al formato VERSAT
        Exportación unificada desde asientos contables:
        - Cuentas por Cobrar (.obl)
        - Aportes al Presupuesto (.obl) 
        - Cobros en Caja (.cyp)
        - Cobros en Banco (.cyp)
        Detección automática y organización en carpetas
    """,
    'author': 'Tu Nombre',
    'website': 'https://www.tudominio.com',
    'depends': ['account', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'data/versat_default_data.xml',
        'views/versat_config_views.xml',
        'views/export_wizard_views.xml',
        'views/menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}