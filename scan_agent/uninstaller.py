# -*- coding: utf-8 -*-
import os
import platform
import sys
import shutil
import time
import subprocess
from pathlib import Path

# --- Importaciones robustas para que el script sea autónomo ---
try:
    import psutil
    import winreg
except ImportError:
    print("Instalando dependencias necesarias (psutil, pywin32)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "pywin32"])
    import psutil
    import winreg

# --- Lógica copiada de configurador.py para ser autónomo ---
LOCK_FILE = Path.home() / '.sgichs_agent.lock'
APP_NAME = "ScanAgentSGICH"

def get_install_path() -> Path:
    system = platform.system()
    if system == "Windows":
        appdata_path_str = os.getenv('LOCALAPPDATA')
        base_path = Path(appdata_path_str) if appdata_path_str else Path.home() / 'AppData' / 'Local'
        return base_path / APP_NAME
    elif system == "Linux":
        return Path.home() / ".local" / "share" / APP_NAME
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        return Path.home() / f".{APP_NAME.lower()}"

def stop_agent_process():
    """Detiene el proceso del agente si se está ejecutando."""
    print("1. Deteniendo el proceso del agente...")
    if not LOCK_FILE.exists():
        print(" -> El agente no parece estar en ejecución (no se encontró el archivo de bloqueo).")
        return
    try:
        pid = int(LOCK_FILE.read_text().strip())
        if psutil.pid_exists(pid):
            proc = psutil.Process(pid)
            print(f" -> Proceso del agente encontrado con PID {pid}. Terminando...")
            proc.terminate()
            proc.wait(timeout=5) # Esperar hasta 5 segundos
        else:
            print(" -> El PID en el archivo de bloqueo no corresponde a un proceso activo.")
    except (psutil.NoSuchProcess, psutil.TimeoutExpired):
        print(" -> El proceso ya no existe o no respondió. Procediendo...")
    except Exception as e:
        print(f" -> Ocurrió un error al intentar detener el proceso: {e}")
    finally:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
            print(" -> Archivo de bloqueo eliminado.")

def remove_persistence():
    """Elimina la entrada de auto-inicio del agente."""
    print("2. Eliminando la persistencia (auto-inicio)...")
    system = platform.system()
    try:
        if system == "Windows":
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key_name = "ScanAgentSGICH"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.DeleteValue(key, key_name)
            print(" -> Entrada de registro de Windows eliminada.")
        elif system == "Linux":
            desktop_file = Path.home() / ".config" / "autostart" / "scan_agent.desktop"
            if desktop_file.exists():
                desktop_file.unlink()
                print(" -> Archivo .desktop de auto-inicio eliminado.")
            else:
                print(" -> No se encontró archivo de auto-inicio en Linux.")
        elif system == "Darwin":
            plist_file = Path.home() / "Library" / "LaunchAgents" / "com.sgich.scanagent.plist"
            if plist_file.exists():
                subprocess.run(["launchctl", "unload", str(plist_file)], check=False)
                plist_file.unlink()
                print(" -> Agente de lanzamiento de macOS eliminado.")
            else:
                print(" -> No se encontró agente de lanzamiento en macOS.")
    except FileNotFoundError:
        # Esto puede pasar si la clave de registro ya no existe, es seguro ignorarlo.
        print(" -> No se encontró la entrada de persistencia (puede que ya haya sido eliminada).")
    except Exception as e:
        print(f" -> Error al eliminar la persistencia: {e}")

def delete_installation_files():
    """Elimina la carpeta de instalación del agente."""
    print("3. Eliminando archivos de la aplicación...")
    install_dir = get_install_path()
    if install_dir.exists():
        try:
            shutil.rmtree(install_dir)
            print(f" -> Directorio de instalación '{install_dir}' eliminado.")
        except Exception as e:
            print(f" -> Error al eliminar el directorio de instalación: {e}")
    else:
        print(" -> No se encontró el directorio de instalación.")

def self_delete():
    """Maneja la auto-eliminación del desinstalador en Windows."""
    if platform.system() == "Windows":
        # En Windows, un script no puede eliminarse a sí mismo.
        # Creamos un archivo .bat temporal que se encarga de la tarea.
        uninstaller_path = sys.executable
        batch_script = f"""
@echo off
echo Esperando para finalizar la desinstalación...
timeout /t 2 /nobreak > NUL
del "{uninstaller_path}"
del "%~f0"
"""
        script_path = Path(os.getenv("TEMP")) / "uninstall_cleanup.bat"
        with open(script_path, "w") as f:
            f.write(batch_script)
        
        # Ejecutamos el script .bat en un nuevo proceso que no depende del actual.
        subprocess.Popen([str(script_path)], shell=True, creationflags=subprocess.DETACHED_PROCESS)

def main():
    """Función principal del desinstalador."""
    print("--- Desinstalador del Agente SGICH ---")
    print("\nEste script eliminará el agente, su configuración y la entrada de auto-inicio.")
    
    try:
        confirm = input("¿Está seguro de que desea continuar? (s/N): ").lower()
        if confirm != 's':
            print("Desinstalación cancelada.")
            time.sleep(2)
            return

        stop_agent_process()
        remove_persistence()
        delete_installation_files()

        print("\n¡Desinstalación completada!")
        
        # Intentar auto-eliminarse
        self_delete()

    except Exception as e:
        print(f"\nOcurrió un error inesperado: {e}")
    
    if platform.system() != "Windows":
        print("Presione Enter para salir.")
        input()

if __name__ == "__main__":
    main()