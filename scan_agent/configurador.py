# -*- coding: utf-8 -*-
import json
import os
import sys
import platform
import subprocess
import psutil
from pathlib import Path
import logging
import getpass
import keyring

_logger = logging.getLogger(__name__)

# --- INICIO DE LA CORRECCIÓN DE RUTA ---
# Determinar el directorio base de forma segura (funciona para .py y .exe)
if getattr(sys, 'frozen', False):
    # Si se ejecuta como un .exe compilado, la base es el directorio del ejecutable
    BASE_DIR = Path(sys.executable).parent
else:
    # Si se ejecuta como un script .py, la base es el directorio del script
    BASE_DIR = Path(__file__).resolve().parent

# Importamos la función para obtener la ruta de instalación.
try:
    from scan.core.deployment import get_install_path
except ImportError:
    # Fallback si el módulo no se encuentra (aunque no debería pasar)
    get_install_path = lambda: BASE_DIR

# Usar el directorio base seguro para definir la ruta del archivo de configuración
CONFIG_FILE = get_install_path() / 'config_agente.json'
_logger.info(f"Ruta del archivo de configuración establecida en: {CONFIG_FILE}")


# --- INICIO: Lógica del Archivo de Bloqueo "Inteligente" (PID File) ---

LOCK_FILE = Path.home() / '.sgichs_agent.lock'

def is_agent_running():
    """
    Verifica si el agente ya se está ejecutando de forma robusta.
    Lee el PID del archivo de bloqueo y comprueba si el proceso existe.
    """
    _logger.debug(f"Verificando archivo de bloqueo en: {LOCK_FILE}")
    if not LOCK_FILE.exists():
        _logger.debug("El archivo de bloqueo no existe. Es la primera instancia.")
        return False
    
    try:
        pid_str = LOCK_FILE.read_text().strip()
        if not pid_str.isdigit():
            _logger.warning("El archivo de bloqueo contiene un valor no numérico. Se considera obsoleto.")
            remove_lock()
            return False
            
        pid = int(pid_str)
        _logger.debug(f"Archivo de bloqueo encontrado con PID: {pid}")

        if psutil.pid_exists(pid):
            # Para estar seguros, verificamos que el nombre del proceso coincida (opcional pero recomendado)
            # Esto evita falsos positivos si otro programa reutiliza el PID.
            proc = psutil.Process(pid)
            # El nombre puede ser 'ScanAgent.exe' o 'python.exe' dependiendo de cómo se ejecute
            if 'scanagent' in proc.name().lower() or 'python' in proc.name().lower():
                _logger.info(f"El proceso con PID {pid} ({proc.name()}) está activo. Es una instancia duplicada.")
                return True

        _logger.warning(f"El proceso con PID {pid} ya no existe. Eliminando archivo de bloqueo obsoleto.")
        remove_lock() # Limpieza automática de archivo obsoleto
        return False

    except (psutil.NoSuchProcess, FileNotFoundError):
        _logger.warning("El proceso del archivo de bloqueo no existe. Eliminando archivo obsoleto.")
        remove_lock()
        return False
    except Exception as e:
        _logger.error(f"Error al verificar el archivo de bloqueo: {e}", exc_info=True)
        remove_lock() # En caso de duda, eliminar el bloqueo para no impedir el inicio.
        return False

def create_lock():
    """Crea el archivo de bloqueo y escribe el PID del proceso actual."""
    try:
        pid = os.getpid()
        LOCK_FILE.write_text(str(pid))
        _logger.info(f"Archivo de bloqueo creado con PID: {pid}")
    except Exception as e:
        _logger.error(f"No se pudo crear el archivo de bloqueo con PID: {e}")

def remove_lock():
    """Elimina el archivo de bloqueo."""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
            _logger.info("Archivo de bloqueo eliminado.")
    except Exception as e:
        _logger.error(f"No se pudo eliminar el archivo de bloqueo: {e}")
# --- FIN: Lógica de Bloqueo ---


# Importación segura para la GUI
try:
    from configurador_gui import ConfiguratorApp, KEYRING_SERVICE_NAME
except ImportError:
    ConfiguratorApp = None
    KEYRING_SERVICE_NAME = "sgich-scan-agent"  # Definir fallback si la GUI no carga

