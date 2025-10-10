import platform
import subprocess
import re
import logging

if platform.system() == "Linux":
    from ..core.linux_sudo_helper import sudo_manager


_logger = logging.getLogger(__name__)

class RecolectorPlacaMadre:
    def obtener_info(self):
        so = platform.system()
        if so == "Windows":
            return self._obtener_info_windows()
        elif so == "Linux":
            return self._obtener_info_linux()
        else:
            return self._info_generica()

    def _info_generica(self):
        return {
            'Mensaje': 'Sistema operativo no soportado para recolección detallada de placa madre.'
        }

    def _obtener_info_windows(self):
        import wmi
        c = wmi.WMI()
        
        info = {}
        
        # Información de la placa base
        for board in c.Win32_BaseBoard():
            info['Fabricante'] = board.Manufacturer
            info['Modelo'] = board.Product
            info['Versión'] = board.Version
            info['Número de Serie'] = board.SerialNumber.strip()
            info['Activo'] = board.Status == 'OK'
        
        if info['Modelo'] == "" or info['Modelo'] == " ":
            info['Modelo'] = "Placa Madre Genérica"
        
        # Información del sistema
        for system in c.Win32_ComputerSystem():
            info['Fabricante del Sistema'] = system.Manufacturer
            info['Modelo del Sistema'] = system.Model
            info['SKU del Sistema'] = system.SystemSKUNumber
            info['Tipo de Sistema'] = system.SystemType
        
        # Información del BIOS
        for bios in c.Win32_BIOS():
            info['BIOS Fabricante'] = bios.Manufacturer
            info['BIOS Versión'] = bios.Version
            info['BIOS Fecha'] = bios.ReleaseDate
            info['BIOS Serial'] = bios.SerialNumber
        
        # Chipset (aproximado)
        for chip in c.Win32_IDEController():
            if 'Chipset' in chip.Name:
                info['Chipset'] = chip.Name
                break
        
        return info

    def _obtener_info_linux(self):
        try:
            # Información de la placa base
            output_baseboard = sudo_manager.run("dmidecode -t baseboard")
            info = self._parsear_dmidecode(output_baseboard, "Base Board Information")
            
            # Información del sistema
            output_system = sudo_manager.run("dmidecode -t system")
            system_info = self._parsear_dmidecode(output_system, "System Information")
            info.update(system_info)
            
            # Información del BIOS
            output_bios = sudo_manager.run("dmidecode -t bios")
            bios_info = self._parsear_dmidecode(output_bios, "BIOS Information")
            info.update(bios_info)
            
            # Información del chipset (aproximación)
            try:
                output_chipset = subprocess.check_output(
                    "lspci | grep -i 'bridge\|chipset'",
                    shell=True,
                    text=True,
                    stderr=subprocess.STDOUT
                )
                if output_chipset:
                    chipsets = [line.split(': ')[1] for line in output_chipset.splitlines() if line]
                    info['Chipset'] = "; ".join(chipsets)
            except:
                pass
            
            return info
        except Exception as e:
            return {
                'error': f"No se pudo obtener información detallada: {str(e)}",
                'sugerencia': "Ejecutar con permisos sudo o instalar dmidecode/lspci"
            }

    def _parsear_dmidecode(self, output, seccion_busqueda):
        info = {}
        bloques = re.split(r'\n\s*\n', output)
        
        for bloque in bloques:
            if seccion_busqueda not in bloque:
                continue
                
            lineas = bloque.split('\n')
            for linea in lineas:
                if ':' not in linea:
                    continue
                    
                clave, valor = [parte.strip() for parte in linea.split(':', 1)]
                
                # Mapeo de claves DMIDecode a nombres más amigables
                mapeo_claves = {
                    'Manufacturer': 'Fabricante',
                    'Product Name': 'Modelo',
                    'Version': 'Versión',
                    'Serial Number': 'Número de Serie',
                    'Vendor': 'Fabricante del Sistema',
                    'Product': 'Modelo del Sistema',
                    'SKU Number': 'SKU del Sistema',
                    'Family': 'Familia del Sistema',
                    'BIOS Revision': 'BIOS Revisión',
                    'Release Date': 'BIOS Fecha',
                    'Vendor': 'BIOS Fabricante',
                    'Version': 'BIOS Versión'
                }
                
                clave_traducida = mapeo_claves.get(clave, clave)
                
                # Filtrar valores "Not Specified" o "None"
                if valor and valor not in ['Not Specified', 'None', 'Not Present']:
                    info[clave_traducida] = valor
                    
        return info