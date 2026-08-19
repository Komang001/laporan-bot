import sys
import os

import customtkinter as ctk
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.controller import DispatchController
from config.settings import (
    INSERA_GROUP_ID,
    CHROME_PORTS,
    TELEGRAM_BOT_TOKEN,
    REPORT_CDP_PORT,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE_DIR, "assets", "logo.png")


# =====================================================
# Appearance & Clean Light Theme Palette
# =====================================================

# Muat tema dari saved settings (jika ada)
def _load_saved_theme():
    import json
    _settings_path = os.path.join(BASE_DIR, "config", "user_settings.json")
    try:
        if os.path.exists(_settings_path):
            with open(_settings_path, "r", encoding="utf-8") as f:
                return json.load(f).get("theme", "light")
    except Exception:
        pass
    return "light"

ctk.set_appearance_mode(_load_saved_theme())
ctk.set_default_color_theme("blue")

# Theme Palette (Crisp Clean Modern Light)
BG_MAIN = "#F1F5F9"          # Soft slate-100 workspace background
BG_HEADER = "#FFFFFF"        # Elevated white header card
BG_CARD = "#FFFFFF"          # Elevated white feature cards
BG_CARD_HOVER = "#F8FAFC"    # Soft hover state
BG_INPUT = "#F8FAFC"         # Soft slate-50 for inputs and chips
BG_TERMINAL = "#0F172A"      # High-contrast slate-900 terminal

BORDER_SUBTLE = "#E2E8F0"    # Crisp slate-200 1px borders
BORDER_CARD = "#E2E8F0"      # Card contour border
BORDER_FOCUS = "#3B82F6"     # Focused / active border

# Load saved accent color (if any)
def _load_saved_accent():
    import json
    _settings_path = os.path.join(BASE_DIR, "config", "user_settings.json")
    try:
        if os.path.exists(_settings_path):
            with open(_settings_path, "r", encoding="utf-8") as f:
                return json.load(f).get("accent_color", "#DC2626")
    except Exception:
        pass
    return "#DC2626"

