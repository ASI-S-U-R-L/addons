{
    'name': 'SGICHS Software AI Classification',
    'summary': 'Clasificación automática de software usando IA',
    'author': 'ALejandro Céspedes Pérez',
    'website': 'https://www.asisurl.cu',
    'category': 'IT/Software',
    'version': '16.0.1.0.0',
    'depends': ['asi_ia', 'sgichs_software'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'data/ir.cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}