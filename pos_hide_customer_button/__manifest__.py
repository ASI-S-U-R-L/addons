
{
    "name": "POS: Restricciones en la sesión del POS",
    "version": "16.0.1.0",
    "summary": "Añade un check en POS para ocultar el botón 'Cliente' y un check para obligar al usuario a usar denominación por billetes al iniciar sesión en el POS.",
    "category": "Point of Sale",
    "author": "José L. Reyes Álvarez",
    "license": "LGPL-3",
    "depends":  ['base','point_of_sale'],
    "data": ["views/pos_config_views.xml"],
    "assets": {
        "point_of_sale.assets": [
            "/pos_hide_customer_button/static/src/js/hide_customer_by_config.js",
            "/pos_hide_customer_button/static/src/js/force_opening_by_denominations.js",
             "/pos_hide_customer_button/static/src/js/force_closing_by_denominations.js",
        ]
    },
    'images': ['static/description/icon.png'],  # Ruta del icono
    "installable": True,
    "application": False
}
