{
    'name': 'VERSAT Finanzas Exports',
    'version': '16.0.4.0.0',
    'category': 'Accounting',
    'summary': 'Exportación unificada a VERSAT desde asientos contables y POS',
    'description': """
        Módulo para exportar documentos financieros de Odoo al formato VERSAT
        Soporte completo para:
        - Asientos contables
        - Pedidos de Punto de Venta (POS)
        - Exportación masiva con estructura organizada
        - Formatos .obl y .cyp exactos para VERSAT
    """,
    'author': 'Reysel',
    'website': 'https://antasi.asisurl.cu',
    'depends': ['account', 'point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/versat_default_data.xml',
        'views/versat_config_views.xml',
        'views/export_wizard_views.xml',
        'views/menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
