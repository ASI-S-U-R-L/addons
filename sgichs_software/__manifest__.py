{
    'name': 'SGICH Software Management',
    'summary': 'Gestión de software y listas de control',
    'author': 'Tu Nombre',
    'website': 'https://www.tudominio.com',
    'category': 'IT/Software',
    'version': '16.0.1.0.0',
    'depends': ['sgichs_core2', 'sgichs_hardware'],
    'data': [
        'security/ir.model.access.csv',
        'views/software_views.xml',
        'views/hw_list_views.xml',
        'views/menus.xml',
        'views/it_asset_backlog_views.xml',
        'views/hardware.xml',
	    'data/demo_data_software.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sgichs_software/static/src/js/dashboard_software.js',
            'sgichs_software/static/src/xml/dashboard_software_templates.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}