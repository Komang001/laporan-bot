import sys
import os
import threading

import customtkinter as ctk
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.controller import DispatchController
from config.settings import INSERA_GROUP_ID


# =====================================================
# Appearance
# =====================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# =====================================================
# Main GUI Class
# =====================================================

class DispatchAssistantGUI(ctk.CTk):

    def __init__(self):

        super().__init__()

        self.controller = DispatchController(self)

        self.controller.on_complete = self._on_dispatch_complete

        self.title(
            "Industrial Programmer - DispatchAssistant"
        )

        self.geometry("960x650")

        self.resizable(False, False)

        self.running = False

        self.create_header()
        self.create_control_section()
        self.create_log_section()

    # =================================================
    # Header
    # =================================================

    def create_header(self):

        frame = ctk.CTkFrame(self)

        frame.pack(fill="x", padx=20, pady=20)

        title = ctk.CTkLabel(
            frame,
            text="DispatchAssistant",
            font=("Arial", 28, "bold"),
        )

        title.pack(pady=10)

        subtitle = ctk.CTkLabel(
            frame,
            text="Industrial Programmer Automation System",
        )

        subtitle.pack()

    # =================================================
    # Control Section
    # =================================================

    def create_control_section(self):

        frame = ctk.CTkFrame(self)

        frame.pack(fill="x", padx=20, pady=10)

        self.connect_button = ctk.CTkButton(
            frame,
            text="CONNECT BROWSER",
            width=180,
            fg_color="#2563EB",
            command=self.connect_browser,
        )

        self.connect_button.pack(
            side="left",
            padx=10,
            pady=15,
        )

        self.to_insera_button = ctk.CTkButton(
            frame,
            text="TO MO-INSERA",
            width=180,
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            command=self.start_to_insera,
        )

        self.to_insera_button.pack(
            side="left",
            padx=10,
        )

        self.to_bima_button = ctk.CTkButton(
            frame,
            text="TO MO-BIMA",
            width=180,
            fg_color="#0EA5E9",
            hover_color="#0284C7",
            command=self.start_to_bima,
        )

        self.to_bima_button.pack(
            side="left",
            padx=10,
        )

        self.stop_button = ctk.CTkButton(
            frame,
            text="STOP",
            width=180,
            fg_color="red",
            command=self.stop,
        )

        self.stop_button.pack(
            side="left",
            padx=10,
        )

        self.status_label = ctk.CTkLabel(
            frame,
            text="Status : READY",
            text_color="#22C55E",
        )

        self.status_label.pack(
            side="right",
            padx=20,
        )

    # =================================================
    # Log Section
    # =================================================

    def create_log_section(self):

        frame = ctk.CTkFrame(self)

        frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=10,
        )

        ctk.CTkLabel(
            frame,
            text="Activity Log",
        ).pack(
            anchor="w",
            padx=10,
            pady=5,
        )

        self.log_box = ctk.CTkTextbox(
            frame,
            width=880,
            height=250,
        )

        self.log_box.pack(
            padx=10,
            pady=10,
            fill="both",
            expand=True,
        )

        self.write_log("Application initialized...")
        self.write_log("")
        self.write_log("=== CARA PAKAI ===")
        self.write_log("1. Jalankan: start_browser.bat")
        self.write_log("2. Login SYGAP di Chrome")
        self.write_log("3. Klik CONNECT BROWSER")
        self.write_log("4. Klik TO MO-INSERA atau TO MO-BIMA")
        self.write_log("=================")

    # =================================================
    # Functions
    # =================================================

    def write_log(self, message):

        timestamp = datetime.now().strftime("%H:%M:%S")

        self.log_box.insert(
            "end",
            f"[{timestamp}] {message}\n",
        )

        self.log_box.see("end")

    def update_status(self, status):

        colors = {
            "READY": "#22C55E",
            "STARTING": "#EAB308",
            "CONNECTING": "#EAB308",
            "SCANNING": "#3B82F6",
            "READING": "#EAB308",
            "TO": "#EAB308",
            "WAITING IN_PROGRESS": "#EAB308",
            "CONNECTED": "#22C55E",
            "STOPPED": "#EF4444",
            "ERROR": "#EF4444",
            "DISCONNECTED": "#6B7280",
        }

        color = colors.get(status, "#6B7280")

        self.status_label.configure(
            text=f"Status : {status}",
            text_color=color,
        )

    def connect_browser(self):

        self.connect_button.configure(state="disabled")

        self.update_status("CHECKING")

        self.controller.connect_browser()

        self.connect_button.configure(state="normal")

    def start_to_insera(self):

        if self.running:
            self.write_log("Assistant already running.")
            return

        self.running = True
        self.to_insera_button.configure(state="disabled")
        self.to_bima_button.configure(state="disabled")
        self.controller.start_auto(group_label="MO-INSERA", group_id=INSERA_GROUP_ID)

    def start_to_bima(self):

        if self.running:
            self.write_log("Assistant already running.")
            return

        self.running = True
        self.to_insera_button.configure(state="disabled")
        self.to_bima_button.configure(state="disabled")
        self.controller.start_auto(group_label="MO-BIMA", group_id=None)

    def stop(self):

        self.running = False

        self.to_insera_button.configure(state="normal")
        self.to_bima_button.configure(state="normal")

        self.controller.stop()

    def _on_dispatch_complete(self):

        self.running = False

        self.after(0, lambda: self.to_insera_button.configure(state="normal"))

        self.after(0, lambda: self.to_bima_button.configure(state="normal"))


# =====================================================
# Run
# =====================================================

if __name__ == "__main__":

    app = DispatchAssistantGUI()

    app.mainloop()
