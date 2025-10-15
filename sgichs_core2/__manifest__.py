# -*- coding: utf-8 -*-
{
    'name': "SGICH Core",
    'summary': """
        Módulo base para la Gestión de Infraestructura y Cambios de TI.
        Proporciona los modelos centrales para la gestión de activos,
        incidentes y tareas programadas.""",
    'author': "Tu Nombre",
    'website': "https://www.tuweb.com",
    'category': 'IT/Infrastructure',
    'version': '16.0.1.0.0',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/it_asset_views.xml',
        'views/it_asset_backlog_views.xml',
        'views/incident_views.xml',
        'views/scheduled_task_views.xml',
        'views/res_config_settings_views.xml',
        'views/dashboard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Esto se asegura de que la librería de gráficos se cargue primero,
            # seguida del CSS para el estilo, el JS con la lógica y finalmente el template XML.
            'sgichs_core2/static/src/js/Chart.min.js',
            'sgichs_core2/static/src/css/dashboard.css',
            'sgichs_core2/static/src/js/dashboard.js',
            'sgichs_core2/static/src/xml/dashboard_templates.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}