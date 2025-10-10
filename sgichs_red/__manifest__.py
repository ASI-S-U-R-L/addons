# -*- coding: utf-8 -*-
{
    'name': "SGICH Network Management",
    'summary': """
        Añade gestión de direcciones IP, servicios de red y monitoreo
        de conectividad (ping) a los activos de hardware.""",
    'author': "Tu Nombre",
    'website': "https://www.tuweb.com",
    'category': 'IT/Infrastructure',
    'version': '16.0.1.0.0',
    'depends': ['sgichs_core2', 'sgichs_hardware'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_jobs.xml',
	    'data/demo_data_network.xml',
        'views/ip_address_views.xml',
        'views/network_service_views.xml',
        'views/hardware_views.xml',
        'views/it_asset_backlog_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    
    'auto_install': False,
}