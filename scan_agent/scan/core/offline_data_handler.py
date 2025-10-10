# -*- coding: utf-8 -*-
import json
import os
import logging
from datetime import datetime
from pathlib import Path
import socket

# Importamos el recolector para obtener toda la información del sistema.
from .recolector import GestorTI

_logger = logging.getLogger(__name__)

def recolectar_todo_y_crear_json_al_fallar_la_conexion_con_odoo():
    """
    Recolecta toda la información del sistema cuando la conexión con Odoo falla,
    y la guarda en un archivo JSON en una carpeta específica.
    """
    _logger.info("Iniciando recolección de datos offline debido a fallo de conexión.")

    try:
        # --- 1. Crear el directorio para los datos offline ---
        # Usamos Path.home() para asegurar que se cree en la carpeta del usuario
        # y sea accesible sin problemas de permisos.
        offline_dir = Path.home() / "Datos Offline de Esta Computadora"
        offline_dir.mkdir(exist_ok=True)
        _logger.debug(f"Directorio para datos offline asegurado en: {offline_dir}")

        # --- 2. Recolectar toda la información del PC ---
        # Instanciamos GestorTI con todos los módulos desactivados para forzar la
        # recolección completa de todo el hardware y software posible.
        gestor = GestorTI(software_installed=True, network_installed=True)
        datos_completos = gestor.recolectar_todo()

        # --- 3. Construir el nombre del archivo según el formato solicitado ---
        cpu_info = datos_completos.get('cpu', {})
        os_info = datos_completos.get('sistema_operativo', {})

        nombre_cpu = cpu_info.get('Modelo', 'CPU_Desconocido').strip()
        ram_total = datos_completos.get('ram_total_gb', 0.0)
        nombre_pc = socket.gethostname()
        sistema_operativo = os_info.get('sistema', 'SO_Desconocido')
        fecha_actual = datetime.now().strftime('%Y-%m-%d') # Usamos el formato AÑO-MES-DIA para evitar problemas con / en nombres de archivo

        # Limpiamos los caracteres inválidos para nombres de archivo
        nombre_cpu_limpio = "".join(c for c in nombre_cpu if c.isalnum() or c in (' ', '.', '_')).rstrip()
        
        nombre_archivo = f"[{nombre_cpu_limpio}][{ram_total:.2f}GB] - ([{nombre_pc}] - [{sistema_operativo}]) [{fecha_actual}].json"
        ruta_archivo_completa = offline_dir / nombre_archivo

        # --- 4. Guardar los datos en el archivo JSON ---
        with open(ruta_archivo_completa, 'w', encoding='utf-8') as f:
            json.dump(datos_completos, f, indent=4, ensure_ascii=False, default=str)
        
        _logger.info(f"Datos offline guardados exitosamente en: {ruta_archivo_completa}")
        return True

    except Exception as e:
        _logger.critical(f"Error fatal durante la recolección de datos offline: {e}", exc_info=True)
        return False