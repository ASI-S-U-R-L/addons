{
    "name": "POS: Otras opciones",
    "version": "16.0.2.0.0",
    "summary": "Añade checks en POS para ocultar botones (Cliente, Banco), forzar denominaciones en apertura/cierre con persistencia de datos, y mostrar/ocultar stock de productos.",
    "description": """
Módulo de opciones avanzadas para Point of Sale que incluye:

Funcionalidades principales:
- Ocultar botones de cliente y funciones relacionadas
- Forzar conteo por denominaciones en apertura/cierre de caja
- **NUEVO**: Persistencia de datos de denominaciones en base de datos
- **NUEVO**: Informes y auditoría de control de efectivo
- Ocultar método de pago Banco/Transferencia
- Mostrar QR de Transfermovil para pagos

Características técnicas:
- Datos de denominaciones se almacenan en modelo pos.session.denomination.control
- Informes detallados con vistas pivot y gráficos
- Integración completa con sesión POS
- Campos computados para análisis de diferencias
- Filtros y agrupaciones avanzadas
    """,
    "category": "Point of Sale",
    "author": "José L. Reyes Álvarez",
    "license": "LGPL-3",
    "depends": ['base', 'point_of_sale', 'l10n_cu_payment_custom_trm'],
    "data": [
        "data/ir.model.access.csv",
        "views/pos_config_views.xml",
        "views/pos_session_denomination_control_views.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "/asi_pos_options/static/src/js/denominations_table_widget.js",
            "/asi_pos_options/static/src/xml/denominations_table_widget.xml",
        ],
        "point_of_sale.assets": [
            "/asi_pos_options/static/src/js/hide_customer_by_config.js",
            "/asi_pos_options/static/src/js/force_opening_by_denominations.js",
            "/asi_pos_options/static/src/js/force_closing_by_denominations.js",
            # "/asi_pos_options/static/src/js/show_product_stock.js",
            "/asi_pos_options/static/src/js/hide_bank_payment.js",
            "/asi_pos_options/static/src/js/show_trm_qr_in_pos.js",
            
        ]
    },
    'images': ['static/description/icon.png'],
    "installable": True,
    "application": False
}