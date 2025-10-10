# -*- coding: utf-8 -*-
import subprocess
import getpass
import logging
import sys
from tkinter import simpledialog, messagebox
import tkinter as tk

_logger = logging.getLogger(__name__)

class SudoPasswordManager:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SudoPasswordManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Evita la reinicialización en un singleton
        if not hasattr(self, 'is_initialized'):
            self.sudo_password = None
            self.gui_mode = False
            self.is_initialized = True
            # Para evitar bucles infinitos si la contraseña es siempre incorrecta
            self._prompt_retries = 0
            self._max_retries = 3

    def set_gui_mode(self, is_gui):
        """Informa al gestor si debe usar la GUI para pedir la contraseña."""
        self.gui_mode = is_gui

    def _prompt_password(self):
        """Solicita la contraseña al usuario, ya sea por GUI o por texto."""
        if self._prompt_retries >= self._max_retries:
            _logger.error("Se ha superado el número máximo de intentos para la contraseña de sudo.")
            raise PermissionError("Demasiados intentos de contraseña de sudo fallidos.")

        self._prompt_retries += 1
        password = None
        
        if self.gui_mode:
            try:
                # Ocultar la ventana principal de tkinter si existe
                root = tk.Tk()
                root.withdraw()
                password = simpledialog.askstring(
                    "Permiso de Administrador Requerido",
                    "Por favor, introduce tu contraseña de sudo para escanear el hardware:",
                    show='*'
                )
                root.destroy()
            except Exception as e:
                _logger.error(f"No se pudo mostrar el diálogo de contraseña GUI: {e}. Volviendo a modo texto.")
                password = getpass.getpass("Sudo password: ")
        else:
            password = getpass.getpass("Se requiere permiso de administrador (sudo). Por favor, introduce tu contraseña: ")
            
        return password

    def run(self, command, timeout=10):
        """
        Ejecuta un comando con sudo, pidiendo la contraseña si es necesario.
        """
        if self.sudo_password is None:
            self.sudo_password = self._prompt_password()
            if not self.sudo_password:
                _logger.error("No se proporcionó contraseña de sudo. El comando no se puede ejecutar.")
                raise PermissionError("Contraseña de sudo no proporcionada.")

        # Usamos `sudo -S` que lee la contraseña desde stdin
        full_command = f"sudo -S {command}"
        
        try:
            process = subprocess.Popen(
                full_command.split(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            
            stdout, stderr = process.communicate(input=self.sudo_password + '\n', timeout=timeout)

            if process.returncode != 0:
                # Comprobar si el error es por contraseña incorrecta
                if "incorrect password attempt" in stderr or "contraseña incorrecta" in stderr.lower():
                    _logger.warning("La contraseña de sudo guardada es incorrecta. Se solicitará de nuevo.")
                    self.sudo_password = None # Forzar que se pida de nuevo
                    # Volver a intentar recursivamente (con control de reintentos)
                    return self.run(command, timeout)
                else:
                    _logger.error(f"Error ejecutando comando sudo '{command}': {stderr.strip()}")
                    raise subprocess.CalledProcessError(process.returncode, command, output=stdout, stderr=stderr)
            
            # Si el comando fue exitoso, reseteamos el contador de reintentos
            self._prompt_retries = 0
            return stdout

        except subprocess.TimeoutExpired:
            _logger.error(f"El comando sudo '{command}' excedió el tiempo de espera.")
            raise
        except Exception as e:
            _logger.error(f"Excepción al ejecutar comando sudo '{command}': {e}")
            raise

# Instancia Singleton para ser usada en todo el agente
sudo_manager = SudoPasswordManager()