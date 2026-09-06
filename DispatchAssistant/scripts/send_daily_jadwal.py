"""Kirim jadwal piket harian ke Telegram.

Dijalankan terjadwal di GitHub Actions (bebas dari laptop lokal):
  - Ambil jadwal dari Google Sheet (public, export CSV + XLSX via gid).
  - Susun pesan: piket semua shift (1, 2, 3) + PIC (sel hijau #00FF00).
  - Kirim via Telegram Bot API (sendMessage).

Env yang dibutuhkan:
  TELEGRAM_BOT_TOKEN  token bot Telegram
  TELEGRAM_CHAT_ID    chat ID tujuan (boleh angka, @username, atau "id1,id2")
  JADWAL_SHEET_URL    opsional, default = tab jadwal L1/L2&L3

Jalankan lokal:
  $env:TELEGRAM_BOT_TOKEN="..."; $env:TELEGRAM_CHAT_ID="903566652"
  python send_daily_jadwal.py --dry-run   (hanya tampilkan pesan)
  python send_daily_jadwal.py             (kirim sungguhan)
"""
import csv
import datetime
import io
import os
import re
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

SHEET_URL = os.environ.get(
    "JADWAL_SHEET_URL",
    "https://docs.google.com/spreadsheets/d/"
    "1VlLQx0CxMeWStMjpkwQWiq8nbXaYqO2fJABAe7JNhmg/export?format=csv&gid=890618279",
)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
# Untuk group forum mode: ID topik tujuan (message_thread_id)
THREAD_ID = os.environ.get("TELEGRAM_MESSAGE_THREAD_ID", "").strip()

SHIFTS = [
    ("Shift 1", "00:00", "09:00"),
    ("Shift 2", "09:00", "16:30"),
    ("Shift 3", "16:30", "23:59"),
]
SHIFT_START_M = {
    int(st.split(":")[0]) * 60 + int(st.split(":")[1]): (label, st, en)
    for label, st, en in SHIFTS
}

NAMES_MAP = {
    "I NYOMAN WINDU": "WINDU",
    "RIZKY SENJA BUDIMAN": "RIZKY",
    "RIZKY": "RIZKY",
}
USERNAMES = {
    "ANNE": "@annemaswa27",
    "ALFIRA": "@hifirrr",
    "TYAS": "@ikhpani",
    "ROFINA": "@InaBiti",
    "RIZKA": "@rizkayln",
    "IHSAN": "@ihsanabdi123",
    "DIKA": "@dikaprndx",
    "WINDU": "@komangwindu",
    "RIZKY": "@rizkysenjab",
}
GREEN_FILL = "FF00FF00"
SUMMARY_ROWS = {"SHIFT 1", "SHIFT 2", "SHIFT 3", "TOTAL MASUK PER HARI"}

DAY_NAMES = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTH_NAMES = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
               "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

_MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MEI": 5, "JUN": 6,
    "JUL": 7, "AGU": 8, "SEP": 9, "OKT": 10, "NOV": 11, "DES": 12,
}


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def resolve_sheet_url(now):
    """Deteksi tab sheet yang memuat tanggal target secara otomatis."""
    if "JADWAL_SHEET_URL" in os.environ:
        return SHEET_URL
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", SHEET_URL)
    if not m:
        return SHEET_URL
    sheet_id = m.group(1)
    try:
        html = http_get(f"https://docs.google.com/spreadsheets/d/{sheet_id}/htmlview").decode("utf-8", errors="replace")
        tabs = re.findall(r'name:\s*"([^"]+)"[^\}]+?gid:\s*"(\d+)"', html)
        target_m = now.month
        target_d = now.day
        for name, gid in tabs:
            clean = re.sub(r'[^a-zA-Z]', ' ', name).upper()
            matched_m = [v for k, v in _MONTH_ABBR.items() if any(t.startswith(k) for t in clean.split())]
            if target_m in matched_m:
                csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
                csv_raw = http_get(csv_url).decode("utf-8", errors="replace")
                rows = list(csv.reader(io.StringIO(csv_raw)))
                for r in rows:
                    if r and r[0] == "NAMA":
                        if any(_cell_day(h, target_d) for h in r):
                            return csv_url
                        break
    except Exception:
        pass
    return SHEET_URL


def _cell_day(value, day):
    if value is None:
        return False
    return str(value).strip().split(".")[0] == str(day)


def _slot_start_min(slot):
    try:
        s, _e = slot.split("-")
        sh, sm = (int(x) for x in s.strip().replace(".", ":").split(":"))
        return sh * 60 + sm
    except Exception:
        return None


def match_shift_slot(sheet_map, start_m):
    """Pilih key slot sheet untuk jam mulai shift config.

    Exact match dulu; jika sheet memakai label jam berbeda (mis. slot
    '08:00-17:00' untuk shift 09:00-16:30), ambil slot yang jam mulainya
    <= jam mulai shift (slot terakhir yang sudah mulai).
    """
    if not sheet_map:
        return None
    if start_m in sheet_map:
        return start_m
    starts = sorted(k for k in sheet_map if k <= start_m)
    return starts[-1] if starts else None


