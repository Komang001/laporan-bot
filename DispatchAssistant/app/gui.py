import sys
import os

import customtkinter as ctk
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.controller import DispatchController
from config.settings import INSERA_GROUP_ID, CHROME_PORTS


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

        self.controllers = {}

        self.title(
            "Industrial Programmer - DispatchAssistant"
        )

        self.geometry("960x700")

        self.resizable(False, False)

        self.create_header()
        self.create_feature_sections()
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
            text="Industrial Programmer Automation System - Multi Chrome",
        )

        subtitle.pack()

    # =================================================
    # Feature Sections (per-fitur: status + tombol)
    # =================================================

    def create_feature_sections(self):

        features = [
            {
                "key": "to_insera",
                "label": "TO MO-INSERA",
                "color": "#7C3AED",
                "hover": "#6D28D9",
                "port_key": "TO",
            },
            {
                "key": "to_bima",
                "label": "TO MO-BIMA",
                "color": "#0EA5E9",
                "hover": "#0284C7",
                "port_key": "TO",
            },
            {
                "key": "canclwork",
                "label": "CANCLWORK WO",
                "color": "#F97316",
                "hover": "#EA580C",
                "port_key": "CANCLWORK",
            },
            {
                "key": "dispatch",
                "label": "DISPATCH",
                "color": "#10B981",
                "hover": "#059669",
                "port_key": "DISPATCH",
            },
            {
                "key": "gamas_relations",
                "label": "GAMAS RELATIONS",
                "color": "#EC4899",
                "hover": "#DB2777",
                "port_key": "GAMAS",
            },
        ]

        for feat in features:
            self._create_feature_row(feat)

    def _create_feature_row(self, feat):

        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=20, pady=5)

        key = feat["key"]
        port = CHROME_PORTS.get(feat["port_key"], 9222)

        label = ctk.CTkLabel(
            frame,
            text=f"{feat['label']}",
            width=200,
            font=("Arial", 14, "bold"),
        )
        label.pack(side="left", padx=10)

        start_btn = ctk.CTkButton(
            frame,
            text=f"START",
            width=100,
            fg_color=feat["color"],
            hover_color=feat["hover"],
            command=lambda k=key, f=feat: self._start_feature(k, f),
        )
        start_btn.pack(side="left", padx=5)

        stop_btn = ctk.CTkButton(
            frame,
            text="STOP",
            width=80,
            fg_color="red",
            command=lambda k=key: self._stop_feature(k),
        )
        stop_btn.pack(side="left", padx=5)

        status_label = ctk.CTkLabel(
            frame,
            text=f"READY (port {port})",
            text_color="#22C55E",
            width=200,
        )
        status_label.pack(side="left", padx=10)

        setattr(self, f"{key}_btn", start_btn)
        setattr(self, f"{key}_status", status_label)

    # =================================================
    # Start / Stop Feature
    # =================================================

    def _start_feature(self, key, feat):

        if key in self.controllers and self.controllers[key].running:
            self.write_log(f"[{key}] Already running!")
            return

        port = CHROME_PORTS.get(feat["port_key"], 9222)

        ctrl = DispatchController(gui=self, cdp_port=port)
        ctrl.on_complete = lambda k=key: self._on_feature_complete(k)
        self.controllers[key] = ctrl

        self._update_feature_status(key, "STARTING", "#EAB308")
        getattr(self, f"{key}_btn").configure(state="disabled")

        if key == "to_insera":
            ctrl.start_auto(group_label="MO-INSERA", group_id=INSERA_GROUP_ID)
        elif key == "to_bima":
            ctrl.start_auto(group_label="MO-BIMA", group_id=None)
        elif key == "canclwork":
            ctrl.start_canclwork()
        elif key == "dispatch":
            ctrl.start_dispatch()
        elif key == "gamas_relations":
            ctrl.start_gamas_relations()

    def _stop_feature(self, key):

        if key in self.controllers:
            self.controllers[key].stop()
            self._update_feature_status(key, "STOPPING", "#EF4444")
        else:
            self.write_log(f"[{key}] Not running.")

    def _on_feature_complete(self, key):

        self.after(0, lambda: self._finish_feature(key))

    def _finish_feature(self, key):

        self._update_feature_status(key, "READY", "#22C55E")
        getattr(self, f"{key}_btn").configure(state="normal")

        if key in self.controllers:
            del self.controllers[key]

    def _update_feature_status(self, key, status, color):

        lbl = getattr(self, f"{key}_status", None)
        if lbl:
            self.after(0, lambda: lbl.configure(
                text=f"{status}",
                text_color=color,
            ))

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
        self.write_log("=== MULTI-CHROME MODE ===")
        self.write_log("Setiap fitur jalan di Chrome berbeda!")
        self.write_log("Pastikan semua Chrome CDP sudah jalan:")
        self.write_log(f"  TO        -> port {CHROME_PORTS['TO']}")
        self.write_log(f"  CANCLWORK -> port {CHROME_PORTS['CANCLWORK']}")
        self.write_log(f"  DISPATCH  -> port {CHROME_PORTS['DISPATCH']}")
        self.write_log(f"  GAMAS     -> port {CHROME_PORTS['GAMAS']}")
        self.write_log("==========================")

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

        pass


# =====================================================
# Run
# =====================================================

if __name__ == "__main__":

    app = DispatchAssistantGUI()

    app.mainloop()
