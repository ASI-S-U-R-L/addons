{'name': 'ASI Firma Web', 'summary': 'Firmar documentos PDF desde el sitio web usando asi_pdf_signature', 
 'version': '16.0.1.0.0',
   'category': 'Website',
   'author': 'Jose L. Reyes Alvarez', 
 'depends': ['website', 'asi_pdf_signature'], 
 'data': ['data/website_menu.xml', 'views/templates.xml'],
 'assets': {
   'web.assets_frontend': [
     'asi_firma_web/static/src/css/drag_drop.css',
     'asi_firma_web/static/src/js/drag_drop.js',
   ],
 },
 'license': 'LGPL-3',
   'images': ['static/description/icon.png'],
   'installable': True,
   'application': False}