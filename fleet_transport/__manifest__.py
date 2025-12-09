# -*- coding: utf-8 -*-
{
    'name': 'Fleet Transport System - Cuba',
    'version': '16.0.1.0.0',
    'category': 'Human Resources/Fleet',
    'summary': 'Sistema Integral de Transporte - Gestión automatizada con análisis de consumo según Decreto 110/2024',
    'description': """
        Sistema Integral de Transporte para Cuba
        ========================================
        
        Este módulo integra funcionalidades completas de transporte que cumplen con el Decreto 110/2024:
        
        🚛 GESTIÓN DE HOJAS DE RUTA:
        - Automatización total: selecciona vehículo → todo se llena automáticamente
        - Datos de empresa automáticos desde la compañía
        - Información de vehículo y conductor automática
        - Campos manuales mínimos: solo totales de viajes y kilómetros
        
        📊 ANÁLISIS DE CONSUMO (NUEVO):
        - Correlación automática: Log Fuel + Hojas de Ruta + Cierres Mensuales
        - Índices automáticos: Km/L (móviles/tecnológicos) y L/Hora (estacionarios)
        - Comparación con normas establecidas según Decreto 110/2024
        - Alertas automáticas por desviaciones >5% de la norma
        - Histórico completo por vehículo y período
        
        ⚖️ CUMPLIMIENTO NORMATIVO:
        - Control de inventario: detección de desbalances >3%
        - Justificación obligatoria para desviaciones críticas
        - Trazabilidad completa para evitar sanciones
        - Reportes con formato oficial para auditorías
        
        🏢 VEHÍCULOS ADMINISTRATIVOS:
        - Cierres mensuales para vehículos sin hojas de ruta
        - Control de odómetro y horas de operación
        - Integración automática con análisis de consumo
        
        📈 NORMAS Y ESTÁNDARES:
        - Tabla configurable de normas por tipo de vehículo
        - Tolerancias personalizables (defecto: 5%)
        - Vigencia por fechas y criterios específicos
        - Aplicación automática según marca/modelo/categoría
        
        🎯 SOLUCIONES PARA ODÓMETROS:
        - Odómetro real, estimación GPS, rutas fijas
        - Registro manual supervisado con validaciones
        - Promedio histórico para casos especiales
        
        📋 REPORTES Y DASHBOARD:
        - Dashboard con KPIs en tiempo real
        - Reportes PDF con formato oficial cubano
        - Análisis por vehículo, flota, tipo y período
        - Gráficos de tendencia y cumplimiento
        
        🔄 AUTOMATIZACIÓN:
        - Cron mensual para análisis automáticos
        - Alertas proactivas por WhatsApp/Email
        - Actividades automáticas para seguimiento
        - Integración completa entre módulos
        
        ✅ VALIDACIONES AVANZADAS:
        - Usa licencias vigentes del BaseTransporte
        - Compatibilidad conductor-vehículo
        - Control de vehículos habilitados
        - Períodos sin solapamiento
        
        📱 PREPARADO PARA FUTURO:
        - Estructura para app móvil
        - API para integración con GPS
        - Extensible para nuevas normativas
    """,
    'author': 'Reysel Osorio Reyes',
    'website': 'https://antasi.asisurl.cu',
    'depends': [
        'base_transporte',  # BaseTransporte
        'fleet_vehicle_log_fuel',  # Log Fuel
        'mail',  # Para chatter y actividades
        'web',   
    ],
    'data': [
        # Seguridad
        'security/ir.model.access.csv',
        
        # Datos base
        'data/fleet_route_sheet_sequence.xml',
        'data/fleet_consumption_sequences.xml',
        'data/fleet_consumption_standards_data.xml',
        'data/fleet_consumption_cron.xml',
        
        # Vistas principales
        'views/fleet_route_sheet_views.xml',
        'views/fleet_consumption_analysis_views.xml',
        'views/fleet_consumption_standard_views.xml',
        'views/fleet_monthly_closure_admin_views.xml',
        # 'views/fleet_consumption_dashboard_views.xml',  # Comentado - no compatible con Odoo 16
        
        # Reportes
        'reports/fleet_consumption_report.xml',
        
        # Menús
        'views/fleet_route_sheet_menus.xml',
        'views/fleet_consumption_menus.xml',
    ],
    'demo': [
        # Datos de demostración (opcional)
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
    'sequence': 10,
    'external_dependencies': {
        'python': ['reportlab', 'pillow'],  # Para generación de PDF
    },
    'images': ['static/description/banner.png'],
    'price': 0.0,
    'currency': 'USD',
}
