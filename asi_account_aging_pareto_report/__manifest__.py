{
    'name': 'Account Aging & Pareto Report',
    'version': '16.0.1.0.0',
    'summary': 'Informe de gestión de cobros: Pareto (20/80) y envejecimiento de deudas',
    'author': 'Javier + Copilot',
    'website': '',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'security/ir_model_access.csv',
        'views/aging_pareto_wizard_views.xml',
        'reports/aging_pareto_report.xml',
        'reports/aging_pareto_templates.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
}
