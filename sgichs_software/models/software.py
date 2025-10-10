from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class Software(models.Model):
    _name = 'it.asset.software'
    _inherit = 'it.asset'
    _description = 'Activo de Software'

    # Configuración de tipo software
    type = fields.Selection(
        selection_add=[('software', 'Software')],
        default='software',
        ondelete={'software': 'cascade'},
    )
    
    version = fields.Char(string='Versión', required=True)
    license_key = fields.Char(string='Clave de Licencia')
    is_authorized = fields.Boolean(string='¿Está Autorizado?', default=True)
    
    subtype = fields.Selection(
        string="Subtipo",
        selection=[
            ('gestor_bd', 'Gestor de Bases de Datos'),
            ('sistema_operativo', 'Sistema Operativo'),
            ('navegador', 'Navegador de Internet'),
            ('gestion_empresarial', 'Gestión Empresarial'),
            ('ofimatica', 'Ofimática'),
            ('comunicacion', 'Software de Comunicación'),
            ('desarrollo', 'Software de Desarrollo'),
            ('multimedia', 'Multimedia'),
            ('seguridad', 'Herramienta de Seguridad'),
            ('redes', 'Gestión de Redes'),
            ('antivirus', 'Antivirus'),
            ('respaldo', 'Respaldo y Recuperación'),
            ('herramientas', 'Útiles y Herramientas'),
            ('arquitectura_redes', 'Arquitectura de Redes'),
            ('diseno', 'Análisis/Diseño'),
            ('servidor_app', 'Servidor de Aplicaciones'),
            ('virtualizacion', 'Virtualización'),
            ('otros', 'Otros')
        ],
        default='otros'
    )
    
    color = fields.Integer(string="Color Index", help="Color para representación visual")
    
    os_type = fields.Selection(string="Sistema Operativo En el que funciona", selection=[('windows', 'Windows'),('linux', 'Linux'),('mac', 'MacOS'),('android', 'Android')])
    
    #=====================#
    #      FUNCIONES      #
    #=====================#
    
    def _log_incident(self, severity, message, operation='change'):
        """Crea un incidente con título dinámico según la operación."""
        if not self.env.get('it.incident'):
            _logger.warning("Módulo de incidentes no instalado. No se creará registro.")
            return
            
        if operation == 'delete':
            asset_ref = None  
        else:
            asset_ref = f"{self._name},{self.id}"
        
        # Mapeo de operaciones a títulos
        operation_titles = {
            'create': 'Añadido de Software',
            'delete': 'Eliminación de Software',
            'change': 'Cambio en Software'
        }
        title = f"{operation_titles.get(operation, 'Cambio en Software')}: {self.name}"
        
        self.env['it.incident'].create({
            'title': title,
            'description': message,
            'severity': severity,
            'asset_ref': asset_ref,
        })

    @api.model
    def create(self, vals):
        try:
            record = super().create(vals)
            # Operación: Creación (título "Añadido de Software")
            record._log_incident('info', f"Software creado: {record.name} v{record.version} (subtipo: {record.subtype})", operation='create')
            _logger.info(f"Software creado exitosamente: {record.name}")
            return record
        except Exception as e:
            _logger.error(f"Error al crear software: {str(e)}")
            raise

    def write(self, vals):
        old_status = {rec.id: rec.status for rec in self}
        old_license = {rec.id: rec.license_key for rec in self}
        
        res = super().write(vals)
        
        for rec in self:
            # Operación: Cambio (título "Cambio en Software")
            if old_license.get(rec.id) != rec.license_key:
                rec._log_incident('medium', f"Licencia actualizada: {rec.license_key}")

            if old_status.get(rec.id) != rec.status:
                rec._log_incident('low', f"Estado cambiado de {old_status.get(rec.id)} a {rec.status}")
        
        return res
    
    def unlink(self):
        # Operación: Eliminación (título "Eliminación de Software")
        # Desvincular incidentes relacionados antes de eliminar
        for rec in self:
            if 'it.incident' in self.env:
                incidents = self.env['it.incident'].search([('asset_ref', '=', f"{rec._name},{rec.id}")])
                incidents.write({'asset_ref': None})
            
            rec._log_incident('high', f"Software eliminado: {rec.name}", operation='delete')
        return super().unlink()
    
    def action_add_to_blacklist(self):
        """Añade el software seleccionado a la lista negra predeterminada"""
        try:
            # Verificar existencia del modelo de listas
            if 'it.hw.list' not in self.env:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Función no disponible',
                        'message': 'El módulo de listas de control no está instalado',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            
            # Buscar o crear lista negra predeterminada
            blacklist = self.env['it.hw.list'].search([
                ('type', '=', 'black'), 
                ('name', '=', 'Lista Negra Predeterminada')
            ], limit=1)
            
            if not blacklist:
                blacklist = self.env['it.hw.list'].create({
                    'name': 'Lista Negra Predeterminada',
                    'type': 'black',
                    'active': True
                })
            
            # Añadir software seleccionado a la lista negra
            software_ids = self.env.context.get('active_ids', [])
            if not software_ids:
                software_ids = self.ids
            
            if software_ids:
                # Añadir software a la lista
                for software_id in software_ids:
                    if software_id not in blacklist.software_ids.ids:
                        blacklist.software_ids = [(4, software_id)]
                
                # Verificar compliance inmediatamente
                for software_id in software_ids:
                    self.env['it.hw.list'].check_software_compliance(software_id, hardware_id=None)
                
                # Obtener nombres del software
                software_names = self.env['it.asset.software'].browse(software_ids).mapped('name')
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Software añadido a Lista Negra',
                        'message': f'Se añadieron {len(software_ids)} software(s) a la lista negra: {", ".join(software_names[:3])}{"..." if len(software_names) > 3 else ""}',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': 'No se seleccionó ningún software.',
                        'type': 'danger',
                        'sticky': False,
                    }
                }
                
        except Exception as e:
            _logger.error(f"Error al añadir software a lista negra: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error al añadir a lista negra: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def action_add_to_whitelist(self):
        """Añade el software seleccionado a la lista blanca predeterminada"""
        try:
            # Verificar existencia del modelo de listas
            if 'it.hw.list' not in self.env:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Función no disponible',
                        'message': 'El módulo de listas de control no está instalado',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            
            # Buscar o crear lista blanca predeterminada
            whitelist = self.env['it.hw.list'].search([
                ('type', '=', 'white'), 
                ('name', '=', 'Lista Blanca Predeterminada')
            ], limit=1)
            
            if not whitelist:
                whitelist = self.env['it.hw.list'].create({
                    'name': 'Lista Blanca Predeterminada',
                    'type': 'white',
                    'active': True
                })
            
            # Añadir software seleccionado a la lista blanca
            software_ids = self.env.context.get('active_ids', [])
            if not software_ids:
                software_ids = self.ids
            
            if software_ids:
                # Añadir software a la lista
                for software_id in software_ids:
                    if software_id not in whitelist.software_ids.ids:
                        whitelist.software_ids = [(4, software_id)]
                
                # Obtener nombres del software
                software_names = self.env['it.asset.software'].browse(software_ids).mapped('name')
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Software añadido a Lista Blanca',
                        'message': f'Se añadieron {len(software_ids)} software(s) a la lista blanca: {", ".join(software_names[:3])}{"..." if len(software_names) > 3 else ""}',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': 'No se seleccionó ningún software.',
                        'type': 'danger',
                        'sticky': False,
                    }
                }
                
        except Exception as e:
            _logger.error(f"Error al añadir software a lista blanca: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error al añadir a lista blanca: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def action_remove_from_lists(self):
        """Remueve el software seleccionado de todas las listas de control"""
        try:
            # Verificar existencia del modelo de listas
            if 'it.hw.list' not in self.env:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Función no disponible',
                        'message': 'El módulo de listas de control no está instalado',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            
            # Obtener software seleccionado
            software_ids = self.env.context.get('active_ids', [])
            if not software_ids:
                software_ids = self.ids
            
            if software_ids:
                # Buscar todas las listas que contengan este software
                all_lists = self.env['it.hw.list'].search([])
                removed_count = 0
                
                for hw_list in all_lists:
                    for software_id in software_ids:
                        if software_id in hw_list.software_ids.ids:
                            hw_list.software_ids = [(3, software_id)]  # Remover de la lista
                            removed_count += 1
                
                # Obtener nombres del software
                software_names = self.env['it.asset.software'].browse(software_ids).mapped('name')
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Software removido de listas',
                        'message': f'Se removieron {len(software_ids)} software(s) de todas las listas de control: {", ".join(software_names[:3])}{"..." if len(software_names) > 3 else ""}',
                        'type': 'info',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': 'No se seleccionó ningún software.',
                        'type': 'danger',
                        'sticky': False,
                    }
                }
                
        except Exception as e:
            _logger.error(f"Error al remover software de listas: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error al remover de listas: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    @api.model
    def get_software_compliance_status(self, software_id):
        """Obtiene el estado de compliance de un software"""
        if 'it.hw.list' not in self.env:
            return 'gray'
        return self.env['it.hw.list'].get_software_status(software_id)
    
    def check_compliance_status(self):
        """Verifica y muestra el estado de compliance del software actual"""
        status = 'gray'
        if 'it.hw.list' in self.env:
            status = self.get_software_compliance_status(self.id)
        
        status_messages = {
            'prohibited': 'Este software está PROHIBIDO (Lista Negra)',
            'authorized': 'Este software está AUTORIZADO (Lista Blanca)',
            'gray': 'Este software no está en ninguna lista (Zona Gris)'
        }
        
        status_types = {
            'prohibited': 'danger',
            'authorized': 'success',
            'gray': 'info'
        }
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': f'Estado de Compliance: {self.name}',
                'message': status_messages.get(status, 'Estado desconocido'),
                'type': status_types.get(status, 'info'),
                'sticky': False,
            }
        }