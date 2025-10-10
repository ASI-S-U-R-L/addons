# RUTA: scan_agent/scan/core/recolector.py

# Asumo que las importaciones de hardware, etc. están correctas
from ..hardware.cpu import RecolectorCPU
from ..hardware.ram import RecolectorRAM
from ..hardware.disco import RecolectorDiscos
from ..hardware.gpu import RecolectorGPU
from ..hardware.red import RecolectorRed
from ..hardware.perifericos import RecolectorPerifericos
from ..hardware.placamadre import RecolectorPlacaMadre
from .exportador import ExportadorOdoo
from ..sistema.os import RecolectorOS
from ..sistema.programas import RecoltadorProgramas
import platform
import hashlib
import logging
import subprocess
import psutil

if platform.system() == "Linux":
    from .linux_sudo_helper import sudo_manager

# --- Importación condicional de WMI ---
if platform.system() == "Windows":
    try:
        import wmi
    except ImportError:
        logging.error("La librería 'wmi' no está instalada. Es necesaria para Windows.")
        wmi = None
else:
    wmi = None

class GestorTI:
    def __init__(self, software_installed=False, network_installed=False):
        """
        Inicializa el gestor y decide qué recolectores usar
        basado en los módulos instalados en Odoo.
        """
        self.recolectores = {
            # Los de hardware siempre se recolectan
            "placa_madre": RecolectorPlacaMadre(),
            "cpu": RecolectorCPU(),
            "almacenamiento": RecolectorDiscos(),
            "ram": RecolectorRAM(),
            "gpu": RecolectorGPU(),
            "perifericos": RecolectorPerifericos(),
            "sistema_operativo": RecolectorOS(),
        }
        
        # Recolección condicional
        if software_installed:
            logging.info("El módulo de software está instalado. Se recolectarán los programas.")
            self.recolectores["programas"] = RecoltadorProgramas()
        else:
            logging.warning("El módulo de software no está instalado. Se omitirá la recolección de programas.")

        if network_installed:
            logging.info("El módulo de red está instalado. Se recolectará la información de red.")
            self.recolectores["red"] = RecolectorRed(debug=True)
        else:
            logging.warning("El módulo de red no está instalado. Se omitirá la recolección de información de red.")

        self.exportador = None

    def set_exportador(self, exportador: ExportadorOdoo):
        """Asigna una instancia pre-configurada y probada del exportador."""
        self.exportador = exportador

    # --- MÉTODO MODIFICADO PARA SER MULTIPLATAFORMA ---
    def recolectar_todo(self):
        resultados = {}
        
        # Obtenemos el serial de la placa madre una sola vez
        motherboard_serial = self._get_motherboard_serial()
        
        for nombre, recolector in self.recolectores.items():
            try:
                if nombre == "perifericos":
                    perifericos = recolector.obtener_info()
                    resultados[nombre] = [self._generar_id_periferico(p) for p in perifericos]
                elif nombre == "ram":
                    # Usamos el serial ya obtenido
                    pc_identifier = f"{platform.node()}_{motherboard_serial}"
                    ram_info = recolector.obtener_info()
                    resultados[nombre] = [self._generar_id_local_ram(p, pc_identifier) for p in ram_info]
                else:
                    resultados[nombre] = recolector.obtener_info()
            except Exception as e:
                resultados[nombre] = {"error": str(e)}
        
        # --- CÁLCULO DE RAM TOTAL ---
        # Es más fiable obtener la RAM total directamente del sistema que sumar los módulos.
        try:
            total_ram_bytes = psutil.virtual_memory().total
            resultados['ram_total_gb'] = round(total_ram_bytes / (1024**3), 2)
            logging.debug(f"RAM total detectada (psutil): {resultados['ram_total_gb']} GB")
        except Exception as e:
            logging.error(f"No se pudo obtener la RAM total con psutil: {e}")
            # Si psutil falla, usamos la suma de los módulos como plan B.
            ram_modules = resultados.get('ram', [])
            if isinstance(ram_modules, list):
                resultados['ram_total_gb'] = sum(r.get('Tamaño (GB)', 0) for r in ram_modules)
                logging.warning(f"Fallback: RAM total calculada sumando módulos: {resultados['ram_total_gb']} GB")
            else:
                resultados['ram_total_gb'] = 0.0
        
        return resultados

    # --- Método multiplataforma para el serial de la placa madre ---
    def _get_motherboard_serial(self) -> str:
        """Obtiene el número de serie de la placa madre según el SO."""
        system = platform.system()
        serial = "UNKNOWN"
        try:
            if system == "Windows" and wmi:
                c = wmi.WMI()
                serial = next((board.SerialNumber.strip() for board in c.Win32_BaseBoard()), "UNKNOWN")
            elif system == "Linux":
                # Usamos el gestor en lugar de Popen
                command = "dmidecode -s baseboard-serial-number"
                serial = sudo_manager.run(command).strip()
            elif system == "Darwin": # macOS
                command = "ioreg -l | grep IOPlatformSerialNumber"
                process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()
                if process.returncode == 0:
                    serial = stdout.decode().split('=')[-1].strip().replace('"', '')
                else:
                    logging.warning(f"No se pudo obtener serial de placa base con ioreg: {stderr.decode().strip()}")
        except Exception as e:
            logging.error(f"Error obteniendo serial de la placa base: {e}")
        
        return serial if serial and "to be filled" not in serial.lower() else "UNKNOWN"

    # El resto de los métodos (_generar_id_local_ram, etc.) no necesitan cambios.
    def _generar_id_local_ram(self, ram, pc_identifier):
        ram_serial = ram.get('Número de Serie', '').strip()
        if ram_serial and ram_serial not in ['0', 'N/A', 'SerNum'] and len(ram_serial) > 4:
            id_unico_ram = ram_serial
        else:
            id_unico_ram = (f"{ram.get('Fabricante', '')}-{ram.get('Modelo', '')}-"
                            f"{ram.get('Tamaño (GB)', '')}-{ram.get('Banco', '')}-{ram.get('Slot', '')}")

        datos_para_hash = f"ram_id:{id_unico_ram.lower()}-pc_id:{pc_identifier.strip().lower()}"
        hash_final = hashlib.sha256(datos_para_hash.encode('utf-8')).hexdigest()
        return {**ram, "id_unico": hash_final}
    
    def _generar_id_periferico(self, periferico):
        datos_id = f"{periferico.get('tipo', '')}-{periferico.get('id_dispositivo', '')}-{periferico.get('serial', '')}"
        hash_id = hashlib.sha256(datos_id.encode()).hexdigest()
        return {**periferico, "id_unico": hash_id}

    def exportar_datos(self):
        if not self.exportador:
            logging.error("El exportador no está configurado. No se pueden enviar datos.")
            raise Exception("Exportador no configurado")

        logging.info("Recolectando todos los datos para la exportación...")
        datos_completos = self.recolectar_todo()
        self.exportador.exportar_activo_completo(datos_completos)
    
    def test(self):
        print("\n" + "="*50)
        print("INICIO DE PRUEBA DEL GESTOR DE TI")
        print("="*50)
        datos = self.recolectar_todo()
        self.imprimir_datos(datos)
        print("\n" + "="*50)
        print("PRUEBA COMPLETADA")
        print("="*50)
        
    def imprimir_datos(self, datos):
        for categoria, info in datos.items():
            print(f"\n[{categoria.upper()}]")
            if isinstance(info, list):
                for item in info:
                    self._imprimir_diccionario(item)
            elif isinstance(info, dict):
                self._imprimir_diccionario(info)

    def _imprimir_diccionario(self, datos, indent=2):
        for clave, valor in datos.items():
            print(f"{' ' * indent}{clave}: {valor}")