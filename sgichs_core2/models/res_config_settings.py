# RUTA: sgichs_core2/models/res_config_settings.py (CÓDIGO ACTUALIZADO)

from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # --- Grupo de Activos ---
    module_sgichs_hardware = fields.Boolean(
        string="Gestión de Activos de Hardware",
        help="Activa el inventario detallado de hardware, componentes y sus relaciones.")
    
    module_sgichs_red = fields.Boolean(
        string="Gestión de Activos de Red",
        help="Añade monitoreo de conectividad (ping), gestión de IPs y servicios de red al hardware.")

    # --- Grupo de Software ---
    module_sgichs_software = fields.Boolean(
        string="Gestión de Activos de Software",
        help="Permite el control de software instalado y la gestión de listas blancas/negras.")

    # --- Grupo de Usuarios ---
    module_sgichs_users = fields.Boolean(
        string="Gestión de Usuarios de TI",
        help="Activa la gestión de usuarios autorizados y la asignación de hardware.")
    
    # CORRECCIÓN: El campo ahora coincide con el nombre del módulo 'sgichs_users_profiles_software'
    module_sgichs_users_profiles_software = fields.Boolean(
        string="Activar Perfiles de Usuario para Software",
        help="Permite crear perfiles para asignar software permitido a grupos de usuarios.")

    # --- Grupo General ---
    module_sgichs_reporting = fields.Boolean(
        string="Módulo de Reportes",
        help="Activa la generación de reportes en PDF, como la ficha técnica de hardware.")