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
    "CHANGE_SERVICE_ID": 9227,
    "DISPATCH_INCIDENT": 9228,
    "MYASSISTANCE": 9229,
}

CHROME_PROFILES = {
    9222: r"C:\ChromeDebug_TO",
    9223: r"C:\ChromeDebug_CANCLWORK",
    9224: r"C:\ChromeDebug_DISPATCH",
    9225: r"C:\ChromeDebug_GAMAS",
    9226: r"C:\ChromeDebug_REPORT",
    9227: r"C:\ChromeDebug_CHANGE_SERVICE_ID",
    9228: r"C:\ChromeDebug_INCIDENT",
    9229: r"C:\ChromeDebug_MYASSISTANCE",
}


# ==================================================
# URLs
# ==================================================

DASHBOARD_URL = "https://sygap.telkom.co.id/req_fulfillment"
INCIDENT_DASHBOARD_URL = "https://sygap.telkom.co.id/incident"

BISCUIT_URL = (
    "https://biscuit-dashboard-dev-playground.apps.mypaas.telkom.co.id"
    "/helpdesk/tools/inseratools"
)

GAMAS_RELATIONS_URL = (
    "https://oss-incident.telkom.co.id"
    "/jw/web/userview/ticketIncidentService/ticketIncidentService/_/gamasRelations"
)

# ==================================================
# OSS Incident API (Service Type Update)
# ==================================================

OSS_INCIDENT_API_URL = os.environ.get(
    "OSS_INCIDENT_API_URL",
    "https://oss-incident.telkom.co.id/jw/web/json/plugin/id.co.itasoft.telkom.oss.plugin.CompleteActivityTicketIncidentApiV4/service?=&",
)

# Secrets diambil dari .env (tidak disimpan di dalam kode/git)
OSS_INCIDENT_API_ID = os.environ.get("OSS_INCIDENT_API_ID", "")
OSS_INCIDENT_API_KEY = os.environ.get("OSS_INCIDENT_API_KEY", "")



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
# Isi di .env: TELEGRAM_BOT_TOKEN_CANCLWORK, TELEGRAM_BOT_TOKEN_DISPATCH, TELEGRAM_BOT_TOKEN_GAMAS, TELEGRAM_BOT_TOKEN_CHANGE_SERVICE_ID
TELEGRAM_BOT_TOKEN_CANCLWORK = os.environ.get("TELEGRAM_BOT_TOKEN_CANCLWORK", "")
TELEGRAM_BOT_TOKEN_DISPATCH = os.environ.get("TELEGRAM_BOT_TOKEN_DISPATCH", "")
TELEGRAM_BOT_TOKEN_DISPATCH_INCIDENT = os.environ.get("TELEGRAM_BOT_TOKEN_DISPATCH_INCIDENT", "")
TELEGRAM_BOT_TOKEN_GAMAS = os.environ.get("TELEGRAM_BOT_TOKEN_GAMAS", "")
TELEGRAM_BOT_TOKEN_CHANGE_SERVICE_ID = os.environ.get("TELEGRAM_BOT_TOKEN_CHANGE_SERVICE_ID", "")

# Chat ID tujuan log per fitur. Kosong -> fallback ke TELEGRAM_ALLOWED_USER_IDS.
TELEGRAM_CHAT_IDS = {
    "canclwork": [],
    "dispatch": [],
    "dispatch_incident": [],
    "gamas_relations": [],
    "change_service_id": [],
}

_raw_allowed = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
if _raw_allowed:
    TELEGRAM_ALLOWED_USER_IDS = [int(x.strip()) for x in _raw_allowed.split(",") if x.strip().isdigit()]
else:
    TELEGRAM_ALLOWED_USER_IDS = []  # chat ID user yang boleh akses; kosongkan = semua boleh akses

# Admin yang berhak menjalankan perintah kontrol sensitif (/stop, start fitur bot, dsb).
# Default: [903566652] (ID Bli Komang). Bisa ditambah via .env: TELEGRAM_ADMIN_USER_IDS=903566652,123456
_raw_admins = os.environ.get("TELEGRAM_ADMIN_USER_IDS", "").strip()
if _raw_admins:
    TELEGRAM_ADMIN_USER_IDS = [int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()]
else:
    TELEGRAM_ADMIN_USER_IDS = [903566652]

# Request Coordinator (solver) yang tiketnya TIDAK boleh disentuh bot (skip semua fitur).
# Rizky Senja Budiman (CRS2018192) = 55652.
# ID angka dicocokkan persis ke value field; nama/username dicocokkan sebagian
# (case-insensitive) ke label — menutup kasus form incident yang valuenya
# berupa username, bukan ID angka.
SKIP_COORDINATOR_USER_IDS = ["55652", "Rizky Senja Budiman", "CRS2018192"]

# ==================================================
# Report Harian Helpdesk Operasional
# ==================================================

# Chrome untuk report — terisolasi di port REPORT (9226) agar tidak tabrakan dengan TO (9222) yang sudah dihapus.
# Profil: C:\ChromeDebug_REPORT — login sekali manual di Chrome port 9226, lalu report akan reuse sesi.
REPORT_CDP_PORT = CHROME_PORTS["REPORT"]

