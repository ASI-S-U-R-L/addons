# -*- coding: utf-8 -*-
import sys
import os
import logging
from datetime import datetime
from pathlib import Path
import platform
import argparse

# --- INICIO: CONFIGURACIÓN DE LOGGING A PRUEBA DE FALLOS ---

# Determinar el directorio base de forma segura
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent

LOG_DIR = BASE_DIR / 'logs'
FAILSAFE_LOG_FILE = LOG_DIR / f"failsafe_crash_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"

def setup_logging():
    """Configura el sistema de logging centralizado."""
    try:
        if not LOG_DIR.exists():
            os.makedirs(LOG_DIR)
        
        log_filename = LOG_DIR / f"agent_log_{datetime.now().strftime('%Y-%m-%d')}.log"

        logging.basicConfig(
            level=logging.DEBUG, # Capturamos todo tipo de logs
            format='%(asctime)s - %(name)-15s - %(levelname)-8s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler(sys.stdout) # También mostramos en consola
            ]
        )
        logging.getLogger(__name__).info(f"Sistema de logging configurado. Log guardado en: {log_filename}")
    except Exception as e:
        # Si el logging falla, escribe en un archivo de emergencia
        with open(FAILSAFE_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(f"ERROR CRÍTICO AL CONFIGURAR EL LOGGER:\n{e}\n")
            import traceback
            traceback.print_exc(file=f)
        sys.exit(1)

# --- FIN: CONFIGURACIÓN DE LOGGING ---

# Se declara el logger aquí para usarlo globalmente en este archivo
_logger = logging.getLogger(__name__)

def iniciar_agente():
    """
    Función principal del agente con logging detallado.
    """
    
    _logger.info("==================================================")
    _logger.info(f"INICIANDO PROCESO DEL AGENTE (PID: {os.getpid()})")
    _logger.info(f"Ejecutando desde: {BASE_DIR}")
    _logger.info("==================================================")
    
    _logger.debug("Función iniciar_agente() comenzada.")
    
    # Mover las importaciones aquí permite registrar si fallan
    try:
        from scan.core.deployment import install_and_relaunch_if_needed
        from agent import AgenteScanner
        from configurador import load_config, run_configuration_wizard, is_agent_running, create_lock, remove_lock, setup_from_cli
    
        
        # --- INICIO: INTEGRACIÓN DEL GESTOR SUDO ---
        if platform.system() == "Linux":
            from scan.core.linux_sudo_helper import sudo_manager
        # --- FIN: INTEGRACIÓN DEL GESTOR SUDO ---
        
        _logger.info("Módulos del proyecto importados correctamente.")
    except ImportError as e:
        _logger.critical(f"FALLO DE IMPORTACIÓN. Error: {e}", exc_info=True)
        sys.exit(1)
        
    # --- INICIO DE LA LÓGICA DE AUTOINSTALACIÓN ---
    # Si el agente no está en la ubicación correcta, se copia y se relanza.
    # El script original (ej. desde el USB) terminará aquí.
    install_and_relaunch_if_needed(BASE_DIR)
    _logger.debug("Verificación de instalación completada.")
    # --- FIN DE LA LÓGICA DE AUTOINSTALACIÓN ---
    
    parser = argparse.ArgumentParser(description="Agente de escaneo SGICHs.")
    parser.add_argument("--config", action="store_true", help="Forzar el asistente de configuración (GUI o texto).")
    parser.add_argument("--text-mode", action="store_true", help="Usar el asistente de configuración en modo texto.")
    
    parser.add_argument("--setup", action="store_true", help="Ejecutar configuración desde CLI y salir.")
    parser.add_argument("--odoo-url", help="URL de Odoo para el setup.")
    parser.add_argument("--odoo-db", help="Base de datos de Odoo para el setup.")
    parser.add_argument("--odoo-user", help="Usuario de Odoo para el setup.")
    parser.add_argument("--odoo-password", help="Contraseña de Odoo para el setup.")
    parser.add_argument("--inventory", help="Nº de inventario. Usar 'AUTO' para autogenerar.")
    
    args = parser.parse_args()
    
    # Si se usa --setup, configurar y salir.
    if args.setup:
        _logger.info("Modo --setup detectado. Realizando configuración remota...")
        if all([args.odoo_url, args.odoo_db, args.odoo_user, args.odoo_password, args.inventory]):
            if setup_from_cli(args):
                _logger.info("Configuración remota exitosa. El agente terminará y se iniciará en el próximo reinicio del sistema.")
                sys.exit(0)
            else:
                _logger.critical("Falló la configuración remota.")
                sys.exit(1)
        else:
            _logger.error("Faltan argumentos para --setup. Se requieren todos los parámetros de conexión.")
            sys.exit(1)
            
    force_config = args.config
    text_mode = args.text_mode
    _logger.debug(f"Argumentos: {sys.argv}. Forzar config: {force_config}. Modo texto: {text_mode}")
    
    _logger.debug(f"Argumentos: {args}. Forzar config: {force_config}. Modo texto: {text_mode}")
    
    # --- INICIO: CONFIGURAR MODO DEL GESTOR SUDO ---
    if platform.system() == "Linux":
        # Le decimos al gestor si debe usar la GUI o no para pedir la contraseña
        sudo_manager.set_gui_mode(not text_mode)
    # --- FIN: CONFIGURAR MODO DEL GESTOR SUDO ---

    if is_agent_running() and not force_config:
        _logger.info("Instancia duplicada detectada. Abriendo configurador.")
        # Pasa el flag de modo texto también aquí
        run_configuration_wizard(text_mode=text_mode)
        _logger.info("Configurador cerrado. Saliendo de la instancia duplicada.")
        sys.exit(0)

    _logger.info("Iniciando nueva instancia del agente de gestión de activos...")
    
    try:
        create_lock()

        config = load_config()
        
        if force_config or not config:
            _logger.info("Configuración no encontrada o forzada. Abriendo asistente.")
            config = run_configuration_wizard(text_mode=text_mode)
            if not config:
                _logger.warning("Configuración cancelada o fallida. Cerrando agente.")
                sys.exit(1)

        _logger.debug("Configuración cargada. Creando instancia de AgenteScanner.")
        agente = AgenteScanner(config)
        _logger.info("Instancia de AgenteScanner creada. Iniciando bucle principal del agente...")
        agente.iniciar()

    except KeyboardInterrupt:
        _logger.info("Agente detenido por el usuario (KeyboardInterrupt).")
    except Exception as e:
        _logger.critical(f"Error fatal no capturado en el agente: {e}", exc_info=True)
    finally:
        remove_lock()
        _logger.info("El agente se ha cerrado y el bloqueo ha sido liberado.")


if __name__ == "__main__":
    # La configuración del logging, lo primero que se ejecuta
    setup_logging()
    
    try:
        iniciar_agente()
    except Exception as e:
        _logger.critical(f"Error fatal no manejado en el punto de entrada __main__: {e}", exc_info=True)
        # Intenta eliminar el lock por si acaso
        try:
            from configurador import remove_lock
            remove_lock()
        except Exception:
            pass # Si falla, ya se registró el error principal