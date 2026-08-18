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
# Appearance
# =====================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG_MAIN = "#FDF5F5"
BG_CARD = "#FFFFFF"
BORDER = "#E5E7EB"
BORDER_RED = "#FECACA"
RED_MAIN = "#DC2626"
RED_DARK = "#991B1B"
RED_HOVER = "#B91C1C"
TEXT_DARK = "#111827"
TEXT_DIM = "#6B7280"
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
        "color": "#0EA5E9",
        "hover": "#0284C7",
        "port_key": "TO",
    },
    {
        "key": "canclwork",
        "label": "CANCLWORK WO",
        "icon": "\U0001F527",
        "desc": "Cancel work order via BISCUIT",
        "color": "#F97316",
        "hover": "#EA580C",
        "port_key": "CANCLWORK",
    },
    {
        "key": "dispatch",
        "label": "DISPATCH",
        "icon": "\U0001F680",
        "desc": "Dispatch tiket via BISCUIT",
        "color": "#10B981",
        "hover": "#059669",
        "port_key": "DISPATCH",
    },
    {
        "key": "gamas_relations",
        "label": "GAMAS RELATIONS",
        "icon": "\U0001F517",
        "desc": "Relasi induk & anak GAMAS di INSERA",
        "color": "#EC4899",
        "hover": "#DB2777",
        "port_key": "GAMAS",
    },
    {
        "key": "report",
        "label": "REPORT HARIAN",
        "icon": "\U0001F4CA",
        "desc": "Laporan harian helpdesk operasional",
        "color": "#6366F1",
        "hover": "#4F46E5",
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

        self.title("Industrial Programmer - DispatchAssistant")

        self.geometry("1280x840")

        self.minsize(1080, 740)

        self.resizable(True, True)

        self.configure(fg_color=BG_MAIN)

        self.create_header()
        self.create_feature_sections()
        self.create_log_section()
        self.create_footer()
        self._start_clock()
        self._start_telegram_bot()

    # =================================================
    # Header
    # =================================================

    def create_header(self):

        frame = ctk.CTkFrame(
            self,
            corner_radius=14,
            fg_color=RED_MAIN,
            border_width=0,
        )

        frame.pack(fill="x", padx=20, pady=(20, 10))

        # Strip putih (pita merah putih)
        strip = ctk.CTkFrame(frame, height=6, corner_radius=0, fg_color=WHITE)
        strip.pack(fill="x", side="top")

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=(14, 12))

        inner.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        title = ctk.CTkLabel(
            left,
            text="DispatchAssistant",
            font=(FONT_UI, 26, "bold"),
            text_color=WHITE,
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            left,
            text="Industrial Programmer Automation System  \u2022  Multi-Chrome  \u2022  Telegram Remote",
            font=(FONT_UI, 12),
            text_color="#FECACA",
        )
        subtitle.pack(anchor="w", pady=(2, 0))

