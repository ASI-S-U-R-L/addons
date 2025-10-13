import json
import logging
from odoo import models, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SoftwareAIClassification(models.AbstractModel):
    _name = 'sgichs.software.ai.classification'
    _description = 'Clasificación de Software con IA'

    @api.model
    def classify_software_with_ai(self):
        """Método principal para clasificar software usando IA"""
        # Verificar si está habilitado
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param('sgichs_software_ai_classification.enable', 'False') == 'True'
        if not enabled:
            _logger.info("Clasificación IA de software está deshabilitada")
            return

        # Buscar software no clasificado (subtype == 'otros')
        software_records = self.env['it.asset.software'].search([
            ('subtype', '=', 'otros')
        ], limit=100)

        if not software_records:
            _logger.info("No hay software no clasificado para procesar")
            return

        # Generar prompt
        prompt = self._generate_classification_prompt(software_records)

        # Enviar a IA
        ai_service = self.env['asi_ia.service']
        try:
            response = ai_service.get_ai_response(prompt)
            _logger.info(f"Respuesta IA: {response}")
        except Exception as e:
            _logger.error(f"Error al obtener respuesta de IA: {str(e)}")
            return

        # Parsear y actualizar
        self._parse_and_update_software(response, software_records)

    def _generate_classification_prompt(self, software_records):
        """Genera el prompt para la IA"""
        categories = {
            'gestor_bd': 'Gestor de Bases de Datos',
            'sistema_operativo': 'Sistema Operativo',
            'navegador': 'Navegador de Internet',
            'gestion_empresarial': 'Gestión Empresarial',
            'ofimatica': 'Ofimática',
            'comunicacion': 'Software de Comunicación',
            'desarrollo': 'Software de Desarrollo',
            'multimedia': 'Multimedia',
            'seguridad': 'Herramienta de Seguridad',
            'redes': 'Gestión de Redes',
            'antivirus': 'Antivirus',
            'respaldo': 'Respaldo y Recuperación',
            'herramientas': 'Útiles y Herramientas',
            'arquitectura_redes': 'Arquitectura de Redes',
            'diseno': 'Análisis/Diseño',
            'servidor_app': 'Servidor de Aplicaciones',
            'virtualizacion': 'Virtualización',
        }

        software_list = "\n".join([f"{rec.id}: {rec.name}" for rec in software_records])

        prompt = f"""
Clasifica los siguientes software en las categorías disponibles. Responde SOLO con un JSON válido donde las claves sean los IDs de software y los valores las claves de categoría.

Categorías disponibles:
{json.dumps(categories, indent=2)}

Software a clasificar:
{software_list}

Ejemplo de respuesta: {{"1": "gestor_bd", "2": "sistema_operativo"}}
"""
        return prompt

    def _parse_and_update_software(self, response, software_records):
        """Parsea la respuesta JSON y actualiza el software"""
        try:
            classifications = json.loads(response)
            if not isinstance(classifications, dict):
                raise ValueError("La respuesta no es un diccionario")

            for sw_id_str, category in classifications.items():
                try:
                    sw_id = int(sw_id_str)
                    software = self.env['it.asset.software'].browse(sw_id)
                    if software.exists() and software.subtype == 'otros':
                        valid_categories = dict(software._fields['subtype'].selection).keys()
                        if category in valid_categories:
                            software.write({'subtype': category})
                            _logger.info(f"Software {software.name} clasificado como {category}")
                        else:
                            _logger.warning(f"Categoría inválida {category} para software {sw_id}")
                except (ValueError, KeyError) as e:
                    _logger.error(f"Error procesando clasificación para ID {sw_id_str}: {str(e)}")

        except json.JSONDecodeError as e:
            _logger.error(f"Error parseando respuesta JSON: {str(e)}")
        except Exception as e:
            _logger.error(f"Error general en parseo: {str(e)}")