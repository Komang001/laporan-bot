import csv
import io
import json
import logging
import os
import re
import threading
import urllib.request
from datetime import datetime, timedelta

from config.settings import (
    JADWAL_SHEET_NAMES,
    JADWAL_SHEET_URL,
    REPORT_ACTIVE_STATUSES,
    REPORT_AGENTS,
    REPORT_CHANNEL,
    REPORT_COMPLETED_STATUSES,
    REPORT_CREATED_DATE_FIELDS,
    REPORT_DATE_FILTER_VALUE,
    REPORT_MAX_PAGES,
    REPORT_LOGIN_WAIT_SECONDS,
    REPORT_PAGES,
    REPORT_BASE_URL,
    REPORT_RESOLVED_DATE_FIELDS,
    REPORT_RESOLVED_DATE_RANGE,
    REPORT_SLA_COLOR_MAP,
    REPORT_SLM_COLOR_MAP,
    REPORT_SLA_YELLOW_HOURS,
    REPORT_RESOLVED_DATE_VALUE,
    REPORT_SOLVER_GROUPS,
    REPORT_TITLE,
    REPORT_PERSONNEL,
    REPORT_SHIFTS,
    TELEGRAM_SOLVER_IDS,
    TELEGRAM_USERNAMES,
)
logger = logging.getLogger(__name__)

CATEGORY_LABELS = {"incident": "Incident", "request": "Request"}

DAY_NAMES = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTH_NAMES = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

# ==================================================
# Helpers
# ==================================================

def _parse_dt(value):
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y %H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    # Format SYGAP: "at Aug 07, 2026, 09:10:26<b> by 40961036 - NAMA"
    m = re.search(r"\b([A-Za-z]{3}) (\d{1,2}), (\d{4}), (\d{2}:\d{2}:\d{2})\b", value)
    if m:
        try:
            return datetime.strptime(
                f"{m.group(1)} {m.group(2)} {m.group(3)} {m.group(4)}",
                "%b %d %Y %H:%M:%S",
            )
        except ValueError:
            pass
    return None


def _normalize_row(raw, headers):
    """Ubah baris DataTable (dict atau list) menjadi dict normal."""
    if isinstance(raw, dict):
        return {str(k).lower(): v for k, v in raw.items()}
    if isinstance(raw, (list, tuple)):
        return {str(h).lower(): raw[i] for i, h in enumerate(headers) if i < len(raw)}
    return {}