def load_config():
    """Carga la configuración desde el archivo JSON."""
    if not CONFIG_FILE.exists():
        _logger.warning(f"No se encontró el archivo de configuración en {CONFIG_FILE}")
        return None
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            _logger.info(f"Cargando configuración desde {CONFIG_FILE}")
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        _logger.error(f"Error al leer el archivo de configuración: {e}")
        return None

def save_config(config_data):
    """Guarda la configuración en el archivo JSON."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        _logger.info(f"Configuración guardada exitosamente en {CONFIG_FILE}")
        return True
    except IOError as e:
        _logger.error(f"Error al guardar el archivo de configuración: {e}")
        return False
    
def _run_text_wizard(initial_config=None):
    """Ejecuta un asistente de configuración interactivo en la consola."""
    print("--- Asistente de Configuración del Agente SGICH (Modo Texto) ---")
    
    config_data = initial_config if initial_config else {}
    odoo_config = config_data.get("odoo_config", {})
    
    # Solicitar cada valor, mostrando el valor actual como predeterminado
    inventory_number = input(f"Nº de Inventario PC [{config_data.get('inventory_number', '00000')}]: ") or config_data.get('inventory_number', '00000')
    url = input(f"URL de Odoo [{odoo_config.get('url', 'http://localhost:8069')}]: ") or odoo_config.get('url', 'http://localhost:8069')
    db = input(f"Base de Datos de Odoo [{odoo_config.get('db', '')}]: ") or odoo_config.get('db', '')
    user = input(f"Usuario de Odoo [{odoo_config.get('username', '')}]: ") or odoo_config.get('username', '')
    
    # Usar getpass para la contraseña para que no se muestre en la terminal
    password = getpass.getpass(f"Contraseña / API Key para '{user}': ")

    if not all([inventory_number, url, db, user, password]):
        print("\nError: Todos los campos son obligatorios. Configuración cancelada.")
        return None

    try:
        keyring.set_password(KEYRING_SERVICE_NAME, user, password)
        print("\nÉxito: La contraseña ha sido guardada de forma segura en el sistema.")
    except Exception as e:
        print(f"\nError de Keyring: No se pudo guardar la contraseña de forma segura.\n{e}")
        return None

    final_config = {
        "intervalo_principal_min": config_data.get("intervalo_principal_min", 60),
        "intervalo_reintento_min": config_data.get("intervalo_reintento_min", 5),
        "listener_port": config_data.get("listener_port", 9191),
        "inventory_number": inventory_number.strip(),
        "odoo_config": {
            "url": url.strip(),
            "db": db.strip(),
            "username": user.strip()
        }
    }

    if save_config(final_config):
        setup_persistence()
        print("\nConfiguración guardada y persistencia configurada exitosamente.")
        return final_config
    else:
        print("\nError: No se pudo guardar el archivo de configuración.")
        return None

def run_configuration_wizard(text_mode=False):
    """
    Ejecuta el asistente de configuración.
    Si text_mode es True, usa la versión de consola.
    De lo contrario, intenta usar la GUI.
    """
    
    current_config = load_config()
    
    if text_mode:
        _logger.info("Iniciando asistente de configuración en modo texto...")
        return _run_text_wizard(initial_config=current_config)

    # Lógica de la GUI (sin cambios)
    if not ConfiguratorApp:
        _logger.error("Tkinter no está disponible. No se puede mostrar la GUI de configuración.")
        _logger.info("Intente ejecutar con el flag --text-mode para configurar desde la consola.")
        return None

    _logger.info("Iniciando asistente de configuración GUI...")
    app = ConfiguratorApp(initial_config=current_config)
    app.mainloop()

    if app.saved:
        if save_config(app.config_data):
            setup_persistence()
            return app.config_data
    else:
        _logger.warning("Configuración cancelada por el usuario.")
    
    return None

def setup_persistence():
    """
    Configura el script para que se inicie automáticamente con el sistema,
    apuntando siempre a la copia instalada.
    """
    os_type = platform.system()
    _logger.info(f"Detectado sistema operativo: {os_type}. Configurando persistencia...")
    
    # Obtenemos la ruta de instalación final.
    install_dir = get_install_path()
    
    # --- Usar el nombre del ejecutable si está compilado ---
    if getattr(sys, 'frozen', False):
        # Si es un .exe, la persistencia debe apuntar directamente a él.
        executable_name = Path(sys.executable).name
        path_to_persist = str(install_dir / executable_name)
    else:
        # Si se ejecuta como script, la persistencia apunta al intérprete y al script.
        # Esto es principalmente para desarrollo.
        path_to_persist = sys.executable
        script_path_arg = str(install_dir / 'main.py') # Asumimos que main.py se copia.
    
    _logger.info(f"La ruta de persistencia apuntará a: {path_to_persist}")

    try:
        if os_type == "Windows":
            # Pasamos un solo argumento: la ruta completa al ejecutable
            _setup_windows_persistence(path_to_persist)
        elif os_type == "Linux":
            # En Linux, el .desktop file contendrá la ruta completa
            _setup_linux_persistence(path_to_persist)
        elif os_type == "Darwin": # macOS
            # En macOS, el .plist contendrá la ruta completa
            _setup_macos_persistence(path_to_persist)
        else:
            _logger.warning(f"La configuración de persistencia automática no es compatible con {os_type}.")
    except Exception as e:
        _logger.error(f"Error al configurar la persistencia: {e}", exc_info=True)

def setup_from_cli(args):
    """
    Configura el agente usando argumentos de línea de comandos y sale.
    """
    _logger.info("Iniciando configuración desde la línea de comandos...")
    
    # 1. Generar número de inventario si es 'AUTO'
    inventory_number = args.inventory
    if inventory_number.upper() == 'AUTO':
        try:
            import uuid
            # Genera un ID basado en la MAC address para unicidad
            mac_address = ':'.join(f'{uuid.getnode():012x}'[i:i+2] for i in range(0, 12, 2))
            inventory_number = f"TEMP-{mac_address.upper()}"
            _logger.info(f"Número de inventario autogenerado: {inventory_number}")
        except Exception as e:
            _logger.error(f"Fallo al autogenerar número de inventario: {e}")
            inventory_number = "TEMP-ERROR"

    # 2. Guardar contraseña en keyring
    try:
        keyring.set_password(KEYRING_SERVICE_NAME, args.odoo_user, args.odoo_password)
        _logger.info("Contraseña para '%s' guardada de forma segura en el keyring.", args.odoo_user)
    except Exception as e:
        _logger.error("Error de Keyring: No se pudo guardar la contraseña de forma segura: %s", e)
        # No continuamos si no se puede guardar la contraseña
        return False

    # 3. Construir y guardar el archivo de configuración
    config = load_config() or {} # Cargar config existente o crear una nueva
    
    final_config = {
        "intervalo_principal_min": config.get("intervalo_principal_min", 60),
        "intervalo_reintento_min": config.get("intervalo_reintento_min", 5),
        "listener_port": config.get("listener_port", 9191),
        "inventory_number": inventory_number,
        "odoo_config": {
            "url": args.odoo_url,
            "db": args.odoo_db,
            "username": args.odoo_user
        }
    }

    if not save_config(final_config):
        _logger.error("No se pudo guardar el archivo de configuración.")
        return False
        
    _logger.info("Archivo de configuración guardado exitosamente.")
    
    # 4. Configurar persistencia (auto-inicio)
    _logger.info("Configurando la persistencia para el inicio automático...")
    setup_persistence()
    
    _logger.info("Configuración desde CLI completada exitosamente.")
    return True

# --- Las funciones auxiliares solo toman una ruta ---
def _setup_windows_persistence(executable_path):
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    key_name = "ScanAgentSGICH"
    command = f'"{executable_path}"' # El comando es solo la ruta al ejecutable
    
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, command)
    _logger.info("Persistencia configurada para Windows.")

def _setup_linux_persistence(executable_path):
    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    desktop_file = autostart_dir / "scan_agent.desktop"
    
    desktop_content = f"""[Desktop Entry]
Type=Application
Exec="{executable_path}"
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name[en_US]=Scan Agent
Name=Scan Agent
Comment[en_US]=Starts the IT asset scanning agent
Comment=Inicia el agente de escaneo de activos de TI
"""
    with open(desktop_file, "w", encoding="utf-8") as f:
        f.write(desktop_content)
    _logger.info("Persistencia configurada para Linux.")

def _setup_macos_persistence(executable_path):
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    launch_agents_dir.mkdir(parents=True, exist_ok=True)
    plist_file = launch_agents_dir / "com.sgich.scanagent.plist"
    
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sgich.scanagent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{executable_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
    with open(plist_file, "w", encoding="utf-8") as f:
        f.write(plist_content)
    _logger.info("Persistencia configurada para macOS.")