{
    'name': 'Custom POS Ticket MYM',
    'version': '1.0.0',
    'summary': 'Custom Ticket Template for Point of Sale in M&M',
    'author': 'F3nrir',
    'company': 'ASI S.U.R.L.',
    'website': 'https://antasi.asisurl.cu',
    'category': 'Point of Sale',
    'depends': ['point_of_sale'],
    'assets': {
        'point_of_sale.assets': [
            'asi_custom_ticket_mym/static/src/xml/custom_order_receipt.xml',
            #'asi_custom_ticket_mym/static/src/css/custom_ticket.css',
        ],
    },
    'installable': True,
    'application': False,
}
