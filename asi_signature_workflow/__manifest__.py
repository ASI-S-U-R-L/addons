{
    'name': 'ASI Signature Workflow',
    'version': '3.0',
    'summary': 'Flujo de trabajo de firma digital entre usuarios con flujo secuencial',
    'description': """
        Módulo para crear flujos de trabajo de firma digital que permite:
        - Iniciar flujos de firma dirigidos a otros usuarios
        - Flujo secuencial: los destinatarios firman en orden
        - Seleccionar documentos locales o de Alfresco
        - Asignar roles y posiciones de firma
        - Definir carpeta de destino para mover documentos firmados
        - Crear y reutilizar plantillas de flujo
        - Notificar automáticamente cuando se completen las firmas
        - Gestionar versiones firmadas en Alfresco o carpetas compartidas
    """,
    'category': 'Tools',
    'author': 'F3nrir',
    'company': 'ASI S.U.R.L.',
    'website': 'https://antasi.asisurl.cu',
    'license': 'AGPL-3',
    'depends': [
        'asi_alfresco_integration', 
        'asi_alfresco_pdf_signature',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/signature_workflow_template_views.xml',
        'wizards/signature_workflow_wizard_views.xml',
        'wizards/pdf_selection_wizard_views.xml',
        'wizards/signature_workflow_reject_wizard_views.xml',
        'wizards/folder_selection_wizard_views.xml',
        'wizards/save_template_wizard_views.xml',
        'models/signature_workflow_views.xml',
        'views/menu_integration.xml',
        'views/alfresco_firma_wizard_workflow_view.xml',
        'views/download_page_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'uninstall_conflicting_module',
}