# Logo: diletakkan di sisi kiri kolom tengah (geser dari titik tengah header)
        center = ctk.CTkFrame(inner, fg_color="transparent")
        center.grid(row=0, column=1)

        logo_label = None
        if os.path.exists(LOGO_PATH):
            try:
                from PIL import Image

                pil_img = Image.open(LOGO_PATH).convert("RGBA")

                # Hilangkan background putih: piksel terang -> transparan,
                # tepi transisi di-soften biar tidak kasar.
                try:
                    gray = pil_img.convert("L")
                    alpha = gray.point(
                        lambda v: 0
                        if v >= 240
                        else int((240 - v) * 255 / 40)
                        if v >= 200
                        else 255
                    )
                    pil_img.putalpha(alpha)
                except Exception:
                    pass

                logo_img = ctk.CTkImage(
                    light_image=pil_img,
                    dark_image=pil_img,
                    size=(200, 200),
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
                text="\U0001F989",
                font=(FONT_UI, 26),
                text_color=WHITE,
            )
        logo_label.pack(side="left")

        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e")

        badge = ctk.CTkLabel(
            right,
            text="  \u25CF SYSTEM READY  ",
            font=(FONT_UI, 12, "bold"),
            text_color=RED_MAIN,
            fg_color=WHITE,
            corner_radius=14,
        )
        badge.pack(anchor="e")
        self._badge_ready = badge

        clock = ctk.CTkLabel(
            right,
            text="",
            font=(FONT_MONO, 13, "bold"),
            text_color=WHITE,
        )
        clock.pack(anchor="e", pady=(4, 0))
        self._clock_label = clock

    # =================================================
    # Feature Cards (2 kolom)
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
            corner_radius=12,
            border_width=2,
            border_color=feat["color"],
            fg_color=BG_CARD,
        )

        card_strip = ctk.CTkFrame(
            card,
            height=5,
            corner_radius=0,
            fg_color=RED_MAIN,
        )
        card_strip.pack(fill="x", side="top")

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 4))

        icon = ctk.CTkLabel(
            top,
            text=feat["icon"],
            font=(FONT_UI, 20),
            text_color=WHITE,
            fg_color=feat["color"],
            corner_radius=10,
            width=44,
            height=44,
        )
        icon.pack(side="left", padx=(0, 10))

        name_col = ctk.CTkFrame(top, fg_color="transparent")
        name_col.pack(side="left", fill="x", expand=True)

        name = ctk.CTkLabel(
            name_col,
            text=feat["label"],
            font=(FONT_UI, 15, "bold"),
            text_color=TEXT_DARK,
        )
        name.pack(anchor="w")

        desc = ctk.CTkLabel(
            name_col,
            text=feat["desc"],
            font=(FONT_UI, 11),
            text_color=TEXT_DIM,
        )
        desc.pack(anchor="w")

        status_label = ctk.CTkLabel(
            top,
            text="\u25CF READY",
            font=(FONT_UI, 11, "bold"),
            text_color="#16A34A",
            fg_color="#F3F4F6",
            corner_radius=12,
            padx=10,
            pady=4,
        )
        status_label.pack(side="right", padx=(8, 0))

        bottom = ctk.CTkFrame(card, fg_color="transparent")
        bottom.pack(fill="x", padx=14, pady=(6, 12))

        chip = ctk.CTkLabel(
            bottom,
            text=f"port {port}",
            font=(FONT_MONO, 11, "bold"),
            text_color=feat["color"],
            fg_color="#F3F4F6",
            corner_radius=10,
            padx=10,
            pady=2,
        )
        chip.pack(side="left")

        stop_btn = ctk.CTkButton(
            bottom,
            text="STOP",
            width=72,
            height=30,
            corner_radius=8,
            fg_color=BG_CARD,
            hover_color="#FEE2E2",
            border_width=1,
            border_color=RED_MAIN,
            text_color=RED_MAIN,
            font=(FONT_UI, 12, "bold"),
            command=lambda k=key: self._stop_feature(k),
        )
        stop_btn.pack(side="right", padx=(6, 0))

        start_btn = ctk.CTkButton(
            bottom,
            text="START",
            width=84,
            height=30,
            corner_radius=8,
            fg_color=feat["color"],
            hover_color=feat["hover"],
            font=(FONT_UI, 12, "bold"),
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

        self._update_feature_status(key, "STARTING", "#EAB308")
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

        color = STATUS_COLORS.get(status.upper(), "#22C55E")
        dim = "#D1D5DB"
        state = {"on": True}

        def tick():
            state["on"] = not state["on"]
            lbl.configure(text_color=color if state["on"] else dim)
            self._blink_jobs[key] = self.after(650, tick)

        tick()

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

        frame = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER,
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
            text_color=TEXT_DARK,
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text="log live per fitur",
            font=(FONT_UI, 11),
            text_color=TEXT_DIM,
        ).pack(side="left", padx=(8, 0), pady=(3, 0))

        ctk.CTkLabel(
            header,
            text="  \u25CF LIVE  ",
            font=(FONT_UI, 10, "bold"),
            text_color=WHITE,
            fg_color=RED_MAIN,
            corner_radius=10,
        ).pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            header,
            text="Copy",
            width=64,
            height=26,
            corner_radius=8,
            fg_color="#F3F4F6",
            hover_color="#E5E7EB",
            text_color=TEXT_DARK,
            font=(FONT_UI, 11, "bold"),
            command=self._copy_log,
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            header,
            text="Clear",
            width=64,
            height=26,
            corner_radius=8,
            fg_color="#F3F4F6",
            hover_color="#E5E7EB",
            text_color=TEXT_DARK,
            font=(FONT_UI, 11, "bold"),
            command=self._clear_log,
        ).pack(side="right")

        self.tabs = ctk.CTkTabview(
            frame,
            corner_radius=10,
            fg_color="#FAF3F3",
            segmented_button_selected_color=RED_MAIN,
            segmented_button_selected_hover_color=RED_HOVER,
            segmented_button_unselected_color=WHITE,
            segmented_button_unselected_hover_color="#FDE8E8",
            text_color="#111827",
        )

        self.tabs.pack(fill="both", expand=True, padx=14, pady=(6, 14))

        for name in LOG_TABS:
            tab = self.tabs.add(name)
            box = ctk.CTkTextbox(
                tab,
                font=(FONT_MONO, 12),
                wrap="word",
                fg_color=WHITE,
                border_color=BORDER,
                border_width=1,
                corner_radius=8,
                text_color="#1F2937",
            )
            box.pack(fill="both", expand=True, padx=4, pady=4)
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
        self.write_log(f"  REPORT    -> port {CHROME_PORTS['REPORT']}")
        self.write_log("==========================")

    def _setup_tags(self, box):

        try:
            box.tag_config("err", foreground="#DC2626")
            box.tag_config("ok", foreground="#16A34A")
            box.tag_config("warn", foreground="#D97706")
            box.tag_config("dim", foreground="#9CA3AF")
        except Exception:
            try:
                box._textbox.tag_config("err", foreground="#DC2626")
                box._textbox.tag_config("ok", foreground="#16A34A")
                box._textbox.tag_config("warn", foreground="#D97706")
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
            fg_color=RED_MAIN,
            border_width=0,
        )

        footer.pack(fill="x", padx=20, pady=(0, 14))

        ctk.CTkLabel(
            footer,
            text="\u25CF ONLINE",
            font=(FONT_UI, 11, "bold"),
            text_color=WHITE,
        ).pack(side="left", padx=14, pady=8)

        ctk.CTkLabel(
            footer,
            text="auto-pilot aktif  \u2022  gunakan STOP saat intervensi manual",
            font=(FONT_UI, 11),
            text_color="#FECACA",
        ).pack(side="left", padx=(10, 0), pady=8)

        ctk.CTkLabel(
            footer,
            text="v3.2",
            font=(FONT_UI, 11, "bold"),
            text_color="#FCA5A5",
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
# Run
# =====================================================

if __name__ == "__main__":

    app = DispatchAssistantGUI()

    app.mainloop()