def parse_piket_csv(raw, day):
    """Blok L1 -> {jam_mulai_shift: [tags]}."""
    rows = list(csv.reader(io.StringIO(raw)))
    header_row = None
    day_col = None
    for i, r in enumerate(rows):
        if not r:
            continue
        if r[0] == "NAMA":
            header_row = i
            for j, h in enumerate(r):
                if _cell_day(h, day):
                    day_col = j
                    break
            break
    if header_row is None or day_col is None:
        return None
    result = {}
    cur_name = None
    cur_shift_m = None
    for r in rows[header_row + 1:]:
        if not r:
            continue
        name = (r[0] or "").strip()
        if name:
            cur_name = name
        if cur_name and cur_name.upper() in SUMMARY_ROWS:
            break
        slot = (r[1] or "").strip() if len(r) > 1 else ""
        if slot:
            cur_shift_m = _slot_start_min(slot)
        if not cur_name or cur_shift_m is None or len(r) <= day_col:
            continue
        if (r[day_col] or "").strip() == "1":
            key = NAMES_MAP.get(cur_name.upper(), cur_name.upper())
            tag = USERNAMES.get(key)
            if tag and tag not in result.setdefault(cur_shift_m, []):
                result[cur_shift_m].append(tag)
    return result or None


def parse_pic_xlsx(raw, day):
    """PIC per shift (sel hijau) -> {jam_mulai_shift: tag}."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    ws = wb.active
    header_row = None
    day_col = None
    for r in range(1, 30):
        if ws.cell(r, 1).value == "NAMA":
            header_row = r
            for c in range(1, ws.max_column + 1):
                if _cell_day(ws.cell(r, c).value, day):
                    day_col = c
                    break
            break
    if header_row is None or day_col is None:
        return None
    result = {}
    cur_name = None
    cur_shift_m = None
    for r in range(header_row + 1, ws.max_row + 1):
        name = ws.cell(r, 1).value
        if name and str(name).strip().upper() in SUMMARY_ROWS:
            break
        if str(name or "").strip().upper().startswith("JADWAL"):
            break
        if name:
            cur_name = str(name).strip()
        slot = ws.cell(r, 2).value
        if slot:
            cur_shift_m = _slot_start_min(str(slot))
        if not cur_name or cur_shift_m is None:
            continue
        f = ws.cell(r, day_col).fill
        green = bool(f and f.patternType and f.fgColor and f.fgColor.rgb == GREEN_FILL)
        if green:
            key = NAMES_MAP.get(cur_name.upper(), cur_name.upper())
            tag = USERNAMES.get(key)
            if tag and cur_shift_m not in result:
                result[cur_shift_m] = tag
    return result or None


def build_message(now):
    day = now.day
    csv_url = resolve_sheet_url(now)
    xlsx_url = csv_url.replace("export?format=csv", "export?format=xlsx")
    piket = parse_piket_csv(http_get(csv_url).decode("utf-8", errors="replace"), day)
    pic = parse_pic_xlsx(
        http_get(xlsx_url), day
    )
    if piket is None:
        raise RuntimeError("Tanggal tidak ada di jadwal sheet / CSV tidak terbaca")

    lines = [
        "📋 Jadwal Piket Hari Ini",
        f"{DAY_NAMES[now.weekday()]}, {now.day} {MONTH_NAMES[now.month - 1]} {now.year}",
        "",
    ]
    for start_m in sorted(SHIFT_START_M):
        label, start, end = SHIFT_START_M[start_m]
        lines.append(f"👥 {label} ({start} - {end}):")
        key = match_shift_slot(piket, start_m)
        tags = piket.get(key) if key is not None else None
        if not tags:
            lines.append("• (tidak ada)")
        for t in tags:
            pic_mark = " — ⭐ PIC" if pic and key is not None and pic.get(key) == t else ""
            lines.append(f"• {t}{pic_mark}")
        lines.append("")
    lines.append("Sumber: Google Sheet jadwal")
    return "\n".join(lines)


def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for cid in CHAT_ID.split(","):
        cid = cid.strip()
        if not cid:
            continue
        params = {"chat_id": cid, "text": text, "disable_web_page_preview": "true"}
        if THREAD_ID:
            params["message_thread_id"] = THREAD_ID
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            if '"ok":false' in body or resp.status != 200:
                raise RuntimeError(f"Telegram gagal ke {cid}: {body[:200]}")


def main():
    if "--dry-run" in sys.argv:
        now = datetime.datetime.now(ZoneInfo("Asia/Jakarta"))
        print(build_message(now))
        return 0
    if not TOKEN or not CHAT_ID:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diatur", file=sys.stderr)
        return 2
    now = datetime.datetime.now(ZoneInfo("Asia/Jakarta"))
    try:
        text = build_message(now)
    except Exception as e:
        text = f"⚠️ Gagal mengambil jadwal piket: {e}"
        try:
            send_message(text)
        except Exception:
            print(text, file=sys.stderr)
        return 1
    send_message(text)
    print("Terkirim ke:", CHAT_ID)
    return 0


if __name__ == "__main__":
    sys.exit(main())
