import os

# Load secrets lokal dari .env (tidak ikut git)
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_ENV_PATH):
    with open(_ENV_PATH, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip().strip('"').strip("'"))


# ==================================================
# Chrome
# ==================================================

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# Multi-Chrome: each feature gets its own Chrome instance + CDP port + profile
CHROME_PORTS = {
    "TO": 9222,
    "CANCLWORK": 9223,
    "DISPATCH": 9224,
    "GAMAS": 9225,
    "REPORT": 9226,
}

CHROME_PROFILES = {
    9222: r"C:\ChromeDebug_TO",
    9223: r"C:\ChromeDebug_CANCLWORK",
    9224: r"C:\ChromeDebug_DISPATCH",
    9225: r"C:\ChromeDebug_GAMAS",
    9226: r"C:\ChromeDebug_REPORT",
}


# ==================================================
# URLs
# ==================================================

DASHBOARD_URL = "https://sygap.telkom.co.id/req_fulfillment"

BISCUIT_URL = (
    "https://biscuit-dashboard-dev-playground.apps.mypaas.telkom.co.id"
    "/helpdesk/tools/inseratools"
)

GAMAS_RELATIONS_URL = (
    "https://oss-incident.telkom.co.id"
    "/jw/web/userview/ticketIncidentService/ticketIncidentService/_/gamasRelations"
)


# ==================================================
# Dispatch
# ==================================================

AUTO_ENTER = True


# ==================================================
# User (untuk Take Ownership)
# ==================================================

USER_NAME = "I Nyoman Windu"

USER_ID = "55654"

INSERA_GROUP_ID = "80148276"


# ==================================================
# Telegram Bot (Remote Control from HP)
# ==================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")  # dari .env (jangan isi manual di sini)

# Token bot per fitur (masing-masing kirim log live fiturnya + remote control fitur itu).
# Isi di .env: TELEGRAM_BOT_TOKEN_CANCLWORK, TELEGRAM_BOT_TOKEN_DISPATCH, TELEGRAM_BOT_TOKEN_GAMAS
TELEGRAM_BOT_TOKEN_CANCLWORK = os.environ.get("TELEGRAM_BOT_TOKEN_CANCLWORK", "")
TELEGRAM_BOT_TOKEN_DISPATCH = os.environ.get("TELEGRAM_BOT_TOKEN_DISPATCH", "")
TELEGRAM_BOT_TOKEN_GAMAS = os.environ.get("TELEGRAM_BOT_TOKEN_GAMAS", "")

# Chat ID tujuan log per fitur. Kosong -> fallback ke TELEGRAM_ALLOWED_USER_IDS.
TELEGRAM_CHAT_IDS = {
    "canclwork": [],
    "dispatch": [],
    "gamas_relations": [],
}

TELEGRAM_ALLOWED_USER_IDS = []  # chat ID admin/pemilik bot; kosongkan = semua boleh akses

# Request Coordinator (solver) yang tiketnya TIDAK boleh disentuh bot (skip semua fitur).
# Rizky Senja Budiman (CRS2018192) = 55652.
SKIP_COORDINATOR_USER_IDS = ["55652"]

# ==================================================
# Report Harian Helpdesk Operasional
# ==================================================

# Chrome untuk report.
# Default: pakai port TO (9222) -> reuse sesi login SYGAP yang sudah ada,
# jadi report langsung bisa ambil data tanpa login lagi.
# Alternatif terisolasi: set ke 9226 (profil C:\ChromeDebug_REPORT) tapi
# harus login sekali manual di Chrome port 9226.
REPORT_CDP_PORT = CHROME_PORTS["TO"]

# Chat ID channel/grup tujuan report (misal @hdsigmaniwbis).
# Untuk channel: ID negatif, dapat via @getidsbot atau forward pesan ke bot.
REPORT_CHAT_IDS = [903566652]  # sementara: pribadi @komangwindu; ganti ke ID grup/channel saat bot masuk group

# Jadwal kirim otomatis: tiap N menit, 24 jam (boundary kelipatan interval
# dari jam 00:00, mis. interval 30 -> 00:00, 00:30, 01:00, ... 23:30).
REPORT_SCHEDULE_INTERVAL_MINUTES = 30

# Shift kerja: header laporan mengikuti shift yang sedang aktif saat report
# dijalankan. Deteksi otomatis dari jam server.
#   Shift 1: 00:00-09:00, Shift 2: 08:00-15:00, Shift 3: 15:00-24:00
# Pergantian shift 2 -> 3 terjadi di 15:00; report tepat di jam AKHIR sebuah
# shift masih dihitung shift itu (mis. 09:00 -> Shift 1, 15:00 -> Shift 2,
# 00:00 -> Shift 3). Jika dua shift memuat waktu sama (overlap 08:00-09:00),
# shift yang BERAKHIR paling awal menang.
# Daftar orang per report = hanya yang MASUK di shift aktif (dari sheet
# jadwal), bukan semua piket hari itu.
# 'end' = "00:00" berarti akhir hari (lewat tengah malam).
REPORT_SHIFTS = [
    {"label": "Shift 1", "level": "L1", "start": "00:00", "end": "09:00"},
    {"label": "Shift 2", "level": "L1", "start": "08:00", "end": "15:00"},
    {"label": "Shift 3", "level": "L1", "start": "15:00", "end": "00:00"},
]

# Google Sheet jadwal shift (export CSV public, tanpa login).
# Ganti gid untuk tab lain (current: tab jadwal L1/L2&L3).
JADWAL_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1VlLQx0CxMeWStMjpkwQWiq8nbXaYqO2fJABAe7JNhmg/export?format=csv&gid=909284534"
)

