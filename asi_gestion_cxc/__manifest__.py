{
    'name': 'ASI - GestiÃ³n de Cuentas por Cobrar',
    'version': '16.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Informe de deudas pendientes por equipo de ventas',
    'description': \"\"\"
        Este mÃ³dulo genera un informe que muestra los totales pendientes
        por equipo de ventas, ordenado por la fecha de la factura mÃ¡s antigua
        de cada equipo. Ideal para la gestiÃ³n de cobros.
    \"\"\",
    'author': 'Javier Escobar',
    'website': 'https://www.asisurl.cu',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'sales_team',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/menu_actions.xml',
        'reports/informe_equipo_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
