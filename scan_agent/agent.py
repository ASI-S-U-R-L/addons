# -*- coding: utf-8 -*-
import time
import logging
import sys
import threading
import keyring

# Definimos el mismo nombre de servicio que en la GUI
KEYRING_SERVICE_NAME = "sgich-scan-agent"

# --- Importación de los módulos del proyecto ---
try:
    from scan.core.exportador import ExportadorOdoo
    from scan.core.recolector import GestorTI
    from scan.core.agent_listener import AgentListener
    from scan.core.offline_data_handler import recolectar_todo_y_crear_json_al_fallar_la_conexion_con_odoo
except ImportError as e:
    logging.critical(f"Error de importación en agent.py: {e}. Asegúrate de ejecutar desde la raíz del proyecto.", exc_info=True)
    sys.exit(1)

class AgenteScanner:
    def __init__(self, config: dict):
        logging.debug("Inicializando AgenteScanner...")
        self.intervalo_principal_seg = config.get("intervalo_principal_min", 30) * 60
        self.intervalo_reintento_seg = config.get("intervalo_reintento_min", 5) * 60
        self.listener_port = config.get("listener_port", 9191)
        
        self.inventory_number = config.get("inventory_number")
        if not self.inventory_number:
            raise ValueError("El número de inventario no se encontró en la configuración. Por favor, ejecute el configurador.")
        
        self.odoo_config = config.get("odoo_config")
        if not self.odoo_config:
            raise ValueError("La configuración de Odoo no se encontró.")
        
        username = self.odoo_config.get('username')
        if not username:
            raise ValueError("El nombre de usuario no se encontró en la configuración.")
        
        logging.debug(f"Recuperando contraseña para el usuario: {username}")
        password = keyring.get_password(KEYRING_SERVICE_NAME, username)
        if not password:
            raise ValueError(f"No se encontró una contraseña guardada para el usuario '{username}'. "
                            "Por favor, ejecute el agente con el argumento '--config' para configurarla.")

        logging.debug("Creando instancia de ExportadorOdoo.")
        self.exportador = ExportadorOdoo(
            url_base=self.odoo_config.get('url'),
            db=self.odoo_config.get('db'),
            username=username,
            password=password,
            inventory_number=self.inventory_number
        )
        
        # --- LÓGICA DE REINICIO ---
        self.restart_event = threading.Event()
        self.listener = AgentListener(port=self.listener_port, restart_event=self.restart_event)
        # --- FIN LÓGICA DE REINICIO ---
        
        logging.info("AgenteScanner inicializado correctamente.")

    def _ejecutar_ciclo(self) -> bool:
        """
        Ejecuta un ciclo completo de escaneo y exportación a Odoo.
        Devuelve True si tiene éxito, False si falla la conexión o la exportación.
        """
        logging.info("Iniciando nuevo ciclo de escaneo...")
        if not self.exportador.test_connection_with_odoo():
            logging.error("La prueba de conexión inicial falló.")
            return False
        
        self.exportador.check_installed_modules()
        
        try:
            logging.debug("Creando instancia de GestorTI.")
            gestor = GestorTI(
                software_installed=self.exportador.software_module_installed,
                network_installed=self.exportador.network_module_installed
            )
            logging.debug("Recolectando todos los datos...")
            datos_completos = gestor.recolectar_todo()
            logging.debug("Exportando activo completo a Odoo...")
            self.exportador.exportar_activo_completo(datos_completos)
            logging.info("Ciclo de escaneo y exportación completado exitosamente.")
            return True
        except Exception as e:
            logging.error(f"Ocurrió un error durante el proceso de escaneo/exportación: {e}", exc_info=True)
            return False

    def iniciar(self):
        """
        Bucle principal del agente con la nueva lógica de reintento y recolección offline.
        """
        logging.info("Iniciando listener de agente en segundo plano...")
        self.listener.start()
        
        logging.info("Agente de escaneo iniciado. Primer escaneo en breve...")
        while not self.restart_event.is_set():
            
            # --- LÓGICA DE CONEXIÓN Y RECOLECCIÓN OFFLINE ---
            
            logging.info("Primer intento de conexión...")
            exitoso = self._ejecutar_ciclo()
            
            intervalo_espera = self.intervalo_principal_seg
            
            if not exitoso:
                # Si el primer intento falla, esperamos 5 minutos
                logging.warning(f"El ciclo falló. Se reintentará en {self.intervalo_reintento_seg / 60} minutos.")
                
                # Esperamos el tiempo de reintento, pero atentos a la señal de reinicio
                if self.restart_event.wait(timeout=self.intervalo_reintento_seg):
                    break # Salir si se pide reiniciar durante la espera de reintento
                
                logging.info("Segundo intento de conexión (reintento)...")
                exitoso = self._ejecutar_ciclo()
                
                if not exitoso:
                    # Si el segundo intento también falla, ejecutamos la recolección offline
                    logging.error("El reintento también falló. Procediendo con la recolección de datos offline.")
                    recolectar_todo_y_crear_json_al_fallar_la_conexion_con_odoo()
            
            # --- FIN LÓGICA DE CONEXIÓN Y RECOLECCIÓN OFFLINE ---
            
            logging.info(f"Próximo escaneo en {intervalo_espera / 60} minutos.")
            # Esperamos el tiempo principal (30 minutos) antes del siguiente ciclo, atentos a la señal de reinicio
            if self.restart_event.wait(timeout=intervalo_espera):
                break # Salir si se pide reiniciar durante la espera principal

        # Si salimos del bucle, es porque se pidió un reinicio.
        logging.warning("Señal de reinicio recibida. Deteniendo el agente...")
        self.listener.stop()