# Nama di sheet jadwal yang berbeda dengan kunci TELEGRAM_USERNAMES.
JADWAL_SHEET_NAMES = {
    "I NYOMAN WINDU": "WINDU",
    "RIZKY SENJA BUDIMAN": "RIZKY",
    "RIZKY": "RIZKY",
}

# Header laporan
REPORT_TITLE = "Laporan Harian Helpdesk Operasional"
REPORT_CHANNEL = "@hdsigmaniwbis"
REPORT_PERSONNEL = ["@dikaprndx", "@komangwindu", "@rizkysenjab"]

# Mapping nama -> tag Telegram.
# Input piket (GUI/Telegram) cukup nama saja, otomatis diubah ke tag ini.
# Pencocokan tidak peka huruf besar/kecil, mis. "windu" -> @komangwindu.
TELEGRAM_USERNAMES = {
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

# Solver ID SYGAP per nama (value opsi #solverSearch).
# Dipakai untuk hitung "Resolved Tiket Per Person" per agen piket.
TELEGRAM_SOLVER_IDS = {
    "ANNE": "70792",
    "ALFIRA": "70793",
    "TYAS": "55656",
    "ROFINA": "70791",
    "RIZKA": "65492",
    "IHSAN": "55655",
    "DIKA": "55653",
    "WINDU": "55654",
    "RIZKY": "55652",
}

# Agen untuk hitung "Resolved Tiket Per Person".
# - name          : nama tampilan di laporan
# - solver_id     : ID user SYGAP (value option #solverSearch), wajib untuk filter akurat
# - username      : username SYGAP (fallback)
# - coordinator_id: ID koordinator (fallback lama)
# solver_id diambil dari baris DataTable (id_coordinator) / opsi #solverSearch SYGAP:
#   I Nyoman Windu  = 55654, Dika Prananda Putra = 55653, Rizky Senja Budiman = 55652
REPORT_AGENTS = [
    {"name": "Windu", "solver_id": "55654", "username": "CRS2019332", "coordinator_id": "55654"},
    {"name": "Dika", "solver_id": "55653", "username": "", "coordinator_id": "55653"},
    {"name": "Rizky", "solver_id": "55652", "username": "", "coordinator_id": "55652"},
]

# Solver group yang dihitung untuk "Resolved Tiket Per Person"
# (jumlahkan filter per group, sesuai workflow: MO-INSERA + MO-BIMA)
REPORT_SOLVER_GROUPS = ["MO-INSERA", "MO-BIMA"]

# Status tiket yang dihitung sebagai "Saldo" (masih terbuka)
REPORT_ACTIVE_STATUSES = ["OPEN", "ASSIGNED", "IN_PROGRESS"]

# Status tiket yang dihitung sebagai "Resolved/Completed"
REPORT_COMPLETED_STATUSES = ["COMPLETED", "COMPLETE", "CLOSED"]

# Rentang tanggal untuk hitung resolved: "today" atau "all"
REPORT_RESOLVED_DATE_RANGE = "today"

# Field tanggal untuk verifikasi klien (basis = "Created at" per filter panel)
REPORT_RESOLVED_DATE_FIELDS = ["created_at", "created_date"]

# Basis tanggal harian di filter panel (#filterDateBtn) untuk hitungan
# "Resolved/Completed" -> "Created at" (label dropdown + value attribute)
REPORT_DATE_FILTER_BUTTON = "Created at"
REPORT_DATE_FILTER_VALUE = "created_at"

# Basis tanggal untuk hitungan Resolved/Completed per kategori.
# Dataset sampel menunjukkan basis ini = tanggal PENYELESAIAN (bukan created):
#   incident: "Resolution at"   (nilai: resolution_at)
#   request : "End Date at"     (nilai: end_date_at)
# (nilai value attribute mungkin perlu dikalibrasi ulang saat verifikasi live)
REPORT_RESOLVED_DATE_VALUE = {
    "incident": "resolution_at",
    "request": "end_date_at",
}

# Field tanggal dibuat tiket (untuk Terlama/Terbaru)
REPORT_CREATED_DATE_FIELDS = ["created_at", "created_date"]

# Pemetaan sla_status SYGAP -> warna laporan
# (tiket tanpa sla_status DAN tanpa end_date tidak dihitung di kolom warna)
REPORT_SLA_COLOR_MAP = {
    "green": ["", "null", "none", "ok", "safe", "green", "fine"],
    "yellow": ["warn", "warning", "yellow", "reminder"],
    "red": ["danger", "breach", "red", "overdue", "expired", "critical"],
}

# Warna SLA dari kolom slm_color (server) -> warna laporan
REPORT_SLM_COLOR_MAP = {"success": "green", "warning": "yellow", "danger": "red"}

# Fallback warna dari deadline (end_date): merah jika lewat,
# kuning jika tersisa < REPORT_SLA_YELLOW_HOURS jam
REPORT_SLA_YELLOW_HOURS = 2

# Halaman kategori tiket
REPORT_BASE_URL = "https://sygap.telkom.co.id//"
REPORT_PAGES = {
    "incident": "https://sygap.telkom.co.id//incident",
    "request": "https://sygap.telkom.co.id//req_fulfillment",
}

# Batas maksimum halaman DataTable yang dibaca saat paginate (keamanan)
REPORT_MAX_PAGES = 200

# Jika halaman login muncul, bot menunggu maksimum N detik sampai user login manual
REPORT_LOGIN_WAIT_SECONDS = 180
