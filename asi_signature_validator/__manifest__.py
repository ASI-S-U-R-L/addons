# -*- coding: utf-8 -*-
# Módulo para validar certificados .p12 y verificar firmas digitales en PDFs
# Permite a los usuarios desde el sitio web:
# 1. Validar certificados P12 y ver su información (emisor, titular, expiración)
# 2. Verificar firmas digitales en documentos PDF
# 3. Validar contra entidades certificadoras configuradas

{
    'name': 'ASI Validador de Firmas',
    'summary': 'Validar certificados P12 y verificar firmas digitales en PDFs desde el sitio web',
    'version': '2.5.0',
    'category': 'Website',
    'author': 'F3nrir',
    'company': 'ASI S.U.R.L.',
    'website': 'https://antasi.asisurl.cu',
    'depends': ['website', 'asi_pdf_signature'],
    'data': [
        'security/ir.model.access.csv',
        'views/certificate_authority_views.xml',
        'views/user_p12_report_views.xml',
        'data/ir_cron.xml',
        'data/website_menu.xml',
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'asi_signature_validator/static/src/css/validator.css',
            'asi_signature_validator/static/src/js/validator.js',
        ],
    },
    'license': 'LGPL-3',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
}
