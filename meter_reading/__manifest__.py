{
    'name': 'Control de Lecturas de Metrocontadores',
    'version': '16.0.1.0.0',
    'category': 'Operations',
    'summary': 'Módulo para el control del consumo eléctrico',
    'description': '''
        Módulo que permite:
        - Registro de metrocontadores (normales , inteligentes y prepagos)
        - Control de planes energéticos
        - Lecturas diarias con múltiples franjas horarias
        - Control de picos y valles energéticos
        - Reportes y alertas de consumo
        - Bitácora de consumo energético
        - Plan vs Real
        - Consumo total de la Entidad
    ''',
    'author': 'Juan Miguel Zaldivar Gordo',
    'website': 'https://antasi.asisurl.cu',
    'depends': ['base', 'mail'],
    'data': [
    'security/meter_reading_security.xml',
    'security/ir.model.access.csv',
    'data/meter_reading_data.xml',
    'views/metrocontador_views.xml',
    'views/plan_energetico_views.xml',
    'views/lectura_consumo_views.xml',
    'wizard/bitacora_views_simple.xml',
    'wizard/consumo_total_empresa_views.xml',  
    'views/meter_reading_menus.xml',   
],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