def safe_eval(page, expr, retries=3, wait_ms=1500):
    """page.evaluate yang tahan race navigation.

    Saat evaluate dijalankan, halaman bisa saja sedang navigasi (reload dari
    bot fitur lain yang share Chrome 9222, atau user reload manual) ->
    Playwright memunculkan 'Execution context was destroyed, most likely
    because of a navigation'. Kita tunggu load-state lalu ulangi beberapa
    kali sebelum menyerah, supaya report tidak gagal karena kebetulan
    bentrok navigasi.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            return page.evaluate(expr)
        except Exception as e:  # noqa: BLE001
            last_err = e
            msg = str(e).lower()
            nav_like = (
                "execution context" in msg
                or "context was destroyed" in msg
                or "navigat" in msg
            )
            if nav_like and attempt < retries:
                try:
                    page.wait_for_timeout(wait_ms)
                except Exception:
                    pass
                continue
            # error selain navigasi -> langsung raise (biar caller tangani)
            raise
    if last_err:
        raise last_err
    return None


# ==================================================
# Report Service
# ==================================================

def _current_shift(now=None):
    """Shift yang sedang aktif pada waktu tertentu (default: sekarang).

    Rule (sesuai Google Sheet jadwal):
    - Interval shift: start <= jam < end (end "00:00" berarti akhir hari,
      diproses sebagai 24:00, sehingga 00:00 = AWAL hari -> Shift 1).
    - Boundary: report tepat di jam AKHIR sebuah shift masih dihitung shift
      itu (mis. 09:00 -> Shift 1, 16:30 -> Shift 2). Khusus 00:00 -> Shift 1
      (bukan Shift 3), karena hari baru dimulai.
    - Overlap: shift yang BERAKHIR paling awal menang (16:30 -> Shift 2,
      09:00 -> Shift 1).
    """
    now = now or datetime.now()
    minutes = now.hour * 60 + now.minute
    candidates = []
    for s in REPORT_SHIFTS:
        sh, sm = (int(x) for x in s["start"].split(":"))
        eh, em = (int(x) for x in s["end"].split(":"))
        start_m = sh * 60 + sm
        end_m = eh * 60 + em
        if end_m == 0:
            end_m = 24 * 60
        if end_m > start_m:
            inside = start_m <= minutes <= end_m
        else:
            inside = minutes >= start_m or minutes <= end_m
        if inside:
            candidates.append({**s, "start_m": start_m, "end_m": end_m})
    if not candidates:
        return REPORT_SHIFTS[0] if REPORT_SHIFTS else None
    for c in candidates:
        if c["end_m"] == minutes:
            return c
    return min(candidates, key=lambda c: c["end_m"])


class ReportService:

    def __init__(self, browser_manager=None, log_callback=None):
        self.browser_manager = browser_manager
        self.log = log_callback or (lambda msg: None)
        self._table_cache = {}
        self._solver_opts = None

    # --------------------------------------------------
    # Browser helpers
    # --------------------------------------------------

    def _browser(self):
        if self.browser_manager is None:
            raise Exception("browser_manager tidak diset.")
        if not self.browser_manager.is_connected():
            self.browser_manager.connect()
        return self.browser_manager

    def _open_page(self, url):
        """Buka halaman SYGAP dengan reuse sesi login yang sudah ada.

        1. Ada tab sygap yang sedang login -> buka tab baru langsung ke target
           (tidak mengganggu tab dashboard yang sedang dipakai fitur lain).
        2. Belum ada sesi -> buka base https://sygap.telkom.co.id// dulu
           (muncul halaman login), user login manual, lalu jalankan lagi.
        """
        bm = self._browser()
        path = re.sub(r"/{2,}", "/", re.sub(r"^https?://[^/]+", "", url).rstrip("/"))

        def _norm(u):
            return (u or "").lower().replace("//", "/")

        logged_in = False
        for p in bm.get_pages():
            try:
                cur = _norm(p.url)
            except Exception:
                continue
            if "sygap.telkom.co.id" not in cur:
                continue
            if path and path in cur:
                bm.activate_page(p)
                # Reload segar: reset seluruh state filter dari eksperimen
                # sebelumnya agar query selanjutnya konsisten.
                try:
                    p.goto(url, wait_until="domcontentloaded", timeout=30000)
                    p.wait_for_timeout(4000)
                except Exception:
                    pass
                return p
            if "login" not in cur:
                logged_in = True

        # Sesi login sudah ada -> buka tab baru langsung ke halaman target
        if logged_in:
            page = bm.open_url(url)
            if page is None:
                raise Exception(f"Gagal buka halaman: {url}")
            bm.activate_page(page)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            self._log_open_result(page, path)
            return page

        # Belum ada sesi -> buka base dulu (login page jika perlu)
        self.log(f"  [open] Membuka SYGAP base: {REPORT_BASE_URL}")
        page = bm.open_url(REPORT_BASE_URL)
        if page is None:
            page = bm.open_url(url)
            if page is None:
                raise Exception(f"Gagal buka halaman: {url}")
        bm.activate_page(page)
        page.wait_for_load_state("domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)

        final = _norm(page.url)
        if "login" in final:
            self.log(
                f"  [login] Halaman login terdeteksi. Silakan login manual di "
                f"tab tersebut (maks {REPORT_LOGIN_WAIT_SECONDS}s)..."
            )
            waited = 0
            while waited < REPORT_LOGIN_WAIT_SECONDS:
                page.wait_for_timeout(5000)
                waited += 5
                try:
                    final = _norm(page.url)
                except Exception:
                    continue
                if "login" not in final and "sygap.telkom.co.id" in final:
                    self.log(f"  [login] Login berhasil setelah {waited}s - lanjut.")
                    break
            else:
                self.log(
                    "  [login] Waktu tunggu login habis. "
                    "Login manual dulu, lalu jalankan report lagi."
                )
                return page

        if path and path not in final:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
            except Exception as e:
                self.log(f"  [nav] Gagal navigasi ke {url}: {e}")
        self._log_open_result(page, path)
        return page

    def _log_open_result(self, page, path):
        try:
            final = page.url.lower()
        except Exception:
            final = ""
        if path and path not in final.replace("//", "/"):
            self.log(
                f"  [WARNING] '{path}' tidak terbuka - redirect ke '{final[:70]}'. "
                "Login manual di tab SYGAP yang terbuka, lalu jalankan report lagi."
            )
        else:
            self.log(f"  [ok] Halaman '{path}' terbuka.")

    # --------------------------------------------------
    # DataTable helpers (server-side DataTables + jQuery)
    # --------------------------------------------------

    def _table_id(self, page):
        if page in self._table_cache:
            return self._table_cache[page]
        # Prioritaskan id eksplisit (requestFulfillmentTable/incidentTable) via getElementById,
        # bukan via table.dataTable yang bisa ketemu MFAUserDetailTable di modal hidden.
        table_id = safe_eval(page,"""
            (() => {
                var pref = ['requestFulfillmentTable', 'incidentTable'];
                for (var i = 0; i < pref.length; i++) {
                    var el = document.getElementById(pref[i]);
                    if (el) return pref[i];
                }
                // Fallback: cari dataTable yang visible dan bukan MFA
                var tables = document.querySelectorAll('table.dataTable');
                for (var j = 0; j < tables.length; j++) {
                    var tid = tables[j].id || '';
                    if (!tid) continue;
                    if (tid.toLowerCase().indexOf('mfa') !== -1) continue;
                    if (tid.toLowerCase().indexOf('userdetail') !== -1) continue;
                    return tid;
                }
                return null;
            })()
        """)
        self._table_cache[page] = table_id
        return table_id

    def _headers(self, page, table_id):
        return safe_eval(page,
            "(() => {"
            "var h = [];"
            f"document.querySelectorAll('#{table_id} thead th').forEach(function (th) {{ h.push((th.innerText || '').trim()); }});"
            "return h;"
            "})()"
        )

    def _page_info(self, page, table_id):
        try:
            return safe_eval(page,f"""
                (() => {{
                    var t = jQuery('#{table_id}').DataTable();
                    if (!t) return null;
                    var i = t.page.info();
                    return {{ records: i.recordsTotal, display: i.recordsDisplay, pages: i.pages, length: i.length }};
                }})()
            """)
        except Exception:
            return None

    def _rows_current(self, page, table_id, headers):
        """Ambil baris pada halaman aktif DataTable via API JS."""
        data = safe_eval(page,f"""
            (() => {{
                var t = jQuery('#{table_id}').DataTable();
                if (!t) return [];
                return t.rows().data().toArray();
            }})()
        """)
        return [_normalize_row(d, headers) for d in (data or [])]

    def _fetch_all_rows(self, page, table_id):
        """Paginate seluruh baris DataTable (server-side) menjadi list dict.

        Catatan: `page.len(-1)` (one-shot all-rows) tidak dipakai karena merusak
        state tabel request SYGAP (server menolak length=-1 lalu recordsTotal
        jadi tidak valid). Iterasi halaman per halaman dengan draw() penuh.
        """
        headers = self._headers(page, table_id)
        if headers is None:
            return [], []

        info = self._page_info(page, table_id)
        total = (info or {}).get("records", 0) or 0
        if total == 0:
            return [], headers

        all_rows = []
        seen = set()
        page_idx = 0
        last_len = -1
        while page_idx < REPORT_MAX_PAGES:
            info_now = safe_eval(page,f"""
                (() => {{
                    var t = jQuery('#{table_id}').DataTable();
                    var i = t.page.info();
                    return {{ records: i.recordsTotal, pages: i.pages, page: i.page, length: i.length }};
                }})()
            """)
            current = safe_eval(page,f"""
                (() => {{
                    var t = jQuery('#{table_id}').DataTable();
                    if (!t) return [];
                    return t.rows().data().toArray();
                }})()
            """)
            for d in (current or []):
                row = _normalize_row(d, headers)
                key = str(row)
                if key not in seen:
                    seen.add(key)
                    all_rows.append(row)
            if len(all_rows) == last_len:
                break
            last_len = len(all_rows)
            if info_now and info_now.get("records") is not None and len(all_rows) >= info_now["records"]:
                break
            next_page = (info_now or {}).get("page", 0) + 1
            max_page = (info_now or {}).get("pages", 1) - 1
            if next_page > max_page:
                break
            try:
                safe_eval(page,f"jQuery('#{table_id}').DataTable().page({next_page}).draw(false);")
                page.wait_for_timeout(2000)
            except Exception:
                break
            page_idx += 1

        # Kembalikan tabel ke halaman pertama agar tab rapi
        try:
            safe_eval(page,f"jQuery('#{table_id}').DataTable().page(0).draw(false);")
        except Exception:
            pass

        self.log(f"  [dtable] paginate selesai: {len(all_rows)} row(s) (maks {REPORT_MAX_PAGES} halaman)")
        return all_rows, headers

    # --------------------------------------------------
    # Filters
    # --------------------------------------------------

    def _select_search(self, page, label):
        """Set #searchSelect ke label tertentu (OPEN/COMPLETED). Best-effort:
        halaman tertentu tidak punya kontrol ini -> klasifikasi status tetap
        dilakukan di sisi klien dari kolom `status`."""
        try:
            sel = page.locator("#searchSelect")
            if sel.count() > 0:
                options = sel.locator("option")
                texts = [options.nth(i).inner_text().strip().upper() for i in range(options.count())]
                if label.upper() in texts:
                    sel.select_option(label=texts[texts.index(label.upper())])
                    page.wait_for_timeout(800)
                    return True
                self.log(f"  [filter] option '{label}' tidak ada. Tersedia: {texts}")
                return False
        except Exception as e:
            self.log(f"  [filter] #searchSelect error: {e}")
        return False

    def _set_date_filter(self, page, start=None, end=None, field_value=None):
        """Set filter tanggal di panel (#filterDateBtn / #start_date / #end_date).

        start/end None -> kosongkan.
        field_value None -> biarkan dropdown apa adanya (default "created_at").
        Format tanggal harus penuh ('YYYY-MM-DD HH:MM:SS'); kalau cuma tanggal,
        otomatis dilengkapi jam (00:00:00 / 23:59:59) agar server memakainya.
        """
        def _full(v, which):
            v = str(v or "").strip()
            if not v:
                return ""
            if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
                return f"{v} 00:00:00" if which == "start" else f"{v} 23:59:59"
            return v
        try:
            start_full = _full(start, "start")
            end_full = _full(end, "end")
            if field_value is not None:
                safe_eval(page,f"""
                    (() => {{
                        var b = document.getElementById('filterDateBtn');
                        if (b) {{
                            b.setAttribute('value', '{field_value}');
                            var t = b.querySelector('span') || b;
                            t.textContent = '{field_value.replace('_', ' ').title()}';
                        }}
                    }})()
                """)
            safe_eval(page,f"""
                (() => {{
                    function setVal(id, v) {{
                        var e = document.getElementById(id);
                        if (!e) return;
                        e.value = v;
                        e.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                    // incident: snake_case; request: camelCase
                    setVal('start_date', '{start_full}');
                    setVal('end_date', '{end_full}');
                    setVal('startDate', '{start_full}');
                    setVal('endDate', '{end_full}');
                }})()
            """)
            self.log(
                f"  [filter] tanggal: start='{start_full or '-'}' end='{end_full or '-'}' "
                f"field='{field_value or '-'}'"
            )
        except Exception as e:
            self.log(f"  [filter] set date filter error: {e}")

    def _apply_filter(self, page):
        """Klik tombol Apply via JS (Playwright locator click kadang tidak
        men-trigger reload saat panel filter tertutup)."""
        try:
            ok = safe_eval(page,
                "(function(){var b=document.getElementById('btn_apply');"
                "if(!b) return false; b.click(); return true;})()"
            )
            if ok:
                page.wait_for_timeout(5000)
                return True
        except Exception as e:
            self.log(f"  [filter] apply gagal: {e}")
        return False

    def _set_select_filter(self, page, select_id, value):
        """Set nilai <select> (termasuk select2) lalu trigger change via jQuery."""
        value = str(value or "")
        try:
            safe_eval(page,f"""
                (() => {{
                    var el = document.getElementById('{select_id}');
                    if (!el) return;
                    el.value = '{value}';
                    if (window.jQuery) {{
                        try {{ jQuery(el).trigger('change'); }} catch (e) {{}}
                    }}
                }})()
            """)
            return True
        except Exception as e:
            self.log(f"  [filter] set select #{select_id} gagal: {e}")
            return False

    def _set_solver_group(self, page, group_name):
        """Filter #solverGroupSearch ke nama group (MO-INSERA / MO-BIMA)."""
        val = safe_eval(page,f"""
            (() => {{
                var s = document.getElementById('solverGroupSearch');
                if (!s) return null;
                for (var i = 0; i < s.options.length; i++) {{
                    if ((s.options[i].text || '').trim().toUpperCase() === '{group_name.upper()}') {{
                        return s.options[i].value;
                    }}
                }}
                if (s.options.length <= 1) {{
                    // opsi belum dimuat -> tidak bisa di-set
                    return 'UNLOADED';
                }}
                return null;
            }})()
        """)
        if val == "UNLOADED":
            self.log(f"  [filter] opsi #solverGroupSearch belum dimuat")
            return False
        if val is None:
            self.log(f"  [filter] solver group '{group_name}' tidak ditemukan")
            return False
        return self._set_select_filter(page, "solverGroupSearch", val)

    def _solver_options(self, page):
        if self._solver_opts is None:
            self._solver_opts = safe_eval(page,"""
                (() => {
                    var s = document.getElementById('solverSearch');
                    if (!s) return [];
                    var out = [];
                    for (var i = 0; i < s.options.length; i++) {
                        out.push({v: s.options[i].value, t: (s.options[i].text || '').trim()});
                    }
                    return out;
                })()
            """)
            self.log(f"  [filter] #solverSearch memuat {len(self._solver_opts or [])} opsi")
        return self._solver_opts or []

    def _solver_id_for(self, page, agent):
        """Cari solver_id: dr konfigurasi, atau auto-detect dari opsi #solverSearch."""
        if agent.get("solver_id"):
            return str(agent["solver_id"])
        hay = (agent.get("name") or "").upper()
        username = (agent.get("username") or "").upper()
        for o in self._solver_options(page):
            t = (o.get("t") or "").upper()
            if hay and hay in t:
                return o.get("v")
            if username and username in t:
                return o.get("v")
        return None

    def _count_completed(self, rows):
        """Hitung baris COMPLETED (server sudah dibatasi tanggal oleh filter)."""
        return sum(1 for r in rows if self._is_completed(r))

    # --------------------------------------------------
    # Extraction per kategori (incident / request)
    # --------------------------------------------------

    def collect_category(self, category):
        url = REPORT_PAGES.get(category)
        label = CATEGORY_LABELS.get(category, category)
        if not url:
            raise Exception(f"Kategori tidak dikenal: {category}")

        self.log(f"=== Kategori {label}: {url} ===")
        page = self._open_page(url)
        table_id = self._table_id(page)
        if not table_id:
            self.log(f"  WARNING: DataTable tidak ditemukan di {url}")
            return self._empty_category(category)

        self.log(f"  Table: #{table_id}")

        # --- Saldo (tiket aktif / backlog OPEN, tanpa filter tanggal) ---
        self._set_date_filter(page)
        self._select_search(page, "OPEN")
        self._apply_filter(page)
        rows, headers = self._fetch_all_rows(page, table_id)
        active = [r for r in rows if self._is_active(r)]
        self.log(f"  Saldo: {len(active)} tiket aktif dari {len(rows)} baris")

        saldo = len(active)
        colors = {"green": 0, "yellow": 0, "red": 0}
        created_dates = []
        for r in active:
            color = self._color_for(r)
            if color:
                colors[color] += 1
            dt = self._first_date(r, REPORT_CREATED_DATE_FIELDS)
            if dt:
                created_dates.append(dt)

        oldest = min(created_dates) if created_dates else None
        newest = max(created_dates) if created_dates else None

        # --- Resolved (Created at = hari ini, server-side filter) ---
        today = datetime.now().strftime("%Y-%m-%d")
        self._set_date_filter(page, today, f"{today} 23:59:59", REPORT_DATE_FILTER_VALUE)
        self._select_search(page, "COMPLETED")
        self._apply_filter(page)
        comp_rows, _ = self._fetch_all_rows(page, table_id)
        resolved = self._count_resolved(comp_rows)
        self.log(f"  Resolved ({REPORT_RESOLVED_DATE_RANGE}): {resolved} dari {len(comp_rows)} completed")

        return {
            "category": category,
            "label": label,
            "saldo": saldo,
            "green": colors["green"],
            "yellow": colors["yellow"],
            "red": colors["red"],
            "oldest": oldest,
            "newest": newest,
            "resolved": resolved,
        }

    def collect_agent(self, agent):
        total = 0
        detail = {}
        today = datetime.now().strftime("%Y-%m-%d")
        for category in REPORT_PAGES:
            page = self._open_page(REPORT_PAGES[category])
            table_id = self._table_id(page)
            if not table_id:
                continue
            self._set_date_filter(page, today, f"{today} 23:59:59", REPORT_DATE_FILTER_VALUE)
            self._select_search(page, "COMPLETED")
            self._apply_filter(page)
            comp_rows, _ = self._fetch_all_rows(page, table_id)
            count = 0
            for r in comp_rows:
                if self._is_completed(r) and self._belongs_to(r, agent) and self._in_date_range(r):
                    count += 1
            detail[category] = count
            total += count
            self.log(f"  {agent['name']} [{category}]: {count}")
        return {"name": agent["name"], "total": total, "detail": detail}

    # --------------------------------------------------
    # Row classification
    # --------------------------------------------------

    def _status(self, row):
        val = row.get("status") or ""
        return str(val).strip().upper()

    def _is_active(self, row):
        status = self._status(row)
        return status in [s.upper() for s in REPORT_ACTIVE_STATUSES]

    def _is_completed(self, row):
        status = self._status(row)
        return status in [s.upper() for s in REPORT_COMPLETED_STATUSES]

    def _is_final(self, row):
        """Status akhir yang dihitung sbg 'resolved' (server sudah menyaring)."""
        return self._status(row) in ("RESOLVED", "COMPLETED")

    def _color_for(self, row):
        """Warna SLA: 🟢 / 🟡 / 🔴. None jika tiket tanpa info SLA."""
        slm = str(row.get("slm_color") or "").strip().lower()
        if slm in REPORT_SLM_COLOR_MAP:
            return REPORT_SLM_COLOR_MAP[slm]

        sla = str(row.get("sla_status") or "").strip().lower()
        end = row.get("end_date") or row.get("end_locking_time") or ""
        end_dt = _parse_dt(end)

        if not sla and end_dt is None:
            return None

        for color, keys in REPORT_SLA_COLOR_MAP.items():
            if sla in [k.strip().lower() for k in keys]:
                return color

        if end_dt is not None:
            now = datetime.now()
            if end_dt < now:
                return "red"
            if end_dt < now + timedelta(hours=REPORT_SLA_YELLOW_HOURS):
                return "yellow"
            return "green"

        return "green"

    def _first_date(self, row, fields):
        for f in fields:
            dt = _parse_dt(row.get(f))
            if dt:
                return dt
        return None

    def _in_date_range(self, row):
        if REPORT_RESOLVED_DATE_RANGE == "all":
            return True
        today = datetime.now().date()
        dt = self._first_date(row, REPORT_RESOLVED_DATE_FIELDS)
        if dt is None:
            return False
        return dt.date() == today

    def _count_resolved(self, rows):
        count = 0
        for r in rows:
            if self._is_completed(r) and self._in_date_range(r):
                count += 1
        return count

    def _belongs_to(self, row, agent):
        if agent.get("coordinator_id"):
            if str(row.get("id_coordinator") or "").strip() == str(agent["coordinator_id"]).strip():
                return True
        if agent.get("username"):
            user = str(row.get("coordinator_username") or "")
            if user.strip().lower() == str(agent["username"]).strip().lower():
                return True
        if agent.get("name"):
            name = str(row.get("coordinator_name") or "")
            if agent["name"].lower() in name.lower():
                return True
        return False

    def _belongs_to_any(self, row, agent):
        """Apakah baris dihandle agent: cocokkan via solver OR coordinator field."""
        name = (agent.get("name") or "").lower()
        solver_id = str(agent.get("solver_id") or "")
        coordinator_id = str(agent.get("coordinator_id") or "")
        username = (agent.get("username") or "").lower()

        solver_vals = [
            str(row.get("solver_id") or ""),
            str(row.get("id_solver") or ""),
            str(row.get("id_coordinator") or ""),
            str(row.get("coordinator_id") or ""),
        ]
        if solver_id and solver_id in solver_vals:
            return True
        if coordinator_id and coordinator_id in solver_vals:
            return True

        name_vals = [
            str(row.get("solver_name") or ""),
            str(row.get("coordinator_name") or ""),
            str(row.get("owner_name") or ""),
            str(row.get("solver_username") or ""),
            str(row.get("coordinator_username") or ""),
        ]
        for v in name_vals:
            v = v.lower()
            if not v or v in ("-", "none", "null"):
                continue
            if username and username in v:
                return True
            if name and name in v:
                return True
        return False

    def _empty_category(self, category):
        return {
            "category": category,
            "label": CATEGORY_LABELS.get(category, category),
            "saldo": 0, "green": 0, "yellow": 0, "red": 0,
            "oldest": None, "newest": None, "resolved": 0,
        }

    # --------------------------------------------------
    # Orchestrator
    # --------------------------------------------------

    def _status_select_id(self, category):
        """ID dropdown status: incident pakai #statusSearch, request #searchSelect."""
        return "statusSearch" if category == "incident" else "searchSelect"

    def _set_status(self, page, category, status):
        """Set nilai dropdown status via DOM tanpa memicu handler (Apply membaca
        nilai saat klik). Menghindari `advancedFilter` yang mengosongkan tanggal
        utk status normal (RESOLVED/COMPLETED)."""
        select_id = self._status_select_id(category)
        try:
            safe_eval(page,f"""
                (() => {{
                    var el = document.getElementById('{select_id}');
                    if (!el) return false;
                    el.value = '{status}';
                    return true;
                }})()
            """)
            return True
        except Exception as e:
            self.log(f"  [filter] set status #{select_id} gagal: {e}")
            return False

    def _set_select2(self, page, select_id, value, text=""):
        """Set nilai <select> select2 dengan cara yang benar: append option,
        set val, trigger change (tanpa destroy). Terbukti mengirim
        solverGroupSearch/solverSearch ke server saat Apply."""
        try:
            safe_eval(page,f"""
                (() => {{
                    var $ = window.jQuery, s = $('#{select_id}');
                    if (!s.length) return;
                    if (!s.find('option[value="{value}"]').length) {{
                        s.append('<option value="{value}">{text}</option>');
                    }}
                    s.val('{value}');
                    s.trigger('change');
                }})()
            """)
            return True
        except Exception as e:
            self.log(f"  [filter] set select2 #{select_id} gagal: {e}")
            return False

    def _clear_select2(self, page, select_id):
        try:
            safe_eval(page,f"""
                (() => {{
                    var $ = window.jQuery;
                    $('#{select_id}').val(null).trigger('change');
                }})()
            """)
        except Exception:
            pass

    def collect_all(self):
        """Kumpulkan semua data laporan (metode terkonfirmasi user).

        Per kategori:
          1. Saldo    -> status OPEN + Created at hari ini (semua grup),
                         warna dari SLA, Terlama/Terbaru dari Created at.
          2. Resolved -> status RESOLVED (incident) / COMPLETED (request)
                         + Created at hari ini (semua grup).
          3. Per person -> SERVER-SIDE #solverSearch per agen (id solver),
                         dijumlahkan dari request COMPLETED + incident RESOLVED.
        Total Resolved All Shift = jumlah resolved/Completed kedua kategori.
        """
        categories = {}
        agents = self._personnel_agents()
        agent_totals = {a["name"]: 0 for a in agents}
        agent_detail = {a["name"]: {c: 0 for c in REPORT_PAGES} for a in agents}
        today = datetime.now().strftime("%Y-%m-%d")

        for cat in REPORT_PAGES:
            url = REPORT_PAGES[cat]
            label = CATEGORY_LABELS.get(cat, cat)
            self.log(f"=== CATAL {label}: {url} ===")

            page = self._open_page(url)
            table_id = self._table_id(page)
            if not table_id:
                self.log(f"  WARNING: DataTable tidak ditemukan di {url}")
                categories[cat] = self._empty_category(cat)
                continue
            self.log(f"  Table: #{table_id}")

            # ---- 1. Saldo: OPEN (seluruh antrean aktif saat ini) ----
            self._clear_select2(page, "solverGroupSearch")
            self._clear_select2(page, "solverSearch")
            self._set_select_filter(page, "solverGroupSearch", "")
            self._set_status(page, cat, "OPEN")
            self._set_date_filter(page, None, None, None)
            self._apply_filter(page)
            open_rows, _ = self._fetch_all_rows(page, table_id)
            masuk = open_rows
            self.log(f"  Saldo (OPEN aktif): {len(masuk)} baris")

            colors = {"green": 0, "yellow": 0, "red": 0}
            created_dates = []
            for r in masuk:
                color = self._color_for(r)
                if color:
                    colors[color] += 1
                dt = self._first_date(r, REPORT_CREATED_DATE_FIELDS)
                if dt:
                    created_dates.append(dt)

            # ---- 2. Resolved/Completed: status + Created at hari ini ----
            resolved_status = "RESOLVED" if cat == "incident" else "COMPLETED"
            self._set_status(page, cat, resolved_status)
            self._set_date_filter(page, today, f"{today} 23:59:59", REPORT_DATE_FILTER_VALUE)
            self._apply_filter(page)
            info = self._page_info(page, table_id)
            resolved = (info or {}).get("records", 0) or 0
            self.log(
                f"  Resolved (status={resolved_status}, created_at hari ini): "
                f"{resolved} baris"
            )

            # ---- 3. Per person: server-side #solverSearch ----
            for a in agents:
                sid = str(a.get("solver_id") or "")
                if not sid:
                    self.log(f"  {a['name']} [{cat}]: SKIP (solver_id kosong)")
                    continue
                self._clear_select2(page, "solverSearch")
                self._set_select2(page, "solverSearch", sid, a["name"])
                self._apply_filter(page)
                pinfo = self._page_info(page, table_id)
                n = (pinfo or {}).get("records", 0) or 0
                agent_detail[a["name"]][cat] = n
                agent_totals[a["name"]] += n
                self.log(f"  {a['name']} [{cat}]: {n}")
            self._clear_select2(page, "solverSearch")

            categories[cat] = {
                "category": cat,
                "label": label,
                "saldo": len(masuk),
                "green": colors["green"],
                "yellow": colors["yellow"],
                "red": colors["red"],
                "oldest": min(created_dates) if created_dates else None,
                "newest": max(created_dates) if created_dates else None,
                "resolved": resolved,
            }

        agents = [
            {"name": name, "total": agent_totals[name], "detail": agent_detail[name]}
            for name in agent_totals
        ]
        return {"categories": categories, "agents": agents}

    def _personnel_agents(self):
        """Daftar agen 'Resolved Per Person': hanya yang MASUK di shift aktif.

        Prioritas: piket per-shift dari Google Sheet jadwal (orang yang masuk
        di shift sekarang) -> simpanan harian (data/daily_piket.json) ->
        REPORT_PERSONNEL. Setiap tag diresolusi ke nama (TELEGRAM_USERNAMES)
        lalu ke solver ID SYGAP (TELEGRAM_SOLVER_IDS) untuk filter server-side.
        """
        tags = _shift_people_tags()
        name_by_tag = {v.strip().lower(): k for k, v in TELEGRAM_USERNAMES.items()}
        agents = []
        for tag in tags or []:
            tag = str(tag).strip()
            if not tag:
                continue
            if not tag.startswith("@"):
                tag = "@" + tag
            name = name_by_tag.get(tag.lower())
            if name is None:
                self.log(f"  {tag}: SKIP (nama tidak dikenal)")
                continue
            sid = str(TELEGRAM_SOLVER_IDS.get(name) or "")
            if not sid:
                self.log(f"  {name}: SKIP (solver_id tidak diketahui)")
                continue
            agents.append({"name": name.title(), "tag": tag, "solver_id": sid})
        if not agents:
            self.log("  WARNING: tidak ada agen piket ter-resolusi - per person kosong")
        return agents

    def _created_today(self, row):
        dt = self._first_date(row, REPORT_CREATED_DATE_FIELDS)
        if dt is None:
            return False
        return dt.date() == datetime.now().date()

    def _count_agent_completed(self, rows, agent):
        return sum(
            1
            for r in rows
            if self._is_completed(r) and self._belongs_to(r, agent) and self._in_date_range(r)
        )

    # --------------------------------------------------
    # Formatting
    # --------------------------------------------------

    def format_report(self, data, now=None, personnel=None):
        now = now or datetime.now()
        categories = data["categories"]
        agents = data["agents"]

        piket = personnel
        if piket is None:
            piket = _shift_people_tags(now)

        cat_lines = []
        for cat in ("incident", "request"):
            c = categories[cat]
            lines = [
                f"{c['label']}: {c['saldo']}",
                f"🟢 : {c['green']} | 🟡 : {c['yellow']} | 🔴 : {c['red']}",
            ]
            if c["oldest"]:
                lines.append(f"⏱️ Terlama: {c['oldest'].strftime('%b %d, %Y, %H:%M:%S')}")
            else:
                lines.append("⏱️ Terlama: -")
            if c["newest"]:
                lines.append(f"🆕 Terbaru: {c['newest'].strftime('%b %d, %Y, %H:%M:%S')}")
            else:
                lines.append("🆕 Terbaru: -")
            resolved_label = "Total Completed" if cat == "request" else "Total Resolved"
            lines.append(f"📦 {resolved_label}: {c['resolved']}")
            cat_lines.append("\n".join(lines))

        agent_lines = []
        for a in agents:
            agent_lines.append(f"{a['name']} : {a['total']}")

        total_all_shift = sum(categories[c]["resolved"] for c in categories)

        shift = _current_shift(now)
        shift_line = (
            f"{shift['level']} ({shift['start']} - {shift['end']}):"
            if shift
            else "-"
        )

        block = [
            f"📄 {REPORT_TITLE}",
            REPORT_CHANNEL,
            f"Hari/Tanggal: {DAY_NAMES[now.weekday()]}, {now.day} {MONTH_NAMES[now.month - 1]} {now.year}",
            f"Last Update: {now.hour:02d}.{now.minute:02d} WIB",
            "",
            f"👥 Piket {shift['label'] if shift else '-'}",
            "",
            shift_line,
        ]
        block += piket
        block += [
            "",
            "————————————————————",
            "📌 Saldo Tiket Masuk",
            "",
            cat_lines[0],
            "",
            cat_lines[1],
            "————————————————————",
            "✅ Resolved Tiket Per Person",
            "",
        ]
        block += agent_lines
        block += [
            "",
            f"📊 Total Resolved All Shift: {total_all_shift}",
            "",
            "",
        ]
        pic_map = _sheet_pic_map(now)
        if pic_map:
            pic_line = None
            if shift:
                sh, sm = (int(x) for x in shift["start"].split(":"))
                key = _match_shift_slot(pic_map, sh * 60 + sm)
                tag = pic_map.get(key) if key is not None else None
                if tag:
                    pic_line = f"• PIC {shift['label']}: {tag}"
            if pic_line:
                block.append(pic_line)
            else:
                block.append("• (tidak ada PIC hijau di shift ini)")
        else:
            block.append("• (tidak terbaca / tanggal di luar jadwal sheet)")

        # ---- Catatan tukar shift (override) ----
        try:
            tukar_notes = _build_tukar_note(now)
            if tukar_notes:
                block.append("")
                block.append("🔄 Catatan Tukar Shift:")
                block.extend(tukar_notes)
        except Exception:
            pass

        return "\n".join(block)


# ==================================================
# Piket Harian (disimpan per tanggal)
# ==================================================

def _piket_path():
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
    return os.path.join(base, "daily_piket.json")


def _load_piket():
    try:
        with open(_piket_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_piket(data):
    path = _piket_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Gagal simpan piket: {e}")


def _norm_piket_names(names):
    """Normalisasi nama piket: resolusi nama -> tag Telegram, pastikan berawalan '@'."""
    result = []
    for n in names or []:
        n = str(n).strip()
        if not n:
            continue
        key = n[1:].upper() if n.startswith("@") else n.upper()
        resolved = TELEGRAM_USERNAMES.get(key)
        if resolved:
            result.append(resolved)
            continue
        if not n.startswith("@"):
            n = "@" + n
        result.append(n)
    return result


def save_piket(names, date=None):
    """Simpan daftar piket untuk tanggal tertentu (default: hari ini)."""
    date = date or datetime.now().strftime("%Y-%m-%d")
    data = _load_piket()
    data[date] = _norm_piket_names(names)
    _save_piket(data)
    return data[date]


def get_piket(date=None):
    """Ambil daftar piket tanggal tertentu (default: hari ini). None jika belum diset."""
    date = date or datetime.now().strftime("%Y-%m-%d")
    names = _load_piket().get(date)
    if not names:
        return None
    return _norm_piket_names(names)


def clear_piket(date=None):
    """Hapus piket tanggal tertentu (default: hari ini)."""
    date = date or datetime.now().strftime("%Y-%m-%d")
    data = _load_piket()
    if date in data:
        del data[date]
        _save_piket(data)
        return True
    return False


# ==================================================
# Tukar Shift - Override per shift (Opsi 1)
# ==================================================
# Struktur file: data/shift_overrides.json
# {
#   "2026-09-02": {
#     "Shift 1": ["@annemaswa27", "@komangwindu"],
#     "Shift 2": ["@dikaprndx"],
#     "Shift 3": ["@rizkayln"]
#   }
# }
# Prioritas di _shift_people_tags: override per shift > sheet > daily_piket > REPORT_PERSONNEL

_override_lock = threading.Lock()


def _override_path():
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
    return os.path.join(base, "shift_overrides.json")


def _load_overrides():
    try:
        with open(_override_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_overrides(data):
    path = _override_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Gagal simpan shift_overrides: {e}")


def _normalize_shift_label(label):
    """Normalisasi label shift: 'shift1','1','Shift 1','SHIFT1' -> 'Shift 1'."""
    s = str(label or "").strip().lower().replace(" ", "")
    if s in ("1", "shift1", "s1"):
        return "Shift 1"
    if s in ("2", "shift2", "s2"):
        return "Shift 2"
    if s in ("3", "shift3", "s3"):
        return "Shift 3"
    # coba parse "shift 2" dengan spasi
    m = re.match(r"shift\s*([123])", str(label or "").strip().lower())
    if m:
        return f"Shift {m.group(1)}"
    # fallback title case
    raw = str(label or "").strip()
    for cand in ("Shift 1", "Shift 2", "Shift 3"):
        if raw.lower() == cand.lower():
            return cand
    return raw.title() if raw else ""


def get_shift_overrides(date=None):
    """Ambil semua override per shift untuk tanggal tertentu. {} jika tidak ada."""
    date = date or datetime.now().strftime("%Y-%m-%d")
    with _override_lock:
        data = _load_overrides()
        day = data.get(date)
        if not isinstance(day, dict):
            return {}
        # filter hanya Shift 1/2/3, normalisasi tag
        out = {}
        for k, v in day.items():
            nk = _normalize_shift_label(k)
            if nk in ("Shift 1", "Shift 2", "Shift 3"):
                if isinstance(v, list):
                    out[nk] = _norm_piket_names(v)
                elif isinstance(v, str):
                    out[nk] = _norm_piket_names([v])
        return out


def get_shift_override(date, shift_label):
    """Ambil override untuk 1 shift. None jika tidak ada."""
    norm = _normalize_shift_label(shift_label)
    return get_shift_overrides(date).get(norm)


def save_shift_override(names, date=None, shift_label=None):
    """Simpan override per shift.

    names: list tag/nama atau single string
    date: YYYY-MM-DD (default hari ini)
    shift_label: 'Shift 1' / 'Shift 2' / 'Shift 3' (wajib)
    Return: list tag yang disimpan.
    """
    if not shift_label:
        raise ValueError("shift_label wajib: Shift 1 / Shift 2 / Shift 3")
    norm = _normalize_shift_label(shift_label)
    if norm not in ("Shift 1", "Shift 2", "Shift 3"):
        raise ValueError(f"shift_label tidak valid: {shift_label}")
    date = date or datetime.now().strftime("%Y-%m-%d")
    tags = _norm_piket_names(names if isinstance(names, (list, tuple)) else [names])
    with _override_lock:
        data = _load_overrides()
        if date not in data or not isinstance(data[date], dict):
            data[date] = {}
        data[date][norm] = tags
        _save_overrides(data)
    return tags


def clear_shift_override(date=None, shift_label=None):
    """Hapus override.

    - date=None, shift_label=None -> hapus semua hari ini
    - date=YYYY-MM-DD, shift_label=None -> hapus semua shift di tanggal itu
    - date, shift_label -> hapus 1 shift saja
    Return True jika ada yang dihapus.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")
    with _override_lock:
        data = _load_overrides()
        if date not in data:
            return False
        if shift_label is None:
            del data[date]
            _save_overrides(data)
            return True
        norm = _normalize_shift_label(shift_label)
        if norm in data[date]:
            del data[date][norm]
            if not data[date]:
                del data[date]
            _save_overrides(data)
            return True
        return False


def get_effective_piket_map(date=None):
    """Piket per shift efektif untuk tanggal: sheet dimerge dengan override.

    Return dict {jam_mulai_menit: [tags]} atau None jika sheet gagal & tidak ada override.
    Override mengganti total shift tersebut (bukan append).
    """
    date = date or datetime.now()
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, "%Y-%m-%d")
        except Exception:
            date = datetime.now()
    sheet_map = _sheet_piket_map(date)
    overrides = get_shift_overrides(date.strftime("%Y-%m-%d"))
    if sheet_map is None and not overrides:
        return None
    # base dari sheet (jika ada), kalau tidak ada buat map kosong
    effective = dict(sheet_map) if sheet_map else {}
    # mapping label -> start_m untuk override
    label_to_start = {}
    for s in REPORT_SHIFTS:
        sh, sm = (int(x) for x in s["start"].split(":"))
        label_to_start[s["label"]] = sh * 60 + sm
    for label, tags in overrides.items():
        start_m = label_to_start.get(label)
        if start_m is not None:
            effective[start_m] = tags
    return effective if effective else None


def _build_tukar_note(date=None, now=None):
    """Susun catatan tukar shift untuk footer laporan.

    Bandingkan sheet asli vs override. Return list baris catatan atau [].
    Contoh: '• Tukar Shift 2: @dikaprndx → @annemaswa27'
    """
    date = date or (now or datetime.now())
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, "%Y-%m-%d")
        except Exception:
            date = datetime.now()
    date_str = date.strftime("%Y-%m-%d")
    overrides = get_shift_overrides(date_str)
    if not overrides:
        return []
    sheet_map = _sheet_piket_map(date)
    label_to_start = {}
    for s in REPORT_SHIFTS:
        sh, sm = (int(x) for x in s["start"].split(":"))
        label_to_start[s["label"]] = sh * 60 + sm
    notes = []
    for label in ("Shift 1", "Shift 2", "Shift 3"):
        if label not in overrides:
            continue
        start_m = label_to_start.get(label)
        orig = []
        if sheet_map is not None and start_m is not None:
            # cari key sheet yang match (via _match_shift_slot)
            key = _match_shift_slot(sheet_map, start_m)
            if key is not None:
                orig = sheet_map.get(key, [])
        new = overrides[label]
        if set(orig) != set(new):
            if orig:
                notes.append(f"• Tukar {label}: {', '.join(orig)} → {', '.join(new)}")
            else:
                notes.append(f"• Override {label}: {', '.join(new)} (jadwal kosong)")
    return notes


# ==================================================
# Piket otomatis dari Google Sheet jadwal shift
# ==================================================

_sheet_cache = {"date": None, "tags": None}
_sheet_lock = threading.Lock()

_L1_SUMMARY_ROWS = {"SHIFT 1", "SHIFT 2", "SHIFT 3", "TOTAL MASUK PER HARI"}

_MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MEI": 5, "JUN": 6,
    "JUL": 7, "AGU": 8, "SEP": 9, "OKT": 10, "NOV": 11, "DES": 12,
}

_sheet_tabs_cache = {"ts": 0, "tabs": []}
_sheet_gid_cache = {}
_sheet_tabs_lock = threading.Lock()
_TABS_CACHE_TTL = 3600  # 1 jam


def _extract_spreadsheet_id(url=None):
    url = url or JADWAL_SHEET_URL
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None


def _fetch_sheet_tabs(sheet_id):
    """Ambil daftar (nama_tab, gid) dari halaman htmlview Google Spreadsheet."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/htmlview"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        return re.findall(r'name:\s*"([^"]+)"[^\}]+?gid:\s*"(\d+)"', html)
    except Exception as e:
        logger.warning(f"Gagal baca tabs htmlview: {e}")
        return []


def _get_cached_sheet_tabs(sheet_id, force_refresh=False):
    now_ts = datetime.now().timestamp()
    with _sheet_tabs_lock:
        if not force_refresh and _sheet_tabs_cache["tabs"] and (now_ts - _sheet_tabs_cache["ts"] < _TABS_CACHE_TTL):
            return _sheet_tabs_cache["tabs"]
    tabs = _fetch_sheet_tabs(sheet_id)
    if tabs:
        with _sheet_tabs_lock:
            _sheet_tabs_cache["ts"] = now_ts
            _sheet_tabs_cache["tabs"] = tabs
    return tabs


def _parse_tab_months(tab_name):
    """Ambil (bulan_1, bulan_2) dari nama tab mis. 'Agu-Sep' -> (8, 9)."""
    clean = re.sub(r'[^a-zA-Z]', ' ', tab_name).upper()
    tokens = clean.split()
    matched = []
    for t in tokens:
        for k, v in _MONTH_ABBR.items():
            if t.startswith(k):
                matched.append(v)
                break
    if len(matched) >= 2:
        return matched[0], matched[1]
    return None, None


def _check_tab_has_date(sheet_id, gid, m1, m2, target_month, target_day):
    """Periksa apakah tab Google Sheet memiliki kolom untuk target tanggal & bulan."""
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    raw = _fetch_sheet_csv(csv_url)
    if not raw:
        return False
    try:
        rows = list(csv.reader(io.StringIO(raw)))
    except Exception:
        return False

    start = None
    for i, r in enumerate(rows):
        if r and r[0] == "NAMA":
            start = i
            break
    if start is None:
        return False

    header = rows[start]
    cur_m = m1
    prev_d = 0
    for j in range(2, len(header)):
        val = (header[j] or "").strip().split(".")[0]
        if not val.isdigit():
            continue
        d = int(val)
        if prev_d and d < prev_d and m2 is not None:
            cur_m = m2
        prev_d = d
        if cur_m == target_month and d == target_day:
            return True
    return False


def _resolve_sheet_gid(target_date=None):
    """Cari gid tab sheet yang sesuai untuk tanggal tertentu secara otomatis.

    1. Cek cache per tanggal.
    2. Ambil daftar tab dari /htmlview Google Sheet.
    3. Filter tab kandidat yang mencakup bulan berjalan.
    4. Validasi keberadaan kolom tanggal pada tab.
    5. Fallback ke None jika tidak ditemukan (akan memakai default JADWAL_SHEET_URL).
    """
    target_date = target_date or datetime.now()
    date_str = target_date.strftime("%Y-%m-%d")
    with _sheet_tabs_lock:
        if date_str in _sheet_gid_cache:
            return _sheet_gid_cache[date_str]

    sheet_id = _extract_spreadsheet_id()
    if not sheet_id:
        return None

    tabs = _get_cached_sheet_tabs(sheet_id)
    if not tabs:
        return None

    target_m = target_date.month
    target_d = target_date.day

    candidate_tabs = []
    other_tabs = []
    for name, gid in tabs:
        m1, m2 = _parse_tab_months(name)
        if m1 == target_m or m2 == target_m:
            candidate_tabs.append((name, gid, m1, m2))
        else:
            other_tabs.append((name, gid, m1, m2))

    for name, gid, m1, m2 in candidate_tabs:
        if _check_tab_has_date(sheet_id, gid, m1, m2, target_m, target_d):
            with _sheet_tabs_lock:
                _sheet_gid_cache[date_str] = gid
            logger.info(f"Otomatis menggunakan tab sheet '{name}' (gid={gid}) untuk {date_str}")
            return gid

    for name, gid, m1, m2 in other_tabs:
        if _check_tab_has_date(sheet_id, gid, m1, m2, target_m, target_d):
            with _sheet_tabs_lock:
                _sheet_gid_cache[date_str] = gid
            logger.info(f"Otomatis menggunakan tab sheet '{name}' (gid={gid}) untuk {date_str}")
            return gid

    return None


def _get_sheet_csv_url_for_date(target_date=None):
    gid = _resolve_sheet_gid(target_date)
    if gid:
        sheet_id = _extract_spreadsheet_id()
        if sheet_id:
            return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return JADWAL_SHEET_URL


def _get_sheet_xlsx_url_for_date(target_date=None):
    gid = _resolve_sheet_gid(target_date)
    if gid:
        sheet_id = _extract_spreadsheet_id()
        if sheet_id:
            return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx&gid={gid}"
    return _sheet_xlsx_url()


def _fetch_sheet_csv(url=None):
    """Ambil CSV jadwal dari Google Sheet (public export). None jika gagal."""
    target_url = url or JADWAL_SHEET_URL
    try:
        req = urllib.request.Request(
            target_url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Gagal ambil jadwal dari sheet: {e}")
        return None


def _slot_to_minutes(slot):
    """'00.00-09.00' / '08:00-17:00' / '15.00-24.00' -> jam mulai dalam menit."""
    try:
        s, _e = slot.split("-")
        sh, sm = (int(x) for x in s.strip().replace(".", ":").split(":"))
        return sh * 60 + sm
    except Exception:
        return None


def _match_shift_slot(sheet_map, start_m):
    """Pilih key slot sheet untuk jam mulai shift dari config.

    Prioritas: key sama persis. Jika sheet memakai label jam yang berbeda
    (mis. slot '08:00-17:00' untuk shift config 09:00-16:30), pilih slot
    yang jam mulainya <= jam mulai shift (slot terakhir yang sudah mulai).
    """
    if not sheet_map:
        return None
    if start_m in sheet_map:
        return start_m
    starts = sorted(k for k in sheet_map if k <= start_m)
    return starts[-1] if starts else None


def _sheet_piket_map(date=None):
    """Piket L1 per shift (key: jam mulai shift dalam menit) pada tanggal
    tertentu dari Google Sheet jadwal. Di-cache per tanggal. None jika gagal
    (sheet tak bisa diambil / tanggal tidak ada di sheet).
    """
    date = date or datetime.now()
    date_str = date.strftime("%Y-%m-%d")
    with _sheet_lock:
        if _sheet_cache["date"] == date_str:
            return _sheet_cache["tags"]
    csv_url = _get_sheet_csv_url_for_date(date)
    raw = _fetch_sheet_csv(csv_url)
    result = None
    if raw is not None:
        result = _parse_sheet_tags(raw, date)
    with _sheet_lock:
        _sheet_cache["date"] = date_str
        _sheet_cache["tags"] = result
    return result


def _parse_sheet_tags(raw, date):
    """Parse CSV sheet: blok pertama (L1) -> {jam_mulai_shift: [tags]} tanggal tsb."""
    try:
        rows = list(csv.reader(io.StringIO(raw)))
    except Exception as e:
        logger.warning(f"Gagal parse CSV jadwal: {e}")
        return None
    day_col = str(date.day)
    col = None
    start = None
    for i, r in enumerate(rows):
        if not r:
            continue
        if r[0] == "NAMA":
            start = i
            for j, h in enumerate(r):
                if _cell_day(h, date.day):
                    col = j
                    break
            break
    if start is None or col is None:
        return None
    result = {}
    cur_name = None
    cur_shift_m = None
    for r in rows[start + 1:]:
        if not r or len(r) <= col:
            continue
        name = (r[0] or "").strip()
        if name:
            cur_name = name
        slot = (r[1] or "").strip() if len(r) > 1 else ""
        if slot:
            cur_shift_m = _slot_to_minutes(slot)
        if not cur_name or cur_name.upper() in _L1_SUMMARY_ROWS or cur_shift_m is None:
            continue
        if (r[col] or "").strip() == "1":
            key = JADWAL_SHEET_NAMES.get(cur_name.upper(), cur_name.upper())
            tag = TELEGRAM_USERNAMES.get(key)
            if tag and tag not in result.setdefault(cur_shift_m, []):
                result[cur_shift_m].append(tag)
    return result or None


def _shift_people_tags(now=None):
    """Tags piket yang MASUK pada shift aktif saat ini (prioritas override > sheet).

    Prioritas:
      1. Override tukar shift (data/shift_overrides.json) per shift
      2. Google Sheet jadwal (per shift)
      3. Piket manual harian (data/daily_piket.json) atau REPORT_PERSONNEL
    """
    now = now or datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    # 1. Override per shift punya prioritas tertinggi
    try:
        overrides = get_shift_overrides(date_str)
        if overrides:
            shift = _current_shift(now)
            if shift:
                norm = _normalize_shift_label(shift["label"])
                if norm in overrides:
                    return overrides[norm]
    except Exception:
        pass

    sheet_map = _sheet_piket_map(now)
    if sheet_map is not None:
        shift = _current_shift(now)
        if shift:
            sh, sm = (int(x) for x in shift["start"].split(":"))
            key = _match_shift_slot(sheet_map, sh * 60 + sm)
            if key is not None:
                return sheet_map.get(key, [])
        return []
    return get_piket(date_str) or REPORT_PERSONNEL


# ==================================================
# PIC Report & SCMT (sel hijau #00FF00 di jadwal)
# ==================================================

_sheet_pic_cache = {"date": None, "data": None}
_sheet_pic_lock = threading.Lock()

_GREEN_FILL = "FF00FF00"


def _cell_day(value, day):
    """Cocokkan header kolom tanggal (bisa int 24, float 24.0, atau str '24')."""
    if value is None:
        return False
    return str(value).strip().split(".")[0] == str(day)


def _sheet_xlsx_url(gid=None):
    if gid:
        sheet_id = _extract_spreadsheet_id()
        if sheet_id:
            return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx&gid={gid}"
    return JADWAL_SHEET_URL.replace("export?format=csv", "export?format=xlsx")


def _fetch_sheet_xlsx(url=None):
    """Ambil tab jadwal sebagai .xlsx (memuat warna sel). None jika gagal."""
    target_url = url or _sheet_xlsx_url()
    try:
        req = urllib.request.Request(
            target_url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception as e:
        logger.warning(f"Gagal ambil xlsx jadwal: {e}")
        return None


def _cell_is_green(cell):
    try:
        f = cell.fill
        return bool(f and f.patternType and f.fgColor and f.fgColor.rgb == _GREEN_FILL)
    except Exception:
        return False


def _sheet_pic_map(date=None):
    """PIC per shift untuk tanggal tertentu: {jam_mulai_shift: tag}.

    PIC ditandai sel hijau #00FF00 ('PIC Report & SCMT') di kolom tanggal.
    Di-cache per tanggal. None jika gagal (xlsx tidak terbaca / tanggal di
    luar jadwal sheet).
    """
    date = date or datetime.now()
    date_str = date.strftime("%Y-%m-%d")
    with _sheet_pic_lock:
        if _sheet_pic_cache["date"] == date_str:
            return _sheet_pic_cache["data"]
    xlsx_url = _get_sheet_xlsx_url_for_date(date)
    raw = _fetch_sheet_xlsx(xlsx_url)
    result = None
    if raw is not None:
        result = _parse_sheet_pic(raw, date)
    with _sheet_pic_lock:
        _sheet_pic_cache["date"] = date_str
        _sheet_pic_cache["data"] = result
    return result


def _parse_sheet_pic(raw, date):
    """Parse xlsx tab jadwal: blok L1, kolom tanggal, ambil PIC sel hijau."""
    try:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
        ws = wb.active
    except Exception as e:
        logger.warning(f"Gagal buka xlsx jadwal: {e}")
        return None
    day = date.day
    header_row = None
    day_col = None
    for r in range(1, 30):
        if ws.cell(r, 1).value == "NAMA":
            header_row = r
            for c in range(1, ws.max_column + 1):
                v = ws.cell(r, c).value
                if _cell_day(v, day):
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
        slot = ws.cell(r, 2).value
        if name and str(name).strip().upper() in _L1_SUMMARY_ROWS:
            break
        if str(name or "").strip().upper().startswith("JADWAL"):
            break
        if name:
            cur_name = str(name).strip()
        if slot:
            cur_shift_m = _slot_to_minutes(str(slot))
        if not cur_name or cur_shift_m is None:
            continue
        if _cell_is_green(ws.cell(r, day_col)):
            key = JADWAL_SHEET_NAMES.get(cur_name.upper(), cur_name.upper())
            tag = TELEGRAM_USERNAMES.get(key)
            if tag and cur_shift_m not in result:
                result[cur_shift_m] = tag
    return result or None


def build_jadwal_piket_text(date=None):
    """Susun blok 'Jadwal Piket Hari Ini' (piket semua shift + PIC hijau).

    Menampilkan override tukar shift jika ada (ditandai 🔄 Tukar).
    """
    date = date or datetime.now()
    piket_map = _sheet_piket_map(date)
    pic_map = _sheet_pic_map(date)
    effective = get_effective_piket_map(date)
    if effective is None and piket_map is None and pic_map is None:
        return None
    # fallback effective ke piket_map jika tidak ada override
    if effective is None:
        effective = piket_map

    date_str = date.strftime("%Y-%m-%d")
    overrides = get_shift_overrides(date_str)

    lines = [
        "📋 Jadwal Piket Hari Ini",
        f"{DAY_NAMES[date.weekday()]}, {date.day} {MONTH_NAMES[date.month - 1]} {date.year}",
        "",
    ]
    for s in REPORT_SHIFTS:
        sh, sm = (int(x) for x in s["start"].split(":"))
        start_m = sh * 60 + sm
        key_eff = _match_shift_slot(effective, start_m) if effective else None
        key_orig = _match_shift_slot(piket_map, start_m) if piket_map else None
        tags = effective.get(key_eff) if key_eff is not None else None
        orig_tags = piket_map.get(key_orig) if key_orig is not None and piket_map else None
        is_override = s["label"] in overrides
        label_extra = " — 🔄 Tukar" if is_override else ""
        lines.append(f"👥 {s['label']} ({s['start']} - {s['end']}):{label_extra}")
        if not tags:
            lines.append("• (tidak ada)")
        else:
            for t in tags:
                pic_mark = (
                    " — ⭐ PIC" if pic_map and key_eff is not None and pic_map.get(key_eff) == t else ""
                )
                # jika override, tampilkan asal jika berbeda
                tukar_mark = ""
                if is_override and orig_tags is not None and t not in orig_tags:
                    tukar_mark = f" (ganti {', '.join(orig_tags)})"
                lines.append(f"• {t}{pic_mark}{tukar_mark}")
        lines.append("")
    # catatan tukar ringkas
    tukar_notes = _build_tukar_note(date)
    if tukar_notes:
        lines.append("🔄 Catatan Tukar Shift:")
        lines.extend(tukar_notes)
        lines.append("")
    lines.append("Sumber: Google Sheet jadwal" + (" + override tukar shift" if overrides else ""))
    return "\n".join(lines)


# ==================================================
# Generate report lengkap (orchestrator untuk GUI/Telegram)
# ==================================================

def generate_report(log_callback=None):
    """Bangun laporan harian. Membuka Chrome khusus report bila belum jalan.

    Diberi lock agar request /report dan jadwal otomatis tidak berjalan
    bersamaan (satu Chrome/CDP port).
    """
    with _REPORT_LOCK:
        return _generate_report_impl(log_callback=log_callback)


_REPORT_LOCK = threading.Lock()


def _generate_report_impl(log_callback=None):
    from app.browser import BrowserManager
    from config.settings import REPORT_CDP_PORT

    log = log_callback or (lambda msg: None)
    bm = BrowserManager(cdp_port=REPORT_CDP_PORT)
    connected = False

    try:
        # Retry 2x untuk handle CDP timeout 180s (Chrome hang / profil TO korup setelah hapus TO)
        for attempt in range(1, 4):
            try:
                if not bm.is_chrome_running():
                    log(f"Report: launching Chrome (port REPORT {REPORT_CDP_PORT})... [attempt {attempt}]")
                    if not bm.launch(log_callback=log):
                        raise Exception("Gagal launch Chrome untuk report")
                log(f"Report: connecting browser port {REPORT_CDP_PORT}... [attempt {attempt}]")
                bm.connect()
                connected = True
                break
            except Exception as e:
                msg = str(e)
                # Timeout 180s via connect_over_cdp → Chrome hang, coba relaunch tanpa kill semua browser
                if "Timeout" in msg and "connect_over_cdp" in msg and attempt < 3:
                    log(f"Report: connect timeout attempt {attempt} — coba disconnect & relaunch Chrome port {REPORT_CDP_PORT} (tidak kill browser pribadi)...")
                    try:
                        bm.disconnect()
                    except Exception:
                        pass
                    # Kill HANYA Chrome di port REPORT, jangan semua chrome (biar browser pribadi tidak tertutup)
                    try:
                        import subprocess as _sp
                        out = _sp.check_output(f'netstat -ano | findstr :{REPORT_CDP_PORT}', shell=True, text=True, stderr=_sp.DEVNULL)
                        for line in out.splitlines():
                            parts = line.strip().split()
                            if parts and parts[-1].isdigit():
                                pid = parts[-1]
                                # Pastikan PID ini memang chrome
                                try:
                                    name = _sp.check_output(f'tasklist /FI \"PID eq {pid}\"', shell=True, text=True, stderr=_sp.DEVNULL)
                                    if "chrome" in name.lower():
                                        log(f"Report: kill Chrome PID {pid} di port {REPORT_CDP_PORT}...")
                                        _sp.run(["taskkill", "/F", "/PID", pid], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    import time as _t
                    _t.sleep(3)
                    continue
                raise

        if not connected:
            raise Exception(f"Gagal connect ke Chrome port {REPORT_CDP_PORT} setelah 3 attempt")

        pages = bm.get_pages()
        log(f"Report: Chrome port {REPORT_CDP_PORT} terhubung - {len(pages)} tab terbuka")
        # Pastikan tab pertama tidak about:blank hang — refresh jika perlu
        try:
            if pages and pages[0].url == "about:blank":
                log("Report: tab pertama about:blank — navigasi ke base SYGAP...")
                pages[0].goto(REPORT_BASE_URL, wait_until="domcontentloaded", timeout=15000)
                pages[0].wait_for_timeout(2000)
        except Exception:
            pass

        svc = ReportService(browser_manager=bm, log_callback=log)
        log("Report: mengumpulkan data...")
        data = svc.collect_all()
        text = svc.format_report(data)
        return text
    finally:
        if connected:
            try:
                bm.disconnect()
            except Exception:
                pass
