import sys
import os

import customtkinter as ctk
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.controller import DispatchController
from config.settings import INSERA_GROUP_ID, CHROME_PORTS, TELEGRAM_BOT_TOKEN


# =====================================================
# Appearance
# =====================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

FEATURES = [
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

# Channel log dari tiap fitur -> tab tujuan
CHANNEL_TAB_MAP = {
    "to_insera": "TO",
    "to_bima": "TO",
    "canclwork": "CANCLWORK",
    "dispatch": "DISPATCH",
    "gamas_relations": "GAMAS",
}

LOG_TABS = ["SEMUA", "TO", "CANCLWORK", "DISPATCH", "GAMAS"]

STATUS_COLORS = {
    "READY": "#22C55E",
    "STARTING": "#EAB308",
    "LAUNCHING": "#EAB308",
    "CONNECTING": "#EAB308",
    "SCANNING": "#3B82F6",
    "RUNNING": "#3B82F6",
    "WAITING": "#6B7280",
    "STOPPING": "#F97316",
    "STOPPED": "#EF4444",
    "ERROR": "#EF4444",
}


# =====================================================
# Adapter: meneruskan log controller ke channel fitur
# =====================================================

class _FeatureGUIAdapter:

    def __init__(self, gui, key):
        self.gui = gui
        self.key = key

    def write_log(self, message):
        self.gui.write_log(message, channel=self.key)

    def update_status(self, status):
        self.gui._update_feature_status_from_controller(self.key, status)


# =====================================================
# Main GUI Class
# =====================================================

class DispatchAssistantGUI(ctk.CTk):

    def __init__(self):

        super().__init__()

        self.controllers = {}
        self.log_boxes = {}

        self.title("Industrial Programmer - DispatchAssistant")

        self.geometry("1040x780")

        self.minsize(960, 700)

        self.resizable(True, True)

        self.create_header()
        self.create_feature_sections()
        self.create_log_section()
        self._start_telegram_bot()

    # =================================================
    # Header
    # =================================================

    def create_header(self):

        frame = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color="#1C1C2E",
            border_width=1,
            border_color="#2A2A3E",
        )

        frame.pack(fill="x", padx=20, pady=(20, 10))

        inner = ctk.CTkFrame(frame, fg_color="transparent")

        inner.pack(pady=(16, 12))

        title = ctk.CTkLabel(
            inner,
            text="DispatchAssistant",
            font=("Arial", 26, "bold"),
            text_color="#FFFFFF",
        )

        title.pack()

        subtitle = ctk.CTkLabel(
            inner,
            text="Industrial Programmer Automation System - Multi Chrome",
            font=("Arial", 12),
            text_color="#9CA3AF",
        )

        subtitle.pack(pady=(2, 0))

        divider = ctk.CTkFrame(
            frame,
            height=3,
            fg_color="#7C3AED",
            corner_radius=0,
        )

        divider.pack(fill="x", side="bottom")

    # =================================================
    # Feature Cards (2 kolom)
    # =================================================

    def create_feature_sections(self):

        self.features_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.features_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.features_frame.grid_columnconfigure(0, weight=1)
        self.features_frame.grid_columnconfigure(1, weight=1)

        for i, feat in enumerate(FEATURES):
            card = self._create_feature_card(feat)

            if feat["key"] == "gamas_relations":
                row, col, span = 2, 0, 2
            else:
                row, col, span = i // 2, i % 2, 1

            card.grid(
                row=row,
                column=col,
                columnspan=span,
                sticky="ew",
                padx=6,
                pady=6,
            )

    def _create_feature_card(self, feat):

        key = feat["key"]
        port = CHROME_PORTS.get(feat["port_key"], 9222)

        card = ctk.CTkFrame(
            self.features_frame,
            corner_radius=10,
            border_width=2,
            border_color=feat["color"],
            fg_color="#17171F",
        )

        top = ctk.CTkFrame(card, fg_color="transparent")

        top.pack(fill="x", padx=14, pady=(10, 4))

        name = ctk.CTkLabel(
            top,
            text=feat["label"],
            font=("Arial", 15, "bold"),
            text_color=feat["color"],
        )

        name.pack(side="left")

        status_label = ctk.CTkLabel(
            top,
            text="\u25CF READY",
            font=("Arial", 12, "bold"),
            text_color="#22C55E",
        )

        status_label.pack(side="right")

        bottom = ctk.CTkFrame(card, fg_color="transparent")

        bottom.pack(fill="x", padx=14, pady=(0, 10))

        port_label = ctk.CTkLabel(
            bottom,
            text=f"port {port}",
            font=("Consolas", 11),
            text_color="#9CA3AF",
        )

        port_label.pack(side="left")

        stop_btn = ctk.CTkButton(
            bottom,
            text="STOP",
            width=72,
            height=28,
            fg_color="#EF4444",
            hover_color="#DC2626",
            font=("Arial", 12, "bold"),
            command=lambda k=key: self._stop_feature(k),
        )

        stop_btn.pack(side="right", padx=(6, 0))

        start_btn = ctk.CTkButton(
            bottom,
            text="START",
            width=80,
            height=28,
            fg_color=feat["color"],
            hover_color=feat["hover"],
            font=("Arial", 12, "bold"),
            command=lambda k=key, f=feat: self._start_feature(k, f),
        )

        start_btn.pack(side="right")

        setattr(self, f"{key}_btn", start_btn)
        setattr(self, f"{key}_status", status_label)

        return card

    # =================================================
    # Start / Stop Feature
    # =================================================

    def _start_feature(self, key, feat):

        if key in self.controllers and self.controllers[key].running:
            self.write_log(f"[{key}] Already running!")
            return

        port = CHROME_PORTS.get(feat["port_key"], 9222)

        ctrl = DispatchController(
            gui=self._make_feature_adapter(key),
            cdp_port=port,
        )

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
                text=f"\u25CF {status}",
                text_color=color,
            ))

    def _update_feature_status_from_controller(self, key, status):

        status = str(status).upper()
        color = STATUS_COLORS.get(status, "#22C55E")
        self._update_feature_status(key, status, color)

    def _make_feature_adapter(self, key):

        return _FeatureGUIAdapter(self, key)

    # =================================================
    # Log Section (tab per fitur)
    # =================================================

    def create_log_section(self):

        frame = ctk.CTkFrame(self)

        frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 20),
        )

        header = ctk.CTkFrame(frame, fg_color="transparent")

        header.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            header,
            text="Activity Log",
            font=("Arial", 14, "bold"),
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="Clear",
            width=70,
            height=26,
            fg_color="#3B3B4F",
            hover_color="#4B4B63",
            command=self._clear_log,
        ).pack(side="right")

        self.tabs = ctk.CTkTabview(frame)

        self.tabs.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        for name in LOG_TABS:
            tab = self.tabs.add(name)
            box = ctk.CTkTextbox(
                tab,
                font=("Consolas", 11),
                wrap="word",
            )
            box.pack(fill="both", expand=True, padx=6, pady=6)
            self.log_boxes[name] = box
            self._setup_tags(box)

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

    def _setup_tags(self, box):

        try:
            box.tag_config("err", foreground="#F87171")
            box.tag_config("ok", foreground="#4ADE80")
            box.tag_config("warn", foreground="#FBBF24")
            box.tag_config("dim", foreground="#9CA3AF")
        except Exception:
            try:
                box._textbox.tag_config("err", foreground="#F87171")
                box._textbox.tag_config("ok", foreground="#4ADE80")
                box._textbox.tag_config("warn", foreground="#FBBF24")
                box._textbox.tag_config("dim", foreground="#9CA3AF")
            except Exception:
                pass

    def _log_tag(self, message):

        up = message.upper()

        if any(k in up for k in ("ERROR", "FAILED", "GAGAL")):
            return "err"
        if any(k in up for k in ("SUCCESS", "SUKSES", "SELESAI", "CONFIRMED", "COMPLETED", "OK")):
            return "ok"
        if any(k in up for k in ("WARNING", "SAFETY")):
            return "warn"
        if any(k in up for k in ("SKIP", "WAITING", "MENUNGGU", "NO TICKET", "NO ACTIONABLE", "NOT FOUND")):
            return "dim"
        return None

    def _append_log(self, box, line, message):

        tag = self._log_tag(message)

        if tag:
            box.insert("end", line + "\n", (tag,))
        else:
            box.insert("end", line + "\n")

        box.see("end")

    def _clear_log(self):

        try:
            name = self.tabs.get()
        except Exception:
            name = "SEMUA"

        box = self.log_boxes.get(name)
        if box:
            box.delete("1.0", "end")

    # =================================================
    # Functions
    # =================================================

    def write_log(self, message, channel="all"):

        line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"

        targets = ["SEMUA"]

        tab_name = CHANNEL_TAB_MAP.get(channel)
        if tab_name and tab_name not in targets:
            targets.append(tab_name)

        for name in targets:
            box = self.log_boxes.get(name)
            if box is None:
                continue
            self.after(0, lambda b=box, s=line, m=message: self._append_log(b, s, m))

    def update_status(self, status):

        pass

    # =================================================
    # Telegram Bot (Remote Control)
    # =================================================

    def _start_telegram_bot(self):
        if not TELEGRAM_BOT_TOKEN:
            return
        try:
            from app.telegram_bot import TelegramRemote
            self.telegram = TelegramRemote(gui=self)
            self.telegram.start()
            self.write_log("Telegram bot started - remote control active.")
        except Exception as e:
            self.write_log(f"Telegram bot error: {e}")


# =====================================================
# Run
# =====================================================

if __name__ == "__main__":

    app = DispatchAssistantGUI()

    app.mainloop()
