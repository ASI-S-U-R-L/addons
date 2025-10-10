# -*- coding: utf-8 -*-
{
    'name': "SGICH Users Management",
    'summary': """Gestión de usuarios de TI y sus autorizaciones, y su relación con los activos de hardware.""",
    'author': "Tu Nombre",
    'website': "https://www.tuweb.com",
    'category': 'IT/Infrastructure',
    'version': '16.0.1.0.1',
    'depends': ['sgichs_core2', 'sgichs_hardware'],
    'data': [
        'security/ir.model.access.csv',
        'views/it_user_views.xml',
        'views/it_user_profile_views.xml',
        'views/menus.xml',
	    'data/demo_data_users.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}