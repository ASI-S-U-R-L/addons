# RUTA: scan_agent/configurador_gui.py

import tkinter as tk
from tkinter import ttk, messagebox # ¡NUEVO! Importamos ttk
import keyring
import requests
import time
import subprocess
import sys
import logging
from pathlib import Path

# Importamos la lógica necesaria
try:
    from configurador import LOCK_FILE, remove_lock
    from scan.core.deployment import get_install_path
except ImportError:
    LOCK_FILE = Path.home() / '.sgichs_agent.lock'
    get_install_path = lambda: Path.home()
    remove_lock = lambda: None

_logger = logging.getLogger(__name__)
KEYRING_SERVICE_NAME = "sgich-scan-agent"

class ConfiguratorApp(tk.Tk):
    """
    Interfaz gráfica mejorada para la configuración del agente.
    """
    def __init__(self, initial_config=None):
        super().__init__()

        # --- Mejoras Visuales ---
        self.title("Configuración del Agente SGICH")
        self.geometry("450x360")
        self.resizable(False, False)
        
        # Estilo ttk
        style = ttk.Style(self)
        style.theme_use('clam') # Tema moderno y limpio

        # Icono de la ventana
        try:
            # Asegúrate de tener un archivo 'agent.ico' en la carpeta scan_agent
            icon_path = Path(__file__).parent / "agent.ico"
            if icon_path.exists():
                self.iconbitmap(icon_path)
        except Exception:
            _logger.warning("No se pudo cargar 'agent.ico'. Asegúrate de que el archivo exista.")

        self.config_data = initial_config if initial_config else {}
        self.saved = False

        # --- Contenedor Principal con Padding ---
        main_frame = ttk.Frame(self, padding="20 20 20 20")
        main_frame.pack(expand=True, fill='both')

        # --- Título ---
        ttk.Label(main_frame, text="Conexión con Odoo", font=("Helvetica", 14, "bold")).pack(pady=(0, 15))

        # --- Frame para los campos ---
        fields_frame = ttk.Frame(main_frame)
        fields_frame.pack(fill='x')
        
        # Configuración de las columnas del grid
        fields_frame.columnconfigure(1, weight=1)

        # --- Widgets (usando ttk) ---
        ttk.Label(fields_frame, text="Nº de Inventario PC:").grid(row=0, column=0, padx=5, pady=8, sticky="w")
        self.inventory_entry = ttk.Entry(fields_frame, width=40)
        self.inventory_entry.grid(row=0, column=1, padx=5, pady=8, sticky="ew")

        ttk.Label(fields_frame, text="URL de Odoo:").grid(row=1, column=0, padx=5, pady=8, sticky="w")
        self.url_entry = ttk.Entry(fields_frame, width=40)
        self.url_entry.grid(row=1, column=1, padx=5, pady=8, sticky="ew")

        ttk.Label(fields_frame, text="Base de Datos:").grid(row=2, column=0, padx=5, pady=8, sticky="w")
        self.db_entry = ttk.Entry(fields_frame, width=40)
        self.db_entry.grid(row=2, column=1, padx=5, pady=8, sticky="ew")

        ttk.Label(fields_frame, text="Usuario:").grid(row=3, column=0, padx=5, pady=8, sticky="w")
        self.user_entry = ttk.Entry(fields_frame, width=40)
        self.user_entry.grid(row=3, column=1, padx=5, pady=8, sticky="ew")

        ttk.Label(fields_frame, text="Contraseña / API Key:").grid(row=4, column=0, padx=5, pady=8, sticky="w")
        self.pass_entry = ttk.Entry(fields_frame, show="*", width=40)
        self.pass_entry.grid(row=4, column=1, padx=5, pady=8, sticky="ew")

        # --- Botones ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(20, 10))
        
        style.configure('Save.TButton', foreground='white', background='#007bff')
        save_button = ttk.Button(button_frame, text="Guardar y Continuar", command=self.save_config, style='Save.TButton')
        save_button.pack(side="left", padx=10)

        cancel_button = ttk.Button(button_frame, text="Cancelar", command=self.cancel)
        cancel_button.pack(side="left", padx=10)
        
        self.load_initial_config()

    # --- El resto de los métodos (load_initial_config, save_config, etc.) no cambian ---
    def load_initial_config(self):
        self.inventory_entry.insert(0, self.config_data.get("inventory_number", "00000"))
        odoo_config = self.config_data.get("odoo_config", {})
        username = odoo_config.get("username", "")
        self.url_entry.insert(0, odoo_config.get("url", "http://localhost:8069"))
        self.db_entry.insert(0, odoo_config.get("db", ""))
        self.user_entry.insert(0, username)
        if username:
            password = keyring.get_password(KEYRING_SERVICE_NAME, username)
            if password:
                self.pass_entry.insert(0, password)

    def save_config(self):
        inventory_number = self.inventory_entry.get().strip()
        url = self.url_entry.get().strip()
        db = self.db_entry.get().strip()
        user = self.user_entry.get().strip()
        password = self.pass_entry.get().strip()
        if not all([inventory_number, url, db, user, password]):
            messagebox.showerror("Error", "Todos los campos son obligatorios.")
            return
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, user, password)
            messagebox.showinfo("Éxito", "La contraseña ha sido guardada de forma segura.")
        except Exception as e:
            messagebox.showerror("Error de Keyring", f"No se pudo guardar la contraseña:\n{e}")
            return
        self.config_data = {
            "intervalo_principal_min": self.config_data.get("intervalo_principal_min", 60),
            "intervalo_reintento_min": self.config_data.get("intervalo_reintento_min", 5),
            "listener_port": self.config_data.get("listener_port", 9191),
            "inventory_number": inventory_number,
            "odoo_config": {"url": url, "db": db, "username": user}
        }
        self.saved = True
        if LOCK_FILE.exists():
            answer = messagebox.askyesno(
                "Aplicar Cambios",
                "Configuración guardada.\n\n¿Desea reiniciar el agente ahora para aplicar los cambios?\n\n(Si elige 'No', los cambios se aplicarán en el próximo inicio del sistema)."
            )
            if answer:
                self.restart_agent()
        self.destroy()

    def restart_agent(self):
        _logger.info("Intentando reiniciar el agente...")
        listener_port = self.config_data.get("listener_port", 9191)
        restart_url = f"http://localhost:{listener_port}/restart"
        try:
            requests.post(restart_url, timeout=5)
            messagebox.showinfo("Reinicio en Progreso", "El agente anterior se está deteniendo. Se iniciará uno nuevo en breve.")
        except requests.exceptions.RequestException as e:
            _logger.error(f"No se pudo conectar con el agente en {restart_url}. Error: {e}")
            messagebox.showwarning("Advertencia", "No se pudo conectar con el agente. Es posible que deba reiniciarse manualmente.")
        time.sleep(2)
        remove_lock()
        try:
            install_dir = get_install_path()
            executable_name = Path(sys.executable).name
            executable_path = install_dir / executable_name
            if not executable_path.exists():
                messagebox.showerror("Error", "No se pudo encontrar el agente instalado para relanzarlo.")
                return
            subprocess.Popen([str(executable_path)])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo relanzar el agente:\n{e}")
            
    def cancel(self):
        self.saved = False
        self.destroy()