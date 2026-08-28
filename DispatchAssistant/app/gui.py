import sys
import os

import customtkinter as ctk
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.controller import DispatchController
from config.settings import (
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

# Theme Palette (Adaptive Light / Dark 2-Tuples for CustomTkinter)
BG_MAIN = ("#F1F5F9", "#0B0F19")          # Main window bg (Light: slate-100, Dark: deep obsidian #0B0F19)
BG_HEADER = ("#FFFFFF", "#161F30")        # Header card (Light: pure white, Dark: slate-800 #161F30)
BG_CARD = ("#FFFFFF", "#161F30")          # Feature card (Light: pure white, Dark: slate-800 #161F30)
BG_CARD_HOVER = ("#F8FAFC", "#1E293B")    # Card hover (Light: slate-50, Dark: slate-700)
BG_INPUT = ("#F8FAFC", "#0F172A")         # Input/chip bg (Light: slate-50, Dark: slate-900)
BG_BTN_SECONDARY = ("#F1F5F9", "#1E293B") # Secondary button bg
BG_BTN_SECONDARY_HOVER = ("#E2E8F0", "#334155")
BG_TERMINAL = ("#0F172A", "#030712")      # Terminal log bg

BORDER_SUBTLE = ("#E2E8F0", "#2A374A")    # Border lines (Light: slate-200, Dark: slate-700)
BORDER_CARD = ("#E2E8F0", "#2A374A")      # Card borders
BORDER_FOCUS = "#3B82F6"

TEXT_MAIN = ("#0F172A", "#F8FAFC")        # Primary text (Light: slate-900, Dark: slate-50 white)
TEXT_SECONDARY = ("#475569", "#94A3B8")   # Secondary text (Light: slate-600, Dark: slate-400)
TEXT_DIM = ("#64748B", "#64748B")         # Muted info text
WHITE = "#FFFFFF"

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
    try:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color

RED_MAIN = _load_saved_accent()             # Vibrant accent (default: Telkom Red)
RED_DARK = _darken_hex(RED_MAIN, 0.6)       # Dark accent
RED_HOVER = _darken_hex(RED_MAIN, 0.82)     # Hover accent

RED_LIGHT = ("#FEF2F2", "#380D0D")        # Light: pastel red, Dark: deep dark red
RED_LIGHT_BORDER = ("#FCA5A5", "#7F1D1D")
RED_LIGHT_HOVER = ("#FEE2E2", "#4C1D1D")

BADGE_READY_BG = ("#ECFDF5", "#064E3B")
BADGE_READY_TEXT = ("#059669", "#34D399")

BADGE_VER_BG = ("#E0F2FE", "#075985")
BADGE_VER_TEXT = ("#0284C7", "#38BDF8")

CLOCK_BG = ("#F1F5F9", "#1E293B")
CLOCK_TEXT = ("#0284C7", "#38BDF8")

TAB_UNSELECTED_BG = ("#FFFFFF", "#161F30")
TAB_UNSELECTED_HOVER = ("#F1F5F9", "#1E293B")

TAG_BG = ("#F8FAFC", "#0F172A")
TAG_BORDER = ("#E2E8F0", "#2A374A")
TAG_TEXT = ("#64748B", "#94A3B8")

FONT_UI = "Segoe UI"
FONT_MONO = "Consolas"

FEATURES = [
    {
        "key": "canclwork",
        "label": "CANCLWORK WO",
        "icon": "\U0001F527",
        "desc": "Cancel work order via BISCUIT",
        "tag": "⚡ BISCUIT API",
        "color": "#EA580C",
        "hover": "#C2410C",
        "port_key": "CANCLWORK",
    },
    {
        "key": "dispatch",
        "label": "DISPATCH",
        "icon": "\U0001F680",
        "desc": "Dispatch tiket via BISCUIT",
        "tag": "⚡ BISCUIT API",
        "color": "#059669",
        "hover": "#047857",
        "port_key": "DISPATCH",
    },
    {
        "key": "dispatch_incident",
        "label": "DISPATCH INCIDENT",
        "icon": "\U0001F692",
        "desc": "Dispatch tiket INCIDENT via BISCUIT",
        "tag": "⚡ BISCUIT API • INCIDENT",
        "color": "#DC2626",
        "hover": "#B91C1C",
        "port_key": "DISPATCH_INCIDENT",
    },
    {
        "key": "change_service_id",
        "label": "CHANGE SERVICE ID",
        "icon": "\U0001F504",
        "desc": "Ubah Service ID (UI) & Type (API)",
        "tag": "🖥️ UI + ⚡ API",
        "color": "#0D9488",
        "hover": "#0F766E",
        "port_key": "CHANGE_SERVICE_ID",
    },
    {
        "key": "gamas_relations",
        "label": "GAMAS RELATIONS",
        "icon": "\U0001F517",
        "desc": "Relasi induk & anak GAMAS di INSERA",
        "tag": "🔗 INSERA + BISCUIT",
        "color": "#DB2777",
        "hover": "#BE185D",
        "port_key": "GAMAS",
    },
    {
        "key": "report",
        "label": "REPORT HARIAN",
        "icon": "\U0001F4CA",
        "desc": "Laporan harian helpdesk operasional",
        "tag": "📊 SYGAP + TG",
        "color": "#4F46E5",
        "hover": "#4338CA",
        "port_key": "REPORT",
    },
]

# Channel log dari tiap fitur -> tab tujuan
CHANNEL_TAB_MAP = {
    "canclwork": "CANCLWORK",
    "dispatch": "DISPATCH",
    "dispatch_incident": "DISPATCH",
    "change_service_id": "SERVICE_ID",
    "gamas_relations": "GAMAS",
    "report": "REPORT",
}

LOG_TABS = ["SEMUA", "CANCLWORK", "DISPATCH", "SERVICE_ID", "GAMAS", "REPORT"]

STATUS_COLORS = {
    "READY": ("#059669", "#34D399"),
    "STARTING": ("#D97706", "#FBBF24"),
    "LAUNCHING": ("#D97706", "#FBBF24"),
    "CONNECTING": ("#D97706", "#FBBF24"),
    "SCANNING": ("#2563EB", "#60A5FA"),
    "RUNNING": ("#2563EB", "#60A5FA"),
    "WAITING": ("#64748B", "#94A3B8"),
    "STOPPING": ("#EA580C", "#FB923C"),
    "STOPPED": ("#DC2626", "#F87171"),
    "ERROR": ("#DC2626", "#F87171"),
}

STATUS_BG_COLORS = {
    "READY": ("#ECFDF5", "#064E3B"),
    "STARTING": ("#FFFBEB", "#451A03"),
    "LAUNCHING": ("#FFFBEB", "#451A03"),
    "CONNECTING": ("#FFFBEB", "#451A03"),
    "SCANNING": ("#EFF6FF", "#172554"),
    "RUNNING": ("#EFF6FF", "#172554"),
    "WAITING": ("#F1F5F9", "#1E293B"),
    "STOPPING": ("#FFF7ED", "#431407"),
    "STOPPED": ("#FEF2F2", "#450A0A"),
    "ERROR": ("#FEF2F2", "#450A0A"),
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
        self._feature_desc_labels = {}
        self._feature_tag_labels = {}
        self._logo_label = None
        self._clock_label = None

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
    # Header (Compact, High-Density Operations Center)
    # =================================================

    def create_header(self):

        frame = ctk.CTkFrame(
            self,
            corner_radius=14,
            fg_color=BG_HEADER,
            border_width=1,
            border_color=BORDER_SUBTLE,
        )
        frame.pack(fill="x", padx=20, pady=(12, 10))

        # Accent top bar (Red / Accent Stripe)
        strip = ctk.CTkFrame(frame, height=3.5, corner_radius=0, fg_color=RED_MAIN)
        strip.pack(fill="x", side="top")
        self._header_strip = strip
        self._accent_widgets.append((strip, "fg_color", "accent"))

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=(6, 6))
        inner.grid_columnconfigure(1, weight=1)

        # ── LEFT: Branding ────────────────────────────
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        title_box = ctk.CTkFrame(left, fg_color="transparent")
        title_box.pack(anchor="w")

        title = ctk.CTkLabel(
            title_box,
            text="DispatchAssistant",
            font=(FONT_UI, 22, "bold"),
            text_color=TEXT_MAIN,
        )
        title.pack(side="left")

        ver_badge = ctk.CTkLabel(
            title_box,
            text=" v3.2 ",
            font=(FONT_MONO, 10, "bold"),
            text_color=BADGE_VER_TEXT,
            fg_color=BADGE_VER_BG,
            corner_radius=8,
            padx=6,
            pady=2,
        )
        ver_badge.pack(side="left", padx=(8, 0))

        subtitle = ctk.CTkLabel(
            left,
            text="Industrial Programmer Automation Suite  \u2022  Multi-Chrome CDP  \u2022  Telegram Remote",
            font=(FONT_UI, 11),
            text_color=TEXT_DIM,
        )
        subtitle.pack(anchor="w", pady=(3, 0))

        # ── CENTER: Logo Mascot Cyber Cat ─────────────
        center = ctk.CTkFrame(inner, fg_color="transparent")
        center.grid(row=0, column=1)

        logo_label = None
        logo_sz = self.user_settings.get("logo_size", 115) if self.user_settings else 115
        if os.path.exists(LOGO_PATH):
            try:
                from PIL import Image

                pil_img = Image.open(LOGO_PATH).convert("RGBA")
                self._logo_img = ctk.CTkImage(
                    light_image=pil_img,
                    dark_image=pil_img,
                    size=(logo_sz, logo_sz),
                )
                logo_label = ctk.CTkLabel(
                    center,
                    text="",
                    image=self._logo_img,
                )
            except Exception:
                logo_label = None

        if logo_label is None:
            logo_label = ctk.CTkLabel(
                center,
                text="\U0001F431",
                font=(FONT_UI, 32),
                text_color=TEXT_MAIN,
            )
        logo_label.pack(side="left")
        self._logo_label = logo_label

        # ── RIGHT: Settings, System Status, Clock ──────
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e")

        top_ctrl = ctk.CTkFrame(right, fg_color="transparent")
        top_ctrl.pack(anchor="e", pady=(0, 4))

        gear_btn = ctk.CTkButton(
            top_ctrl,
            text="\u2699\ufe0f  Settings",
            width=92,
            height=28,
            corner_radius=7,
            fg_color=BG_BTN_SECONDARY,
            hover_color=BG_BTN_SECONDARY_HOVER,
            text_color=TEXT_MAIN,
            font=(FONT_UI, 11, "bold"),
            command=self._open_settings,
        )
        gear_btn.pack(side="right")
        self._gear_btn = gear_btn

        badge = ctk.CTkLabel(
            right,
            text="  \u25CF SYSTEM READY  ",
            font=(FONT_UI, 10, "bold"),
            text_color=BADGE_READY_TEXT,
            fg_color=BADGE_READY_BG,
            corner_radius=12,
            padx=8,
            pady=3,
        )
        badge.pack(anchor="e", pady=(2, 2))
        self._badge_ready = badge

        clock = ctk.CTkLabel(
            right,
            text="",
            font=(FONT_MONO, 12, "bold"),
            text_color=CLOCK_TEXT,
        )
        clock.pack(anchor="e", pady=(2, 0))
        self._clock_label = clock

    def _start_all(self):
        """Mulai semua fitur sekaligus."""
        for feat in FEATURES:
            key = feat["key"]
            if key not in self.controllers or not self.controllers[key].running:
                self._start_feature(key, feat)
        self.write_log("[control] \u25b6 START ALL - semua fitur dijalankan.", channel="all")

    def _stop_all(self):
        """Hentikan semua fitur yang sedang berjalan."""
        for feat in FEATURES:
            key = feat["key"]
            if key in self.controllers and self.controllers[key].running:
                self._stop_feature(key)
        self.write_log("[control] \u23f9 STOP ALL - semua fitur dihentikan.", channel="all")

    # =================================================
    # Feature Cards (2 Baris x 3 Kolom)
    # =================================================

    def create_feature_sections(self):

        self.features_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.features_frame.pack(fill="x", padx=20, pady=(0, 8))

        for col in range(3):
            self.features_frame.grid_columnconfigure(col, weight=1)

        for i, feat in enumerate(FEATURES):
            card = self._create_feature_card(feat)
            row, col = i // 3, i % 3

            card.grid(
                row=row,
                column=col,
                sticky="ew",
                padx=5,
                pady=5,
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
        top.pack(fill="x", padx=14, pady=(10, 4))

        # Icon badge
        icon = ctk.CTkLabel(
            top,
            text=feat["icon"],
            font=(FONT_UI, 20),
            text_color=WHITE,
            fg_color=feat["color"],
            corner_radius=10,
            width=40,
            height=40,
        )
        icon.pack(side="left", padx=(0, 10))

        name_col = ctk.CTkFrame(top, fg_color="transparent")
        name_col.pack(side="left", fill="x", expand=True)

        name = ctk.CTkLabel(
            name_col,
            text=feat["label"],
            font=(FONT_UI, 13, "bold"),
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
        self._feature_desc_labels[key] = desc

        status_label = ctk.CTkLabel(
            top,
            text="  \u25CF READY  ",
            font=(FONT_UI, 10, "bold"),
            text_color=BADGE_READY_TEXT,
            fg_color=BADGE_READY_BG,
            corner_radius=12,
            padx=8,
            pady=3,
        )
        status_label.pack(side="right", padx=(6, 0))

        bottom = ctk.CTkFrame(card, fg_color="transparent")
        bottom.pack(fill="x", padx=14, pady=(4, 10))

        chip_port = ctk.CTkLabel(
            bottom,
            text=f"\U0001F50C Port {port}",
            font=(FONT_MONO, 10, "bold"),
            text_color=feat["color"],
            fg_color=BG_INPUT,
            corner_radius=6,
            padx=7,
            pady=2,
        )
        chip_port.pack(side="left", padx=(0, 6))

        tag_text = feat.get("tag", "")
        if tag_text:
            chip_tag = ctk.CTkLabel(
                bottom,
                text=tag_text,
                font=(FONT_UI, 10, "bold"),
                text_color=TAG_TEXT,
                fg_color=TAG_BG,
                border_width=1,
                border_color=TAG_BORDER,
                corner_radius=6,
                padx=6,
                pady=2,
            )
            chip_tag.pack(side="left")
            self._feature_tag_labels[key] = chip_tag

        stop_btn = ctk.CTkButton(
            bottom,
            text="STOP",
            width=65,
            height=28,
            corner_radius=7,
            fg_color=RED_LIGHT,
            hover_color=RED_LIGHT_HOVER,
            border_width=1.2,
            border_color=RED_LIGHT_BORDER,
            text_color=RED_MAIN,
            font=(FONT_UI, 10, "bold"),
            command=lambda k=key: self._stop_feature(k),
        )
        stop_btn.pack(side="right", padx=(5, 0))
        setattr(self, f"{key}_stop_btn", stop_btn)

        start_btn = ctk.CTkButton(
            bottom,
            text="START",
            width=75,
            height=28,
            corner_radius=7,
            fg_color=feat["color"],
            hover_color=feat["hover"],
            text_color=WHITE,
            font=(FONT_UI, 10, "bold"),
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
        elif key == "canclwork":
            ctrl.start_canclwork()
        elif key == "dispatch":
            ctrl.start_dispatch()
        elif key == "dispatch_incident":
            ctrl.start_dispatch_incident()
        elif key == "change_service_id":
            ctrl.start_change_service_id()
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
            text="📊 Export Excel",
            width=110,
            height=26,
            corner_radius=8,
            fg_color="#107C41",
            hover_color="#0B5E31",
            text_color=WHITE,
            font=(FONT_UI, 11, "bold"),
            command=self._show_export_dialog,
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            header,
            text="📋 Salin",
            width=68,
            height=26,
            corner_radius=8,
            fg_color=BG_BTN_SECONDARY,
            hover_color=BG_BTN_SECONDARY_HOVER,
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
            fg_color=BG_BTN_SECONDARY,
            hover_color=BG_BTN_SECONDARY_HOVER,
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
            segmented_button_unselected_color=TAB_UNSELECTED_BG,
            segmented_button_unselected_hover_color=TAB_UNSELECTED_HOVER,
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
                border_color=BORDER_SUBTLE,
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
        self.write_log(f"  CANCLWORK         -> port {CHROME_PORTS['CANCLWORK']}")
        self.write_log(f"  DISPATCH          -> port {CHROME_PORTS['DISPATCH']}")
        self.write_log(f"  DISPATCH INCIDENT -> port {CHROME_PORTS['DISPATCH_INCIDENT']}")
        self.write_log(f"  CHANGE SERVICE ID -> port {CHROME_PORTS['CHANGE_SERVICE_ID']}")
        self.write_log(f"  GAMAS             -> port {CHROME_PORTS['GAMAS']}")
        self.write_log(f"  REPORT            -> port {CHROME_PORTS['REPORT']}")
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

    def _show_export_dialog(self):
        """Dialog pilih rentang tanggal untuk export (dari kapan sampai kapan) — record mulai hari ini."""
        from datetime import datetime, timedelta
        self.write_log("[export] dialog dibuka — isi Tanggal Mulai & Akhir lalu klik ⬇ Export", channel="all")
        dlg = ctk.CTkToplevel(self)
        dlg.title("Export History — Pilih Tanggal")
        dlg.geometry("420x320")
        dlg.resizable(False, False)
        dlg.configure(fg_color=BG_HEADER)
        dlg.transient(self)
        dlg.grab_set()

        # Header
        hdr = ctk.CTkFrame(dlg, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(14, 6))
        ctk.CTkLabel(hdr, text="📊 Export History Excel", font=(FONT_UI, 16, "bold"), text_color=TEXT_MAIN).pack(anchor="w")
        ctk.CTkLabel(hdr, text="Record mulai hari ini (27 Agu 2026). Pilih rentang tanggal untuk export.", font=(FONT_UI, 10), text_color=TEXT_DIM, wraplength=380, justify="left").pack(anchor="w", pady=(2,0))

        body = ctk.CTkFrame(dlg, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=6)

        # Default 30 hari: mulai hari ini 00:00, akhir hari ini
        today = datetime.now()
        default_start = (today - timedelta(days=29)).strftime("%Y-%m-%d")
        default_end = today.strftime("%Y-%m-%d")

        ctk.CTkLabel(body, text="Tanggal Mulai (YYYY-MM-DD):", font=(FONT_UI, 11, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(6,2))
        e_start = ctk.CTkEntry(body, height=32, font=(FONT_MONO, 11), fg_color=BG_INPUT, border_color=BORDER_SUBTLE, text_color=TEXT_MAIN)
        e_start.insert(0, default_start)
        e_start.pack(fill="x")

        ctk.CTkLabel(body, text="Tanggal Akhir (YYYY-MM-DD):", font=(FONT_UI, 11, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(8,2))
        e_end = ctk.CTkEntry(body, height=32, font=(FONT_MONO, 11), fg_color=BG_INPUT, border_color=BORDER_SUBTLE, text_color=TEXT_MAIN)
        e_end.insert(0, default_end)
        e_end.pack(fill="x")

        # Quick buttons
        quick = ctk.CTkFrame(body, fg_color="transparent")
        quick.pack(fill="x", pady=(10, 4))
        def _set_range(d):
            s = (today - timedelta(days=d-1)).strftime("%Y-%m-%d") if d>0 else today.strftime("%Y-%m-%d")
            e = today.strftime("%Y-%m-%d")
            e_start.delete(0, "end"); e_start.insert(0, s)
            e_end.delete(0, "end"); e_end.insert(0, e)

        for label, d in [("Hari Ini",1), ("7 Hari",7), ("30 Hari",30)]:
            ctk.CTkButton(quick, text=label, width=70, height=26, corner_radius=7, fg_color=BG_BTN_SECONDARY, hover_color=BG_BTN_SECONDARY_HOVER, text_color=TEXT_MAIN, font=(FONT_UI, 10, "bold"), command=lambda v=d: _set_range(v)).pack(side="left", padx=(0,6))

        info = ctk.CTkLabel(body, text="Kosong sebelum 27 Agu → hanya 27 Agu ke depan yang ada. File: logs/history_YYYY-MM-DD.csv + history_all.csv", font=(FONT_UI, 9), text_color=TEXT_DIM, wraplength=380, justify="left")
        info.pack(anchor="w", pady=(8,0))

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(10, 14))

        def _do_export():
            s = e_start.get().strip()
            e = e_end.get().strip()
            # Validasi format
            try:
                from datetime import datetime as _dt
                sd = _dt.strptime(s, "%Y-%m-%d")
                ed = _dt.strptime(e, "%Y-%m-%d")
                if ed < sd:
                    raise ValueError("Tanggal akhir < mulai")
                days = (ed - sd).days + 1
                dlg.destroy()
                # Panggil export dengan range eksplisit
                self._export_history_range(s, e, days)
            except Exception as ex:
                self.write_log(f"[export] Format tanggal salah: {ex} (pakai YYYY-MM-DD)", channel="all")

        ctk.CTkButton(btn_row, text="⬇ Export", width=110, height=32, corner_radius=8, fg_color="#107C41", hover_color="#0B5E31", text_color=WHITE, font=(FONT_UI, 11, "bold"), command=_do_export).pack(side="left")
        ctk.CTkButton(btn_row, text="Batal", width=80, height=32, corner_radius=8, fg_color=BG_BTN_SECONDARY, hover_color=BG_BTN_SECONDARY_HOVER, text_color=TEXT_MAIN, font=(FONT_UI, 11, "bold"), command=dlg.destroy).pack(side="left", padx=(8,0))

    def _export_history_range(self, start_str, end_str, days):
        """Helper untuk dialog: export dengan start/end eksplisit."""
        try:
            import csv
            import os
            from datetime import datetime, timedelta
            from pathlib import Path
            self.write_log(f"[export] mulai export {start_str} s/d {end_str} ({days} hari)...", channel="all")
            base = Path(__file__).resolve().parents[1]
            history_all = base / "logs" / "history_all.csv"
            history_dir = base / "logs"
            if not history_all.exists():
                self.write_log("[export] history_all.csv belum ada", channel="all")
                return
            start_dt = datetime.strptime(start_str, "%Y-%m-%d")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d")
            rows = []
            header = None
            with open(history_all, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames
                for r in reader:
                    tgl_str = r.get("Waktu Proses") or r.get("Tanggal Selesai Dikerjakan") or ""
                    try:
                        dt = datetime.strptime(tgl_str[:10], "%Y-%m-%d")
                    except Exception:
                        continue
                    if start_dt.date() <= dt.date() <= end_dt.date():
                        rows.append(r)
            if not rows:
                self.write_log(f"[export] Tidak ada tiket {start_str} s/d {end_str}", channel="all")
                return
            # Reuse logic export Excel (duplikat dari _export_history agar dialog mandiri)
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
            from openpyxl.formatting.rule import CellIsRule
            out = history_dir / f"History_{start_dt.strftime('%Y%m%d')}_to_{end_dt.strftime('%Y%m%d')}.xlsx"
            # --- Build per-fitur sheets ---
            from collections import defaultdict
            grouped = defaultdict(list)
            for r in rows:
                fitur = (r.get("Fitur") or "UNKNOWN").strip().upper()
                if fitur not in ["CANCLWORK","DISPATCH","DISPATCH_INCIDENT","GAMAS","CHANGE_SERVICE_ID","REPORT"]:
                    fitur = "LAINNYA"
                grouped[fitur].append(r)

            def _make_sheet(wb, title, rows_sub, header, start_str, end_str, is_summary=False):
                ws = wb.create_sheet(title=title) if not is_summary else wb.active
                if is_summary:
                    ws.title = title
                ws.sheet_properties.pageSetUpPr.fitToPage = True
                ws.page_setup.fitToWidth = 1
                ws.page_setup.fitToHeight = 0
                ws.page_setup.orientation = "landscape"
                ws.page_setup.paperSize = ws.PAPERSIZE_A3
                ws.merge_cells("A1:M1")
                t = ws["A1"]
                t.value = f"{'RINGKASAN' if is_summary else title} — {start_str} s/d {end_str} ({len(rows_sub)} tiket)" if not is_summary else f"HISTORY TIKET SYGAP → INSERA — {start_dt.strftime('%d %b %Y')} s/d {end_dt.strftime('%d %b %Y')} ({len(rows)} tiket) | Per sheet = per fitur"
                t.font = Font(size=12 if is_summary else 11, bold=True, color="1F4E78")
                t.alignment = Alignment(horizontal="center", vertical="center")
                ws.row_dimensions[1].height = 20
                ws.merge_cells("A2:M2")
                s = ws["A2"]
                s.value = f"Sumber: {history_all.name} — {start_str} s/d {end_str} | Sheet per fitur, jangan campur" if is_summary else f"Fitur: {title} — {len(rows_sub)} tiket"
                s.font = Font(size=8, italic=True, color="5B7FA6")
                s.alignment = Alignment(horizontal="center")
                ws.row_dimensions[2].height = 14
                header_row = 4
                header_font = Font(bold=True, color="FFFFFF", size=9)
                header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
                thin_border = Border(left=Side(style="thin", color="B4C6E7"), right=Side(style="thin", color="B4C6E7"), top=Side(style="thin", color="B4C6E7"), bottom=Side(style="thin", color="B4C6E7"))
                center = Alignment(horizontal="center", vertical="center", wrap_text=True)
                left_wrap = Alignment(horizontal="left", vertical="center", wrap_text=True)
                for col, h in enumerate(header, start=1):
                    c = ws.cell(row=header_row, column=col, value=h)
                    c.font = header_font
                    c.fill = header_fill
                    c.alignment = center
                    c.border = thin_border
                ws.row_dimensions[header_row].height = 34
                widths = [19,13,20,20,38,19,19,22,22,14,32,12,12]
                for i,w in enumerate(widths, start=1):
                    ws.column_dimensions[get_column_letter(i)].width = w
                ws.freeze_panes = "A5"
                ws.auto_filter.ref = f"A{header_row}:M{header_row}"
                if not rows_sub:
                    ws.merge_cells("A5:M5")
                    c = ws["A5"]
                    c.value = "Tidak ada tiket untuk fitur ini di rentang tanggal tersebut."
                    c.font = Font(size=9, italic=True, color="7F7F7F")
                    c.alignment = center
                    ws.row_dimensions[5].height = 22
                else:
                    for r_idx, r in enumerate(rows_sub, start=5):
                        for c_idx, h in enumerate(header, start=1):
                            val = r.get(h, "")
                            c = ws.cell(row=r_idx, column=c_idx, value=val)
                            c.font = Font(size=9)
                            c.border = thin_border
                            c.alignment = left_wrap if c_idx in (5,11) else center
                            if c_idx in (1,6,7):
                                c.number_format = "yyyy-mm-dd hh:mm:ss"
                        ws.row_dimensions[r_idx].height = 18
                        if r_idx % 2 == 0:
                            for c_idx in range(1, len(header)+1):
                                ws.cell(row=r_idx, column=c_idx).fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
                    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                    ws.conditional_formatting.add(f"L5:L{5+len(rows_sub)}", CellIsRule(operator="equal", formula=['"SUCCESS"'], fill=green_fill, font=Font(color="006100")))
                    ws.conditional_formatting.add(f"L5:L{5+len(rows_sub)}", CellIsRule(operator="equal", formula=['"FAILED"'], fill=red_fill, font=Font(color="9C0006")))
                ws.sheet_properties.pageSetUpPr.fitToPage = True
                ws.page_setup.orientation = "landscape"
                ws.page_setup.paperSize = ws.PAPERSIZE_A3
                ws.page_setup.fitToWidth = 1
                ws.print_title_rows = f"{header_row}:{header_row}"
                return ws

            wb = openpyxl.Workbook()
            # Summary first
            _make_sheet(wb, "RINGKASAN", rows, header, start_str, end_str, is_summary=True)
            # Per fitur sheets in order
            order = ["DISPATCH","DISPATCH_INCIDENT","CANCLWORK","GAMAS","CHANGE_SERVICE_ID","REPORT","LAINNYA"]
            for fitur in order:
                if fitur in grouped or fitur in ["DISPATCH","GAMAS","CANCLWORK"]:  # selalu buat sheet utama walau kosong
                    _make_sheet(wb, fitur, grouped.get(fitur, []), header, start_str, end_str, is_summary=False)
            # Hapus sheet default jika ada duplikat
            wb.save(out)
            self.write_log(f"[export] Excel per-fitur tersimpan: {out} ({len(rows)} tiket, {len(grouped)} fitur) — sheets: RINGKASAN + {', '.join([k for k in order if k in grouped])} | {start_str} s/d {end_str}", channel="all")
            try:
                os.startfile(str(out))
            except Exception:
                pass
        except Exception as e:
            self.write_log(f"[export] Gagal export range: {e}", channel="all")

    def _export_history(self, days=30):
        """Export history sebulan kebelakang ke Excel (tombol di header log)."""
        try:
            import csv
            import os
            from datetime import datetime, timedelta
            from pathlib import Path

            base = Path(__file__).resolve().parents[1]
            history_all = base / "logs" / "history_all.csv"
            history_dir = base / "logs"

            if not history_all.exists():
                self.write_log("[export] history_all.csv belum ada — bot belum log sejak aktivasi. Cek history_2026-07-15_to_2026-07-21.csv", channel="all")
                return

            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=days)

            # Baca & filter
            rows = []
            header = None
            with open(history_all, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames
                for r in reader:
                    tgl_str = r.get("Waktu Proses") or r.get("Waktu") or r.get("Tanggal Selesai Dikerjakan") or ""
                    try:
                        dt = datetime.strptime(tgl_str[:10], "%Y-%m-%d")
                    except Exception:
                        continue
                    if start_dt.date() <= dt.date() <= end_dt.date():
                        rows.append(r)

            if not rows:
                self.write_log(f"[export] Tidak ada tiket dalam {days} hari terakhir ({start_dt.strftime('%Y-%m-%d')} s/d {end_dt.strftime('%Y-%m-%d')})", channel="all")
                return

            # Coba export Excel via openpyxl
            try:
                import openpyxl
                from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
                from openpyxl.utils import get_column_letter
                from openpyxl.formatting.rule import CellIsRule
            except Exception as e:
                # Fallback CSV filtered
                out_csv = history_dir / f"History_{start_dt.strftime('%Y%m%d')}_to_{end_dt.strftime('%Y%m%d')}.csv"
                with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.DictWriter(f, fieldnames=header)
                    w.writeheader()
                    w.writerows(rows)
                self.write_log(f"[export] openpyxl tidak ada, export CSV: {out_csv} ({len(rows)} baris)", channel="all")
                try:
                    os.startfile(str(out_csv))
                except Exception:
                    pass
                return

            out = history_dir / f"History_{start_dt.strftime('%Y%m%d')}_to_{end_dt.strftime('%Y%m%d')}.xlsx"
            # --- Build per-fitur sheets (RINGKASAN + per fitur) ---
            from collections import defaultdict
            grouped = defaultdict(list)
            for r in rows:
                fitur = (r.get("Fitur") or "UNKNOWN").strip().upper()
                if fitur not in ["CANCLWORK","DISPATCH","DISPATCH_INCIDENT","GAMAS","CHANGE_SERVICE_ID","REPORT"]:
                    fitur = "LAINNYA"
                grouped[fitur].append(r)

            def _make_sheet2(wb, title, rows_sub, header, start_dt, end_dt, is_summary=False):
                ws = wb.create_sheet(title=title) if not is_summary else wb.active
                if is_summary:
                    ws.title = title
                ws.sheet_properties.pageSetUpPr.fitToPage = True
                ws.page_setup.fitToWidth = 1
                ws.page_setup.fitToHeight = 0
                ws.page_setup.orientation = "landscape"
                ws.page_setup.paperSize = ws.PAPERSIZE_A3
                ws.merge_cells("A1:M1")
                t = ws["A1"]
                t.value = f"{'RINGKASAN' if is_summary else title} — {start_dt.strftime('%d %b %Y')} s/d {end_dt.strftime('%d %b %Y')} ({len(rows_sub)} tiket)" if not is_summary else f"HISTORY TIKET SYGAP → INSERA — {start_dt.strftime('%d %b %Y')} s/d {end_dt.strftime('%d %b %Y')} ({len(rows)} tiket) | Per sheet = per fitur"
                t.font = Font(size=12 if is_summary else 11, bold=True, color="1F4E78")
                t.alignment = Alignment(horizontal="center", vertical="center")
                ws.row_dimensions[1].height = 20
                ws.merge_cells("A2:M2")
                s = ws["A2"]
                s.value = f"Sumber: {history_all.name} — {start_dt.strftime('%Y-%m-%d')} s/d {end_dt.strftime('%Y-%m-%d')} | Sheet per fitur, jangan campur" if is_summary else f"Fitur: {title} — {len(rows_sub)} tiket"
                s.font = Font(size=8, italic=True, color="5B7FA6")
                s.alignment = Alignment(horizontal="center")
                ws.row_dimensions[2].height = 14
                header_row = 4
                header_font = Font(bold=True, color="FFFFFF", size=9)
                header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
                thin_border = Border(left=Side(style="thin", color="B4C6E7"), right=Side(style="thin", color="B4C6E7"), top=Side(style="thin", color="B4C6E7"), bottom=Side(style="thin", color="B4C6E7"))
                center = Alignment(horizontal="center", vertical="center", wrap_text=True)
                left_wrap = Alignment(horizontal="left", vertical="center", wrap_text=True)
                for col, h in enumerate(header, start=1):
                    c = ws.cell(row=header_row, column=col, value=h)
                    c.font = header_font
                    c.fill = header_fill
                    c.alignment = center
                    c.border = thin_border
                ws.row_dimensions[header_row].height = 34
                widths = [19,13,20,20,38,19,19,22,22,14,32,12,12]
                for i,w in enumerate(widths, start=1):
                    ws.column_dimensions[get_column_letter(i)].width = w
                ws.freeze_panes = "A5"
                ws.auto_filter.ref = f"A{header_row}:M{header_row}"
                if not rows_sub:
                    ws.merge_cells("A5:M5")
                    c = ws["A5"]
                    c.value = "Tidak ada tiket untuk fitur ini di rentang tanggal tersebut."
                    c.font = Font(size=9, italic=True, color="7F7F7F")
                    c.alignment = center
                    ws.row_dimensions[5].height = 22
                else:
                    for r_idx, r in enumerate(rows_sub, start=5):
                        for c_idx, h in enumerate(header, start=1):
                            val = r.get(h, "")
                            c = ws.cell(row=r_idx, column=c_idx, value=val)
                            c.font = Font(size=9)
                            c.border = thin_border
                            c.alignment = left_wrap if c_idx in (5,11) else center
                            if c_idx in (1,6,7):
                                c.number_format = "yyyy-mm-dd hh:mm:ss"
                        ws.row_dimensions[r_idx].height = 18
                        if r_idx % 2 == 0:
                            for c_idx in range(1, len(header)+1):
                                ws.cell(row=r_idx, column=c_idx).fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
                    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                    ws.conditional_formatting.add(f"L5:L{5+len(rows_sub)}", CellIsRule(operator="equal", formula=['"SUCCESS"'], fill=green_fill, font=Font(color="006100")))
                    ws.conditional_formatting.add(f"L5:L{5+len(rows_sub)}", CellIsRule(operator="equal", formula=['"FAILED"'], fill=red_fill, font=Font(color="9C0006")))
                ws.sheet_properties.pageSetUpPr.fitToPage = True
                ws.page_setup.orientation = "landscape"
                ws.page_setup.paperSize = ws.PAPERSIZE_A3
                ws.page_setup.fitToWidth = 1
                ws.print_title_rows = f"{header_row}:{header_row}"
                return ws

            wb = openpyxl.Workbook()
            _make_sheet2(wb, "RINGKASAN", rows, header, start_dt, end_dt, is_summary=True)
            order = ["DISPATCH","DISPATCH_INCIDENT","CANCLWORK","GAMAS","CHANGE_SERVICE_ID","REPORT","LAINNYA"]
            for fitur in order:
                if fitur in grouped or fitur in ["DISPATCH","GAMAS","CANCLWORK"]:
                    _make_sheet2(wb, fitur, grouped.get(fitur, []), header, start_dt, end_dt, is_summary=False)
            wb.save(out)
            self.write_log(f"[export] Excel per-fitur tersimpan: {out} ({len(rows)} tiket, {len(grouped)} fitur) — sheets: RINGKASAN + {', '.join([k for k in order if k in grouped])} | {start_dt.strftime('%Y-%m-%d')} s/d {end_dt.strftime('%Y-%m-%d')}", channel="all")
            try:
                os.startfile(str(out))
                self.write_log(f"[export] Membuka file Excel...", channel="all")
            except Exception:
                pass
        except Exception as e:
            self.write_log(f"[export] Gagal export history: {e}", channel="all")

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
            text_color=BADGE_READY_TEXT,
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
            TELEGRAM_BOT_TOKEN_DISPATCH_INCIDENT,
            TELEGRAM_BOT_TOKEN_GAMAS,
            TELEGRAM_BOT_TOKEN_CHANGE_SERVICE_ID,
            TELEGRAM_CHAT_IDS,
            TELEGRAM_ALLOWED_USER_IDS,
            REPORT_CHAT_IDS,
        )

        specs = [
            ("canclwork", TELEGRAM_BOT_TOKEN_CANCLWORK, "CANCLWORK"),
            ("dispatch", TELEGRAM_BOT_TOKEN_DISPATCH, "DISPATCH"),
            ("dispatch_incident", TELEGRAM_BOT_TOKEN_DISPATCH_INCIDENT, "DISPATCH_INCIDENT"),
            ("change_service_id", TELEGRAM_BOT_TOKEN_CHANGE_SERVICE_ID, "CHANGE_SERVICE_ID"),
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

# =====================================================
# Settings Modal (CTkToplevel) - UI & Settings Studio
# =====================================================

    def _open_settings(self):
        from app.user_settings import DEFAULTS, USER_SETTINGS_PATH

        win = ctk.CTkToplevel(self)
        win.title("Pengaturan Bot & UI Studio")
        win.geometry("660x720")
        win.resizable(False, False)
        win.configure(fg_color=BG_HEADER)
        win.transient(self)
        win.grab_set()

        cur = self.user_settings or dict(DEFAULTS)

        # Header
        hdr = ctk.CTkFrame(win, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(16, 0))
        ctk.CTkLabel(
            hdr, text="⚙  Pengaturan & UI Studio",
            font=(FONT_UI, 20, "bold"), text_color=RED_MAIN,
        ).pack(side="left")
        ctk.CTkLabel(
            hdr, text="Simpan = langsung aktif di dashboard",
            font=(FONT_UI, 11), text_color=TEXT_DIM,
        ).pack(side="left", padx=(12, 0), pady=(4, 0))

        # Tab View (4 Tabs)
        tabs = ctk.CTkTabview(
            win, corner_radius=10, fg_color=BG_HEADER,
            segmented_button_selected_color=RED_MAIN,
            segmented_button_selected_hover_color=RED_HOVER,
            segmented_button_unselected_color=BG_INPUT,
            segmented_button_unselected_hover_color=BG_BTN_SECONDARY_HOVER,
            text_color=TEXT_MAIN,
        )
        tabs.pack(fill="both", expand=True, padx=20, pady=(6, 6))

        tab_general = tabs.add("Umum")
        tab_studio = tabs.add("UI Studio")
        tab_terminal = tabs.add("Terminal Log")
        tab_features = tabs.add("Fitur & Safety")

        # ── Helper builders ──────────────────────────
        def _entry_row(parent, label, value, hint=None):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            box.pack(fill="x", pady=4)
            ctk.CTkLabel(box, text=label, font=(FONT_UI, 12, "bold"),
                         text_color=TEXT_MAIN).pack(anchor="w")
            entry = ctk.CTkEntry(box, font=(FONT_MONO, 12), fg_color=BG_INPUT,
                                 border_color=BORDER_SUBTLE, text_color=TEXT_MAIN,
                                 corner_radius=8, height=32)
            entry.insert(0, str(value))
            entry.pack(fill="x", pady=(2, 0))
            if hint:
                ctk.CTkLabel(box, text=hint, font=(FONT_UI, 10),
                             text_color=TEXT_DIM).pack(anchor="w", pady=(1, 0))
            return entry

        def _switch_row(parent, label, value, hint=None):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            box.pack(fill="x", pady=4)
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkLabel(row, text=label, font=(FONT_UI, 12, "bold"),
                         text_color=TEXT_MAIN).pack(side="left")
            sw = ctk.CTkSwitch(row, text="", width=46,
                               fg_color=("#CBD5E1", "#334155"), progress_color=RED_MAIN,
                               button_color=WHITE, button_hover_color="#F1F5F9")
            if value:
                sw.select()
            else:
                sw.deselect()
            sw.pack(side="right")
            if hint:
                ctk.CTkLabel(box, text=hint, font=(FONT_UI, 10),
                             text_color=TEXT_DIM).pack(anchor="w", pady=(1, 0))
            return sw

        def _dropdown_row(parent, label, values, current, hint=None):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            box.pack(fill="x", pady=4)
            ctk.CTkLabel(box, text=label, font=(FONT_UI, 12, "bold"),
                         text_color=TEXT_MAIN).pack(anchor="w")
            dd = ctk.CTkOptionMenu(box, values=values, fg_color=BG_INPUT,
                                   button_color=("#CBD5E1", "#334155"), button_hover_color=("#94A3B8", "#475569"),
                                   dropdown_fg_color=BG_HEADER, dropdown_hover_color=BG_CARD_HOVER,
                                   text_color=TEXT_MAIN, font=(FONT_UI, 12),
                                   corner_radius=8, height=32)
            dd.set(current)
            dd.pack(fill="x", pady=(2, 0))
            if hint:
                ctk.CTkLabel(box, text=hint, font=(FONT_UI, 10),
                             text_color=TEXT_DIM).pack(anchor="w", pady=(1, 0))
            return dd

        def _slider_row(parent, label, value, from_, to_, hint=None, unit="", on_change=None):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            box.pack(fill="x", pady=4)
            top_r = ctk.CTkFrame(box, fg_color="transparent")
            top_r.pack(fill="x")
            ctk.CTkLabel(top_r, text=label, font=(FONT_UI, 12, "bold"),
                         text_color=TEXT_MAIN).pack(side="left")
            val_lbl = ctk.CTkLabel(top_r, text=f"{int(value)}{unit}",
                                   font=(FONT_MONO, 12, "bold"),
                                   text_color=RED_MAIN)
            val_lbl.pack(side="right")
            sl = ctk.CTkSlider(box, from_=from_, to=to_, number_of_steps=to_ - from_,
                               fg_color=("#CBD5E1", "#334155"), progress_color=RED_MAIN,
                               button_color=RED_MAIN, button_hover_color=RED_HOVER)
            sl.set(value)
            def _handler(v):
                val_lbl.configure(text=f"{int(v)}{unit}")
                if on_change:
                    on_change(v)
            sl.configure(command=_handler)
            sl.pack(fill="x", pady=(2, 0))
            if hint:
                ctk.CTkLabel(box, text=hint, font=(FONT_UI, 10),
                             text_color=TEXT_DIM).pack(anchor="w", pady=(1, 0))
            return sl

        def _section_label(parent, text):
            ctk.CTkLabel(parent, text=text, font=(FONT_UI, 13, "bold"),
                         text_color="#0284C7").pack(anchor="w", pady=(8, 3))

        # ── TAB 1: UMUM ─────────────────────────────
        scroll_gen = ctk.CTkScrollableFrame(tab_general, fg_color="transparent")
        scroll_gen.pack(fill="both", expand=True, padx=4, pady=4)

        _section_label(scroll_gen, "🔄  Loop & Scan Interval")
        e_loop = _entry_row(scroll_gen,
            "Loop Interval (detik)",
            cur.get("loop_interval", DEFAULTS["loop_interval"]),
            "Jeda scan ulang tiap fitur. Minimum 60 detik.",
        )

        _section_label(scroll_gen, "👤  Koordinator & Identitas")
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

        # ── TAB 2: UI STUDIO ─────────────────────────
        scroll_stu = ctk.CTkScrollableFrame(tab_studio, fg_color="transparent")
        scroll_stu.pack(fill="both", expand=True, padx=4, pady=4)

        _section_label(scroll_stu, "🎭  Tema Aplikasi")
        dd_theme = _dropdown_row(scroll_stu,
            "Mode Tampilan", ["light", "dark"],
            cur.get("theme", DEFAULTS["theme"]),
            "Terapkan instan tanpa restart.",
        )

        _section_label(scroll_stu, "🎨  Warna Aksen Kustom (Signature Color)")
        _ACCENT_PRESETS = {
            "Merah (Telkom)": "#DC2626",
            "Biru Langit": "#0284C7",
            "Ungu Neon": "#7C3AED",
            "Hijau Emerald": "#059669",
            "Oranye Sunset": "#EA580C",
            "Pink Fuchsia": "#DB2777",
            "Indigo Cyber": "#4F46E5",
            "Teal Modern": "#0D9488",
            "Emas Amber": "#D97706",
            "Slate Minimal": "#475569",
        }

        # Preset Dropdown + Custom Hex Row
        accent_curr = cur.get("accent_color", DEFAULTS["accent_color"])
        dd_accent = _dropdown_row(scroll_stu,
            "Preset Warna Aksen",
            list(_ACCENT_PRESETS.keys()) + ["Kustom (Hex)"],
            next((k for k, v in _ACCENT_PRESETS.items() if v.lower() == accent_curr.lower()), "Kustom (Hex)"),
            "Pilih dari palet preset atau masukkan kode HEX di bawah.",
        )

        hex_box = ctk.CTkFrame(scroll_stu, fg_color="transparent")
        hex_box.pack(fill="x", pady=3)
        ctk.CTkLabel(hex_box, text="Kode Hex Kustom (#RRGGBB):", font=(FONT_UI, 11, "bold"),
                     text_color=TEXT_MAIN).pack(side="left")
        e_hex = ctk.CTkEntry(hex_box, width=100, height=28, font=(FONT_MONO, 11),
                             fg_color=BG_INPUT, border_color=BORDER_SUBTLE, text_color=TEXT_MAIN)
        e_hex.insert(0, accent_curr)
        e_hex.pack(side="left", padx=(8, 10))

        _preview_swatch = ctk.CTkLabel(
            hex_box, text="  ████  ",
            font=(FONT_MONO, 12, "bold"),
            text_color=accent_curr,
            fg_color=BG_INPUT, corner_radius=6, padx=4, pady=2,
        )
        _preview_swatch.pack(side="left")

        def _update_swatch_from_hex(*_):
            val = e_hex.get().strip()
            if val.startswith("#") and len(val) in (4, 7):
                try:
                    _preview_swatch.configure(text_color=val)
                except Exception:
                    pass

        e_hex.bind("<KeyRelease>", _update_swatch_from_hex)

        def _on_preset_change(choice):
            if choice in _ACCENT_PRESETS:
                hex_val = _ACCENT_PRESETS[choice]
                e_hex.delete(0, "end")
                e_hex.insert(0, hex_val)
                _preview_swatch.configure(text_color=hex_val)

        dd_accent.configure(command=_on_preset_change)

        # Quick palette chips
        chip_bar = ctk.CTkFrame(scroll_stu, fg_color="transparent")
        chip_bar.pack(fill="x", pady=(2, 6))
        for pname, phex in list(_ACCENT_PRESETS.items())[:6]:
            btn_chip = ctk.CTkButton(
                chip_bar, text="", width=24, height=20, corner_radius=5,
                fg_color=phex, hover_color=phex,
                command=lambda h=phex, n=pname: (
                    e_hex.delete(0, "end"), e_hex.insert(0, h),
                    dd_accent.set(n), _preview_swatch.configure(text_color=h)
                ),
            )
            btn_chip.pack(side="left", padx=2)

        def _live_resize_logo(v):
            if hasattr(self, "_logo_label") and self._logo_label and os.path.exists(LOGO_PATH):
                try:
                    from PIL import Image
                    pil_img = Image.open(LOGO_PATH).convert("RGBA")
                    self._logo_img = ctk.CTkImage(
                        light_image=pil_img,
                        dark_image=pil_img,
                        size=(int(v), int(v)),
                    )
                    self._logo_label.configure(image=self._logo_img, text="")
                except Exception:
                    pass

        _section_label(scroll_stu, "🐱  Logo Maskot & Header")
        sw_logo = _switch_row(scroll_stu,
            "Tampilkan Logo Maskot", cur.get("show_logo", DEFAULTS.get("show_logo", True)),
            "Sembunyikan atau tampilkan gambar logo di header.",
        )
        sl_logosize = _slider_row(scroll_stu,
            "Ukuran Logo di Header", cur.get("logo_size", DEFAULTS.get("logo_size", 115)),
            60, 160, "Dimensi tampilan logo (60px – 160px).", unit="px",
            on_change=_live_resize_logo,
        )
        sw_clock = _switch_row(scroll_stu,
            "Tampilkan Jam Digital", cur.get("show_clock", DEFAULTS.get("show_clock", True)),
            "Tampilkan jam digital live di pojok kanan header.",
        )

        _section_label(scroll_stu, "🗂️  Kartu Fitur Dashboard")
        sw_desc = _switch_row(scroll_stu,
            "Tampilkan Deskripsi Fitur", cur.get("show_feature_desc", DEFAULTS.get("show_feature_desc", True)),
            "Tampilkan teks penjelasan singkat di bawah judul tiap kartu.",
        )
        sw_tags = _switch_row(scroll_stu,
            "Tampilkan Tag / Badge Spesifikasi", cur.get("show_feature_tags", DEFAULTS.get("show_feature_tags", True)),
            "Tampilkan chip badge target (misal: MO-INSERA #32, BISCUIT API).",
        )

        # ── TAB 3: TERMINAL LOG ──────────────────────
        scroll_term = ctk.CTkScrollableFrame(tab_terminal, fg_color="transparent")
        scroll_term.pack(fill="both", expand=True, padx=4, pady=4)

        _section_label(scroll_term, "🖥️  Gaya Console Terminal")
        _TERM_NAMES = {
            "obsidian": "Obsidian Dark (Slate 900)",
            "matrix": "Matrix Cyber (Neon Green)",
            "midnight": "Midnight Navy (Deep Blue)",
            "light_slate": "Clean Light Slate (White)",
        }
        _TERM_REVERSE = {v: k for k, v in _TERM_NAMES.items()}
        curr_term_key = cur.get("terminal_theme", DEFAULTS.get("terminal_theme", "obsidian"))

        dd_term = _dropdown_row(scroll_term,
            "Tema Console Terminal",
            list(_TERM_NAMES.values()),
            _TERM_NAMES.get(curr_term_key, _TERM_NAMES["obsidian"]),
            "Warna latar belakang dan font terminal log console.",
        )

        _section_label(scroll_term, "🔤  Tipografi & Font")
        _FONTS = ["Consolas", "Courier New", "Lucida Console", "Segoe UI"]
        dd_fontfam = _dropdown_row(scroll_term,
            "Jenis Font Monospace", _FONTS,
            cur.get("log_font_family", DEFAULTS.get("log_font_family", "Consolas")),
            "Font monospace untuk baris output terminal.",
        )
        sl_fontsize = _slider_row(scroll_term,
            "Ukuran Font Log", cur.get("log_font_size", DEFAULTS["log_font_size"]),
            8, 22, "Ukuran font terminal log (8 – 22 pt).", unit="pt",
        )

        _section_label(scroll_term, "📜  Perilaku & Kapasitas Log")
        e_maxlog = _entry_row(scroll_term,
            "Maks Baris Log per Tab",
            cur.get("max_log_lines", DEFAULTS["max_log_lines"]),
            "0 = tidak dibatasi. Rekomendasi 1000 – 5000.",
        )
        sw_autoscroll = _switch_row(scroll_term,
            "Auto-Scroll Log", cur.get("auto_scroll_log", DEFAULTS["auto_scroll_log"]),
            "Otomatis scroll ke baris terbaru saat ada log baru.",
        )
        sw_timestamp = _switch_row(scroll_term,
            "Tampilkan Timestamp [HH:MM:SS]", cur.get("show_timestamp", DEFAULTS["show_timestamp"]),
            "Tampilkan waktu di awal setiap baris log.",
        )

        # ── TAB 4: FITUR & SAFETY ────────────────────
        scroll_feat = ctk.CTkScrollableFrame(tab_features, fg_color="transparent")
        scroll_feat.pack(fill="both", expand=True, padx=4, pady=4)

        _section_label(scroll_feat, "🚀  Auto-Start saat Launch")
        _FEATURE_KEYS = [
            ("canclwork", "CANCLWORK WO"),
            ("dispatch", "DISPATCH"),
            ("change_service_id", "CHANGE SERVICE ID"),
            ("gamas_relations", "GAMAS RELATIONS"),
            ("report", "REPORT HARIAN"),
        ]
        auto_start_cur = cur.get("auto_start_features") or []
        auto_start_cbs = {}
        for fkey, flabel in _FEATURE_KEYS:
            cb_box = ctk.CTkFrame(scroll_feat, fg_color="transparent")
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

        ctk.CTkLabel(scroll_feat, text="Fitur yang dicentang akan otomatis START saat aplikasi dibuka (aktif setelah restart).",
                     font=(FONT_UI, 10), text_color=TEXT_DIM, wraplength=520
                     ).pack(anchor="w", pady=(2, 6))

        _section_label(scroll_feat, "🛡  Safety & Proteksi")
        sw_confirm_stop = _switch_row(scroll_feat,
            "Konfirmasi Sebelum STOP", cur.get("confirm_before_stop", DEFAULTS["confirm_before_stop"]),
            "Tampilkan dialog konfirmasi saat menekan tombol STOP.",
        )

        _section_label(scroll_feat, "🔌  Konektivitas API")
        e_biscuit_timeout = _entry_row(scroll_feat,
            "BISCUIT API Timeout (detik)",
            cur.get("biscuit_api_timeout", DEFAULTS["biscuit_api_timeout"]),
            "Timeout request ke BISCUIT API. Minimum 30 detik.",
        )

        # ── Bottom Bar ───────────────────────────────
        bot_bar = ctk.CTkFrame(win, fg_color="transparent")
        bot_bar.pack(fill="x", padx=24, pady=(0, 14))

        ctk.CTkLabel(
            bot_bar, text=f"📁 {USER_SETTINGS_PATH}",
            font=(FONT_UI, 10), text_color=TEXT_DIM,
        ).pack(anchor="w", pady=(0, 6))

        btns = ctk.CTkFrame(bot_bar, fg_color="transparent")
        btns.pack(fill="x")

        def _save():
            try:
                loop = int(e_loop.get().strip() or DEFAULTS["loop_interval"])
                loop = max(60, loop)
            except ValueError:
                loop = DEFAULTS["loop_interval"]

            skip = [x.strip() for x in e_skip.get().replace(",", " ").split() if x.strip()]

            # Accent color resolution
            hex_input = e_hex.get().strip()
            if hex_input.startswith("#") and len(hex_input) in (4, 7):
                accent_hex = hex_input
            else:
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

            selected_term = _TERM_REVERSE.get(dd_term.get(), "obsidian")

            data = {
                "loop_interval": loop,
                "skip_coordinator_user_ids": skip,
                "user_id": e_uid.get().strip() or DEFAULTS["user_id"],
                "user_name": e_uname.get().strip() or DEFAULTS["user_name"],
                "theme": dd_theme.get(),
                "accent_color": accent_hex,
                "show_logo": bool(sw_logo.get()),
                "logo_size": int(sl_logosize.get()),
                "show_clock": bool(sw_clock.get()),
                "show_feature_desc": bool(sw_desc.get()),
                "show_feature_tags": bool(sw_tags.get()),
                "terminal_theme": selected_term,
                "log_font_family": dd_fontfam.get(),
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

            # Live-apply visual settings immediately
            self._apply_visual_settings(data)

            self.write_log(
                f"[settings] UI Studio disimpan: aksen={accent_hex}, tema={data['theme']}, "
                f"logo={data['logo_size']}px, term={selected_term}",
                channel="all",
            )
            win.destroy()

        ctk.CTkButton(
            btns, text="💾  Simpan & Terapkan", width=145, height=34,
            corner_radius=8, fg_color=RED_MAIN, hover_color=RED_HOVER,
            text_color=WHITE, font=(FONT_UI, 12, "bold"),
            command=_save,
        ).pack(side="left")

        ctk.CTkButton(
            btns, text="Batal", width=80, height=34,
            corner_radius=8, fg_color=BG_BTN_SECONDARY, hover_color=BG_BTN_SECONDARY_HOVER,
            text_color=TEXT_MAIN, font=(FONT_UI, 12, "bold"),
            command=win.destroy,
        ).pack(side="left", padx=(10, 0))

        # Reset defaults button
        def _reset():
            from app.user_settings import save as _save_settings, DEFAULTS as _DEF
            self.user_settings = _save_settings(dict(_DEF))
            self._apply_visual_settings(_DEF)
            self.write_log("[settings] UI Studio direset ke default!", channel="all")
            win.destroy()

        ctk.CTkButton(
            btns, text="🔄  Reset Default", width=125, height=34,
            corner_radius=8, fg_color=RED_LIGHT, hover_color=RED_LIGHT_HOVER,
            border_width=1, border_color=RED_LIGHT_BORDER,
            text_color=RED_MAIN, font=(FONT_UI, 11, "bold"),
            command=_reset,
        ).pack(side="right")

    def _apply_visual_settings(self, data):
        """Terapkan pengaturan visual & UI Studio secara live (tanpa restart)."""
        accent = data.get("accent_color", RED_MAIN)
        if not isinstance(accent, str) or not accent.startswith("#") or len(accent) not in (4, 7):
            accent = RED_MAIN

        # ── Darken helper for hover color ──
        def _darken(hex_color, factor=0.8):
            try:
                hex_color = hex_color.lstrip("#")
                if len(hex_color) == 3:
                    hex_color = "".join(c * 2 for c in hex_color)
                r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
                r, g, b = int(r * factor), int(g * factor), int(b * factor)
                return f"#{r:02x}{g:02x}{b:02x}"
            except Exception:
                return hex_color

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
            if hasattr(self, "_log_tabs") and self._log_tabs:
                self._log_tabs.configure(
                    segmented_button_selected_color=accent,
                    segmented_button_selected_hover_color=accent_hover,
                )
        except Exception:
            pass

        # ── 3. Update STOP button text colors on all feature cards ──
        for feat in FEATURES:
            key = feat["key"]
            stop_btn = getattr(self, f"{key}_stop_btn", None)
            if stop_btn:
                try:
                    stop_btn.configure(text_color=accent)
                except Exception:
                    pass

        # ── 4. Logo Visibility & Size ──
        show_logo = data.get("show_logo", True)
        logo_sz = int(data.get("logo_size", 115))
        if hasattr(self, "_logo_label") and self._logo_label:
            try:
                if not show_logo:
                    self._logo_label.pack_forget()
                else:
                    self._logo_label.pack(side="left")
                    if os.path.exists(LOGO_PATH):
                        from PIL import Image
                        pil_img = Image.open(LOGO_PATH).convert("RGBA")
                        self._logo_img = ctk.CTkImage(
                            light_image=pil_img,
                            dark_image=pil_img,
                            size=(logo_sz, logo_sz),
                        )
                        self._logo_label.configure(image=self._logo_img, text="")
            except Exception:
                pass

        # ── 5. Clock Visibility ──
        show_clock = data.get("show_clock", True)
        if hasattr(self, "_clock_label") and self._clock_label:
            try:
                if show_clock:
                    self._clock_label.pack(side="right")
                else:
                    self._clock_label.pack_forget()
            except Exception:
                pass

        # ── 6. Feature Descriptions Visibility ──
        show_desc = data.get("show_feature_desc", True)
        if hasattr(self, "_feature_desc_labels"):
            for k, lbl in self._feature_desc_labels.items():
                try:
                    if show_desc:
                        lbl.pack(anchor="w")
                    else:
                        lbl.pack_forget()
                except Exception:
                    pass

        # ── 7. Feature Tags Visibility ──
        show_tags = data.get("show_feature_tags", True)
        if hasattr(self, "_feature_tag_labels"):
            for k, lbl in self._feature_tag_labels.items():
                try:
                    if show_tags:
                        lbl.pack(side="left", padx=(0, 6))
                    else:
                        lbl.pack_forget()
                except Exception:
                    pass

        # ── 8. Terminal Theme & Fonts ──
        term_theme = data.get("terminal_theme", "obsidian")
        _TERM_PALETTES = {
            "obsidian": {"bg": "#0F172A", "fg": "#E2E8F0"},
            "matrix": {"bg": "#031408", "fg": "#4ADE80"},
            "midnight": {"bg": "#0A1128", "fg": "#93C5FD"},
            "light_slate": {"bg": "#F8FAFC", "fg": "#0F172A"},
        }
        pal = _TERM_PALETTES.get(term_theme, _TERM_PALETTES["obsidian"])
        font_fam = data.get("log_font_family", "Consolas")
        font_sz = data.get("log_font_size", 12)

        for name, box in self.log_boxes.items():
            try:
                box.configure(
                    fg_color=pal["bg"],
                    text_color=pal["fg"],
                    font=(font_fam, font_sz),
                )
            except Exception:
                pass

        # ── 9. Max log lines trimming ──
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

        # ── 10. Theme mode (light/dark) ──
        theme = data.get("theme", "light")
        try:
            ctk.set_appearance_mode(theme)
        except Exception:
            pass

        # ── 11. Update Header KPI Labels ──
        if hasattr(self, "_kpi_loop") and self._kpi_loop:
            try:
                loop_val = data.get("loop_interval", 180)
                self._kpi_loop.configure(text=f"\u23f1 Loop: {loop_val}s")
            except Exception:
                pass
        if hasattr(self, "_kpi_skip") and self._kpi_skip:
            try:
                skip_val = data.get("skip_coordinator_user_ids", ["55652"])
                skip_str = ", ".join(skip_val) if skip_val else "None"
                self._kpi_skip.configure(text=f"\U0001F6E1 Skip: {skip_str}")
            except Exception:
                pass

        self.write_log(
            f"[settings] Visual diterapkan: aksen={accent}, tema={theme}, "
            f"logo={logo_sz}px, term={term_theme}, font={font_fam} {font_sz}pt",
            channel="all",
        )


# =====================================================
# Run
# =====================================================

if __name__ == "__main__":

    app = DispatchAssistantGUI()

    app.mainloop()
