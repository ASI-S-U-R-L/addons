{
    'name': 'ASI Signature Workflow',
    'version': '2.3',
    'summary': 'Flujo de trabajo de firma digital entre usuarios',
    'description': """
        Módulo para crear flujos de trabajo de firma digital que permite:
        - Iniciar flujos de firma dirigidos a otros usuarios
        - Seleccionar documentos locales o de Alfresco
        - Asignar roles y posiciones de firma
        - Notificar automáticamente cuando se completen las firmas
        - Gestionar versiones firmadas en Alfresco o carpetas compartidas
    """,
    'category': 'Tools',
    'author': 'F3nrir',
    'company': 'ASI S.U.R.L.',
    'website': 'https://antasi.asisurl.cu',
    'license': 'AGPL-3',
    'depends': [
        'asi_pdf_signature',
        'asi_alfresco_integration', 
        'asi_alfresco_pdf_signature',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        #'data/mail_templates.xml',
        'wizards/signature_workflow_wizard_views.xml',
        'wizards/pdf_selection_wizard_views.xml',
        'wizards/signature_workflow_reject_wizard_views.xml',
        'models/signature_workflow_views.xml',
        'views/menu_integration.xml',
        'views/alfresco_firma_wizard_workflow_view.xml',
        'views/firma_documento_wizard_workflow_view.xml',
        'views/download_page_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'uninstall_conflicting_module',
}