def _darken_hex(hex_color, factor=0.8):
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r, g, b = int(r * factor), int(g * factor), int(b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"

RED_MAIN = _load_saved_accent()             # Vibrant accent (default: Telkom Red)
RED_DARK = _darken_hex(RED_MAIN, 0.6)       # Dark accent
RED_HOVER = _darken_hex(RED_MAIN, 0.82)     # Hover accent
RED_LIGHT = "#FEF2F2"        # Pastel Red Background

TEXT_MAIN = "#0F172A"        # Deep slate-900 for sharp primary text
TEXT_SECONDARY = "#475569"   # Slate-600 for descriptions
TEXT_DIM = "#64748B"         # Slate-500 for secondary info
WHITE = "#FFFFFF"

FONT_UI = "Segoe UI"
FONT_MONO = "Consolas"

FEATURES = [
    {
        "key": "to_insera",
        "label": "TO MO-INSERA",
        "icon": "\U0001F916",
        "desc": "Take Ownership tiket group MO-INSERA",
        "color": "#7C3AED",
        "hover": "#6D28D9",
        "port_key": "TO",
    },
    {
        "key": "to_bima",
        "label": "TO MO-BIMA",
        "icon": "\U0001F3ED",
        "desc": "Take Ownership tiket group MO-BIMA",
        "color": "#0284C7",
        "hover": "#0369A1",
        "port_key": "TO",
    },
    {
        "key": "canclwork",
        "label": "CANCLWORK WO",
        "icon": "\U0001F527",
        "desc": "Cancel work order via BISCUIT",
        "color": "#EA580C",
        "hover": "#C2410C",
        "port_key": "CANCLWORK",
    },
    {
        "key": "dispatch",
        "label": "DISPATCH",
        "icon": "\U0001F680",
        "desc": "Dispatch tiket via BISCUIT",
        "color": "#059669",
        "hover": "#047857",
        "port_key": "DISPATCH",
    },
    {
        "key": "gamas_relations",
        "label": "GAMAS RELATIONS",
        "icon": "\U0001F517",
        "desc": "Relasi induk & anak GAMAS di INSERA",
        "color": "#DB2777",
        "hover": "#BE185D",
        "port_key": "GAMAS",
    },
    {
        "key": "report",
        "label": "REPORT HARIAN",
        "icon": "\U0001F4CA",
        "desc": "Laporan harian helpdesk operasional",
        "color": "#4F46E5",
        "hover": "#4338CA",
        "port_key": "REPORT",
    },
]

# Channel log dari tiap fitur -> tab tujuan
CHANNEL_TAB_MAP = {
    "to_insera": "TO",
    "to_bima": "TO",
    "canclwork": "CANCLWORK",
    "dispatch": "DISPATCH",
    "gamas_relations": "GAMAS",
    "report": "REPORT",
}

LOG_TABS = ["SEMUA", "TO", "CANCLWORK", "DISPATCH", "GAMAS", "REPORT"]

STATUS_COLORS = {
    "READY": "#059669",
    "STARTING": "#D97706",
    "LAUNCHING": "#D97706",
    "CONNECTING": "#D97706",
    "SCANNING": "#2563EB",
    "RUNNING": "#2563EB",
    "WAITING": "#64748B",
    "STOPPING": "#EA580C",
    "STOPPED": "#DC2626",
    "ERROR": "#DC2626",
}

STATUS_BG_COLORS = {
    "READY": "#ECFDF5",
    "STARTING": "#FFFBEB",
    "LAUNCHING": "#FFFBEB",
    "CONNECTING": "#FFFBEB",
    "SCANNING": "#EFF6FF",
    "RUNNING": "#EFF6FF",
    "WAITING": "#F1F5F9",
    "STOPPING": "#FFF7ED",
    "STOPPED": "#FEF2F2",
    "ERROR": "#FEF2F2",
}

# Status yang dot-nya berkedip
_BLINK_STATUSES = {
    "STARTING", "LAUNCHING", "CONNECTING", "SCANNING", "RUNNING", "STOPPING",
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
        self._blink_jobs = {}
        self._clock_job = None
        self._accent_widgets = []  # [(widget, property, value_type), ...]

        self.title("Industrial Programmer - DispatchAssistant")

        self.geometry("1280x850")
        self.minsize(1080, 740)
        self.resizable(True, True)

        self.configure(fg_color=BG_MAIN)

        from app.user_settings import load as _load_user_settings
        self.user_settings = _load_user_settings()

        self.create_header()
        self.create_feature_sections()
        self.create_log_section()
        self.create_footer()
        self._start_clock()

        # Terapkan warna & tema dari saved settings (jika ada)
        if self.user_settings:
            self._apply_visual_settings(self.user_settings)

        self._start_telegram_bot()

    # =================================================
    # Header
    # =================================================

    def create_header(self):

        frame = ctk.CTkFrame(
            self,
            corner_radius=16,
            fg_color=BG_HEADER,
            border_width=1,
            border_color=BORDER_SUBTLE,
        )
        frame.pack(fill="x", padx=20, pady=(16, 12))

        # Accent top bar (Red Stripe)
        strip = ctk.CTkFrame(frame, height=4, corner_radius=0, fg_color=RED_MAIN)
        strip.pack(fill="x", side="top")
        self._header_strip = strip
        self._accent_widgets.append((strip, "fg_color", "accent"))

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=(12, 12))
        inner.grid_columnconfigure(1, weight=1)

        # Left Branding
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        title_box = ctk.CTkFrame(left, fg_color="transparent")
        title_box.pack(anchor="w")

        title = ctk.CTkLabel(
            title_box,
            text="DispatchAssistant",
            font=(FONT_UI, 24, "bold"),
            text_color=TEXT_MAIN,
        )
        title.pack(side="left")

        ver_badge = ctk.CTkLabel(
            title_box,
            text=" v3.2 ",
            font=(FONT_MONO, 11, "bold"),
            text_color="#0284C7",
            fg_color="#E0F2FE",
            corner_radius=8,
            padx=6,
            pady=2,
        )
        ver_badge.pack(side="left", padx=(10, 0))

        subtitle = ctk.CTkLabel(
            left,
            text="Industrial Programmer Automation Suite  \u2022  Multi-Chrome CDP  \u2022  Telegram Remote",
            font=(FONT_UI, 11),
            text_color=TEXT_DIM,
        )
        subtitle.pack(anchor="w", pady=(3, 0))

        # Center Logo (Cyber Mascot Cat)
        center = ctk.CTkFrame(inner, fg_color="transparent")
        center.grid(row=0, column=1)

        logo_label = None
        if os.path.exists(LOGO_PATH):
            try:
                from PIL import Image

                pil_img = Image.open(LOGO_PATH).convert("RGBA")
                logo_img = ctk.CTkImage(
                    light_image=pil_img,
                    dark_image=pil_img,
                    size=(120, 120),
                )
                logo_label = ctk.CTkLabel(
                    center,
                    text="",
                    image=logo_img,
                )
            except Exception:
                logo_label = None

        if logo_label is None:
            logo_label = ctk.CTkLabel(
                center,
                text="\U0001F431",
                font=(FONT_UI, 28),
                text_color=TEXT_MAIN,
            )
        logo_label.pack(side="left")

        # Right Controls: Settings, System Status, Clock
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e")

        top_ctrl = ctk.CTkFrame(right, fg_color="transparent")
        top_ctrl.pack(anchor="e", pady=(0, 4))

        gear_btn = ctk.CTkButton(
            top_ctrl,
            text="\u2699\ufe0f  Settings",
            width=96,
            height=30,
            corner_radius=8,
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color=TEXT_MAIN,
            font=(FONT_UI, 11, "bold"),
            command=self._open_settings,
        )
        gear_btn.pack(side="right")
        self._gear_btn = gear_btn

        badge = ctk.CTkLabel(
            right,
            text="  \u25CF SYSTEM READY  ",
            font=(FONT_UI, 11, "bold"),
            text_color="#059669",
            fg_color="#ECFDF5",
            corner_radius=12,
            padx=8,
            pady=3,
        )
        badge.pack(anchor="e", pady=(2, 2))
        self._badge_ready = badge

        clock = ctk.CTkLabel(
            right,
            text="",
            font=(FONT_MONO, 13, "bold"),
            text_color="#0284C7",
        )
        clock.pack(anchor="e", pady=(2, 0))
        self._clock_label = clock

    # =================================================
    # Feature Cards (2 Baris x 3 Kolom)
    # =================================================

    def create_feature_sections(self):

        self.features_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.features_frame.pack(fill="x", padx=20, pady=(0, 10))

        for col in range(3):
            self.features_frame.grid_columnconfigure(col, weight=1)

        for i, feat in enumerate(FEATURES):
            card = self._create_feature_card(feat)
            row, col = i // 3, i % 3

            card.grid(
                row=row,
                column=col,
                sticky="ew",
                padx=6,
                pady=6,
            )

    def _create_feature_card(self, feat):

        key = feat["key"]
        port = REPORT_CDP_PORT if key == "report" else CHROME_PORTS.get(feat["port_key"], 9222)

        card = ctk.CTkFrame(
            self.features_frame,
            corner_radius=14,
            border_width=1.5,
            border_color=BORDER_CARD,
            fg_color=BG_CARD,
        )

        # Card top accent line matching feature signature color
        card_strip = ctk.CTkFrame(
            card,
            height=3.5,
            corner_radius=0,
            fg_color=feat["color"],
        )
        card_strip.pack(fill="x", side="top")

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 6))

        # Icon badge
        icon = ctk.CTkLabel(
            top,
            text=feat["icon"],
            font=(FONT_UI, 20),
            text_color=WHITE,
            fg_color=feat["color"],
            corner_radius=10,
            width=42,
            height=42,
        )
        icon.pack(side="left", padx=(0, 10))

        name_col = ctk.CTkFrame(top, fg_color="transparent")
        name_col.pack(side="left", fill="x", expand=True)

        name = ctk.CTkLabel(
            name_col,
            text=feat["label"],
            font=(FONT_UI, 14, "bold"),
            text_color=TEXT_MAIN,
        )
        name.pack(anchor="w")

        desc = ctk.CTkLabel(
            name_col,
            text=feat["desc"],
            font=(FONT_UI, 11),
            text_color=TEXT_SECONDARY,
        )
        desc.pack(anchor="w")

        status_label = ctk.CTkLabel(
            top,
            text="\u25CF READY",
            font=(FONT_UI, 11, "bold"),
            text_color="#059669",
            fg_color="#ECFDF5",
            corner_radius=12,
            padx=10,
            pady=3,
        )
        status_label.pack(side="right", padx=(8, 0))

        bottom = ctk.CTkFrame(card, fg_color="transparent")
        bottom.pack(fill="x", padx=14, pady=(6, 12))

        chip = ctk.CTkLabel(
            bottom,
            text=f"🔌 Port {port}",
            font=(FONT_MONO, 11, "bold"),
            text_color=feat["color"],
            fg_color=BG_MAIN,
            corner_radius=8,
            padx=8,
            pady=3,
        )
        chip.pack(side="left")

        stop_btn = ctk.CTkButton(
            bottom,
            text="STOP",
            width=70,
            height=30,
            corner_radius=8,
            fg_color=RED_LIGHT,
            hover_color="#FEE2E2",
            border_width=1.5,
            border_color="#FCA5A5",
            text_color=RED_MAIN,
            font=(FONT_UI, 11, "bold"),
            command=lambda k=key: self._stop_feature(k),
        )
        stop_btn.pack(side="right", padx=(6, 0))
        setattr(self, f"{key}_stop_btn", stop_btn)

        start_btn = ctk.CTkButton(
            bottom,
            text="START",
            width=80,
            height=30,
            corner_radius=8,
            fg_color=feat["color"],
            hover_color=feat["hover"],
            text_color=WHITE,
            font=(FONT_UI, 11, "bold"),
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

        port = REPORT_CDP_PORT if key == "report" else CHROME_PORTS.get(feat["port_key"], 9222)

        ctrl = DispatchController(
            gui=self._make_feature_adapter(key),
            cdp_port=port,
        )

        ctrl.on_complete = lambda k=key: self._on_feature_complete(k)
        self.controllers[key] = ctrl

        self._update_feature_status(key, "STARTING", "#D97706")
        getattr(self, f"{key}_btn").configure(state="disabled")

        if key == "report":
            ctrl.on_report = self._telegram_send_report
            ctrl.start_report()
        elif key == "to_insera":
            ctrl.start_auto(group_label="MO-INSERA", group_id=INSERA_GROUP_ID)
        elif key == "to_bima":
            ctrl.start_auto(group_label="MO-BIMA", group_id=None)
        elif key == "canclwork":
            ctrl.start_canclwork()
        elif key == "dispatch":
            ctrl.start_dispatch()
        elif key == "gamas_relations":
            ctrl.start_gamas_relations()

    def _telegram_send_report(self, text):
        tg = getattr(self, "telegram", None)
        if tg and tg.send_report_text(text):
            self.write_log("[report] Laporan dikirim ke Telegram.", channel="report")
        else:
            self.write_log(
                "[report] Telegram belum dikonfigurasi / belum siap - laporan hanya di log.",
                channel="report",
            )

    def _stop_feature(self, key):

        if key in self.controllers:
            self.controllers[key].stop()
            self._update_feature_status(key, "STOPPING", "#EA580C")
        else:
            self.write_log(f"[{key}] Not running.")

    def _on_feature_complete(self, key):

        self.after(0, lambda: self._finish_feature(key))

    def _finish_feature(self, key):

        self._update_feature_status(key, "READY", "#059669")
        getattr(self, f"{key}_btn").configure(state="normal")

        if key in self.controllers:
            del self.controllers[key]

    def _update_feature_status(self, key, status, color):

        lbl = getattr(self, f"{key}_status", None)
        if lbl:
            bg_col = STATUS_BG_COLORS.get(status.upper(), "#F1F5F9")
            self.after(0, lambda: lbl.configure(
                text=f"\u25CF {status}",
                text_color=color,
                fg_color=bg_col,
            ))

        self._manage_blink(key, status)

    def _manage_blink(self, key, status):
        """Dot status berkedip saat fitur aktif, berhenti saat diam."""

        job = self._blink_jobs.pop(key, None)
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                pass

        if status.upper() not in _BLINK_STATUSES:
            return

        lbl = getattr(self, f"{key}_status", None)
        if lbl is None:
            return

        color = STATUS_COLORS.get(status.upper(), "#059669")
        dim = "#94A3B8"
        state = {"on": True}

        def tick():
            state["on"] = not state["on"]
            try:
                lbl.configure(text_color=color if state["on"] else dim)
                self._blink_jobs[key] = self.after(650, tick)
            except Exception:
                pass

        tick()

    def _update_feature_status_from_controller(self, key, status):

        status = str(status).upper()
        color = STATUS_COLORS.get(status, "#059669")
        self._update_feature_status(key, status, color)

    def _make_feature_adapter(self, key):

        return _FeatureGUIAdapter(self, key)

    # =================================================
    # Log Section (Activity Terminal dengan Tab)
    # =================================================

    def create_log_section(self):

        frame = ctk.CTkFrame(
            self,
            corner_radius=14,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_SUBTLE,
        )

        frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 10),
        )

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(
            header,
            text="Activity Log",
            font=(FONT_UI, 14, "bold"),
            text_color=TEXT_MAIN,
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="live console feed",
            font=(FONT_UI, 11),
            text_color=TEXT_DIM,
        ).pack(side="left", padx=(8, 0), pady=(2, 0))

        self._live_badge = ctk.CTkLabel(
            header,
            text="  \u25CF LIVE STREAM  ",
            font=(FONT_UI, 10, "bold"),
            text_color=WHITE,
            fg_color=RED_MAIN,
            corner_radius=8,
            padx=6,
            pady=1,
        )
        self._live_badge.pack(side="left", padx=(10, 0))
        self._accent_widgets.append((self._live_badge, "fg_color", "accent"))

        ctk.CTkButton(
            header,
            text="📋 Salin",
            width=68,
            height=26,
            corner_radius=8,
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color=TEXT_MAIN,
            font=(FONT_UI, 11, "bold"),
            command=self._copy_log,
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            header,
            text="🗑 Bersihkan",
            width=80,
            height=26,
            corner_radius=8,
            fg_color="#F1F5F9",
            hover_color="#E2E8F0",
            text_color=TEXT_MAIN,
            font=(FONT_UI, 11, "bold"),
            command=self._clear_log,
        ).pack(side="right")

        self.tabs = ctk.CTkTabview(
            frame,
            corner_radius=10,
            fg_color=BG_MAIN,
            segmented_button_selected_color=RED_MAIN,
            segmented_button_selected_hover_color=RED_HOVER,
            segmented_button_unselected_color=WHITE,
            segmented_button_unselected_hover_color="#FEE2E2",
            text_color=TEXT_MAIN,
        )
        self._log_tabs = self.tabs

        self.tabs.pack(fill="both", expand=True, padx=14, pady=(4, 12))

        for name in LOG_TABS:
            tab = self.tabs.add(name)
            box = ctk.CTkTextbox(
                tab,
                font=(FONT_MONO, 12),
                wrap="word",
                fg_color=BG_TERMINAL,
                border_color="#1E293B",
                border_width=1,
                corner_radius=8,
                text_color="#E2E8F0",
            )
            box.pack(fill="both", expand=True, padx=2, pady=2)
            self.log_boxes[name] = box
            self._setup_tags(box)

        self.write_log("Application initialized...")
        self.write_log("")
        self.write_log("=== MULTI-CHROME CDP MODE ===")
        self.write_log("Setiap fitur terisolasi pada Chrome CDP terpisah.")
        self.write_log("Daftar alokasi port:")
        self.write_log(f"  TO        -> port {CHROME_PORTS['TO']}")
        self.write_log(f"  CANCLWORK -> port {CHROME_PORTS['CANCLWORK']}")
        self.write_log(f"  DISPATCH  -> port {CHROME_PORTS['DISPATCH']}")
        self.write_log(f"  GAMAS     -> port {CHROME_PORTS['GAMAS']}")
        self.write_log(f"  REPORT    -> port {CHROME_PORTS['REPORT']}")
        self.write_log("=============================")

    def _setup_tags(self, box):

        try:
            box.tag_config("err", foreground="#F87171")
            box.tag_config("ok", foreground="#4ADE80")
            box.tag_config("warn", foreground="#FBBF24")
            box.tag_config("dim", foreground="#94A3B8")
        except Exception:
            try:
                box._textbox.tag_config("err", foreground="#F87171")
                box._textbox.tag_config("ok", foreground="#4ADE80")
                box._textbox.tag_config("warn", foreground="#FBBF24")
                box._textbox.tag_config("dim", foreground="#94A3B8")
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

    def _copy_log(self):

        try:
            name = self.tabs.get()
        except Exception:
            name = "SEMUA"

        box = self.log_boxes.get(name)
        if box is None:
            return
        content = box.get("1.0", "end").strip()
        if not content:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(content)
            self.write_log("[gui] Log disalin ke clipboard.")
        except Exception as e:
            self.write_log(f"[gui] Gagal copy log: {e}")

    # =================================================
    # Footer
    # =================================================

    def create_footer(self):

        footer = ctk.CTkFrame(
            self,
            corner_radius=10,
            fg_color=BG_HEADER,
            border_width=1,
            border_color=BORDER_SUBTLE,
        )

        footer.pack(fill="x", padx=20, pady=(0, 14))

        ctk.CTkLabel(
            footer,
            text="\u25CF ONLINE",
            font=(FONT_UI, 11, "bold"),
            text_color="#059669",
        ).pack(side="left", padx=14, pady=8)

        ctk.CTkLabel(
            footer,
            text="Autonomous Loop Aktif  \u2022  Gunakan STOP saat intervensi manual",
            font=(FONT_UI, 11),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(10, 0), pady=8)

        ctk.CTkLabel(
            footer,
            text="Industrial Programmer Suite  \u2022  v3.2",
            font=(FONT_UI, 11, "bold"),
            text_color=TEXT_DIM,
        ).pack(side="right", padx=14, pady=8)

    def _start_clock(self):

        def tick():
            self._clock_label.configure(
                text=datetime.now().strftime("%H:%M:%S")
            )
            self._clock_job = self.after(1000, tick)

        tick()

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

        self._start_feature_telegram_bots()

    def _start_feature_telegram_bots(self):
        from app.telegram_bot import FeatureTelegramBot
        from config.settings import (
            TELEGRAM_BOT_TOKEN_CANCLWORK,
            TELEGRAM_BOT_TOKEN_DISPATCH,
            TELEGRAM_BOT_TOKEN_GAMAS,
            TELEGRAM_CHAT_IDS,
            TELEGRAM_ALLOWED_USER_IDS,
            REPORT_CHAT_IDS,
        )

        specs = [
            ("canclwork", TELEGRAM_BOT_TOKEN_CANCLWORK, "CANCLWORK"),
            ("dispatch", TELEGRAM_BOT_TOKEN_DISPATCH, "DISPATCH"),
            ("gamas_relations", TELEGRAM_BOT_TOKEN_GAMAS, "GAMAS"),
        ]
        self.feature_telegrams = {}
        for key, token, port_key in specs:
            if not token:
                self.write_log(f"[telegram:{key}] token belum diatur di .env - bot dilewati.")
                continue
            try:
                chat_ids = (
                    TELEGRAM_CHAT_IDS.get(key)
                    or TELEGRAM_ALLOWED_USER_IDS
                    or REPORT_CHAT_IDS
                )
                bot = FeatureTelegramBot(
                    gui=self,
                    key=key,
                    token=token,
                    port_key=port_key,
                    chat_ids=chat_ids,
                )
                if bot.start():
                    self.feature_telegrams[key] = bot
                    self.write_log(f"[telegram:{key}] bot started - log live + remote control.")
                else:
                    self.write_log(f"[telegram:{key}] gagal start bot.")
            except Exception as e:
                self.write_log(f"[telegram:{key}] error: {e}")


