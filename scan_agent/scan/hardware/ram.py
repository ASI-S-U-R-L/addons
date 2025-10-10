import psutil
import platform
import subprocess
import re
import logging

if platform.system() == "Linux":
    from ..core.linux_sudo_helper import sudo_manager

_logger = logging.getLogger(__name__) 

class RecolectorRAM:
    def obtener_info(self):
        so = platform.system()
        if so == "Windows":
            return self._obtener_info_windows()
        elif so == "Linux":
            return self._obtener_info_linux()
        else:
            return self._info_basica()

    def _info_basica(self):
        memoria = psutil.virtual_memory()
        return [{
            'Tamaño (GB)': round(memoria.total / (1024 ** 3), 2)
        }]

    def _obtener_info_windows(self):
        try:
            import wmi
            c = wmi.WMI()
            modulos = []
            
            for modulo in c.Win32_PhysicalMemory():
                modulos.append({
                    'Fabricante': modulo.Manufacturer,
                    'Modelo': modulo.PartNumber,
                    'Tamaño (GB)': int(modulo.Capacity) / (1024**3),
                    'Número de Serie': modulo.SerialNumber.strip(),
                    'Tipo RAM': self._traducir_tipo_ram_windows(modulo.MemoryType), # ¡NUEVO!
                    'Velocidad (MHz)': modulo.Speed,
                    'Factor de Forma': self._traducir_factor_forma_windows(modulo.FormFactor),
                    'Banco': modulo.BankLabel,
                    'Slot': modulo.DeviceLocator
                })
            
            return modulos
        except ImportError:
            _logger.error("Módulo WMI no disponible para recolectar info de RAM en Windows.")
            return self._info_basica()
        except Exception as e:
            _logger.error(f"Error al obtener info de RAM en Windows: {e}")
            return self._info_basica()

    def _obtener_info_linux(self):
        try:
            
            # Ya no usamos subprocess directamente
            output = sudo_manager.run("dmidecode --type memory")
            
            return self._parsear_dmidecode(output)
        except Exception as e:
            _logger.error(f"No se pudo obtener información detallada de RAM: {str(e)}")
            return [{
                'error': f"No se pudo obtener información detallada: {str(e)}",
                'sugerencia': "Ejecutar con permisos sudo o instalar dmidecode"
            }]

    def _parsear_dmidecode(self, output):
        bloques = re.split(r'\n\s*\n', output)
        modulos = []
        bloque_actual = {}
        
        for bloque in bloques:
            if "Memory Device" not in bloque:
                continue
                
            lineas = bloque.split('\n')
            for linea in lineas:
                if ':' not in linea:
                    continue
                    
                clave, valor = [parte.strip() for parte in linea.split(':', 1)]
                
                if clave == "Size" and "No Module Installed" not in valor:
                    bloque_actual['Tamaño (GB)'] = int(valor.split()[0]) / 1024
                    
                elif clave == "Type":
                    bloque_actual['Tipo'] = valor
                    
                elif clave == "Speed":
                    if "Unknown" not in valor:
                        bloque_actual['Velocidad (MHz)'] = valor.split()[0]
                    
                elif clave == "Manufacturer":
                    bloque_actual['Fabricante'] = valor
                    
                elif clave == "Serial Number":
                    bloque_actual['Número de Serie'] = valor
                    
                elif clave == "Part Number":
                    bloque_actual['Modelo'] = valor
                    
                elif clave == "Locator":
                    bloque_actual['Slot'] = valor
                    
                elif clave == "Bank Locator":
                    bloque_actual['Banco'] = valor
                    
                elif clave == "Form Factor":
                    bloque_actual['Factor de Forma'] = valor
            
            if bloque_actual:
                modulos.append(bloque_actual)
                bloque_actual = {}
                
        return modulos or self._info_basica()
    
    
    # --- MÉTODOS HELPER WINDOWS---
    def _traducir_tipo_ram_windows(self, tipo_id):
        tipos = {
            20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM", 24: "DDR3",
            26: "DDR4", 27: "LPDDR4", 28: "LPDDR5", 29: "DDR5"
        }
        return tipos.get(tipo_id, "Otro")

    def _traducir_factor_forma_windows(self, factor_id):
        factores = {8: "DIMM", 12: "SODIMM"}
        return factores.get(factor_id, "Otro")


    # --- MÉTODOS HELPER STANDAR---
    def _traducir_tipo(self, tipo_id):
        tipos = {
            20: "DDR",
            21: "DDR2",
            22: "DDR2 FB-DIMM",
            24: "DDR3",
            26: "DDR4",
            27: "LPDDR4",
            28: "LPDDR5",
            29: "DDR5"
        }
        return tipos.get(tipo_id, f"Desconocido ({tipo_id})")

    def _traducir_factor_forma(self, factor_id):
        factores = {
            0: "Desconocido",
            1: "Other",
            2: "SIP",
            3: "DIP",
            4: "ZIP",
            5: "SOJ",
            6: "Proprietary",
            7: "SIMM",
            8: "DIMM",
            9: "TSOP",
            10: "PGA",
            11: "RIMM",
            12: "SODIMM",
            13: "SRIMM",
            14: "SMD",
            15: "SSMP",
            16: "QFP",
            17: "TQFP",
            18: "SOIC",
            19: "LCC",
            20: "PLCC",
            21: "BGA",
            22: "FPBGA",
            23: "LGA"
        }
        return factores.get(factor_id, f"Desconocido ({factor_id})")