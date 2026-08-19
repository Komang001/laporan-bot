import json
import os

from config import settings as _cfg
from app import controller as _ctrl
from app.services import sygap_service as _svg

USER_SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "user_settings.json",
)

DEFAULTS = {
    "loop_interval": 180,
    "skip_coordinator_user_ids": ["55652"],
    "user_id": "55654",
    "user_name": "I Nyoman Windu",
    # Tampilan
    "theme": "light",                # light / dark
    "accent_color": "#DC2626",       # warna aksen utama
    "log_font_size": 12,             # ukuran font terminal log
    "max_log_lines": 2000,           # batas baris log per tab (0 = unlimited)
    # Advanced
    "auto_scroll_log": True,         # auto-scroll log ke bawah
    "show_timestamp": True,          # tampilkan [HH:MM:SS] di log
    "confirm_before_stop": False,    # konfirmasi sebelum STOP
    "auto_start_features": [],       # fitur yang auto-start saat launch
    "biscuit_api_timeout": 180,      # timeout BISCUIT API (detik)
}

# Kunci yang berlaku langsung tanpa restart
_LIVE_KEYS = {
    "loop_interval", "skip_coordinator_user_ids",
    "theme", "accent_color", "log_font_size", "max_log_lines",
    "auto_scroll_log", "show_timestamp", "confirm_before_stop",
    "biscuit_api_timeout",
}

# Kunci yang butuh restart
_RESTART_KEYS = {"user_id", "user_name", "auto_start_features"}


def load():
    """Baca user_settings.json (jika ada), lalu terapkan ke modul-modul runtime."""
    data = dict(DEFAULTS)
    if os.path.exists(USER_SETTINGS_PATH):
        try:
            with open(USER_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data.update(json.load(f))
        except Exception:
            pass
    apply(data)
    return data


def apply(data):
    """Terapkan nilai ke runtime (module-level) supaya langsung aktif."""
    try:
        _ctrl.LOOP_INTERVAL = int(data.get("loop_interval", 180))
    except Exception:
        pass
    try:
        _svg.LOOP_INTERVAL = int(data.get("loop_interval", 180))
    except Exception:
        pass

    _cfg.USER_ID = str(data.get("user_id", "55654"))
    _cfg.USER_NAME = str(data.get("user_name", "I Nyoman Windu"))

    skip = data.get("skip_coordinator_user_ids") or []
    _cfg.SKIP_COORDINATOR_USER_IDS = [str(x).strip() for x in skip if str(x).strip()]


def save(data):
    """Simpan ke file + terapkan ke runtime."""
    payload = {}
    for k in DEFAULTS:
        payload[k] = data.get(k, DEFAULTS.get(k))
    payload["loop_interval"] = max(60, int(payload.get("loop_interval", 180)))
    payload["skip_coordinator_user_ids"] = list(payload.get("skip_coordinator_user_ids") or [])
    payload["log_font_size"] = max(8, min(24, int(payload.get("log_font_size", 12))))
    payload["max_log_lines"] = max(0, int(payload.get("max_log_lines", 2000)))
    payload["biscuit_api_timeout"] = max(30, int(payload.get("biscuit_api_timeout", 180)))
    try:
        with open(USER_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    apply(payload)
    return payload