# =====================================================
# Settings Modal (CTkToplevel)
# =====================================================

    def _open_settings(self):
        from app.user_settings import DEFAULTS

        win = ctk.CTkToplevel(self)
        win.title("Pengaturan Bot")
        win.geometry("620x680")
        win.resizable(False, False)
        win.configure(fg_color=BG_HEADER)
        win.transient(self)
        win.grab_set()

        cur = self.user_settings or dict(DEFAULTS)

        # Header
        hdr = ctk.CTkFrame(win, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 0))
        ctk.CTkLabel(
            hdr, text="⚙  Pengaturan Bot",
            font=(FONT_UI, 20, "bold"), text_color=RED_MAIN,
        ).pack(side="left")
        ctk.CTkLabel(
            hdr, text="Simpan = langsung aktif",
            font=(FONT_UI, 11), text_color=TEXT_DIM,
        ).pack(side="left", padx=(12, 0), pady=(4, 0))

        # Tab View
        tabs = ctk.CTkTabview(
            win, corner_radius=10, fg_color=BG_HEADER,
            segmented_button_selected_color=RED_MAIN,
            segmented_button_selected_hover_color=RED_HOVER,
            segmented_button_unselected_color=BG_INPUT,
            segmented_button_unselected_hover_color="#E2E8F0",
            text_color=TEXT_MAIN,
        )
        tabs.pack(fill="both", expand=True, padx=20, pady=(4, 6))

        tab_general = tabs.add("Umum")
        tab_tampilan = tabs.add("Tampilan")
        tab_advanced = tabs.add("Advanced")

        # ── Helper builders ──────────────────────────
        def _entry_row(parent, label, value, hint=None):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            box.pack(fill="x", pady=5)
            ctk.CTkLabel(box, text=label, font=(FONT_UI, 12, "bold"),
                         text_color=TEXT_MAIN).pack(anchor="w")
            entry = ctk.CTkEntry(box, font=(FONT_MONO, 12), fg_color=BG_INPUT,
                                 border_color=BORDER_SUBTLE, text_color=TEXT_MAIN,
                                 corner_radius=8, height=34)
            entry.insert(0, str(value))
            entry.pack(fill="x", pady=(3, 0))
            if hint:
                ctk.CTkLabel(box, text=hint, font=(FONT_UI, 10),
                             text_color=TEXT_DIM).pack(anchor="w", pady=(2, 0))
            return entry

        def _switch_row(parent, label, value, hint=None):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            box.pack(fill="x", pady=5)
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkLabel(row, text=label, font=(FONT_UI, 12, "bold"),
                         text_color=TEXT_MAIN).pack(side="left")
            sw = ctk.CTkSwitch(row, text="", width=46,
                               fg_color="#CBD5E1", progress_color=RED_MAIN,
                               button_color=WHITE, button_hover_color="#F1F5F9")
            if value:
                sw.select()
            else:
                sw.deselect()
            sw.pack(side="right")
            if hint:
                ctk.CTkLabel(box, text=hint, font=(FONT_UI, 10),
                             text_color=TEXT_DIM).pack(anchor="w", pady=(2, 0))
            return sw

        def _dropdown_row(parent, label, values, current, hint=None):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            box.pack(fill="x", pady=5)
            ctk.CTkLabel(box, text=label, font=(FONT_UI, 12, "bold"),
                         text_color=TEXT_MAIN).pack(anchor="w")
            dd = ctk.CTkOptionMenu(box, values=values, fg_color=BG_INPUT,
                                   button_color="#CBD5E1", button_hover_color="#94A3B8",
                                   dropdown_fg_color=WHITE, dropdown_hover_color="#F1F5F9",
                                   text_color=TEXT_MAIN, font=(FONT_UI, 12),
                                   corner_radius=8, height=34)
            dd.set(current)
            dd.pack(fill="x", pady=(3, 0))
            if hint:
                ctk.CTkLabel(box, text=hint, font=(FONT_UI, 10),
                             text_color=TEXT_DIM).pack(anchor="w", pady=(2, 0))
            return dd

        def _slider_row(parent, label, value, from_, to_, hint=None):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            box.pack(fill="x", pady=5)
            top_r = ctk.CTkFrame(box, fg_color="transparent")
            top_r.pack(fill="x")
            ctk.CTkLabel(top_r, text=label, font=(FONT_UI, 12, "bold"),
                         text_color=TEXT_MAIN).pack(side="left")
            val_lbl = ctk.CTkLabel(top_r, text=str(int(value)),
                                   font=(FONT_MONO, 12, "bold"),
                                   text_color=RED_MAIN)
            val_lbl.pack(side="right")
            sl = ctk.CTkSlider(box, from_=from_, to=to_, number_of_steps=to_ - from_,
                               fg_color="#CBD5E1", progress_color=RED_MAIN,
                               button_color=RED_MAIN, button_hover_color=RED_HOVER)
            sl.set(value)
            sl.configure(command=lambda v, l=val_lbl: l.configure(text=str(int(v))))
            sl.pack(fill="x", pady=(3, 0))
            if hint:
                ctk.CTkLabel(box, text=hint, font=(FONT_UI, 10),
                             text_color=TEXT_DIM).pack(anchor="w", pady=(2, 0))
            return sl

        def _section_label(parent, text):
            ctk.CTkLabel(parent, text=text, font=(FONT_UI, 13, "bold"),
                         text_color="#0284C7").pack(anchor="w", pady=(10, 4))

        # ── TAB 1: UMUM ─────────────────────────────
        scroll_gen = ctk.CTkScrollableFrame(tab_general, fg_color="transparent")
        scroll_gen.pack(fill="both", expand=True, padx=4, pady=4)

        _section_label(scroll_gen, "🔄  Loop & Scan")
        e_loop = _entry_row(scroll_gen,
            "Loop Interval (detik)",
            cur.get("loop_interval", DEFAULTS["loop_interval"]),
            "Jeda scan ulang tiap fitur. Minimum 60 detik.",
        )

        _section_label(scroll_gen, "👤  Koordinator")
        e_skip = _entry_row(scroll_gen,
            "Skip Coordinator (ID/Nama, pisah koma)",
            ", ".join(cur.get("skip_coordinator_user_ids") or DEFAULTS["skip_coordinator_user_ids"]),
            "Angka = ID. Teks = nama/username di SYGAP.",
        )
        e_uid = _entry_row(scroll_gen,
            "User ID (Request Coordinator)",
            cur.get("user_id", DEFAULTS["user_id"]),
        )
        e_uname = _entry_row(scroll_gen,
            "Nama (Request Coordinator)",
            cur.get("user_name", DEFAULTS["user_name"]),
            "User ID & Nama berlaku setelah restart.",
        )

        # ── TAB 2: TAMPILAN ──────────────────────────
        scroll_vis = ctk.CTkScrollableFrame(tab_tampilan, fg_color="transparent")
        scroll_vis.pack(fill="both", expand=True, padx=4, pady=4)

        _section_label(scroll_vis, "🎨  Tema & Warna")
        dd_theme = _dropdown_row(scroll_vis,
            "Tema Aplikasi", ["light", "dark"],
            cur.get("theme", DEFAULTS["theme"]),
            "Berlaku setelah restart.",
        )

        # Accent Color Picker
        _ACCENT_PRESETS = {
            "Merah (Telkom)": "#DC2626",
            "Biru Langit": "#0284C7",
            "Ungu": "#7C3AED",
            "Hijau Emerald": "#059669",
            "Oranye Sunset": "#EA580C",
            "Pink Fuchsia": "#DB2777",
            "Indigo": "#4F46E5",
            "Teal": "#0D9488",
        }
        dd_accent = _dropdown_row(scroll_vis,
            "Warna Aksen",
            list(_ACCENT_PRESETS.keys()),
            next((k for k, v in _ACCENT_PRESETS.items()
                  if v == cur.get("accent_color", DEFAULTS["accent_color"])),
                 "Merah (Telkom)"),
            "Warna utama tombol, header strip, dan status badge.",
        )

        # Live color preview swatch
        preview_box = ctk.CTkFrame(scroll_vis, fg_color="transparent")
        preview_box.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(preview_box, text="Preview:", font=(FONT_UI, 10),
                     text_color=TEXT_DIM).pack(side="left")
        _preview_swatch = ctk.CTkLabel(
            preview_box, text="  ████████  ",
            font=(FONT_MONO, 14, "bold"),
            text_color=cur.get("accent_color", DEFAULTS["accent_color"]),
            fg_color=BG_INPUT, corner_radius=6, padx=6, pady=2,
        )
        _preview_swatch.pack(side="left", padx=(6, 0))

        def _on_accent_change(choice):
            color = _ACCENT_PRESETS.get(choice, "#DC2626")
            _preview_swatch.configure(text_color=color)

        dd_accent.configure(command=_on_accent_change)

        _section_label(scroll_vis, "🔤  Font & Log")
        sl_fontsize = _slider_row(scroll_vis,
            "Ukuran Font Log", cur.get("log_font_size", DEFAULTS["log_font_size"]),
            8, 22, "Font terminal log (8 – 22 pt).",
        )
        e_maxlog = _entry_row(scroll_vis,
            "Maks Baris Log per Tab",
            cur.get("max_log_lines", DEFAULTS["max_log_lines"]),
            "0 = tidak dibatasi. Rekomendasi 1000 – 5000.",
        )

        # ── TAB 3: ADVANCED ──────────────────────────
        scroll_adv = ctk.CTkScrollableFrame(tab_advanced, fg_color="transparent")
        scroll_adv.pack(fill="both", expand=True, padx=4, pady=4)

        _section_label(scroll_adv, "📜  Perilaku Log")
        sw_autoscroll = _switch_row(scroll_adv,
            "Auto-Scroll Log", cur.get("auto_scroll_log", DEFAULTS["auto_scroll_log"]),
            "Otomatis scroll ke baris terbaru.",
        )
        sw_timestamp = _switch_row(scroll_adv,
            "Tampilkan Timestamp", cur.get("show_timestamp", DEFAULTS["show_timestamp"]),
            "Tampilkan [HH:MM:SS] di awal setiap baris log.",
        )

        _section_label(scroll_adv, "🛡  Safety")
        sw_confirm_stop = _switch_row(scroll_adv,
            "Konfirmasi Sebelum STOP", cur.get("confirm_before_stop", DEFAULTS["confirm_before_stop"]),
            "Tampilkan dialog konfirmasi saat menekan tombol STOP.",
        )

        _section_label(scroll_adv, "🔌  BISCUIT API")
        e_biscuit_timeout = _entry_row(scroll_adv,
            "API Timeout (detik)",
            cur.get("biscuit_api_timeout", DEFAULTS["biscuit_api_timeout"]),
            "Timeout request ke BISCUIT API. Min 30 detik.",
        )

        _section_label(scroll_adv, "🚀  Auto-Start saat Launch")
        _FEATURE_KEYS = [
            ("to_insera", "TO MO-INSERA"),
            ("to_bima", "TO MO-BIMA"),
            ("canclwork", "CANCLWORK WO"),
            ("dispatch", "DISPATCH"),
            ("gamas_relations", "GAMAS RELATIONS"),
            ("report", "REPORT HARIAN"),
        ]
        auto_start_cur = cur.get("auto_start_features") or []
        auto_start_cbs = {}
        for fkey, flabel in _FEATURE_KEYS:
            cb_box = ctk.CTkFrame(scroll_adv, fg_color="transparent")
            cb_box.pack(fill="x", pady=2)
            cb = ctk.CTkCheckBox(cb_box, text=flabel, font=(FONT_UI, 12),
                                 text_color=TEXT_MAIN,
                                 fg_color=RED_MAIN, hover_color=RED_HOVER,
                                 border_color=BORDER_SUBTLE,
                                 checkmark_color=WHITE, corner_radius=6)
            if fkey in auto_start_cur:
                cb.select()
            cb.pack(anchor="w")
            auto_start_cbs[fkey] = cb

        ctk.CTkLabel(scroll_adv, text="Fitur yang dicentang akan otomatis START saat aplikasi dibuka (setelah restart).",
                     font=(FONT_UI, 10), text_color=TEXT_DIM, wraplength=480
                     ).pack(anchor="w", pady=(2, 0))

        # ── Bottom Bar ───────────────────────────────
        from app.user_settings import USER_SETTINGS_PATH

        bot_bar = ctk.CTkFrame(win, fg_color="transparent")
        bot_bar.pack(fill="x", padx=24, pady=(0, 16))

        ctk.CTkLabel(
            bot_bar, text=f"📁 {USER_SETTINGS_PATH}",
            font=(FONT_UI, 10), text_color=TEXT_DIM,
        ).pack(anchor="w", pady=(0, 8))

        btns = ctk.CTkFrame(bot_bar, fg_color="transparent")
        btns.pack(fill="x")

        def _save():
            try:
                loop = int(e_loop.get().strip() or DEFAULTS["loop_interval"])
                loop = max(60, loop)
            except ValueError:
                loop = DEFAULTS["loop_interval"]

            skip = [x.strip() for x in e_skip.get().replace(",", " ").split() if x.strip()]

            accent_name = dd_accent.get()
            accent_hex = _ACCENT_PRESETS.get(accent_name, DEFAULTS["accent_color"])

            auto_start_list = [k for k, cb in auto_start_cbs.items() if cb.get()]

            try:
                maxlog = int(e_maxlog.get().strip() or DEFAULTS["max_log_lines"])
            except ValueError:
                maxlog = DEFAULTS["max_log_lines"]

            try:
                biscuit_t = int(e_biscuit_timeout.get().strip() or DEFAULTS["biscuit_api_timeout"])
            except ValueError:
                biscuit_t = DEFAULTS["biscuit_api_timeout"]

            data = {
                "loop_interval": loop,
                "skip_coordinator_user_ids": skip,
                "user_id": e_uid.get().strip() or DEFAULTS["user_id"],
                "user_name": e_uname.get().strip() or DEFAULTS["user_name"],
                "theme": dd_theme.get(),
                "accent_color": accent_hex,
                "log_font_size": int(sl_fontsize.get()),
                "max_log_lines": maxlog,
                "auto_scroll_log": bool(sw_autoscroll.get()),
                "show_timestamp": bool(sw_timestamp.get()),
                "confirm_before_stop": bool(sw_confirm_stop.get()),
                "auto_start_features": auto_start_list,
                "biscuit_api_timeout": biscuit_t,
            }

            from app.user_settings import save as _save_settings
            self.user_settings = _save_settings(data)

            # Live-apply visual settings
            self._apply_visual_settings(data)

            self.write_log(
                f"[settings] Disimpan: loop={loop}s, skip={skip or 'none'}, "
                f"user={data['user_name']} ({data['user_id']}), "
                f"theme={data['theme']}, accent={accent_hex}, "
                f"font={data['log_font_size']}pt",
                channel="all",
            )
            self.write_log(
                "[settings] Perubahan tampilan & perilaku langsung aktif. "
                "Tema, User ID/Nama, Auto-Start aktif setelah restart.",
                channel="all",
            )
            win.destroy()

        ctk.CTkButton(
            btns, text="💾  Simpan", width=120, height=36,
            corner_radius=8, fg_color=RED_MAIN, hover_color=RED_HOVER,
            text_color=WHITE, font=(FONT_UI, 12, "bold"),
            command=_save,
        ).pack(side="left")

        ctk.CTkButton(
            btns, text="Batal", width=90, height=36,
            corner_radius=8, fg_color="#F1F5F9", hover_color="#E2E8F0",
            text_color=TEXT_MAIN, font=(FONT_UI, 12, "bold"),
            command=win.destroy,
        ).pack(side="left", padx=(10, 0))

        # Reset defaults button
        def _reset():
            if hasattr(ctk, "CTkInputDialog"):
                pass  # no modal needed, just reset
            from app.user_settings import save as _save_settings
            self.user_settings = _save_settings(dict(DEFAULTS))
            self._apply_visual_settings(DEFAULTS)
            self.write_log("[settings] Reset ke default!", channel="all")
            win.destroy()

        ctk.CTkButton(
            btns, text="🔄  Reset Default", width=130, height=36,
            corner_radius=8, fg_color="#FEF2F2", hover_color="#FEE2E2",
            text_color=RED_MAIN, font=(FONT_UI, 11, "bold"),
            command=_reset,
        ).pack(side="right")

    def _apply_visual_settings(self, data):
        """Terapkan pengaturan visual secara live (tanpa restart)."""
        accent = data.get("accent_color", RED_MAIN)

        # ── Darken helper for hover color ──
        def _darken(hex_color, factor=0.8):
            hex_color = hex_color.lstrip("#")
            r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            r, g, b = int(r * factor), int(g * factor), int(b * factor)
            return f"#{r:02x}{g:02x}{b:02x}"

        accent_hover = _darken(accent, 0.82)

        # ── 1. Update semua accent widgets ──
        for widget, prop, val_type in self._accent_widgets:
            try:
                if val_type == "accent":
                    widget.configure(**{prop: accent})
            except Exception:
                pass

        # ── 2. Update log tab segmented button colors ──
        try:
            self._log_tabs.configure(
                segmented_button_selected_color=accent,
                segmented_button_selected_hover_color=accent_hover,
            )
        except Exception:
            pass

        # ── 3. Update header title label color ──
        # (Settings gear title uses RED_MAIN, but title text stays TEXT_MAIN)

        # ── 4. Update STOP button text colors on all feature cards ──
        for feat in FEATURES:
            key = feat["key"]
            stop_btn = getattr(self, f"{key}_stop_btn", None)
            if stop_btn:
                try:
                    stop_btn.configure(text_color=accent)
                except Exception:
                    pass

        # ── 5. Font size log ──
        font_size = data.get("log_font_size", 12)
        for name, box in self.log_boxes.items():
            try:
                box.configure(font=(FONT_MONO, font_size))
            except Exception:
                pass

        # ── 6. Max log lines trimming ──
        max_lines = data.get("max_log_lines", 2000)
        if max_lines > 0:
            for name, box in self.log_boxes.items():
                try:
                    content = box.get("1.0", "end")
                    lines = content.split("\n")
                    if len(lines) > max_lines:
                        box.delete("1.0", f"{len(lines) - max_lines}.0")
                except Exception:
                    pass

        # ── 7. Theme mode (light/dark) ──
        theme = data.get("theme", "light")
        try:
            ctk.set_appearance_mode(theme)
        except Exception:
            pass

        self.write_log(f"[settings] Visual diterapkan: aksen={accent}, tema={theme}, font={font_size}pt", channel="all")


# =====================================================
# Run
# =====================================================

if __name__ == "__main__":

    app = DispatchAssistantGUI()

    app.mainloop()
