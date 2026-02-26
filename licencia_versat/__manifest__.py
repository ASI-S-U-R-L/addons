# -*- coding: utf-8 -*-
{
    'name': 'Licencias Versat',
    'version': '16.0.1.0.0',
    'summary': 'Módulo para gestión de solicitudes de licencias Versat',
    'author': 'Custom',
    'category': 'Services',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/servicio_data.xml',
        'data/persona_data.xml',
        'views/res_config_settings_views.xml',
        'views/convenio_views.xml',
        'views/solicitud_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
