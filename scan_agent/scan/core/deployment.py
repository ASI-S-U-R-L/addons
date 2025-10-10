# -*- coding: utf-8 -*-
import sys
import platform
import shutil
import subprocess
import logging
import os
from pathlib import Path

_logger = logging.getLogger(__name__)

def get_install_path() -> Path:
    """
    Determina la ruta de instalación estándar según el sistema operativo.
    Crea el directorio si no existe.
    """
    system = platform.system()
    app_name = "ScanAgentSGICH"
    
    base_path: Path

    if system == "Windows":
        appdata_path_str = os.getenv('LOCALAPPDATA')
        if not appdata_path_str:
            _logger.warning("Variable LOCALAPPDATA no definida. Usando fallback.")
            base_path = Path.home() / 'AppData' / 'Local'
        else:
            base_path = Path(appdata_path_str)
        path = base_path / app_name

    elif system == "Linux":
        base_path = Path.home() / ".local" / "share"
        path = base_path / app_name
    elif system == "Darwin": # macOS
        base_path = Path.home() / "Library" / "Application Support"
        path = base_path / app_name
    else:
        # Fallback para otros sistemas.
        base_path = Path.home()
        path = base_path / f".{app_name.lower()}"

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        _logger.error(f"No se pudo crear el directorio de instalación en {path}: {e}")
        # Como fallback, usar el directorio del ejecutable actual.
        return Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent

    return path

def install_and_relaunch_if_needed(source_dir: Path):
    """
    Verifica si el agente está en su directorio de instalación final.
    Si no, fuerza la configuración, copia la carpeta completa y se relanza.
    """
    target_dir = get_install_path()
    
    if str(target_dir.resolve()) != str(source_dir.resolve()):
        _logger.info(f"El agente se está ejecutando desde una ubicación temporal: {source_dir}")
        _logger.info(f"Iniciando proceso de copia a: {target_dir}")

        try:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            
            shutil.copytree(source_dir, target_dir)
            _logger.info(f"Directorio completo del agente copiado a {target_dir}")
            
            args = sys.argv[1:]
            if '--config' not in args:
                _logger.info("Forzando el modo de configuración para la primera ejecución.")
                args.append('--config')

            command_to_run = []
            if getattr(sys, 'frozen', False):
                # Ejecutando como un ejecutable de PyInstaller
                executable_name = Path(sys.executable).name
                target_exe = target_dir / executable_name
                command_to_run = [str(target_exe)] + args
                _logger.info(f"Relanzando ejecutable desde {target_exe} con argumentos: {args}")
            else:
                # Ejecutando como script
                target_script = target_dir / 'main.py'
                command_to_run = [sys.executable, str(target_script)] + args
                _logger.info(f"Relanzando script con '{sys.executable}' desde {target_script} con argumentos: {args}")
            
            subprocess.Popen(command_to_run)

            sys.exit(0)
            
        except Exception as e:
            _logger.critical(f"Falló la autoinstalación al copiar el directorio: {e}", exc_info=True)
            # Devuelve falso para permitir al script original continuar si falla el re-levantado
            
    _logger.debug("El agente ya se está ejecutando desde la ubicación de instalación correcta.")
    return False