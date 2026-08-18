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
}


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
    payload = {k: data.get(k, DEFAULTS.get(k)) for k in DEFAULTS}
    payload["loop_interval"] = max(60, int(payload.get("loop_interval", 180)))
    payload["skip_coordinator_user_ids"] = list(payload.get("skip_coordinator_user_ids") or [])
    try:
        with open(USER_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    apply(payload)
    return payload