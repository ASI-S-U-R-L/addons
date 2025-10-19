# -*- coding: utf-8 -*-
{
    'name': 'ASI POS Reports - Ventas por Mercancías',
    'version': '2.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Reportes de ventas por mercancías para Point of Sale',
    'description': """
        Módulo personalizado que extiende el Point of Sale con:
        - Botón "Ventas por Mercancías" en sesiones POS
        - Descarga automática de informe al cerrar sesión
        - Impresión en formato ticket para impresoras Epson
        - Agrupación de productos por categorías
    """,
    'author': 'F3nrir',
    'company': 'ASI S.U.R.L.',
    'website': 'https://antasi.asisurl.cu',
    'depends': ['point_of_sale', 'web', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_session_views.xml',
        'reports/pos_merchandise_report.xml',
        'reports/inventory_summary_report.xml',
        'reports/shift_balance_report.xml',
        'wizard/pos_merchandise_report_wizard_views.xml',
        'wizard/inventory_summary_wizard_views.xml',
        'wizard/pos_merchandise_report_by_date_wizard_views.xml',
        'wizard/pos_shift_balance_wizard_views.xml',
        'views/pos_reports_menu.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'asi_pos_reports/static/src/js/pos_session_close.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
