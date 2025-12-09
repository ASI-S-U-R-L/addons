{
    "name": "Alfresco Tasks Integration",
    "version": "1.3",
    "summary": "Sincroniza tareas de Alfresco con actividades de Odoo",
    "description": """
        Este módulo sincroniza las tareas asignadas en Alfresco con actividades en Odoo.
        
        Características:
        - Campo alfresco_user en res.users para mapear usuarios de Odoo con Alfresco
        - Cron cada 5 minutos que revisa tareas en Alfresco
        - Crea actividades automáticamente para usuarios con alfresco_user configurado
        - Las actividades se crean con fecha de vencimiento del día actual
        - Sincroniza documentos asociados a las tareas
        - Permite descargar documentos directamente desde Alfresco
        - Vista Kanban organizada por estado de la tarea
        - Botón de Firmar para procesar tareas con firma digital
        - Wizard de firma digital con gestión de errores
        - Actualización automática del estado de tarea en Alfresco
    """,
    "category": "Tools",
    "author": "F3nrir",
    "company": "ASI S.U.R.L.",
    "website": "https://antasi.asisurl.cu",
    "depends": ["base", "mail", "asi_alfresco_integration", "asi_pdf_signature"],
    "external_dependencies": {
        "python": ["requests"]
    },
    "data": [
        "security/ir.model.access.csv",
        "views/res_users_views.xml",
        "views/alfresco_task_views.xml",
        "data/mail_activity_type_data.xml",
        "data/cron_sync_alfresco_tasks.xml",
        "wizards/alfresco_task_firma_wizard_views.xml",
    ],
    "images": ["static/description/icon.png"],
    "installable": True,
    "auto_install": False,
    "application": True,
    "license": "LGPL-3",
}