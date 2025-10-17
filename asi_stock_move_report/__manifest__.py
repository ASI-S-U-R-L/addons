{
    'name': 'ASI - Reporte de Movimientos de Inventario',
    'version': '1.6',
    'summary': 'Genera reportes consolidados de movimientos de inventario por producto',
    
    'description': "Genera reportes PDF de movimientos de inventario consolidados por producto con rango de fechas.",
    
    'author': 'F3nrir',
    'company': 'ASI S.U.R.L.',
    'website': 'https://antasi.asisurl.cu',
    'category': 'Inventory/Inventory',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/stock_move_report_wizard_view.xml',
        'wizard/product_move_report_wizard_view.xml',
        'report/stock_move_report_template.xml',
        'report/product_move_report_template.xml',
        'views/stock_menu_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
