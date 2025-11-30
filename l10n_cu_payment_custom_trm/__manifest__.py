# -*- coding: utf-8 -*-
{
    'name': "Transfermovil Wire Transfer",

    'summary': """
        Extending Wire Transfers to generate Transfermovil qr on payment transaction""",

    'description': """
        Extending Wire Transfers to generate Transfermovil qr on payment transaction
    """,

    'author': "rolandoperezrebollo@gmail.com",

    # Categories can be used to filter modules in modules listing
    'category': 'Accounting',
    'version': '16.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['payment', 'payment_custom'],

    # always loaded
    'data': [
        'data/payment_provider_data.xml',
        'views/payment_custom_templates.xml',
        'views/website_sale_templates.xml',
        'views/res_users_views.xml',
    ],
}
