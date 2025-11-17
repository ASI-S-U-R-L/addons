{
    'name': 'ASI Custom Sale',
    'version': '16.0.1.0.0',
    'summary': 'Personalizaciones para ventas, facturas y socios.',
    'description': """
        Este módulo agrega personalizaciones a las órdenes de venta, facturas y socios.
        Incluye campos adicionales, filtros personalizados y mejoras en los informes.
    """,
    'author': 'Javier',
    'website': 'https://www.asisurl.cu',
    'category': 'Sales',
    'depends': ['base','web','sale', 'account'],
    'data': [
        'views/invoice_views.xml',
        'views/partner_views.xml',  
        'views/sale_order_views.xml',
        'reports/report_templates.xml',
        'reports/report_invoice_extend.xml',
        'reports/sale_report.xml',
    ],
    'assets': {
        'web.assets_common': [
            'asi_custom_sale/static/src/css/styles.css',
        ],
    },
   
    'installable': True,
    'application': True,
}