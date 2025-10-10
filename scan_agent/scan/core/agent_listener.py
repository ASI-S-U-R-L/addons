# -*- coding: utf-8 -*-

import threading
import logging
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from typing import Optional, cast

_logger = logging.getLogger(__name__)

# --- Subclase para manejar el evento de reinicio ---
class RestartableHTTPServer(HTTPServer):
    """Un HTTPServer que conoce el evento de reinicio."""
    def __init__(self, server_address, RequestHandlerClass, restart_event: Optional[threading.Event] = None):
        super().__init__(server_address, RequestHandlerClass)
        self.restart_event = restart_event

class AgentRequestHandler(BaseHTTPRequestHandler):
    """
    Manejador de peticiones HTTP para el agente.
    Responde a peticiones de estado.
    Soporta GET /status y POST /restart.
    """
    
    def _send_response(self, code, data):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_GET(self):
        if self.path == '/status':
            try:
                response_data = {
                    "status": "active",
                    "hostname": socket.gethostname()
                }
                self._send_response(200, response_data)
                _logger.info(f"Petición (GET /status) de estado recibida desde {self.client_address[0]}. Respuesta: OK")
            except Exception as e:
                _logger.error(f"Error al procesar la petición de estado: {e}", exc_info=True)
                self._send_response(500, {"status": "error", "message": str(e)})
        else:
            self._send_response(404, {"status": "error", "message": "Endpoint no encontrado"})
    
    def do_POST(self):
        if self.path == '/restart':
            try:
                _logger.warning(f"Petición de REINICIO recibida desde {self.client_address[0]}.")
                self._send_response(200, {"status": "restarting", "message": "Señal de reinicio recibida."})
                
                server = cast(RestartableHTTPServer, self.server)
                
                # Activa el evento para que el hilo principal del agente se detenga
                if server and server.restart_event:
                    server.restart_event.set()
            
            except Exception as e:
                self._send_response(500, {"status": "error", "message": str(e)})
        else:
            self._send_response(404, {"status": "error", "message": "Endpoint no encontrado"})
    
    def log_message(self, format, *args):
        # Silenciamos los logs por defecto de HTTPServer para no llenar la consola
        return


class AgentListener:
    """
    Servidor HTTP ligero que se ejecuta en un hilo para escuchar
    peticiones de estado desde Odoo.
    """
    def __init__(self, port=9191, restart_event: Optional[threading.Event] = None):
        self.port = port
        self.handler = AgentRequestHandler
        self.server = None
        self.thread = None
        self.restart_event = restart_event

    def start(self):
        """Inicia el servidor en un hilo daemon."""
        try:
            self.server = RestartableHTTPServer(('', self.port), self.handler, restart_event=self.restart_event)

            # Hace que el evento de reinicio sea accesible desde el manejador.
            if self.restart_event:
                self.server.restart_event = self.restart_event

            self.thread = threading.Thread(target=self.server.serve_forever)
            self.thread.daemon = True  # Permite que el programa principal termine aunque el hilo esté activo
            self.thread.start()
            _logger.info(f"✅ Agente escuchando en el puerto {self.port} para peticiones de estado.")
        except OSError as e:
            _logger.critical(f"❌ No se pudo iniciar el listener en el puerto {self.port}. ¿El puerto ya está en uso? Error: {e}")
        except Exception as e:
            _logger.critical(f"❌ Error desconocido al iniciar el listener: {e}", exc_info=True)

    def stop(self):
        """Detiene el servidor (para un cierre limpio si fuera necesario)."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            _logger.info("El listener del agente se ha detenido.")