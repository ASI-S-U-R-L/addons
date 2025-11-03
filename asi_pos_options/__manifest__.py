{
    "name": "POS: Otras opciones",
    "version": "16.0.1.0.0",
    "summary": "Añade checks en POS para ocultar botones (Cliente, Banco), forzar denominaciones en apertura/cierre, y mostrar/ocultar stock de productos.",
    "category": "Point of Sale",
    "author": "José L. Reyes Álvarez",
    "license": "LGPL-3",
    "depends": ['base', 'point_of_sale'],
    "data": ["views/pos_config_views.xml"],
    "assets": {
        "point_of_sale.assets": [
            "/asi_pos_options/static/src/js/hide_customer_by_config.js",
            "/asi_pos_options/static/src/js/force_opening_by_denominations.js",
            "/asi_pos_options/static/src/js/force_closing_by_denominations.js",
            # "/asi_pos_options/static/src/js/show_product_stock.js",
            "/asi_pos_options/static/src/js/hide_bank_payment.js",
        ]
    },
    'images': ['static/description/icon.png'],
    "installable": True,
    "application": False
}