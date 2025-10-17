# -*- coding: utf-8 -*-
{
    'name': 'ASI Solicitudes de Firma',
    'version': '1.5',
    'summary': 'Flujo de trabajo de firma digital local entre usuarios',
    'description': """
        Módulo para crear flujos de trabajo de firma digital local que permite:
        - Iniciar flujos de firma dirigidos a otros usuarios
        - Seleccionar documentos locales (ir.attachment)
        - Asignar roles y posiciones de firma
        - Notificar automáticamente cuando se completen las firmas
        - Gestionar versiones firmadas localmente
    """,
    'category': 'Tools',
    'author': 'F3nrir',
    'company': 'ASI S.U.R.L.',
    'website': 'https://antasi.asisurl.cu',
    'license': 'AGPL-3',
    'depends': [
        'asi_pdf_signature',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizards/local_workflow_wizard_views.xml',
        'wizards/local_workflow_reject_wizard_views.xml',
        'models/local_workflow_views.xml',
        'views/menu_integration.xml',
        'views/firma_documento_wizard_workflow_view.xml',
        'views/download_page_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'uninstall_conflicting_module',
}
