# -*- coding: utf-8 -*-
import requests
import socket
import json
import logging
import random
from typing import Dict, Any, List, Optional
from .mapper import ComponentMapper

_logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(module)s] - %(message)s'
)

# --- CONTROL MANUAL DE EXPORTACIÓN DE SOFTWARE ---
# Cambia esta variable a True si deseas que el agente cree los registros de software.
# Si es False, Odoo se encargará de procesarlos desde raw_data.
CREATE_SOFTWARE_RECORDS_FROM_AGENT = False

if not CREATE_SOFTWARE_RECORDS_FROM_AGENT:
    _logger.warning("La exportación y creación de software desde el agente está DESACTIVADA.")
    _logger.warning("Odoo se encargará de procesar la lista de software desde los datos en bruto (raw_data).")
    _logger.warning("Para activar esta función, cambie la variable 'CREATE_SOFTWARE_RECORDS_FROM_AGENT' a True en el archivo 'scan_agent/scan/core/exportador.py' (línea ~20).")

class ExportadorOdoo:
    def __init__(self, url_base: str, db: str, username: str, password: str, inventory_number: str):
        self.url_base = url_base.rstrip('/')
        self.db = db
        self.username = username
        self.password = password
        self.inventory_number = inventory_number
        self.session = requests.Session()
        self.uid = None
        self.software_module_installed = False
        self.network_module_installed = False
        self.mapper = ComponentMapper() # Instanciamos el mapeador
        self.modelos = {
            'backlog': 'it.asset.backlog',
            'componente': 'it.component',
            'software': 'it.asset.software',
            'ip': 'it.ip.address',
            'subtype': 'it.component.subtype',
            'module': 'ir.module.module'
        }

    def _autenticar(self) -> Optional[int]:
        endpoint = f"{self.url_base}/web/session/authenticate"
        payload = {"jsonrpc": "2.0", "params": {"db": self.db, "login": self.username, "password": self.password}}
        try:
            response = self.session.post(endpoint, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json().get('result')
            print(f"Valores de la variable resultado {result}")
            if result and result.get('uid'):
                self.uid = result['uid']
                logging.info(f"Autenticación exitosa - UID: {self.uid}")
                return self.uid
            logging.error(f"Autenticación fallida: {response.json().get('error')}")
            return None
        except Exception as e:
            logging.error(f"Error en autenticación: {e}")
            return None

    def _llamar_api(self, modelo: str, metodo: str, args: List[Any] = None, kwargs: Dict[str, Any] = None) -> Any:
        if not self.uid and not self._autenticar(): return None
        url = f"{self.url_base}/web/dataset/call_kw"
        payload = {
            "jsonrpc": "2.0", "method": "call",
            "params": {"model": modelo, "method": metodo, "args": args or [], "kwargs": kwargs or {}},
            "id": random.randint(1, 1000000)
        }
        try:
            response = self.session.post(url, json=payload, timeout=20)
            response_data = response.json()
            if 'error' in response_data:
                logging.error(f"Error API Odoo: {response_data['error'].get('data', {}).get('message')}")
                return None
            return response_data.get('result')
        except Exception as e:
            logging.error(f"Error en llamada API: {e}")
            return None

    def check_installed_modules(self):
        domain = [('state', '=', 'installed'), ('name', 'in', ['sgichs_software', 'sgichs_red'])]
        installed_modules = self._llamar_api('ir.module.module', 'search_read', [domain], {'fields': ['name']})
        if installed_modules is not None:
            module_names = {mod['name'] for mod in installed_modules}
            self.software_module_installed = 'sgichs_software' in module_names
            self.network_module_installed = 'sgichs_red' in module_names
        logging.info(f"Módulo Software: {'Instalado' if self.software_module_installed else 'No Instalado'}")
        logging.info(f"Módulo Red: {'Instalado' if self.network_module_installed else 'No Instalado'}")

    def _fetch_and_load_subtypes(self):
        """Obtiene todos los subtipos de Odoo y los carga en el mapeador."""
        logging.info("Obteniendo mapa de subtipos de componentes desde Odoo...")
        subtype_data = self._llamar_api(self.modelos['subtype'], 'search_read', [[]], {'fields': ['id', 'name']})
        if subtype_data:
            self.mapper.load_subtypes_from_odoo(subtype_data)
        else:
            logging.error("No se pudieron obtener los subtipos de componentes de Odoo.")

    def _buscar_o_crear(self, modelo: str, search_domain: list, create_vals: dict, update_vals: dict = None):
        update_vals = update_vals or create_vals
        existente_ids = self._llamar_api(modelo, 'search', [search_domain], {'limit': 1})
        if existente_ids:
            record_id = existente_ids[0]
            self._llamar_api(modelo, 'write', [[record_id], update_vals])
            return record_id
        else:
            return self._llamar_api(modelo, 'create', [create_vals])

    def exportar_activo_completo(self, datos: Dict[str, Any]):
        
        if not self.uid and not self._autenticar():
            logging.error("Exportación abortada. Se requiere autenticación.")
            return
        
        # Obtenemos el mapa de subtipos antes de empezar a procesar
        self._fetch_and_load_subtypes()


        # Codigo comentado: Pone el identificador unico tomando la placa mandre y numero de serie como base

        # id_unico_hw = datos.get('placa_madre', {}).get('Número de Serie') or \
        #               next((iface.get('mac') for iface in datos.get('red', []) if iface.get('mac')), None)
        # if not id_unico_hw:
        #     logging.error("No se pudo determinar un ID único para el hardware. Abortando.")
        #     return
        
        
        # El identificador unico ahora sera el numero de inventario
        id_unico_hw = self.inventory_number
        if not id_unico_hw:
            logging.error("No se proporcionó un número de inventario en la configuración. Abortando.")
            return
        

        # --- 1. PROCESAR Y CREAR COMPONENTES CON MAPEADOR ---
        component_ids = []
        todos_los_componentes = (datos.get('almacenamiento', []) + datos.get('ram', []) + 
                                [datos.get('cpu', {})] + [datos.get('placa_madre', {})] + 
                                datos.get('gpu', []) + datos.get('perifericos', []))

        for comp_data in todos_los_componentes:
            if not comp_data: continue
            
            # Usamos diferentes campos como número de serie de respaldo
            serial_number = comp_data.get('Número de Serie') or comp_data.get('ID único') or comp_data.get('id_unico') or comp_data.get('pnp_id')
            if not serial_number:
                continue
            
            # Usamos el mapeador para obtener el subtype_id
            subtype_id = self.mapper.get_subtype_id(comp_data)
            if not subtype_id:
                logging.warning(f"Omitiendo componente sin subtipo mapeado: {comp_data.get('Modelo') or comp_data.get('nombre')}")
                continue

            comp_vals = {
                'model': comp_data.get('Modelo') or comp_data.get('nombre', 'Desconocido'),
                'serial_number': serial_number,
                'subtype_id': subtype_id
            }
            
            # Verificamos si el componente es un periférico basándonos en los datos del recolector.
            # El recolector añade la clave 'tipo' a los periféricos (ej. 'Mouse', 'Teclado').
            if comp_data.get('tipo') in ['Mouse', 'Teclado', 'Monitor', 'Impresora', 'Altavoces', 'Webcam']:
                # Creamos un identificador temporal y único para el número de inventario.
                # Usamos el 'id_unico' del componente (que es un hash sha256) para garantizar estabilidad y unicidad.
                id_unico_periferico = comp_data.get('id_unico', serial_number)
                temp_inventory_number = f"TEMP_INV_{id_unico_periferico}"
                comp_vals['inventory_number'] = temp_inventory_number
                logging.debug(f"Componente periférico detectado. Asignando N° de Inventario temporal: {temp_inventory_number}")
            
            if 'Tamaño (GB)' in comp_data:
                comp_vals['size_gb'] = comp_data.get('Tamaño (GB)')
                
            if 'Tipo RAM' in comp_data:
                # Mapeamos los valores recolectados a los valores de la selección de Odoo
                ram_type_map = {
                    'DDR3': 'ddr3', 'DDR4': 'ddr4', 'DDR5': 'ddr5',
                    'DDR2': 'ddr2', 'DDR': 'ddr'
                }
                recollected_type = comp_data.get('Tipo RAM', '').upper()
                comp_vals['ram_type'] = ram_type_map.get(recollected_type, 'otro')
                
            comp_id = self._buscar_o_crear(
                self.modelos['componente'],
                [('serial_number', '=', comp_vals['serial_number'])],
                comp_vals
            )
            if comp_id:
                component_ids.append(comp_id)

        # --- 2. PROCESAR IPs ---
        ip_ids = []
        if self.network_module_installed and 'red' in datos:
            for iface in datos['red']:
                for ip_addr in iface.get('ipv4', []):
                    ip_vals = {'address': ip_addr, 'description': iface.get('nombre')}
                    ip_id = self._buscar_o_crear(self.modelos['ip'], [('address', '=', ip_addr)], ip_vals)
                    if ip_id:
                        ip_ids.append(ip_id)
        
        # --- 3. PROCESAR SOFTWARE ---
        software_ids = []
        # Solo se ejecuta si la variable de control es True
        if CREATE_SOFTWARE_RECORDS_FROM_AGENT and self.software_module_installed and 'programas' in datos:
            _logger.info("Creando registros de software directamente desde el agente.")
            for prog in datos['programas']:
                sw_vals = {'name': prog.get('nombre', 'Desconocido'), 'version': prog.get('version', 'N/A')}
                sw_id = self._buscar_o_crear(self.modelos['software'], [('name', '=', sw_vals['name']), ('version', '=', sw_vals['version'])], sw_vals)
                if sw_id:
                    software_ids.append(sw_id)

        # --- 4. VINCULACIÓN FINAL EN BACKLOG ---
        os_info = datos.get('sistema_operativo', {})
        
        # --- Construcción del nombre descriptivo ---
        try:
            cpu_model = datos.get('cpu', {}).get('Modelo', 'CPU Desconocido').strip()
            total_ram_gb = datos.get('ram_total_gb', 0.0)
            hostname_part = f"{socket.gethostname()} - {os_info.get('sistema', 'OS Desc.')}"
            
            # Formateamos el nombre como lo pediste
            description_text = f"{cpu_model} {total_ram_gb:.2f} GB RAM ({hostname_part})"
        except Exception as e:
            logging.error(f"Error construyendo la descripción del hardware: {e}")
            # Fallback al nombre anterior si algo falla
            description_text = f"{socket.gethostname()} - {os_info.get('sistema', 'OS Desc.')}"

        
        backlog_vals = {
            'name': id_unico_hw,
            'description': description_text,
            'type': 'hardware',
            'raw_data': json.dumps(datos, indent=2, default=str),
            'components_ids': [(6, 0, list(set(component_ids)))],
            'software_ids': [(6, 0, software_ids)] if self.software_module_installed else False,
            'ip_ids': [(6, 0, ip_ids)] if self.network_module_installed else False,
        }

        backlog_vals = {k: v for k, v in backlog_vals.items() if v is not False}

        self._buscar_o_crear(
            self.modelos['backlog'],
            [('name', '=', id_unico_hw)],
            {'name': id_unico_hw, **backlog_vals},
            backlog_vals
        )
        logging.info(f"Proceso de exportación para '{id_unico_hw}' completado.")

    def test_connection_with_odoo(self) -> bool:
        if not self._autenticar(): return False
        try:
            if isinstance(self._llamar_api('ir.module.module', 'search_count', [[('state', '=', 'installed')]]), int): return True
        except Exception: pass
        return False