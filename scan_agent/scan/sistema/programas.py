import platform
import subprocess
import re
import os
import logging
from datetime import datetime

# Se elimina la importación global de winreg de aquí

_logger = logging.getLogger(__name__)

class RecoltadorProgramas:
    def obtener_info(self):
        """Obtiene información de programas instalados en el sistema."""
        _logger.debug("Iniciando recolección de información de programas.")
        so = platform.system()
        _logger.debug(f"Sistema operativo detectado: {so}")
        
        if so == "Windows":
            return self._obtener_programas_windows()
        elif so == "Linux":
            return self._obtener_programas_linux()
        else:
            _logger.warning(f"Sistema operativo no soportado para recolección de programas: {so}")
            # --- CORRECCIÓN: Devolver lista vacía en lugar de llamar a método inexistente ---
            return []
    
    def _obtener_programas_windows(self):
        """Obtiene programas instalados en Windows usando el registro."""
        _logger.debug("Iniciando búsqueda de programas en Windows.")
        
        # --- CORRECCIÓN: Importación de winreg local a la función ---
        try:
            import winreg
        except ImportError:
            _logger.error("No se pudo importar 'winreg'. Esta función solo es compatible con Windows.")
            return []
        
        programas = []
        rutas_registro = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
        ]
        
        for ruta in rutas_registro:
            _logger.debug(f"Buscando en ruta del registro: {ruta}")
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ruta) as key:
                    idx = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, idx)
                            subkey_path = f"{ruta}\\{subkey_name}"
                            
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey_path) as subkey:
                                programa = {}
                                try:
                                    programa["nombre"] = self._obtener_valor_registro(subkey, "DisplayName")
                                    programa["version"] = self._obtener_valor_registro(subkey, "DisplayVersion")
                                    programa["fabricante"] = self._obtener_valor_registro(subkey, "Publisher")
                                    programa["licencia"] = self._obtener_clave_licencia(subkey)
                                    programa["fecha_instalacion"] = self._obtener_valor_registro(subkey, "InstallDate")
                                    programa["tamaño"] = self._convertir_tamano(self._obtener_valor_registro(subkey, "EstimatedSize"))
                                    programa["ubicacion"] = self._obtener_valor_registro(subkey, "InstallLocation")
                                    
                                    if programa.get("nombre") and not programa["nombre"].startswith("KB") and not programa["nombre"].startswith("Update for"):
                                        programas.append(programa)
                                        _logger.debug(f"Programa encontrado: {programa['nombre']}")
                                
                                except OSError:
                                    # Algunas subclaves no tienen todos los valores, es normal.
                                    pass
                        except OSError:
                            # Se acabaron las subclaves en esta ruta del registro.
                            break
                        idx += 1
            except FileNotFoundError:
                _logger.debug(f"Ruta de registro no encontrada (normal en algunas versiones de SO): {ruta}")
            except Exception as e:
                _logger.error(f"Error al acceder a la ruta del registro {ruta}: {e}")
        
        _logger.debug(f"Total de programas encontrados en Windows: {len(programas)}")
        return programas

    def _obtener_programas_linux(self):
        """Obtiene programas instalados en Linux usando diferentes métodos."""
        _logger.debug("Iniciando búsqueda de programas en Linux.")
        programas = []
        try:
            if os.path.exists("/var/lib/dpkg/status"):
                _logger.debug("Detectado sistema Debian/Ubuntu.")
                programas.extend(self._obtener_paquetes_deb())
            elif os.path.exists("/var/lib/rpm"):
                _logger.debug("Detectado sistema RedHat/Fedora.")
                programas.extend(self._obtener_paquetes_rpm())
            
            programas.extend(self._obtener_paquetes_snap())
            programas.extend(self._obtener_paquetes_flatpak())
            
            _logger.debug(f"Total de programas encontrados en Linux: {len(programas)}")
        except Exception as e:
            _logger.error(f"Error al obtener programas en Linux: {e}", exc_info=True)
        return programas

    def _obtener_valor_registro(self, key, value_name):
        """Obtiene un valor del registro de Windows."""
        # --- CORRECCIÓN: Importación local necesaria ---
        try:
            import winreg
        except ImportError:
            return ""

        try:
            value, _ = winreg.QueryValueEx(key, value_name)
            return value
        except OSError:
            return ""
    
    def _obtener_clave_licencia(self, key):
        """Intenta obtener clave de licencia de varias ubicaciones posibles."""
        # --- CORRECCIÓN: Importación local necesaria ---
        try:
            import winreg
        except ImportError:
            return ""

        claves_posibles = [
            "ProductKey", "SerialKey", "LicenseKey", 
            "CDKey", "ActivationKey", "RegistrationKey"
        ]
        
        for clave in claves_posibles:
            try:
                valor, _ = winreg.QueryValueEx(key, clave)
                if valor and isinstance(valor, str) and valor.strip():
                    return valor
            except OSError:
                continue
        
        try:
            install_path = self._obtener_valor_registro(key, "InstallLocation")
            if install_path and os.path.isdir(install_path):
                for archivo in ["license.key", "serial.txt", "product.key"]:
                    ruta_archivo = os.path.join(install_path, archivo)
                    if os.path.exists(ruta_archivo):
                        with open(ruta_archivo, "r", errors='ignore') as f:
                            contenido = f.read().strip()
                            if contenido:
                                return contenido
        except Exception:
            pass # Evitar que un error aquí detenga la recolección
        
        return ""

    def _convertir_tamano(self, size_kb):
        """Convierte tamaño de KB a formato legible."""
        if not size_kb:
            return "Desconocido"
        try:
            size_kb = int(size_kb)
            if size_kb > 1024 * 1024:
                return f"{size_kb/(1024*1024):.2f} GB" # Corregido a GB
            elif size_kb > 1024:
                return f"{size_kb/1024:.2f} MB" # Corregido a MB
            else:
                return f"{size_kb} KB" # Corregido a KB
        except (ValueError, TypeError):
            return "Desconocido"

    # --- ¡NUEVO! Método placeholder para evitar crash ---
    def _obtener_licencia_debian(self, nombre_paquete: str) -> str:
        """
        Placeholder para la lógica de obtención de licencias en Debian.
        Esta es una tarea compleja y no trivial.
        """
        # Se podría implementar una lógica que busque en /usr/share/doc/{paquete}/copyright
        return "Desconocido"

    def _obtener_paquetes_deb(self):
        """Obtiene paquetes .deb instalados."""
        _logger.debug("Obteniendo paquetes DEB.")
        programas = []
        try:
            output = subprocess.check_output(
                "dpkg-query -W -f='${Package}||${Version}||${Maintainer}||${Installed-Size}\\n'",
                shell=True, text=True, stderr=subprocess.DEVNULL
            )
            for linea in output.splitlines():
                if '||' in linea:
                    nombre, version, fabricante, tamano = linea.split('||', 3)
                    programas.append({
                        "nombre": nombre,
                        "version": version,
                        "fabricante": fabricante,
                        "licencia": self._obtener_licencia_debian(nombre),
                        "tamaño": f"{int(tamano)} KB" if tamano.isdigit() else "Desconocido"
                    })
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            _logger.error(f"Error al ejecutar dpkg-query: {e}")
        return programas
    
    def _obtener_paquetes_rpm(self):
        """Obtiene paquetes RPM instalados."""
        _logger.debug("Obteniendo paquetes RPM.")
        programas = []
        try:
            output = subprocess.check_output(
                "rpm -qa --qf '%{NAME}||%{VERSION}||%{VENDOR}||%{LICENSE}||%{SIZE}\\n'",
                shell=True, text=True, stderr=subprocess.DEVNULL
            )
            for linea in output.splitlines():
                if '||' in linea:
                    nombre, version, fabricante, licencia, tamano_bytes = linea.split('||', 4)
                    programas.append({
                        "nombre": nombre,
                        "version": version,
                        "fabricante": fabricante,
                        "licencia": licencia,
                        "tamaño": self._convertir_tamano(int(tamano_bytes) // 1024) if tamano_bytes.isdigit() else "Desconocido"
                    })
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            _logger.error(f"Error al ejecutar rpm: {e}")
        return programas
    
    def _obtener_paquetes_snap(self):
        """Obtiene paquetes Snap instalados."""
        _logger.debug("Obteniendo paquetes SNAP.")
        programas = []
        try:
            output = subprocess.check_output(
                "snap list", shell=True, text=True, stderr=subprocess.DEVNULL
            )
            # El formato de 'snap list' es más tabular, requiere un parseo diferente
            lines = output.strip().split('\n')
            if len(lines) > 1:
                for line in lines[1:]: # Omitir la cabecera
                    parts = line.split()
                    if len(parts) >= 4:
                        programas.append({
                            "nombre": parts[0],
                            "version": parts[1],
                            "fabricante": parts[3],
                            "licencia": "Desconocido",
                            "tamaño": "N/A",
                            "tipo": "snap"
                        })
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            _logger.warning(f"Comando 'snap' no encontrado o falló: {e}")
        return programas
    
    def _obtener_paquetes_flatpak(self):
        """Obtiene paquetes Flatpak instalados."""
        _logger.debug("Obteniendo paquetes FLATPAK.")
        programas = []
        try:
            output = subprocess.check_output(
                "flatpak list --app --columns=application,version,origin",
                shell=True, text=True, stderr=subprocess.DEVNULL
            )
            lines = output.strip().split('\n')
            if len(lines) > 1:
                for line in lines[1:]:
                    parts = line.split('\t') # Separado por tabuladores
                    if len(parts) >= 3:
                        programas.append({
                            "nombre": parts[0],
                            "version": parts[1],
                            "fabricante": parts[2], # 'origin' como fabricante
                            "licencia": "Desconocido",
                            "tamaño": "N/A",
                            "tipo": "flatpak"
                        })
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            _logger.warning(f"Comando 'flatpak' no encontrado o falló: {e}")
        return programas