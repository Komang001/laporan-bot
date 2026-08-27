import csv
import os
import threading
from datetime import datetime

# Lokasi: DispatchAssistant/logs/history_YYYY-MM-DD.csv
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HISTORY_DIR = os.path.join(BASE_DIR, "logs")

_lock = threading.Lock()

HEADER = [
    "Waktu Proses",
    "Fitur",
    "Tiket SYGAP (REQ)",
    "No Tiket INSERA (INC)",
    "Isi Note (500 char)",
    "Tanggal Masuk SYGAP",
    "Tanggal Selesai Dikerjakan",
    "Owner Group/Inc/ServiceType",
    "Reply SYGAP",
    "BISCUIT Status",
    "BISCUIT Message",
    "Status",
    "Solver ID",
]

def _history_path():
    return os.path.join(HISTORY_DIR, f"history_{datetime.now().strftime('%Y-%m-%d')}.csv")

def log_history(
    feature="",
    ticket_code="",
    ticket_id="",
    owner_group="",
    service_id="",
    note="",
    reply_sygap="",
    biscuit_status="",
    biscuit_message="",
    status="",
    solver_id="",
    tgl_masuk="",
    tgl_selesai="",
):
    """Tulis 1 baris history harian. Aman untuk dipanggil dari thread manapun."""
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        path = _history_path()
        need_header = not os.path.exists(path) or os.path.getsize(path) == 0

        waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Tanggal selesai default = waktu proses jika tidak diisi
        if not tgl_selesai:
            tgl_selesai = waktu
        # Sanitasi note: 1 baris, max 500 char, tanpa newline
        note_clean = " ".join((note or "").split())[:500]
        reply_clean = " ".join((reply_sygap or "").split())[:200]
        biscuit_msg_clean = " ".join((biscuit_message or "").split())[:300]

        row = [
            waktu,
            feature,
            ticket_code,
            ticket_id or service_id or "",
            note_clean,
            tgl_masuk or "",
            tgl_selesai,
            owner_group or service_id or "",
            reply_clean,
            biscuit_status,
            biscuit_msg_clean,
            status,
            solver_id,
        ]

        with _lock:
            with open(path, "a", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                if need_header:
                    w.writerow(HEADER)
                w.writerow(row)
        # Juga tulis ke history_all.csv untuk rekap panjang
        all_path = os.path.join(HISTORY_DIR, "history_all.csv")
        need_header_all = not os.path.exists(all_path) or os.path.getsize(all_path) == 0
        with _lock:
            with open(all_path, "a", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                if need_header_all:
                    w.writerow(HEADER)
                w.writerow(row)

    except Exception as e:
        # Jangan ganggu flow utama jika log gagal
        try:
            print(f"[history] gagal tulis: {e}")
        except Exception:
            pass
