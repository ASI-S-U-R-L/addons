{
    'name': 'Exportación VERSAT para Inventario',
    'version': '1.0',
    'summary': 'Exportar transferencias de stock al formato VERSAT',
    'description': """
        Módulo para exportar transferencias de stock al formato .mvt compatible con el sistema VERSAT de inventarios.
        Permite configurar conceptos VERSAT por tipo de operación y generar archivos ZIP con múltiples archivos .mvt.
    """,
    'category': 'Inventory',
    'author': 'Reysel Osorio',
    'website': 'https://antasi.asisurl.cu',
    'depends': ['stock', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_picking_type_views.xml',
        'views/stock_versat_export_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}