# Chat ID channel/grup tujuan report (misal @hdsigmaniwbis).
# Untuk channel: ID negatif, dapat via @getidsbot atau forward pesan ke bot.
REPORT_CHAT_IDS = [903566652]  # sementara: pribadi @komangwindu; ganti ke ID grup/channel saat bot masuk group

# Jadwal kirim otomatis: tiap N menit, 24 jam (boundary kelipatan interval
# dari jam 00:00, mis. interval 30 -> 00:00, 00:30, 01:00, ... 23:30).
REPORT_SCHEDULE_INTERVAL_MINUTES = 30

# Shift kerja: header laporan mengikuti shift yang sedang aktif saat report
# dijalankan. Deteksi otomatis dari jam server.
#   Shift 1: 00:00-09:00, Shift 2: 09:00-16:30, Shift 3: 16:30-23:59
# Pergantian shift 1 -> 2 di 09:00, shift 2 -> 3 di 16:30; report tepat di
# jam AKHIR sebuah shift masih dihitung shift itu (mis. 09:00 -> Shift 1,
# 16:30 -> Shift 2). Khusus 00:00 -> Shift 1 (bukan Shift 3), karena hari
# baru dimulai. Jika dua shift memuat waktu sama (overlap), shift yang
# BERAKHIR paling awal menang.
# Daftar orang per report = hanya yang MASUK di shift aktif (dari sheet
# jadwal), bukan semua piket hari itu.
# 'end' = "00:00" berarti akhir hari (lewat tengah malam).
REPORT_SHIFTS = [
    {"label": "Shift 1", "level": "L1", "start": "00:00", "end": "09:00"},
    {"label": "Shift 2", "level": "L1", "start": "09:00", "end": "16:30"},
    {"label": "Shift 3", "level": "L1", "start": "16:30", "end": "23:59"},
]

# Google Sheet jadwal shift (export CSV public, tanpa login).
# Ganti gid untuk tab lain (current: tab jadwal L1/L2&L3).
JADWAL_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1VlLQx0CxMeWStMjpkwQWiq8nbXaYqO2fJABAe7JNhmg/export?format=csv&gid=890618279"
)

# Katalog Owner Group INSERA untuk koreksi typo dispatch.
# Isi dengan link Google Sheet (tab berisi kolom 'Person Group Name' + 'Status',
# share "Anyone with the link" Viewer), atau kosongkan untuk memakai file lokal
# DispatchAssistant/data/owner_groups.xlsx|.csv.
OG_SHEET_URL = os.environ.get("OG_SHEET_URL", "")

# Nama di sheet jadwal yang berbeda dengan kunci TELEGRAM_USERNAMES.
JADWAL_SHEET_NAMES = {
    "I NYOMAN WINDU": "WINDU",
    "RIZKY SENJA BUDIMAN": "RIZKY",
    "RIZKY SENJA": "RIZKY",
    "RIZKY": "RIZKY",
    # L2
    "ADAM (L2)": "ADAM",
    "ADAM": "ADAM",
    "RIYAN (L2)": "RIYAN",
    "RIYAN": "RIYAN",
    "ADYTAMA (L2)": "ADY",
    "ADYTAMA": "ADY",
    "ADY": "ADY",
    "FAISHAL (L2)": "FAISAL",
    "FAISHAL": "FAISAL",
    "FAISAL (L2)": "FAISAL",
    "FAISAL": "FAISAL",
    "ERWIN (L2)": "ERWIN",
    "ERWIN": "ERWIN",
    "RIZKY ARDIAN (L2)": "RIZKY ARDIAN",
    "RIZKY ARDIAN": "RIZKY ARDIAN",
    # DEV
    "REZA (DEV INSERA)": "REZA",
    "REZA": "REZA",
    "AJI (DEV BIMA)": "AJI",
    "AJI": "AJI",
    "WILDAN (DEV BIMA)": "WILDAN",
    "WILDAN": "WILDAN",
    # L3
    "KEVIN (L3)": "KEVIN",
    "KEVIN": "KEVIN",
    "GUNTUR (L3)": "GUNTUR",
    "GUNTUR": "GUNTUR",
    "DANA (L3)": "DANA",
    "DANA": "DANA",
}

# Header laporan
REPORT_TITLE = "Laporan Harian Helpdesk Operasional"
REPORT_CHANNEL = "@hdsigmaniwbis"
REPORT_PERSONNEL = ["@dikaprndx", "@komangwindu", "@rizkysenjab"]

# Mapping nama -> tag Telegram.
# Input piket (GUI/Telegram) cukup nama saja, otomatis diubah ke tag ini.
# Pencocokan tidak peka huruf besar/kecil, mis. "windu" -> @komangwindu.
TELEGRAM_USERNAMES = {
    # L1
    "ANNE": "@annemaswa27",
    "ALFIRA": "@hifirrr",
    "TYAS": "@ikhpani",
    "ROFINA": "@InaBiti",
    "RIZKA": "@rizkayln",
    "IHSAN": "@ihsanabdi123",
    "DIKA": "@dikaprndx",
    "WINDU": "@komangwindu",
    "RIZKY": "@rizkysenjab",
    # L2 & DEV
    "RIYAN": "@riyanalwandika",
    "ADAM": "@Adamilhamm",
    "ADY": "@ady_tama",
    "FAISAL": "@ishal223",
    "AJI": "@aifllvyy",
    "WILDAN": "@wildanfariz",
    "REZA": "@rezzamf",
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
