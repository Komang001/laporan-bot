"""Scheduler 1-pintu PROTOTYPE — implementasi live (folder terpisah).

TIDAK menyentuh `app/`, `config/`, `main.py`, `start.bat`.
Jalankan terpisah:
  dry-run : .venv\\Scripts\\python.exe unified_prototype\\main_unified.py
  1 siklus: ... main_unified.py --live --once
  loop    : ... main_unified.py --live

Desain (sesuai kesepakatan):
  1 Chrome (:9229) kerja bergantian, bukan 6 thread paralel.
  LOOP per jenis: EXECUTE milik saya (Assigned to Me + OPEN) dulu ->
  kalau habis baru TO(filter ASSIGNED saja) -> EXECUTE(filter OPEN + Assigned to Me).
  Kedua filter TIDAK digabung, selalu bergantian.
  Urutan: DISPATCH -> GAMAS -> SERVICE_ID.
  TIDAK digabung: INCIDENT (:9228), CANCLWORK (:9223), REPORT (:9226)

Reuse (read-only, tanpa modifikasi):
  app.browser.BrowserManager, app.services.sygap_service.SygapService,
  app.services.biscuit_service.BiscuitService,
  app.services.oss_incident_service.OssIncidentService,
  app.services.insera_gamas_service.InseraGamasService,
  app.parser.*, config.settings, history_service.log_history
Filter anti-rebut lokal: unified_prototype.to_filter
"""

import os
import sys
import time
import threading

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)
_PROTO = os.path.dirname(os.path.abspath(__file__))
if _PROTO not in sys.path:
    sys.path.insert(0, _PROTO)

try:
    from to_filter import (check_open_for_to, check_assigned_for_to,
                           is_assigned_to_me, is_mine,
                           filter_rows_open_for_to, filter_rows_assigned_for_to)
except ImportError:  # dijalankan sebagai package
    from unified_prototype.to_filter import (
        check_open_for_to, check_assigned_for_to,
        is_assigned_to_me, is_mine,
        filter_rows_open_for_to, filter_rows_assigned_for_to,
    )

# Versi engine prototype. Naikkan tiap ada perubahan perilaku agar
# terlihat di log GUI mana yang sedang jalan (cegah kode basi).
ENGINE_VERSION = "v19-insera-keepalive"

LOOP_INTERVAL = 0  # Default tanpa idle time (langsung siklus berikutnya)
TO_TIMEOUT_PER_TICKET = 60
EXECUTE_TIMEOUT_TOTAL = 8 * 60
BISCUIT_MAX_RETRIES = 2

# Aturan filter SYGAP (tidak bisa digabung, harus bergantian):
#   FASE TO     : notes + ASSIGNED + assignee All
#   FASE EXECUTE: notes + status milik saya + assignee Assigned to Me
TO_STATUS = "ASSIGNED"
EXEC_STATUS = "OPEN"
# Urutan sapuan milik saya: Assigned to Me + OPEN saja (1 filter).
EXEC_STATUSES = ("OPEN",)

# SOP: permintaan ubah Symptom DILARANG dikerjakan (jangan TO, jangan eksekusi).
# Terdeteksi bila note menyebut symptom + kata perubahan.
SYMPTOM_WORDS = ("symptom", "symtomp")
SYMPTOM_CHANGE_WORDS = ("ubah", "ganti", "rubah", "pelurusan", "luruskan",
                        "perbaiki", "update", "edit", "revisi")

# NOTE PENOLAKAN SYMPTOM — DIKUNCI. Jangan pernah diubah tanpa perintah user.
SYMPTOM_REJECT_NOTE = "mohon maaf kami tidak dapat melakukan perubahan symptomp"

# NOTE ARAHAN C4 — DIKUNCI. Jangan pernah diubah tanpa perintah user.
C4_REDIRECT_NOTE = ("untuk permintaan dispatch ke C4_CONSUMER silahkan "
                    "koordinasikan ke OG terkait")

# NOTE SELESAI GAMAS — DIKUNCI (sama seperti bot lama). Jangan diubah tanpa perintah.
GAMAS_DONE_NOTE = "Cek Kembali"

# NOTE INDUK GAMAS CLOSED — DIKUNCI (perintah user).
GAMAS_CLOSED_NOTE = "status induk gamas sudah closed, mohon maaf permintaan tidak dapat kami penuhi"

# NOTE INDUK GAMAS PROACTIVE — DIKUNCI (perintah user).
GAMAS_PROACTIVE_NOTE = (
    "Terkait induk gamas dengan source PROACTIVE tidak bisa kami bantu relasikan ,\n"
    "silahkan buat ticket baru dengan source GAMAS dan wajib mengisi perangkat pada kolom perangkatnya juga . terimakasih"
)

# NOTE WORKZONE — DIKUNCI. Jangan pernah diubah tanpa perintah user.
WORKZONE_DONE_NOTE = ("untuk perubahan WORKZONE silahkan disesuaikan dahulu "
                      "DATEK nya kemudian di Load Technical Data")


def is_symptom_request(note):
    """True jika note = permintaan ubah Symptom (murni, tanpa browser)."""
    low = (note or "").lower()
    if not any(w in low for w in SYMPTOM_WORDS):
        return False
    return any(w in low for w in SYMPTOM_CHANGE_WORDS)


def is_c4_dispatch_request(note):
    """True jika note minta dispatch ke C4 (murni, tanpa browser).

    Untuk note TANPA kata kunci OG (loker/og/owner group/ke) sehingga
    OG tak terparse, mis. 'Mohon bantu Dispatch C4 CONSUMER'.
    SOP: target C4 jelas -> TANPA BISCUIT, reply arahan terkunci.
    """
    import re as _re
    if not note:
        return False
    return bool(_re.search(
        r"(?i)dispatch\s+(ke\s+)?c4\b|c4[\s_]*consumer", note))


def decide_service_id_path(service_id, service_type, symptom):
    """Prioritas eksekusi service_id (murni, tanpa browser). Urutan mengikat:
    biscuit (ada Service ID — menang atas Symptom) > symptom-reject >
    svctype-reject > skip.
    """
    if service_id:
        return "biscuit"
    if symptom:
        return "symptom-reject"
    if service_type:
        return "svctype-reject"
    return "skip"
JENIS_NOTES = {"dispatch": "dispatch",
               "gamas": "gamas",
               "service_id": "Service"}
# Varian notes gamas: singkatan ig/ag/tiket_relasi TIDAK mengandung kata
# "gamas", jadi filter tunggal selalu luput. "relasi" menangkapnya
# (relasi/relasikan/tiket_relasi) tanpa mengorbankan "anak gamas".
JENIS_NOTES_VARIANTS = {"dispatch": ["dispatch"],
                        "gamas": ["gamas", "relasi"],
                        "service_id": ["Service"]}

# Timeout filter (ms). Disengaja kecil + skip-jika-sudah-benar agar siklus cepat.
F_SLEEP_TINY = 150
F_SLEEP_SHORT = 250
F_SLEEP_MED = 400
F_APPLY_SETTLE = 1500   # jeda setelah Apply (didahului tunggu tabel reload)
F_TABLE_TIMEOUT = 8000  # tunggu tabel selesai reload setelah Apply


class UnifiedController:
    """1 thread bos pengganti 6x _run_* (nanti setelah disetujui)."""

    def __init__(self, gui=None, cdp_port=9229, dry_run=True,
                 loop_interval=LOOP_INTERVAL, log_callback=None):
        self.gui = gui
        self.cdp_port = cdp_port
        self.dry_run = dry_run
        self.loop_interval = loop_interval
        self._ext_log = log_callback
        self.running = False
        self.on_complete = None  # kompatibel GUI (dipanggil saat loop berhenti)
        self._browser = None
        self._sygap = None
        self._warmed_up = False  # warmup SEKALI per START (reset di start())
        self.stats = {"cycles": 0, "to_ok": 0, "exec_ok": 0, "skipped": 0}

    # ---------------- logging ----------------
    def log(self, msg, channel="myassistance"):
        if self._ext_log:
            try:
                self._ext_log(msg)
            except Exception:
                pass
        if self.gui is not None:
            # Adapter GUI (_FeatureGUIAdapter) hanya terima write_log(msg)
            # tanpa channel; GUI asli terima channel. Coba keduanya.
            try:
                self.gui.write_log(msg, channel=channel)
                return
            except TypeError:
                pass
            except Exception:
                pass
            try:
                self.gui.write_log(msg)
                return
            except Exception:
                pass
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:
            try:
                print(str(msg).encode("ascii", errors="replace").decode(),
                      flush=True)
            except Exception:
                pass
        except Exception:
            pass
        except UnicodeEncodeError:
            try:
                print(str(msg).encode("ascii", errors="replace").decode(),
                      flush=True)
            except Exception:
                pass

    # ---------------- browser (live only) ----------------
    def _ensure_browser(self):
        from app.browser import BrowserManager
        from app.services.sygap_service import SygapService

        if self._browser is None:
            self._browser = BrowserManager(cdp_port=self.cdp_port)
        bm = self._browser

        if not bm.is_chrome_running():
            ok = bm.launch(log_callback=self.log)
            if not ok:
                raise RuntimeError(f"Gagal launch Chrome port {self.cdp_port}")
        bm.connect()
        # Sapu tab about:blank sisa (gagal load / run lama) SEBELUM buka
        # tab baru — blank tidak pernah cocok deteksi has_* sehingga retry
        # selalu menumpuk tab baru.
        try:
            bm.close_blank_tabs(log_callback=self.log)
        except Exception:
            pass
        # Butuh 3 tab dalam 1 browser: SYGAP + BISCUIT + INSERA.
        # open_required_tabs -> SYGAP+BISCUIT, open_required_tabs_gamas -> +INSERA.
        try:
            bm.open_required_tabs(log_callback=self.log)
        except Exception as e:
            self.log(f"WARNING open_required_tabs: {e}")
        try:
            bm.open_required_tabs_gamas(log_callback=self.log)
        except Exception as e:
            self.log(f"WARNING open_required_tabs_gamas: {e}")
        # Workaround bug deteksi: URL BISCUIT mengandung kata "inseratools"
        # sehingga fungsi shared mengira tab INSERA sudah ada. Verifikasi
        # langsung, bukakan bila belum ada (tanpa ubah kode shared).
        try:
            if bm.get_insera_gamas_page() is None:
                from config.settings import GAMAS_RELATIONS_URL
                self.log("Tab INSERA belum ada -> bukakan langsung...")
                _ins = bm.open_url(GAMAS_RELATIONS_URL)
                self.log("INSERA tab opened (langsung)." if _ins else
                         "WARNING: Gagal buka INSERA (tab kosong ditutup, retry loop berikut)")
        except Exception as e:
            self.log(f"WARNING buka INSERA: {e}")

        if self._sygap is None:
            self._sygap = SygapService(
                browser_manager=bm,
                stop_check=lambda: not self.running,
            )
        # WARMUP SEKALI per START: browser dingin (baru launch) + SYGAP
        # dingin = komit navigasi lambat -> tab tiket macet about:blank di
        # siklus awal. Panaskan dulu sebelum hajar klik tiket.
        if not getattr(self, "_warmed_up", False):
            try:
                self._warmup_startup(bm, self._sygap)
            except Exception as e:
                self.log(f"WARNING warmup: {e}")
        return bm, self._sygap

    def _warmup_startup(self, bm, sygap):
        """Pemanasan SEKALI per START (cold browser + cold SYGAP)."""
        self.log(">>> WARMUP: pemanasan browser + dashboard <<<")
        # 1. Sapu sisa run lama: blank + tab form basi (bebaskan renderer).
        try:
            bm.close_blank_tabs(log_callback=self.log)
        except Exception:
            pass
        try:
            n = 0
            for p in bm.get_pages():
                try:
                    u = (p.url or "").lower()
                except Exception:
                    continue
                if "/form/" in u:
                    try:
                        if not p.is_closed():
                            p.close()
                            n += 1
                    except Exception:
                        pass
            if n:
                self.log(f"Menutup {n} tab form sisa run lama.")
        except Exception:
            pass
        # 2. Dashboard harus TERMUAT (tunggu tabel, bukan cuma domcontentloaded).
        try:
            page = sygap.navigate_to_dashboard()
        except Exception as e:
            self.log(f"WARNING warmup dashboard: {e}")
            page = None
        if page is not None:
            try:
                page.wait_for_selector(
                    "#requestFulfillmentTable tbody tr", timeout=60000)
                self.log("Dashboard termuat (tabel ada).")
            except Exception:
                self.log("WARNING: tabel dashboard tak muncul 60 dtk — "
                         "lanjut, retry loop berikut")
            # 3. Sesi kadaluarsa semalam -> terlempar ke login: tunggu login
            # manual (maks 180 dtk) daripada siklus gagal terus.
            try:
                if not sygap._wait_for_sygap_login(page, self.log, timeout=180):
                    self.log("WARNING: belum login — siklus lanjut apa adanya")
            except Exception:
                pass
        # 4. Pastikan tab INSERA Gamas terbuka & lakukan keepalive awal
        try:
            insera_pg = bm.get_insera_gamas_page()
            if insera_pg is None or not bm.is_page_alive(insera_pg):
                from config.settings import GAMAS_RELATIONS_URL
                self.log("Warmup: membuka tab INSERA Gamas...")
                insera_pg = bm.open_url(GAMAS_RELATIONS_URL)
                if insera_pg:
                    try:
                        insera_pg.wait_for_load_state("domcontentloaded", timeout=15000)
                    except Exception:
                        pass
            self._keepalive_insera()
        except Exception as e:
            self.log(f"WARNING warmup INSERA: {e}")
        self._warmed_up = True
        self.log(">>> WARMUP selesai, mulai siklus <<<")

    # ---------------- filter dashboard (milik prototype, sekali Apply) ----------------
    def _select_status_option(self, page, select_id, status_value):
        """Pilih opsi status SYGAP secara toleran (underscore/spasi/case).

        Return True jika opsi cocok & terpilih (terverifikasi), False jika
        label tidak ada — pemanggil harus LEWATI fase, jangan lanjut dengan
        filter status yang salah.
        """
        import re as _re
        try:
            loc = page.locator(select_id)
            if loc.count() == 0:
                return False
            norm = lambda s: _re.sub(r"[\s_\-]+", "", s or "").lower()
            target = norm(status_value)
            opts = loc.locator("option")
            for i in range(opts.count()):
                try:
                    txt = (opts.nth(i).inner_text() or "").strip()
                except Exception:
                    continue
                if txt and norm(txt) == target:
                    loc.select_option(label=txt)
                    page.wait_for_timeout(F_SLEEP_TINY)
                    try:
                        chosen = (loc.locator("option:checked").first.inner_text() or "").strip()
                    except Exception:
                        chosen = txt
                    return norm(chosen) == target
            return False
        except Exception:
            return False

    def _apply_notes_filter(self, page, notes_value, status, assignee="ALL"):
        """Pasang filter lengkap SEKALIGUS lalu Apply (tanpa status sementara).

        assignee ALL: notes + status + All Request Coordinator (FASE TO).
        assignee ME : notes + status + Assigned to Me (FASE EXECUTE).

        Optimasi: setiap field dicek dulu — kalau sudah benar dilewati
        (tidak diisi ulang), sehingga Apply ulang yang berurutan jadi cepat.
        """
        # Panel advanced (lewati jika sudah terbuka)
        try:
            collapse = page.locator("#multiCollapseExample1")
            is_open = False
            try:
                is_open = collapse.evaluate("el => el.classList.contains('show')")
            except Exception:
                pass
            if not is_open:
                adv = page.locator('a[href="#multiCollapseExample1"]')
                if adv.count() > 0:
                    adv.first.click()
                try:
                    page.wait_for_selector("#multiCollapseExample1.show", timeout=3000)
                except Exception:
                    pass
                page.wait_for_timeout(F_SLEEP_SHORT)
        except Exception:
            pass
        # Notes (lewati jika sudah sama)
        try:
            notes_input = page.locator("#notes")
            if notes_input.count() == 0:
                notes_input = page.locator("input[name='notes']")
            if notes_input.count() > 0:
                try:
                    cur = notes_input.input_value().strip()
                except Exception:
                    cur = ""
                if cur != notes_value:
                    notes_input.fill("")
                    page.wait_for_timeout(F_SLEEP_TINY)
                    notes_input.fill(notes_value)
                    page.wait_for_timeout(F_SLEEP_SHORT)
                self.log(f"  [filter] notes = {notes_value}")
            else:
                self.log("  [filter] WARNING notes input tidak ketemu")
                return False
        except Exception as e:
            self.log(f"  [filter] WARNING notes: {e}")
            return False
        # Solver Group MO-INSERA (lewati jika sudah terpilih)
        try:
            try:
                og_txt = page.locator("#select2-solverGroupSearch-container").inner_text()
            except Exception:
                og_txt = ""
            if "MO-INSERA" not in (og_txt or "").upper():
                from config.settings import INSERA_GROUP_ID
                page.evaluate(f"""(function(){{
                    var el = document.getElementById('solverGroupSearch');
                    if (el && window.jQuery) {{
                        var $el = jQuery(el);
                        $el.empty();
                        $el.append(new Option('MO-INSERA', '{INSERA_GROUP_ID}', true, true));
                        $el.val('{INSERA_GROUP_ID}').trigger('change');
                    }}
                }})();""")
                page.wait_for_timeout(F_SLEEP_MED)
        except Exception:
            pass
        # Status + assignee (pasangan yang benar sejak awal; lewati jika sama).
        # Pilih opsi toleran (underscore/spasi/case) + verifikasi, agar fase
        # tidak jalan dengan filter status yang salah.
        try:
            if not self._select_status_option(page, "#searchSelect", status):
                self.log(f"  [filter] WARNING status '{status}' tidak ada -> fase dilewati")
                return False
        except Exception as e:
            self.log(f"  [filter] WARNING set status {status}: {e}")
            return False
        want_assign = "ASSIGN_TO_ME" if assignee == "ME" else ""
        try:
            box = page.locator("#assigneeSearch")
            if box.count() > 0:
                try:
                    cur_as = box.input_value()
                except Exception:
                    cur_as = None
                if cur_as != want_assign:
                    box.select_option(value=want_assign)
                    page.wait_for_timeout(F_SLEEP_TINY)
                self.log(f"  [filter] {status} + "
                         f"{'Assigned to Me' if assignee == 'ME' else 'All Request Coordinator'}")
            else:
                self.log("  [filter] WARNING #assigneeSearch tidak ketemu")
        except Exception as e:
            self.log(f"  [filter] WARNING set assignee: {e}")
        # Apply + tunggu tabel selesai reload (dinamis, bukan sleep buta)
        try:
            info_sel = "#requestFulfillmentTable_info"
            try:
                before = page.locator(info_sel).inner_text()
            except Exception:
                before = ""
            btn = page.locator("#btn_apply")
            if btn.count() > 0:
                try:
                    btn.first.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                try:
                    btn.first.click(timeout=5000)
                except Exception:
                    btn.first.evaluate("el => el.click()")
            try:
                page.wait_for_function(
                    "([sel, old]) => { var el = document.querySelector(sel); "
                    "return el && el.innerText !== old; }",
                    arg=[info_sel, before], timeout=F_TABLE_TIMEOUT)
            except Exception:
                pass  # tabel tidak berubah (hasil sama) -> lanjut saja
            page.wait_for_timeout(F_APPLY_SETTLE)
        except Exception as e:
            self.log(f"  [filter] WARNING klik Apply: {e}")
            return False
        return True

    def _collect_filtered_rows(self, sygap, page, jenis, status, asg):
        """Terapkan tiap varian notes + baca + gabung per kode (1 filter penuh).

        Varian yang filternya gagal diterapkan dilewati (jangan baca tabel
        basi dari filter sebelumnya).
        """
        merged = {}
        for nv in JENIS_NOTES_VARIANTS.get(jenis, [JENIS_NOTES.get(jenis, "")]):
            if not self._apply_notes_filter(page, nv, status, asg):
                continue
            for r in self._read_table_rows(sygap, page):
                code = (r.get("request_code") or "").strip()
                if code:
                    merged.setdefault(code, r)
        rows = list(merged.values())
        self.log(f"  [filter] {jenis} {status}+{asg}: {len(rows)} baris gabungan")
        return rows

    def _find_row_in_current_table(self, sygap, page, code):
        """Cari 1 kode di baris tabel yang sedang aktif tanpa reload/re-apply filter."""
        code = (code or "").strip().upper()
        try:
            for r in sygap.get_ticket_rows(page):
                if (r.get("request_code") or "").strip().upper() == code:
                    return r
        except Exception:
            pass
        return None

    def _find_code_in_variants(self, sygap, page, jenis, code, status, asg):
        """Cari 1 kode lintas varian notes + lintas halaman. Returns row/None."""
        for nv in JENIS_NOTES_VARIANTS.get(jenis, [JENIS_NOTES.get(jenis, "")]):
            self._apply_notes_filter(page, nv, status, asg)
            row = self._find_row_by_code(sygap, page, code)
            if row is not None:
                return row
        return None

    # ---------------- kolom Solver yang benar (Owner = pengirim!) ----------------
    def fix_solver_column(self, page, rows):
        """Timpa row['solver'] dengan isi kolom header 'Solver' (col 5).

        Bot lama membaca kolom 'Owner' (col 4 = PENGIRIM, mis. Jakariah71)
        karena keyword 'owner' ikut cocok. Kolom Solver asli: 'MO-INSERA'
        = kosong (siap TO), nama orang = sudah bertuan.
        """
        try:
            data = page.evaluate("""() => {
                const ths = Array.from(document.querySelectorAll(
                    "#requestFulfillmentTable thead th"));
                const sIdx = ths.findIndex(
                    th => th.innerText.trim().toLowerCase() === "solver");
                if (sIdx < 0) return null;
                return Array.from(document.querySelectorAll(
                    "#requestFulfillmentTable tbody tr")).map(tr => {
                    const a = tr.querySelector("td a");
                    const tds = tr.querySelectorAll("td");
                    return {
                        code: a ? a.innerText.trim() : "",
                        solver: tds[sIdx] ? tds[sIdx].innerText.trim() : ""
                    };
                });
            }""")
        except Exception as e:
            self.log(f"  [solver-col] WARNING baca kolom Solver: {e}")
            return rows
        if not data:
            self.log("  [solver-col] WARNING header 'Solver' tidak ketemu")
            return rows
        by_code = {}
        for d in data:
            c = (d.get("code") or "").strip()
            if c and c not in by_code:
                by_code[c] = (d.get("solver") or "").strip()
        fixed = 0
        for r in rows:
            code = (r.get("request_code") or "").strip()
            if code in by_code:
                r["solver"] = by_code[code]
                fixed += 1
        self.log(f"  [solver-col] {fixed}/{len(rows)} baris dikoreksi ke kolom Solver")
        return rows

    # ---------------- baca tabel (tunggu + ambil + koreksi kolom Solver) ----------------
    def _read_table_rows(self, sygap, page):
        """Tunggu tabel, ambil baris, koreksi kolom Solver. Returns rows (bisa [])."""
        try:
            page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=10000)
            page.wait_for_timeout(800)
        except Exception:
            return []
        try:
            rows = sygap.get_ticket_rows(page)
        except Exception:
            return []
        try:
            rows = self.fix_solver_column(page, rows)
        except Exception:
            pass
        return rows

    def _is_symptom_request(self, note):
        """True jika note = permintaan ubah Symptom (dilarang SOP)."""
        return is_symptom_request(note)

    def _assert_reply_locked(self, rule, note, done_note):
        """Jaring pengaman terakhir SEBELUM complete: pastikan note reply
        sesuai aturan. Gagal -> raise (complete DIBATALKAN, tiket aman)."""
        if rule == "SYMPTOM" and self._is_symptom_request(note):
            if done_note != SYMPTOM_REJECT_NOTE:
                raise AssertionError(
                    f"REPLY MISMATCH [{rule}]: {done_note!r} != locked note")
        elif rule == "DISPATCH-C4":
            if done_note != C4_REDIRECT_NOTE:
                raise AssertionError(
                    f"REPLY MISMATCH [{rule}]: {done_note!r} != locked note")
        elif rule == "GAMAS":
            if done_note != GAMAS_DONE_NOTE:
                raise AssertionError(
                    f"REPLY MISMATCH [{rule}]: {done_note!r} != locked note")
        elif rule == "GAMAS-CLOSED":
            if done_note != GAMAS_CLOSED_NOTE:
                raise AssertionError(
                    f"REPLY MISMATCH [{rule}]: {done_note!r} != locked note")
        elif rule == "GAMAS-PROACTIVE":
            if done_note != GAMAS_PROACTIVE_NOTE:
                raise AssertionError(
                    f"REPLY MISMATCH [{rule}]: {done_note!r} != locked note")
        elif rule == "DISPATCH-WORKZONE":
            if done_note != WORKZONE_DONE_NOTE:
                raise AssertionError(
                    f"REPLY MISMATCH [{rule}]: {done_note!r} != locked note")
        if not (done_note or "").strip():
            raise AssertionError(f"REPLY KOSONG [{rule}] — dibatalkan")
        self.log(f'    [REPLY-LOCK] {rule}: "{done_note}"')
        return True
    def _read_coordinator_stable(self, sygap, ticket_page, timeout=12,
                                   settle=3.0):
        """Baca koordinator yang STABIL + LAPORAN kestabilan.

        Select #id_coordinator SYGAP mula-mula menampilkan user LOGIN,
        baru belakangan diganti data asli via async (bisa >6 detik saat
        server lambat). Klaim 'mine'/'empty' dari 1x baca = tebak-tebakan.
        polling 500ms; STABIL bila nilai tak berubah selama `settle` detik.
        Kosong pun harus stabil (min total 6 dtk) baru dipercaya.
        Returns ((uid, label), stable: bool).
        """
        import time as _t

        def _once():
            try:
                return ((sygap.read_coordinator_user_id(ticket_page) or "").strip(),
                        (sygap.read_coordinator_label(ticket_page) or "").strip())
            except Exception:
                return ("", "")

        end = _t.time() + max(1, timeout)
        cur = _once()
        changed_at = _t.time()
        while True:
            now = _t.time()
            if cur != ("", "") and now - changed_at >= settle:
                return cur, True
            if cur == ("", "") and now - changed_at >= settle:
                # Kosong stabil: cukup stabil settle detik (3 dtk)
                return cur, True
            if now >= end:
                return cur, False
            try:
                ticket_page.wait_for_timeout(500)
            except Exception:
                return cur, False
            nxt = _once()
            if nxt != cur:
                cur, changed_at = nxt, _t.time()

    def _classify_coordinator(self, uid, label):
        """Klasifikasi 1x baca koordinator (tanpa tunggu ulang).
        Returns: skip-rizky | mine | empty | other."""
        from config import settings as cfg
        uid_s = (uid or "").strip()
        label_s = (label or "").strip()
        if not uid_s and not label_s:
            return "empty"
        if label_s.lower() in ("-", "--", "none", "null", "unassigned",
                               "pilih", "select", "--pilih--"):
            return "empty"
        # Koordinator masih nama GROUP (belum ada orangnya) = kosong.
        if not uid_s and label_s.strip().upper() in ("MO-INSERA", "MO-BIMA"):
            return "empty"
        for item in (getattr(cfg, "SKIP_COORDINATOR_USER_IDS", []) or []):
            item_s = str(item).strip()
            if not item_s:
                continue
            if item_s.isdigit():
                if uid_s == item_s:
                    return "skip-rizky"
            elif item_s.lower() in label_s.lower():
                return "skip-rizky"
        my_id = str(getattr(cfg, "USER_ID", "55654")).strip()
        my_name = str(getattr(cfg, "USER_NAME", "I Nyoman Windu")).strip().lower()
        if (uid_s and uid_s == my_id) or (label_s and my_name in label_s.lower()):
            return "mine"
        if not uid_s and len(label_s) < 3:
            return "empty"
        return "other"

    # ---------------- TO cepat (pengganti take_ownership bot lama) ----------------
    def fast_take_ownership(self, sygap, ticket_page):
        """Versi ramping dari take_ownership: sleep minimal, tanpa tunggu
        selector 8 detik berlapis. Kontrak hasil sama ('SKIP_COORDINATOR',
        'NEXT_STAGE'/'SAVE'/..., None saat error). Bot lama tidak diubah."""
        from config import settings as cfg
        USER_ID = str(getattr(cfg, "USER_ID", "55654"))
        USER_NAME = str(getattr(cfg, "USER_NAME", "I Nyoman Windu"))

        try:
            ticket_page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        try:
            ticket_page.wait_for_selector("#id_coordinator", timeout=4000)
        except Exception:
            pass

        # Guard koordinator SUDAH dilakukan 1x di _to_one_ticket
        # (baca ulang di sini hanya buang 3 detik) -> langsung isi.

        js_code = f"""
        (async function() {{
            function sleep(ms) {{ return new Promise(r => setTimeout(r, ms)); }}
            for (var w = 0; w < 4; w++) {{
                if (window.jQuery && jQuery.fn.select2) break;
                await sleep(250);
            }}
            if (!window.jQuery) return 'NO_JQUERY';
            var ic = document.getElementById('id_coordinator');
            if (!ic) return 'NO_IC';
            var $ic = jQuery(ic);
            if ($ic.find('option[value="{USER_ID}"]').length === 0) {{
                $ic.append(new Option('{USER_NAME}', '{USER_ID}', false, false));
            }}
            // Cek NILAI TERKINI tepat sebelum isi (anti rebut last-moment):
            // terisi orang -> BATAL. Kosong/group/milik-saya -> lanjut ISI +
            // KLIK (JANGAN lewati klik meski nilainya saya: SYGAP mengisi
            // awal field kosong dengan user LOGIN sebagai prefill BELUM
            // tersimpan — tanpa klik, tiket tidak pernah jadi milik saya).
            var cur = $ic.val();
            if (cur && cur !== '' && cur !== '0' && cur !== '{USER_ID}') {{
                // Pastikan bukan sekadar label group
                var curTxt = '';
                try {{
                    var o = $ic.find('option[value="' + cur + '"]');
                    curTxt = o.length ? o.text() : cur;
                }} catch (e) {{ curTxt = cur; }}
                var up = (curTxt + '').toUpperCase();
                if (up.indexOf('MO-INSERA') < 0 && up.indexOf('MO-BIMA') < 0)
                    return 'TAKEN:' + cur;
            }}
            $ic.val('{USER_ID}').trigger('change');
            await sleep(500);
            if ($ic.val() !== '{USER_ID}') return 'VERIFY_FAIL:' + $ic.val();
            // Tunggu tombol aksi MUNCUL & layak klik (SYGAP me-render-nya
            // async setelah change; klik buta = miss). Maks ~6 detik.
            // Daftar tombol lengkap spt bot lama (request + incident).
            var clicked = '';
            for (var t = 0; t < 12; t++) {{
                var nb = document.getElementById('btn_next_stage');
                if (nb && nb.offsetParent !== null && !nb.disabled) {{
                    nb.click(); clicked = 'NEXT_STAGE'; break;
                }}
                var wn = document.getElementById('btn_wip_note');
                if (wn && wn.offsetParent !== null && !wn.disabled) {{
                    wn.click(); clicked = 'WIP_NOTE_CLICKED'; break;
                }}
                var wi = document.getElementById('btn_wip_inc');
                if (wi && wi.offsetParent !== null && !wi.disabled) {{
                    wi.click(); clicked = 'WIP_INC'; break;
                }}
                var rd = document.getElementById('btn_redispatch_inc');
                if (rd && rd.offsetParent !== null && !rd.disabled) {{
                    rd.click(); clicked = 'REDISPATCH'; break;
                }}
                var up = document.getElementById('btn_update_inc');
                if (up && up.offsetParent !== null && !up.disabled) {{
                    up.click(); clicked = 'UPDATE_INC'; break;
                }}
                var sv = document.getElementById('btn_submit_request');
                if (sv && sv.offsetParent !== null && !sv.disabled) {{
                    sv.click(); clicked = 'SAVE'; break;
                }}
                await sleep(500);
            }}
            if (clicked) return clicked;
            return 'NO_BUTTON';
        }})();
        """
        try:
            return ticket_page.evaluate(js_code)
        except Exception as e:
            print(f"fast_take_ownership JS error: {e}")
            return None

    def _verify_in_progress_js(self, ticket_page, timeout=8):
        """Pastikan Request Status sudah IN_PROGRESS (baca kontrol form).

        Syarat user: ASSIGNED -> IN_PROGRESS TERBUKTI baru lanjut tahap berikut.
        """
        import time as _t
        end = _t.time() + max(1, timeout)
        js = """() => {
            const vals = [];
            ["#status", "#select_incident_status"].forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    try {
                        if (el.tagName === "SELECT" && el.selectedOptions.length)
                            vals.push(el.selectedOptions[0].text + "|" + el.value);
                        else vals.push(el.innerText || el.value || "");
                    } catch (e) {}
                });
            });
            return vals.join(" ").toUpperCase();
        }"""
        while True:
            try:
                txt = ticket_page.evaluate(js) or ""
                if "IN_PROGRESS" in txt or txt.strip() == "WIP" \
                        or "WORK_IN_PROGRESS" in txt or "IN PROGRESS" in txt:
                    return True
            except Exception:
                return False
            if _t.time() >= end:
                return False
            try:
                ticket_page.wait_for_timeout(500)
            except Exception:
                return False

    def _handle_wip_modal(self, ticket_page):
        """Selesaikan modal WIP (klik btn_wip_note hanya membuka modal)."""
        try:
            ticket_page.wait_for_selector("#form_wip_inc, .modal.show", timeout=4000)
            ticket_page.wait_for_timeout(800)
            editor = ticket_page.locator(
                "#form_wip_inc .ck-editor__editable, .modal.show .ck-editor__editable").first
            if editor.count() > 0:
                editor.click()
                ticket_page.wait_for_timeout(400)
                ticket_page.keyboard.press("Control+a")
                ticket_page.keyboard.press("Backspace")
                ticket_page.wait_for_timeout(200)
                ticket_page.keyboard.type("WIP", delay=30)
                ticket_page.wait_for_timeout(400)
            else:
                ta = ticket_page.locator("#progress_note").first
                if ta.count() > 0:
                    ticket_page.evaluate(
                        "() => { const el=document.getElementById('progress_note');"
                        " if(el) el.style.display='block'; }")
                    ta.fill("WIP")
                    ticket_page.wait_for_timeout(400)
            confirm = ticket_page.locator("#btn_wip_inc").first
            if confirm.count() == 0:
                confirm = ticket_page.locator(
                    ".modal-footer #btn_wip_inc, .modal.show #btn_wip_inc").first
            if confirm.count() > 0:
                confirm.scroll_into_view_if_needed()
                ticket_page.wait_for_timeout(400)
                confirm.click()
                ticket_page.wait_for_timeout(2500)
                return True
            btn = ticket_page.locator(".modal.show button:has-text('Work Progress')").last
            if btn.count() > 0:
                btn.click()
                ticket_page.wait_for_timeout(2500)
                return True
        except Exception as e:
            try:
                self.log(f"    WIP modal error: {e}")
            except Exception:
                pass
        return False

    def _to_one_ticket(self, sygap, page, ticket_page, code, form_status=""):
        """TO 1 tiket. Koordinator dibaca CUKUP 1x. Returns ok|mine|skip.

        Aturan klik (temuan: SYGAP prefill field kosong dgn user login):
        - mine + IN_PROGRESS -> sudah tersimpan, TANPA klik.
        - mine/kosong + status lain -> WAJIB klik (simpan + majukan).
        - ok HANYA bila status TERBUKTI IN_PROGRESS sesudah klik.
        """
        import time as _t
        _t0 = _t.time()
        # Baca STABIL (nilai tak berubah >=3 dtk). Tak stabil = JANGAN tebak:
        # skip dan coba lagi siklus berikut.
        try:
            (uid, label), stable = self._read_coordinator_stable(
                sygap, ticket_page, timeout=12)
        except Exception:
            uid, label, stable = "", "", False
        cls = self._classify_coordinator(uid, label)
        self.log(f"    {code} koordinator: uid={uid!r} label={label[:40]!r} "
                 f"-> {cls} (stabil={stable})")
        if not stable:
            return "skip:koordinator belum stabil, retry next loop"
        if cls == "skip-rizky":
            return "skip:koordinator Rizky"
        if cls == "other":
            return f"skip:sudah di-TO orang ({((label or uid)[:40])})"
        if cls == "mine" and "IN_PROGRESS" in (form_status or "").upper():
            return "mine"
        btn = self.fast_take_ownership(sygap, ticket_page)
        if btn == "SKIP_COORDINATOR":
            return "skip:koordinator Rizky (TO guard)"
        if btn is not None and str(btn).startswith("TAKEN"):
            self.log(f"    {code} koordinator berubah saat isi ({btn}) -> BATAL anti rebut")
            return f"skip:{btn}"
        if btn == "WIP_NOTE_CLICKED":
            self.log(f"    {code} modal WIP terbuka, selesaikan...")
            if not self._handle_wip_modal(ticket_page):
                return "skip:modal WIP gagal"
            btn = "WIP_NOTE"
        if btn in ("NEXT_STAGE", "SAVE", "WIP_INC", "REDISPATCH",
                   "UPDATE_INC", "WIP_NOTE"):
            # SYARAT MUTLAK (permintaan user): status TERBUKTI IN_PROGRESS.
            if self._verify_in_progress_js(ticket_page, timeout=8):
                dt = _t.time() - _t0
                self.log(f"    {code} status TERBUKTI IN_PROGRESS ({dt:.0f}s)")
                return "ok"
            # Cadangan: tunggu cara lama sebentar.
            if sygap.wait_for_in_progress(ticket_page, timeout=10):
                dt = _t.time() - _t0
                self.log(f"    {code} TO confirmed ({dt:.0f}s)")
                return "ok"
            dt = _t.time() - _t0
            self.log(f"    {code} status TAK jadi IN_PROGRESS ({dt:.0f}s) — retry next loop")
            return "skip:status tak jadi IN_PROGRESS"
        if btn is None or btn in ("NO_BUTTON", "NO_IC", "NO_JQUERY"):
            # Fallback 1x ke take_ownership bot lama (lambat tapi lengkap).
            self.log(f"    {code} fast-TO {btn} -> fallback bot lama...")
            try:
                old = sygap.take_ownership(ticket_page)
            except Exception as e:
                return f"skip:fallback error ({e})"
            if old == "SKIP_COORDINATOR":
                return "skip:koordinator Rizky (TO guard)"
            if self._verify_in_progress_js(ticket_page, timeout=8) \
                    or sygap.wait_for_in_progress(ticket_page, timeout=10):
                self.log(f"    {code} TO confirmed via fallback")
                return "ok"
            return "skip:fallback tak jadi IN_PROGRESS"
        self.log(f"    {code} klik TO gagal ({btn}) -> skip tanpa tunggu")
        return f"skip:klik TO gagal ({btn})"

    # ---------------- filter assigned-to-me (FASE EXECUTE sweep) ----------------
    def _filter_assigned_to_me(self, page):
        """Set dashboard ke ASSIGNED + solver saya. Fallback: filter client-side."""
        try:
            from config.settings import USER_ID
        except Exception:
            USER_ID = "55654"
        try:
            page.locator("#searchSelect").select_option(label="ASSIGNED")
            page.wait_for_timeout(500)
        except Exception:
            pass
        # Coba set solverSearch select2 ke ID saya (pola sama spt solverGroupSearch).
        try:
            js = f"""(function(){{
                var el = document.getElementById('solverSearch');
                if (el && window.jQuery) {{
                    var $el = jQuery(el);
                    if ($el.find('option[value="{USER_ID}"]').length === 0) {{
                        $el.append(new Option('{USER_ID}', '{USER_ID}', true, true));
                    }}
                    $el.val('{USER_ID}').trigger('change');
                    return true;
                }}
                return false;
            }})();"""
            page.evaluate(js)
            page.wait_for_timeout(800)
        except Exception:
            pass
        try:
            btn = page.locator("#btn_apply")
            if btn.count() > 0:
                btn.first.click()
                page.wait_for_timeout(4000)
        except Exception:
            pass

    # ---------------- koreksi OG via katalog (anti typo) ----------------
    OG_TRAILING_JUNK = ("terima", "terimakasih", "terima kasih", "trimakasih",
                        "trima kasih", "makasih", "thanks", "thank you",
                        "kasih", "tq", "mohon", "mohon dibantu", "tolong")

    def _clean_og_trailing(self, og):
        """Buang kata ekor sampah (TERIMA/makasih/dll) sebelum ke katalog."""
        import re as _re
        s = (og or "").strip()
        for _ in range(3):
            new = _re.sub(
                r"(?i)\s+(terima\s*kasih|terima|trimakasih|trima\s*kasih|makasih|"
                r"thanks|thank\s*you|kasih|tq|mohon|tolong)[\s.,;:!]*$", "", s).strip()
            if new == s or not new:
                break
            s = new
        return s

    def _join_inc_msg(self, inc, msg):
        """Gabung INC + pesan tanpa duplikat prefix ('INC1: INC1: ...')."""
        import re as _re
        m = (msg or "").strip()
        m = _re.sub(rf"^\d+\.\s*", "", m)
        if _re.match(rf"(?i){_re.escape(inc)}\s*:", m):
            return m[:200]
        return f"{inc}: {m}"[:200]

    def _resolve_og(self, og, log):
        """Kembalikan (resolved, retry_candidates) via katalog OG INSERA."""
        try:
            from app.services.owner_group_service import resolve_owner_group
        except Exception as e:
            log(f"    OG katalog tak bisa dimuat ({e}) -> pakai apa adanya")
            return og, []
        cleaned = self._clean_og_trailing(og)
        if cleaned != og:
            log(f"    OG ekor sampah dibuang: {og!r} -> {cleaned!r}")
        try:
            resolved, info = resolve_owner_group(cleaned)
        except Exception as e:
            log(f"    OG resolve error ({e}) -> pakai apa adanya")
            return cleaned, []
        if info.get("corrected"):
            log(f"    OG dikoreksi katalog: {cleaned!r} -> {resolved!r} "
                f"(skor {info.get('score') or 0:.2f})")
        elif not info.get("score"):
            log("    OG katalog KOSONG (tidak ada file/sheet) -> tanpa koreksi")
        return resolved, info.get("retry") or []

    # ---------------- eksekusi per jenis (pakai helper app/ yang sudah ada) ----------------
    def _execute_dispatch(self, sygap, page, ticket_page, code, note):
        from app.parser import (extract_owner_group, extract_inc_number,
                                is_bulk_og_change, extract_bulk_og_target,
                                extract_bulk_inc_list, is_workzone_request)
        from app.services.biscuit_service import BiscuitService
        from app.services.history_service import log_history
        from config.settings import USER_ID

        if "dispatch" not in (note or "").lower():
            return "skip:no dispatch in note"
        if is_workzone_request(note):
            # ATURAN WORKZONE (keputusan user, mengikat): TANPA dispatch
            # BISCUIT, langsung complete dengan note terkunci.
            done_note = WORKZONE_DONE_NOTE
            self.log(f'    WORKZONE -> TANPA dispatch BISCUIT, reply="{done_note}"')
            self._assert_reply_locked("DISPATCH-WORKZONE", note, done_note)
            try:
                page.bring_to_front()
                self._browser.activate_page(ticket_page)
            except Exception:
                pass
            done = sygap.complete_ticket(ticket_page, note=done_note)
            if not done:
                try:
                    ticket_page.reload(wait_until="domcontentloaded", timeout=8000)
                    done = sygap.complete_ticket(ticket_page, note=done_note)
                except Exception:
                    pass
            if done:
                try:
                    log_history(feature="DISPATCH", ticket_code=code,
                                ticket_id="", owner_group="WORKZONE",
                                note=note, reply_sygap=done_note,
                                biscuit_status="", biscuit_message="workzone no-dispatch",
                                status="SUCCESS", solver_id=str(USER_ID))
                except Exception:
                    pass
                return "ok:workzone-tanpa-dispatch"
            return "retry:complete gagal"

        owner_group = extract_owner_group(note)
        inc_number = extract_inc_number(note)

        owner_group = extract_owner_group(note)
        inc_number = extract_inc_number(note)

        # Fallback: INC tidak ada di note -> baca dari field halaman tiket
        # (pola Salah_Dispatch_Regional tanpa INC di note, spt bot lama).
        if not inc_number:
            try:
                inc_number = sygap.wait_for_ticket_inc(ticket_page) or None
                if inc_number:
                    self.log(f"    INC dari halaman: {inc_number}")
            except Exception:
                pass

        # Koreksi OG via katalog INSERA (wajib — jangan kirim mentah).
        owner_group, _og_retry = self._resolve_og(owner_group, self.log) \
            if owner_group else (owner_group, [])

        # ATURAN C4-EARLY (SOP): target C4 jelas tapi OG tak terparse
        # (note tanpa loker/og/owner group/ke, mis. "Mohon bantu Dispatch
        # C4 CONSUMER"). Tetap TANPA BISCUIT: langsung complete + note
        # arahan terkunci, jangan dibuang sebagai skip.
        if not owner_group and not is_bulk_og_change(note) \
                and is_c4_dispatch_request(note):
            done_note = C4_REDIRECT_NOTE
            self.log('    target C4 jelas (OG tak terparse) -> TANPA dispatch '
                     f'BISCUIT, reply="{done_note}"')
            self._assert_reply_locked("DISPATCH-C4", note, done_note)
            try:
                page.bring_to_front()
                self._browser.activate_page(ticket_page)
            except Exception:
                pass
            done = sygap.complete_ticket(ticket_page, note=done_note)
            if not done:
                try:
                    ticket_page.reload(wait_until="domcontentloaded", timeout=8000)
                    done = sygap.complete_ticket(ticket_page, note=done_note)
                except Exception:
                    pass
            if done:
                try:
                    log_history(feature="DISPATCH", ticket_code=code,
                                ticket_id=inc_number or "", owner_group="C4_CONSUMER",
                                note=note, reply_sygap=done_note,
                                biscuit_status="", biscuit_message="C4 no-dispatch",
                                status="SUCCESS", solver_id=str(USER_ID))
                except Exception:
                    pass
                return "ok:c4-tanpa-dispatch"
            return "retry:complete gagal"

        targets = []
        og_retries = {}
        if is_bulk_og_change(note):
            bulk_og = extract_bulk_og_target(note)
            bulk_incs = extract_bulk_inc_list(note)
            if not bulk_incs:
                try:
                    inc_pg = sygap.wait_for_ticket_inc(ticket_page) or None
                    if inc_pg:
                        bulk_incs = [inc_pg]
                        self.log(f"    INC dari halaman: {inc_pg}")
                except Exception:
                    pass
            if not bulk_og or not bulk_incs:
                return "skip:bulk tidak terparse"
            bulk_og, _bulk_retry = self._resolve_og(bulk_og, self.log)
            og_retries[bulk_og] = _bulk_retry
            targets = [(inc, bulk_og) for inc in bulk_incs]
        else:
            if not owner_group or not inc_number:
                return "skip:OG/INC tidak terparse"
            og_retries[owner_group] = _og_retry
            targets = [(inc_number, owner_group)]

        # ATURAN C4 (SOP, bukan error teknis): OG mengandung C4/C4_CONSUMER
        # -> JANGAN kirim ke BISCUIT (walau BISCUIT mau menerima, SOP
        # melarang kita mengubah OG ke C4). Cukup TO + complete + note arahan.
        if targets and all("C4" in (og or "").upper() for _, og in targets):
            done_note = C4_REDIRECT_NOTE
            self.log(f'    OG=C4 -> TANPA dispatch BISCUIT, reply="{done_note}"')
            self._assert_reply_locked("DISPATCH-C4", note, done_note)
            try:
                page.bring_to_front()
                self._browser.activate_page(ticket_page)
            except Exception:
                pass
            done = sygap.complete_ticket(ticket_page, note=done_note)
            if not done:
                try:
                    ticket_page.reload(wait_until="domcontentloaded", timeout=8000)
                    done = sygap.complete_ticket(ticket_page, note=done_note)
                except Exception:
                    pass
            if done:
                try:
                    log_history(feature="DISPATCH", ticket_code=code,
                                ticket_id=targets[0][0], owner_group=targets[0][1],
                                note=note, reply_sygap=done_note,
                                biscuit_status="", biscuit_message="C4 no-dispatch",
                                status="SUCCESS", solver_id=str(USER_ID))
                except Exception:
                    pass
                return "ok:c4-tanpa-dispatch"
            return "retry:complete gagal"

        biscuit = BiscuitService(browser_manager=self._browser)
        if not biscuit.open():
            return "retry:biscuit tab not found"
        try:
            from app.services.sygap_service import is_invalid_owner_group_error
        except Exception:
            is_invalid_owner_group_error = lambda m: False
        ok_all, msgs = True, []
        targets = list(targets)
        for idx, (inc, og) in enumerate(targets):
            cmd = f"/dispatchticket {inc} {og}"
            resp = None
            for attempt in range(1, BISCUIT_MAX_RETRIES + 1):
                self.log(f"    Sending: {cmd} (attempt {attempt})")
                resp = biscuit.execute(cmd, "INSERA")
                self.log(f"    BISCUIT: {resp.status} - {resp.message}")
                if resp.status != "UNKNOWN":
                    break
                biscuit.wait_for_ready()
            # OG ditolak BISCUIT -> coba kandidat katalog berikut (maks 2).
            if resp is not None and resp.status == "FAILED" \
                    and is_invalid_owner_group_error(resp.message or ""):
                for cand, score in (og_retries.get(og) or [])[:2]:
                    if cand == og:
                        continue
                    self.log(f"    OG invalid, retry kandidat katalog: {cand!r} "
                             f"(skor {score:.2f})")
                    resp = biscuit.execute(f"/dispatchticket {inc} {cand}", "INSERA")
                    self.log(f"    BISCUIT retry: {resp.status} - {resp.message}")
                    if resp.status == "SUCCESS":
                        og = cand
                        targets[idx] = (inc, cand)
                        break
                    biscuit.wait_for_ready()
            if resp is None or resp.status != "SUCCESS":
                ok_all = False
                msgs.append(self._join_inc_msg(
                    inc, resp.message if resp else "?"))
        note_done = "Cek Kembali" if ok_all else "; ".join(msgs)[:200]
        # JARING PENGAMAN: pastikan bukan tiket Symptom/C4 yang lolos ke
        # jalur dispatch biasa. Gagal -> raise, complete batal.
        if self._is_symptom_request(note):
            raise AssertionError("REPLY MISMATCH [DISPATCH]: tiket Symptom "
                                 "tidak boleh lewat jalur dispatch")
        if all("C4" in (og or "").upper() for _, og in targets):
            raise AssertionError("REPLY MISMATCH [DISPATCH]: tiket C4 "
                                 "tidak boleh lewat jalur dispatch")
        self._assert_reply_locked("DISPATCH", note, note_done)
        try:
            page.bring_to_front()
            self._browser.activate_page(ticket_page)
        except Exception:
            pass
        done = sygap.complete_ticket(ticket_page, note=note_done)
        if not done:
            try:
                ticket_page.reload(wait_until="domcontentloaded", timeout=8000)
                done = sygap.complete_ticket(ticket_page, note=note_done)
            except Exception:
                pass
        if done:
            try:
                # Log status murni dari hasil eksekusi BISCUIT
                b_status = "SUCCESS" if ok_all else "FAILED"
                t_status = "SUCCESS" if ok_all else "FAILED"
                log_history(feature="DISPATCH", ticket_code=code,
                            ticket_id=targets[0][0], owner_group=targets[0][1],
                            note=note, reply_sygap=note_done,
                            biscuit_status=b_status,
                            biscuit_message="; ".join(msgs)[:300],
                            status=t_status, solver_id=str(USER_ID))
            except Exception:
                pass
            return "ok" if ok_all else f"done-with-error:{note_done[:80]}"
        return "retry:complete gagal"

    def _execute_service_id(self, sygap, page, ticket_page, code, note):
        from app.parser import (extract_service_id, extract_service_type,
                                extract_inc_number, extract_bulk_inc_list,
                                is_impacted_service_request)
        from app.services.biscuit_service import BiscuitService
        from app.services.oss_incident_service import OssIncidentService
        from app.services.history_service import log_history
        from app.models.response import Response
        from config.settings import USER_ID

        # ATURAN PRIORITAS (keputusan user, mengikat):
        #   0. Note 'tiket_impacted_service_tidak_ada' -> WAJIB via BISCUIT
        #      /loaddatek INC1,INC2,... (SATU command, koma). Reply "Cek Kembali" OK.
        #   1. Ada nomor Service ID di note -> WAJIB eksekusi BISCUIT,
        #      walau note juga menyebut Symptom. Reply "Cek Kembali" OK.
        #   2. Tanpa Service ID + ada permintaan Symptom -> complete dengan
        #      note penolakan terkunci, tanpa BISCUIT/OSS.
        #   3. Tanpa keduanya -> skip.
        # Cabang impacted (0) WAJIB SEBELUM service_id/type biasa: request
        # impacted TANPA Service ID tidak boleh kena penolakan "sepaket".
        service_id = extract_service_id(note)
        service_type = extract_service_type(note)
        symptom = self._is_symptom_request(note)
        inc_number = extract_inc_number(note)
        if not inc_number:
            inc_number = sygap.wait_for_ticket_inc(ticket_page) or ""
        if not inc_number:
            return "skip:INC tidak ketemu"

        path = decide_service_id_path(service_id, service_type, symptom)
        resp = None
        lock_rule = "SERVICEID"
        if is_impacted_service_request(note) and not service_id:
            loaddatek_incs = extract_bulk_inc_list(note) \
                or ([inc_number] if inc_number else [])
            if not loaddatek_incs:
                return "skip:LOADDATEK INC tidak ketemu"
            self.log(f"    [LOADDATEK] Target {len(loaddatek_incs)} INC: "
                     f"{','.join(loaddatek_incs[:8])}")
            biscuit_ld = BiscuitService(browser_manager=self._browser)
            if not biscuit_ld.open():
                return "retry:biscuit tab not found"
            if not sygap._wait_for_biscuit_login(self.log, timeout=10):
                return "retry:biscuit belum login"
            ld_cmd = f"/loaddatek {','.join(loaddatek_incs)}"
            self.log(f"    Sending: {ld_cmd[:150]}")
            for _ in range(BISCUIT_MAX_RETRIES):
                resp = biscuit_ld.execute(ld_cmd, "INSERA")
                self.log(f"    BISCUIT: {resp.status} - {resp.message}")
                if resp.status != "UNKNOWN":
                    break
                biscuit_ld.wait_for_ready()
            # Samakan ke shared tail: histori catat semua INC + OG=LOADDATEK.
            lock_rule = "LOADDATEK"
            inc_number = ",".join(loaddatek_incs)
            service_id = "LOADDATEK"
        elif path == "biscuit":
            if symptom:
                self.log("    note campuran: Service ID diprioritaskan, Symptom diabaikan")
            biscuit = BiscuitService(browser_manager=self._browser)
            if not biscuit.open():
                return "retry:biscuit tab not found"
            if not sygap._wait_for_biscuit_login(self.log, timeout=10):
                return "retry:biscuit belum login"
            cmd = f"/changeserviceid {inc_number} {service_id}"
            self.log(f"    Sending: {cmd}")
            for _ in range(BISCUIT_MAX_RETRIES):
                resp = biscuit.execute(cmd, "INSERA")
                self.log(f"    BISCUIT: {resp.status} - {resp.message}")
                if resp.status != "UNKNOWN":
                    break
                biscuit.wait_for_ready()
            # Service Type via OSS API (API-first, sepaket dengan Service ID)
            if service_type:
                try:
                    api = OssIncidentService()
                    r2 = api.update_service_type(inc_number, service_type)
                    self.log(f"    OSS API service_type: {r2.status} - {r2.message}")
                except Exception as e:
                    self.log(f"    OSS API error: {e}")
        elif path == "symptom-reject":
            self.log("    tanpa Service ID + permintaan Symptom -> note penolakan")
            resp = Response(status="REJECTED", message=SYMPTOM_REJECT_NOTE)
            lock_rule = "SYMPTOM"
        elif path == "svctype-reject":
            resp = Response(status="REJECTED", message=(
                "service type sudah sepaket dengan service ID, maka dari itu "
                "tidak dapat kami penuhi, silahkan request perubahan service ID"))
        else:
            return "skip:Service ID/Type tidak ketemu"

        if resp and resp.status == "SUCCESS":
            done_note = "Cek Kembali"
        elif resp and resp.status == "REJECTED":
            done_note = resp.message[:500]
        elif resp and ("biscuit" in (resp.message or "").lower()
                       or "timeout" in (resp.message or "").lower()):
            return "retry:biscuit tidak siap"
        else:
            done_note = (resp.message if resp else "Unknown error")[:200]
        # JARING PENGAMAN: verifikasi note SEBELUM complete. Gagal -> raise,
        # complete batal, tiket aman. Jalur Symptom: harus TEPAT locked note.
        # Jalur BISCUIT (walau note menyebut Symptom): "Cek Kembali" sah.
        self._assert_reply_locked(lock_rule, note, done_note)
        try:
            page.bring_to_front()
            self._browser.activate_page(ticket_page)
        except Exception:
            pass
        done = sygap.complete_ticket(ticket_page, note=done_note)
        if not done:
            try:
                ticket_page.reload(wait_until="domcontentloaded", timeout=8000)
                done = sygap.complete_ticket(ticket_page, note=done_note)
            except Exception:
                pass
        if done:
            try:
                log_history(feature="CHANGE_SERVICE_ID", ticket_code=code,
                            ticket_id=inc_number, owner_group=service_id or "",
                            note=note, reply_sygap=done_note,
                            biscuit_status=resp.status if resp else "",
                            biscuit_message=(resp.message if resp else "")[:300],
                            status="SUCCESS", solver_id=str(USER_ID))
            except Exception:
                pass
            return "ok"
        return "retry:complete gagal"

    # ---------------- submit relasi GAMAS (API via DOM + fallback UI) ----------------
    def _gamas_api_dom(self, svc, parent_inc, child_str):
        """Submit relasi via HTTP dengan token dari DOM tab hidup.

        GET mentah tidak memuat _NONCE_TOKEN_REQUEST_HASH (di-render di DOM),
        sehingga POST tanpa nonce selalu 403. Token wajib dibaca dari tab.
        Returns Response, atau None bila tab/token/cookie tak tersedia.
        """
        import re as _re
        import urllib.request
        import uuid
        from app.models.response import Response
        from app.services.response_service import clean_error_message

        bm = self._browser
        page = None
        try:
            page = bm.get_insera_gamas_page()
            if page is None or not bm.is_page_alive(page):
                self.log("    tab INSERA belum ada -> bukakan dulu...")
                from config.settings import GAMAS_RELATIONS_URL
                page = bm.open_url(GAMAS_RELATIONS_URL)
                if page is None:
                    return None
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    page.wait_for_timeout(3000)
                except Exception:
                    pass
        except Exception as e:
            self.log(f"    buka tab INSERA gagal: {e}")
            return None
        try:
            toks = page.evaluate("""() => {
                const g = n => { const el = document.querySelector(
                    'input[name=\"' + n + '\"]'); return el ? (el.value || '') : ''; };
                return {csrf: g('OWASP_CSRFTOKEN'),
                        nonce: g('_NONCE_TOKEN_REQUEST_HASH')};
            }""") or {}
        except Exception:
            toks = {}
        csrf, nonce = (toks.get("csrf") or ""), (toks.get("nonce") or "")
        # Token kosong kemungkinan halaman belum render sempurna -> reload
        # 1x lalu baca ulang, sebelum menyimpulkan sesi mati.
        if (not csrf or not nonce) and page is not None:
            try:
                self.log("    token tak lengkap -> reload tab 1x...")
                page.reload(wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(5000)
                toks = page.evaluate("""() => {
                    const g = n => { const el = document.querySelector(
                        'input[name="' + n + '"]'); return el ? (el.value || '') : ''; };
                    return {csrf: g('OWASP_CSRFTOKEN'),
                            nonce: g('_NONCE_TOKEN_REQUEST_HASH')};
                }""") or {}
                csrf, nonce = (toks.get("csrf") or ""), (toks.get("nonce") or "")
            except Exception:
                pass
        # Dinding login = sesi INSERA mati. Bedakan dari error biasa agar
        # pesannya jelas (bukan retry buta tiap siklus). Tanpa tab -> None
        # (biar fallback UI yang coba bukakan).
        if page is None:
            return None
        try:
            login_wall = "login" in (page.url or "").lower()
            if not login_wall:
                login_wall = bool(page.evaluate(
                    "() => !!document.querySelector('input[type=\"password\"]')"))
        except Exception:
            login_wall = False
        if login_wall:
            from app.models.response import Response
            return Response(status="FAILED", message="LOGIN_INSERA_EXPIRED")
        cookie = ""
        try:
            cookie = svc._get_cookie_header() or ""
        except Exception:
            pass
        if not csrf or not nonce or not cookie:
            self.log(f"    token/cookie tak lengkap "
                     f"(csrf={bool(csrf)} nonce={bool(nonce)} cookie={bool(cookie)})")
            return None
        boundary = "----WebKitFormBoundary" + uuid.uuid4().hex[:16]

        def field(name, value):
            return (f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n")

        body = "".join([
            field("_NONCE_TOKEN_REQUEST_HASH", nonce),
            field("massGamasRelations_SUBMITTED", "true"),
            field("_FORM_META_ORIGINAL_ID", ""),
            field("OWASP_CSRFTOKEN", csrf),
            field("parent_ticket", parent_inc),
            field("child_ticket", child_str),
            field("submit", "Save"),
            f"--{boundary}--\r\n",
        ]).encode()
        try:
            req = urllib.request.Request(
                svc.GAMAS_FORM_URL + "?_action=submit",
                data=body, method="POST",
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                         "Cookie": cookie, "User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            self.log(f"    GAMAS API DOM: POST gagal ({e})")
            return None
        m = _re.search(r'&quot;errors&quot;\s*:\s*\{[^}]*\}', content) or \
            _re.search(r'"errors"\s*:\s*\{[^}]*\}', content)
        if m:
            return Response(status="FAILED", message=clean_error_message(m.group(0)))
        return Response(status="SUCCESS", message="Relasi GAMAS tersimpan via API (DOM)")

    def _gamas_ui_fallback(self, svc, parent_inc, child_str):
        """Fallback UI: pastikan tab ada -> isi field -> klik Save."""
        from app.models.response import Response
        try:
            page = None
            try:
                if svc.open():
                    page = svc.page
            except Exception:
                page = None
            if page is None or not self._browser.is_page_alive(page):
                from config.settings import GAMAS_RELATIONS_URL
                self.log("    fallback UI: bukakan tab INSERA...")
                self._browser.open_url(GAMAS_RELATIONS_URL)
                try:
                    import time as _t
                    _t.sleep(3)
                except Exception:
                    pass
                if not svc.open():
                    return Response(status="FAILED", message="Tab INSERA tidak bisa dibuka")
            svc.navigate_to_relations()
            if not svc.wait_for_fields(timeout=20):
                return Response(status="FAILED", message="Field INSERA tak muncul (20 dtk)")
            if not svc.fill_parent(parent_inc):
                return Response(status="FAILED", message="Gagal isi parent")
            if not svc.fill_child(child_str):
                return Response(status="FAILED", message="Gagal isi child")
            if not svc.click_save():
                return Response(status="FAILED", message="Tombol Save gagal diklik")
            return Response(status="SUCCESS", message="Relasi GAMAS tersimpan via UI")
        except Exception as e:
            return Response(status="FAILED", message=f"UI fallback error: {e}")

    def _keepalive_insera(self):
        """Kirim heartbeat ringan ke tab INSERA agar sesi tidak logout karena idle."""
        if self._browser is None or self.dry_run:
            return
        try:
            page = self._browser.get_insera_gamas_page()
            if page is None or not self._browser.is_page_alive(page):
                return
            res = page.evaluate("""() => {
                try {
                    const isLogin = !!document.querySelector('input[type="password"]') || 
                                    window.location.href.toLowerCase().includes('login');
                    if (isLogin) {
                        return { status: 'LOGIN_REQUIRED' };
                    }
                    if (typeof keepMeAlive === 'function') {
                        keepMeAlive('image_alive');
                    }
                    fetch(window.location.href, { method: 'GET', cache: 'no-store' }).catch(() => {});
                    return { status: 'OK' };
                } catch (e) {
                    return { status: 'ERROR', message: e.message };
                }
            }""")
            if res and res.get("status") == "LOGIN_REQUIRED":
                self.log("    [HEARTBEAT] Sesi INSERA expired (terlempar ke login). Silakan login ulang tab INSERA.")
        except Exception:
            pass

    def _execute_gamas(self, sygap, page, ticket_page, code, note):
        from app.services.biscuit_service import BiscuitService
        from app.services.insera_gamas_service import InseraGamasService
        from app.services.history_service import log_history
        from config.settings import USER_ID
        import re as _re

        biscuit = BiscuitService(browser_manager=self._browser)

        # KASKADE CARI INDUK (paritas bot lama):
        #  1. Penanda eksplisit di note (IG/INDUK GAMAS/INDUKAN/ke induk/
        #     Tiket GAMAS berikut/GAMAS INC non-anak).
        #  2. Field Ticket ID form (INC yg tak ada di note, saat note
        #     menyebut ANAK GAMAS).
        #  3. Deteksi source via BISCUIT: bila TEPAT 1 INC bersource GAMAS
        #     di antara semua INC -> itulah induk, sisanya kandidat anak.
        #     Bila >=2 GAMAS -> ambigu, SKIP (pelapor harus tentukan 1 induk).
        parent_inc = None
        biscuit = BiscuitService(browser_manager=self._browser)
        # Extract kandidat induk GAMAS:
        # Coba ambil via pola teks induk terlebih dahulu
        parent_candidates = []
        try:
            m_cand = _re.search(
                r"\b(?:INDUK\s+GAMAS|IG|INDUKAN|INDUK|NDUK\s+GAMAS)\s*[:;\s]*([A-Z0-9_ -]+)",
                note or "",
                _re.IGNORECASE,
            )
            if m_cand:
                parent_candidates = [i.upper() for i in _re.findall(r"INC\d+", m_cand.group(1))]
        except Exception:
            parent_candidates = []

        # Cek validitas kandidat via BISCUIT (induk WAJIB ber-source GAMAS)
        proactive_parent = None
        for cand in parent_candidates:
            try:
                chk_c = biscuit.check_ticket(cand)
                if chk_c.get("found"):  # source == GAMAS
                    parent_inc = cand
                    self.log(f"    induk terverifikasi GAMAS dari note: {parent_inc}")
                    break
                elif chk_c.get("source") == "PROACTIVE" or "PROACTIVE" in str(chk_c.get("detail", "")).upper():
                    proactive_parent = cand
                    self.log(f"    kandidat induk {cand} bersource PROACTIVE")
                else:
                    self.log(f"    kandidat induk {cand} bukan GAMAS ({chk_c.get('detail', '')[:80]})")
            except Exception:
                pass

        if not parent_inc and proactive_parent:
            parent_inc = proactive_parent

        if not parent_inc:
            try:
                if hasattr(sygap, "extract_parent_gamas_from_note"):
                    parent_inc = sygap.extract_parent_gamas_from_note(note)
            except Exception:
                pass
            if parent_inc:
                self.log(f"    induk dari note: {parent_inc}")
        if not parent_inc:
            try:
                if hasattr(sygap, "find_parent_from_ticket_id_field"):
                    parent_inc = sygap.find_parent_from_ticket_id_field(
                        ticket_page, note)
                    if parent_inc:
                        self.log(f"    induk dari field form: {parent_inc}")
            except Exception:
                pass
        if not parent_inc:
            try:
                _all = [i.upper() for i in _re.findall(r"INC\d+", note or "", _re.IGNORECASE)]
                try:
                    _fld = sygap.read_child_incs_with_retry(
                        ticket_page, retries=2, log=None) or []
                except Exception:
                    _fld = []
                for _i in _fld:
                    if _i not in _all:
                        _all.append(_i)
                if len(_all) > 1:
                    _src = biscuit.check_children(_all)
                    _gamas = [e["inc"] for e in _src.get("excluded", [])
                              if e.get("source") == "GAMAS"]
                    if len(_gamas) == 1:
                        parent_inc = _gamas[0]
                        self.log(f"    induk terdeteksi otomatis by source: {parent_inc}")
                    elif len(_gamas) > 1:
                        return ("skip:induk ambigu "
                                f"({len(_gamas)} kandidat GAMAS) - perlu 1 induk saja")
            except Exception as e:
                self.log(f"    deteksi induk by source error: {e}")
        if not parent_inc:
            m = _re.search(r"INC\d+", note or "", _re.IGNORECASE)
            parent_inc = m.group(0).upper() if m else None
            if parent_inc:
                self.log(f"    induk fallback INC pertama note: {parent_inc}")
        child_incs = []
        try:
            if hasattr(sygap, "extract_child_incs_excluding_parent"):
                child_incs = sygap.extract_child_incs_excluding_parent(note) or []
        except Exception:
            pass
        if not child_incs or all(c == parent_inc for c in child_incs):
            all_incs = [i.upper() for i in _re.findall(r"INC\d+", note or "", _re.IGNORECASE)]
            child_incs = [i for i in all_incs if i != parent_inc]
        if not child_incs:
            # Note hanya menyebut 1 INC (mis. "relasikan ke Tiket GAMAS
            # berikut : INC53170006") -> anaknya biasanya ada di field
            # Ticket ID form (INC milik request ini sendiri). Baca dari sana
            # spt bot lama, jangan langsung menyerah.
            try:
                field_incs = sygap.read_child_incs_with_retry(
                    ticket_page, retries=3, log=self.log) or []
                child_incs = [i for i in field_incs if i != parent_inc]
                if child_incs:
                    self.log(f"    Child INCs dari field form: {','.join(child_incs[:8])}...")
            except Exception as e:
                self.log(f"    baca field child error: {e}")
        if not parent_inc or not child_incs:
            return "skip:parent/child tidak lengkap"

        # Urutan VERIFIKASI (fail-fast): INDUK dulu, baru anak.
        # Induk WAJIB bersource GAMAS — kalau bukan, stop sebelum cek anak
        # (jangan submit relasi ke induk yang salah).
        try:
            chk = biscuit.check_ticket(parent_inc)
            self.log(f"    cek induk {parent_inc}: {chk.get('detail', '')[:120]}")
        except Exception as e:
            self.log(f"    cek induk error: {e}")
            chk = {"found": False, "detail": str(e)}

        # Validasi source induk GAMAS: jika source PROACTIVE, langsung tolak & complete ticket di SYGAP
        is_proactive = (
            chk.get("source") == "PROACTIVE"
            or "PROACTIVE" in str(chk.get("source", "")).upper()
            or "PROACTIVE" in str(chk.get("detail", "")).upper()
        )
        if is_proactive:
            done_note = GAMAS_PROACTIVE_NOTE
            self.log(f"    induk {parent_inc} source PROACTIVE -> langsung complete dengan reply: '{done_note}'")
            self._assert_reply_locked("GAMAS-PROACTIVE", note, done_note)
            try:
                page.bring_to_front()
                self._browser.activate_page(ticket_page)
            except Exception:
                pass
            done = sygap.complete_ticket(ticket_page, note=done_note)
            if not done:
                try:
                    ticket_page.reload(wait_until="domcontentloaded", timeout=8000)
                    done = sygap.complete_ticket(ticket_page, note=done_note)
                except Exception:
                    pass
            if done:
                try:
                    log_history(feature="GAMAS_RELATIONS", ticket_code=code,
                                ticket_id=parent_inc, owner_group=",".join(child_incs)[:200],
                                note=note, reply_sygap=done_note,
                                biscuit_status="REJECTED", biscuit_message="induk PROACTIVE",
                                status="SUCCESS", solver_id=str(USER_ID))
                except Exception:
                    pass
                try:
                    sygap.related_ids.add(code)
                except Exception:
                    pass
                return "ok:induk-proactive"
            return "retry:complete gagal"

        if not chk.get("found"):
            return f"skip:induk bukan GAMAS ({chk.get('detail', '')[:100]})"

        # Validasi status induk GAMAS: jika status CLOSED, langsung tolak & complete ticket di SYGAP
        if chk.get("is_closed") or "CLOSED" in str(chk.get("ticket_status", "")).upper():
            done_note = GAMAS_CLOSED_NOTE
            self.log(f"    induk {parent_inc} status CLOSED -> langsung complete dengan reply: '{done_note}'")
            self._assert_reply_locked("GAMAS-CLOSED", note, done_note)
            try:
                page.bring_to_front()
                self._browser.activate_page(ticket_page)
            except Exception:
                pass
            done = sygap.complete_ticket(ticket_page, note=done_note)
            if not done:
                try:
                    ticket_page.reload(wait_until="domcontentloaded", timeout=8000)
                    done = sygap.complete_ticket(ticket_page, note=done_note)
                except Exception:
                    pass
            if done:
                try:
                    log_history(feature="GAMAS_RELATIONS", ticket_code=code,
                                ticket_id=parent_inc, owner_group=",".join(child_incs)[:200],
                                note=note, reply_sygap=done_note,
                                biscuit_status="REJECTED", biscuit_message="induk CLOSED",
                                status="SUCCESS", solver_id=str(USER_ID))
                except Exception:
                    pass
                try:
                    sygap.related_ids.add(code)
                except Exception:
                    pass
                return "ok:induk-closed"
            return "retry:complete gagal"

        # Lanjut VERIFIKASI ANAK (1 panggilan batch): yang bersumber GAMAS
        # DILARANG direlasikan; tak terverifikasi dibuang demi aman.
        try:
            child_incs = [c for c in child_incs if c != parent_inc]
            chk_child = biscuit.check_children(child_incs)
            for ex in chk_child.get("excluded", []):
                self.log(f"    anak {ex['inc']} dibuang: source={ex['source']} "
                         f"({ex['detail'][:80]})")
            child_incs = chk_child.get("valid", [])
            if not child_incs:
                return "skip:tidak ada anak valid (semua GAMAS/tak terverifikasi)"
            self.log(f"    anak valid ({len(child_incs)}): {','.join(child_incs[:8])}...")
        except Exception as e:
            self.log(f"    verifikasi anak error ({e}) -> lanjut apa adanya")

        svc = InseraGamasService(browser_manager=self._browser, log_callback=self.log)
        # API via token DOM dulu (tanpa ini POST selalu 403); bila tak bisa,
        # fallback UI (tab dipastikan ada dulu — bukan diasumsikan ada).
        resp = self._gamas_api_dom(svc, parent_inc, ",".join(child_incs))
        if resp is None:
            self.log("    API DOM tak bisa -> fallback UI...")
            resp = self._gamas_ui_fallback(svc, parent_inc, ",".join(child_incs))
        self.log(f"    submit relasi: {resp.status} - {resp.message}")
        if resp is None or resp.status != "SUCCESS":
            return f"retry:submit relasi gagal ({resp.message if resp else 'None'})"
        # Relasi INSERA ok -> WAJIB complete tiket SYGAP (bot lama: note "Cek Kembali").
        done_note = GAMAS_DONE_NOTE
        self._assert_reply_locked("GAMAS", note, done_note)
        try:
            page.bring_to_front()
            self._browser.activate_page(ticket_page)
        except Exception:
            pass
        done = sygap.complete_ticket(ticket_page, note=done_note)
        if not done:
            try:
                ticket_page.reload(wait_until="domcontentloaded", timeout=8000)
                done = sygap.complete_ticket(ticket_page, note=done_note)
            except Exception:
                pass
        if not done:
            return "retry:complete gagal"
        try:
            log_history(feature="GAMAS_RELATIONS", ticket_code=code,
                        ticket_id=parent_inc, owner_group=",".join(child_incs)[:200],
                        note=note, reply_sygap=done_note,
                        biscuit_status="SUCCESS", biscuit_message="",
                        status="SUCCESS", solver_id=str(USER_ID))
        except Exception:
            pass
        try:
            sygap.related_ids.add(code)
        except Exception:
            pass
        return "ok"

    # ---------------- fase per jenis (SCAN OPEN-only + TO) ----------------
    def _phase_to(self, jenis, max_items=None):
        """FASE TO: filter notes + ASSIGNED + All -> TO yang solver-nya kosong.

        max_items: batasi jumlah tiket yang dibuka untuk TO (None = semua).
        Returns [{code, jenis, note}] untuk tiket yang berhasil di-TO / sudah milik saya.
        """
        bm, sygap = self._ensure_browser()
        page = sygap.navigate_to_dashboard()
        self.log(f"--- FASE TO {jenis.upper()}: notes + {TO_STATUS} + All ---")
        rows = self._collect_filtered_rows(sygap, page, jenis, TO_STATUS, "ALL")
        if not rows:
            self.log(f"[TO {jenis}] tidak ada baris setelah filter")
            return []
        self.log(f"[TO {jenis}] {len(rows)} baris, saring solver kosong...")
        hasil = []
        attempts = 0
        for r in rows:
            if not self.running:
                break
            if max_items is not None and attempts >= max_items:
                self.log(f"[TO {jenis}] batas {max_items} tiket tercapai, stop")
                break
            code = r.get("request_code", "?")
            # Sudah milik saya (terbaca akurat di kolom Solver) -> tanpa buka form.
            if is_mine(r):
                self.log(f"  [TO {jenis}] {code} sudah milik saya (tabel), tanpa buka form")
                hasil.append({"code": code, "jenis": jenis, "note": ""})
                continue
            allowed, reason = check_assigned_for_to(r)
            if not allowed:
                self.log(f"  [TO {jenis}] {code} SKIP ({reason})")
                self.stats["skipped"] += 1
                continue
            attempts += 1
            self.log(f"  [TO {jenis}] buka {code}...")
            import time as _t
            _t0 = _t.time()
            ticket_page = sygap.click_ticket(page, r, log_callback=self.log)
            if ticket_page is None:
                self.log(f"    {code} gagal dibuka -> retry next loop")
                self.stats["skipped"] += 1
                continue
            try:
                st = sygap.read_ticket_status(ticket_page) or ""
                if "COMPLETED" in st.upper():
                    self.log(f"    {code} sudah COMPLETED di form -> skip")
                    continue
                # Note TIDAK dibaca di fase TO (hemat 3-8 dtk/tiket).
                # Eksekusi membaca note sendiri saat dibutuhkan.
                note = ""
                res = self._to_one_ticket(sygap, page, ticket_page, code,
                                          form_status=st)
                self.log(f"    {code} TO -> {res} (total {(_t.time() - _t0):.0f}s sejak buka form)")
                if res == "ok" or res == "mine":
                    hasil.append({"code": code, "jenis": jenis, "note": note})
                    if res == "ok":
                        self.stats["to_ok"] += 1
                else:
                    self.stats["skipped"] += 1
            except Exception as e:
                # 1 tiket timeout/error tidak boleh membunuh 1 fase -> tutup tab & lanjut
                self.log(f"    {code} TO error/timeout SYGAP ({e}) -> tutup tab & lanjut tiket berikut")
                self.stats["skipped"] += 1
                continue
            finally:
                try:
                    if ticket_page is not None and not ticket_page.is_closed():
                        ticket_page.close()
                except Exception:
                    pass
                try:
                    page.bring_to_front()
                except Exception:
                    pass
        self.log(f"[TO {jenis}] selesai: {len(hasil)} tiket jadi milik saya")
        return hasil

    def _scan_mine(self, jenis, known_codes=(), statuses=None):
        """FASE EXECUTE scan: notes + OPEN + Assigned to Me (1 filter saja).

        Returns [{code, jenis, note:""}] untuk tiket milik saya yang belum ada
        di known_codes (note dibaca ulang saat eksekusi).
        """
        bm, sygap = self._ensure_browser()
        page = sygap.navigate_to_dashboard()
        statuses = tuple(statuses or EXEC_STATUSES)
        hasil = []
        seen = set(known_codes or ())
        for st in statuses:
            if not self.running:
                break
            self.log(f"--- SCAN milik saya {jenis.upper()}: notes + {st} + Assigned to Me ---")
            rows = self._collect_filtered_rows(sygap, page, jenis, st, "ME")
            if not rows:
                self.log(f"[SCAN {jenis}] tidak ada baris ({st} + Assigned to Me)")
                continue
            for r in rows:
                code = r.get("request_code", "?")
                if code in seen:
                    continue
                if is_mine(r):
                    self.log(f"  [SCAN {jenis}] {code} MILIK-SAYA [{st}]")
                    hasil.append({"code": code, "jenis": jenis, "note": ""})
                    seen.add(code)
                else:
                    self.log(f"  [SCAN {jenis}] {code} SKIP (bukan milik saya)")
        return hasil

    def _execute_jenis(self, jenis, items):
        """Eksekusi 1 jenis: cari tiap tiket (OPEN + Assigned to Me),
        lalu kerjakan satu-per-satu. Returns jumlah tiket berhasil dieksekusi."""
        if not items:
            return 0
        bm, sygap = self._ensure_browser()
        page = sygap.navigate_to_dashboard()
        t0 = time.time()
        fail_streak = 0
        done = 0
        for it in items:
            if not self.running:
                break
            if time.time() - t0 > EXECUTE_TIMEOUT_TOTAL:
                self.log("[EXECUTE] timeout total, sisa next loop")
                break
            code = it["code"]
            self.log(f"  [EXE] {code} ({jenis}) buka untuk eksekusi...")
            try:
                # 1. Coba cari di tabel yang sedang aktif tanpa reload filter
                row = self._find_row_in_current_table(sygap, page, code)
                # 2. Jika belum ada, cari lintas varian notes + lintas halaman
                if row is None:
                    for _st in EXEC_STATUSES:
                        try:
                            row = self._find_code_in_variants(
                                sygap, page, jenis, code, _st, "ME")
                        except Exception:
                            row = None
                        if row is not None:
                            break
            except Exception:
                row = None
            if row is None:
                self.log(f"    {code} tidak ketemu (OPEN + Assigned to Me) -> skip")
                continue
            ticket_page = sygap.click_ticket(page, row, log_callback=self.log)
            if ticket_page is None:
                self.log(f"    {code} gagal dibuka/timeout SYGAP -> lanjut tiket berikut")
                continue
            try:
                # Guard form: status tabel tak bisa dipercaya (kolom ikon),
                # jadi cek COMPLETED di form sebelum eksekusi.
                try:
                    _fst = sygap.read_ticket_status(ticket_page) or ""
                except Exception:
                    _fst = ""
                if "COMPLETED" in _fst.upper() or "CLOSED" in _fst.upper():
                    self.log(f"    {code} sudah {_fst} di form -> skip")
                    continue
                note = it.get("note") or ""
                if not note:
                    # Note wajib ada untuk eksekusi: 1x baca, gagal -> 1x retry.
                    try:
                        note = sygap.read_ticket_note(ticket_page) or ""
                    except Exception:
                        note = ""
                    if not note:
                        try:
                            ticket_page.wait_for_timeout(1000)
                            note = sygap.read_ticket_note(ticket_page) or ""
                        except Exception:
                            note = ""
                if not note:
                    self.log(f"    {code} note kosong -> skip (retry next loop)")
                    continue
                if jenis == "dispatch":
                    res = self._execute_dispatch(sygap, page, ticket_page, code, note)
                elif jenis == "service_id":
                    res = self._execute_service_id(sygap, page, ticket_page, code, note)
                else:
                    res = self._execute_gamas(sygap, page, ticket_page, code, note)
                self.log(f"    {code} EXEC -> {res}")
                if res == "ok" or str(res).startswith("done-with") or str(res).startswith("ok:"):
                    self.stats["exec_ok"] += 1
                    done += 1
                    fail_streak = 0
                else:
                    # Circuit breaker khusus GAMAS: jika error sistemik (mis. INSERA down / network error)
                    # Jangan trigger circuit breaker jika skip karena data tiket tidak valid (induk salah / anak tidak ada)
                    is_data_skip = str(res).startswith("skip:")
                    if not is_data_skip:
                        fail_streak += 1
                        if jenis == "gamas" and fail_streak >= 3:
                            self.log("    [CIRCUIT-BREAKER] gamas gagal 3x beruntun "
                                     "-> setop fase gamas siklus ini, lanjut jenis berikut")
                            break
                    else:
                        fail_streak = 0
            except Exception as e:
                self.log(f"    {code} EXEC error/timeout SYGAP ({e}) -> tutup tab & lanjut tiket berikut")
            finally:
                try:
                    if ticket_page is not None and not ticket_page.is_closed():
                        ticket_page.close()
                except Exception:
                    pass
                try:
                    page.bring_to_front()
                except Exception:
                    pass
        return done

    # ---------------- 1 siklus & loop ----------------
    def run_once(self, demo_rows=None, max_to_per_jenis=None):
        if self.dry_run:
            return self._run_dry(demo_rows)
        self.running = True
        self.stats["cycles"] += 1
        self.log("=" * 46)
        self.log(f"SIKLUS #{self.stats['cycles']} 1-PINTU :{self.cdp_port} "
                 f"(MINE:{'+'.join(EXEC_STATUSES)}+ME dulu -> TO:{TO_STATUS} -> EXEC:{EXEC_STATUS}+ME)")
        self.log("=" * 46)
        try:
            # TAHAP 0 — kerjakan dulu tiket milik saya (OPEN + Assigned to
            # Me), semua jenis. Sesudah itu filter SELALU diganti lagi ke
            # All Request Coordinator + ASSIGNED untuk TO (perintah user):
            # tidak ada SKIP TO; tumpukan yang gagal/skip tidak menahan
            # siklus (dicoba lagi loop berikut, bukan di TAHAP 2 ini).
            self.log(">>> TAHAP 0: kerjakan dulu semua tiket milik saya <<<")
            backlog_done = 0
            backlog_found = 0
            backlog_codes = set()
            for jenis in ("dispatch", "gamas", "service_id"):
                if not self.running:
                    break
                mine = self._scan_mine(jenis)
                backlog_found += len(mine)
                backlog_codes.update(t["code"] for t in mine)
                if mine:
                    self.log(f">>> Eksekusi {len(mine)} tiket {jenis} milik saya <<<")
                    backlog_done += self._execute_jenis(jenis, mine) or 0
            if backlog_found > 0:
                self.log(f">>> Tumpukan milik saya ({backlog_found}, dikerjakan {backlog_done}) "
                         f"selesai, lanjut TO (ganti filter ke All + {TO_STATUS}) <<<")
            # TAHAP 1 — TO SEMUA jenis (notes + ASSIGNED + All Request Coordinator)
            self.log(f">>> TAHAP 1: TO semua tiket dulu (notes + {TO_STATUS} + All) <<<")
            todos = {}
            for jenis in ("dispatch", "gamas", "service_id"):
                if not self.running:
                    break
                todos[jenis] = self._phase_to(jenis, max_items=max_to_per_jenis)
            # TAHAP 2 — BARU kerjakan semuanya (notes + OPEN + Assigned to Me)
            self.log(">>> TAHAP 2: kerjakan semua tiket milik saya <<<")
            for jenis, items in todos.items():
                if not self.running:
                    break
                # Kode yang sudah dicoba di TAHAP 0 jangan diulang di siklus ini.
                known = {t["code"] for t in items} | backlog_codes
                extra = self._scan_mine(jenis, known)
                self._execute_jenis(jenis, items + extra)
            if not any(v for v in todos.values()):
                self.log("Tidak ada tiket milik saya siklus ini.")
            self._keepalive_insera()
            self.log(f"STAT: {self.stats}")
        except Exception as e:
            self.log(f"SIKLUS error: {e}")
        return self.stats

    def _run_dry(self, demo_rows=None):
        demo_rows = demo_rows or {}
        self.running = True
        self.log("[DRY-RUN] tanpa browser (filter ASSIGNED milik saya)", channel="dispatch")
        queue = []
        for jenis in ("dispatch", "gamas", "sid"):
            rows = demo_rows.get(jenis, [])
            mine = [r for r in rows if is_assigned_to_me(r)]
            skipped = len(rows) - len(mine)
            self.log(f"[{jenis}] {len(mine)}/{len(rows)} milik saya ({skipped} skip)")
            for r in mine:
                queue.append({"code": r.get("request_code"), "jenis": jenis})
        self.log(f"[SCAN-DRY] queue={len(queue)} (tanpa TO, langsung eksekusi)")
        for it in queue:
            self.log(f"  [EXE-DRY] {it['code']} jenis={it['jenis']}")
        self.running = False
        return {"dry_queue": len(queue)}

    def _test_open_read(self, sygap, page, r, jenis, limit_note=True):
        """Buka 1 form HANYA untuk baca (testing). Returns 1 jika terbaca, 0 jika gagal."""
        from app.parser import (extract_owner_group, extract_inc_number,
                                extract_service_id, extract_service_type)
        code = r.get("request_code", "?")
        try:
            ticket_page = sygap.click_ticket(page, r, log_callback=self.log)
        except Exception as e:
            self.log(f"    [TEST] {code} gagal dibuka: {e}")
            return 0
        if ticket_page is None:
            self.log(f"    [TEST] {code} gagal dibuka (None)")
            return 0
        try:
            try:
                ticket_page.bring_to_front()
                ticket_page.wait_for_timeout(3000)
            except Exception:
                pass
            try:
                st = sygap.read_ticket_status(ticket_page) or "?"
            except Exception:
                st = "?"
            try:
                note = sygap.read_ticket_note(ticket_page) or ""
            except Exception:
                note = ""
            note_short = " ".join(note.split())[:120]
            self.log(f"    [TEST] {code} form status={st} note={note_short!r}")
            if jenis == "dispatch":
                og = extract_owner_group(note)
                inc = extract_inc_number(note)
                self.log(f"    [TEST] WOULD TO + /dispatchticket {inc or '?'} {og or '?'} (TIDAK dikirim)")
            elif jenis == "service_id":
                sid = extract_service_id(note)
                stype = extract_service_type(note)
                self.log(f"    [TEST] WOULD TO + /changeserviceid ? {sid or '?'}"
                         + (f" + OSS SERVICE_TYPE={stype}" if stype else "")
                         + " (TIDAK dikirim)")
            else:
                self.log("    [TEST] WOULD TO + cek parent/child + submit INSERA (TIDAK dikirim)")
            return 1
        finally:
            try:
                if not ticket_page.is_closed():
                    ticket_page.close()
            except Exception:
                pass
            try:
                page.bring_to_front()
                page.wait_for_timeout(800)
            except Exception:
                pass

    def run_test_live(self, limit_per_jenis=3, jenis_list=None):
        """MODE TESTING live read-only: buka browser + baca, TANPA aksi tulis.

        Dijamin TIDAK memanggil: take_ownership, change_coordinator_to_me,
        BiscuitService.execute, complete_ticket, OSS API, INSERA submit,
        log_history. Hanya: filter dashboard, baca baris tabel, buka form,
        baca status/note/koordinator, parse OG/INC/ServiceID, lalu tutup form.

        jenis_list: subset dari ("dispatch","gamas","service_id"). Default semua.
        limit_per_jenis: batasi tiket yang dibuka per jenis (default 3).
        """
        from app.parser import (extract_owner_group, extract_inc_number,
                                extract_service_id, extract_service_type)

        jenis_list = jenis_list or ("dispatch", "gamas", "service_id")
        self.running = True
        self.log("=" * 56)
        self.log("[TEST-LIVE] MODE TESTING — READ-ONLY, DIJAMIN TANPA TO / complete /")
        self.log("[TEST-LIVE] dispatch / changeserviceid / gamas-submit / OSS API / log_history")
        self.log("=" * 56)
        try:
            bm, sygap = self._ensure_browser()
            page = sygap.navigate_to_dashboard()
            # Bawa window dashboard ke depan agar gerakan bot terlihat user
            try:
                bm.activate_page(page)
            except Exception:
                pass
            try:
                page.bring_to_front()
                page.wait_for_timeout(1500)
            except Exception:
                pass
            total = 0
            # TAHAP 1 — TO semua jenis dulu (ASSIGNED saja, tanpa Assigned to Me)
            self.log(">>> TAHAP 1 (TEST): TO semua jenis dulu <<<")
            for jenis in jenis_list:
                if not self.running:
                    break
                self.log(f"[TEST] --- {jenis.upper()} LANGKAH 1 (TO): "
                         f"notes + {TO_STATUS} + All (limit {limit_per_jenis}) ---")
                rows = self._collect_filtered_rows(sygap, page, jenis,
                                                   TO_STATUS, "ALL")
                if not rows:
                    self.log(f"[TEST] {jenis}: tidak ada baris (TO)")
                    continue
                self.log(f"[TEST] {jenis}: {len(rows)} baris (TO)")
                dibuka = 0
                for r in rows:
                    if dibuka >= limit_per_jenis or not self.running:
                        break
                    code = r.get("request_code", "?")
                    allowed, reason = check_assigned_for_to(r)
                    self.log(f"  [TEST-TO] {code} status={r.get('status')} "
                             f"solver={r.get('solver') or '-'} -> "
                             f"{'SIAP-TO' if allowed else 'SKIP'} ({reason})")
                    if not allowed:
                        continue
                    total += self._test_open_read(
                        sygap, page, r, jenis, limit_note=True) or 0
                    dibuka += 1

            # TAHAP 2 — BARU cek eksekusi semua jenis (OPEN + Assigned to Me)
            self.log(">>> TAHAP 2 (TEST): cek eksekusi semua jenis <<<")
            for jenis in jenis_list:
                if not self.running:
                    break
                self.log(f"[TEST] --- {jenis.upper()} LANGKAH 2 (EXECUTE): "
                         f"notes + {EXEC_STATUS} + Assigned to Me (limit {limit_per_jenis}) ---")
                rows = self._collect_filtered_rows(sygap, page, jenis,
                                                   EXEC_STATUS, "ME")
                if not rows:
                    self.log(f"[TEST] {jenis}: tidak ada baris (OPEN + Assigned to Me)")
                    continue
                self.log(f"[TEST] {jenis}: {len(rows)} baris (EXECUTE)")
                dibuka = 0
                for r in rows:
                    if dibuka >= limit_per_jenis or not self.running:
                        break
                    code = r.get("request_code", "?")
                    mine = is_mine(r)
                    self.log(f"  [TEST-EXE] {code} status={r.get('status')} "
                             f"solver={r.get('solver') or '-'} -> "
                             f"{'MILIK-SAYA' if mine else 'SKIP'}")
                    if not mine:
                        continue
                    total += self._test_open_read(
                        sygap, page, r, jenis, limit_note=False) or 0
                    dibuka += 1
            self.log(f"[TEST] SELESAI. {total} tiket dibaca, 0 aksi tulis. Aman.")
        except Exception as e:
            self.log(f"[TEST] error: {e}")
        finally:
            self.running = False
        return {"tested": total}

    def _find_row_by_code(self, sygap, page, code, max_pages=10):
        """Cari baris 1 kode lintas halaman DataTables (page 1..N).

        Returns row_info atau None. Read-only (klik Next saja).
        """
        code = (code or "").strip().upper()
        for p in range(max_pages):
            rows = self._read_table_rows(sygap, page)
            for r in rows:
                if (r.get("request_code") or "").strip().upper() == code:
                    if p > 0:
                        self.log(f"  [cari] {code} ketemu di halaman {p + 1}")
                    return r
            # Pindah halaman berikut bila tombol Next aktif
            try:
                nxt = page.locator(
                    "#requestFulfillmentTable_next.paginate_button:not(.disabled)")
                if nxt.count() == 0:
                    break
                nxt.first.click()
                page.wait_for_timeout(1500)
            except Exception:
                break
        return None

    def to_single_ticket(self, code, jenis="dispatch"):
        """TO 1 tiket spesifik (live, tanpa eksekusi/complete).

        Cari lintas varian notes + lintas halaman dalam pasangan TO resmi
        (ASSIGNED + All). Hanya TO bila koordinator stabil-kosong; wajib
        TERBUKTI IN_PROGRESS. Returns hasil string.
        """
        import time as _t
        code = (code or "").strip().upper()
        bm, sygap = self._ensure_browser()
        page = sygap.navigate_to_dashboard()
        try:
            bm.activate_page(page)
        except Exception:
            pass
        self.running = True
        row = self._find_code_in_variants(sygap, page, jenis, code,
                                          TO_STATUS, "ALL")
        if row is None:
            self.log(f"[TO-ONE] {code} tidak ketemu (ASSIGNED + All) -> batal")
            return "not-found"
        allowed, reason = check_assigned_for_to(row)
        if not allowed:
            self.log(f"[TO-ONE] {code} SKIP ({reason})")
            return f"skip:{reason}"
        ticket_page = sygap.click_ticket(page, row, log_callback=self.log)
        if ticket_page is None:
            return "open-failed"
        _t0 = _t.time()
        try:
            st = sygap.read_ticket_status(ticket_page) or ""
            if "COMPLETED" in st.upper():
                return "skip:COMPLETED di form"
            res = self._to_one_ticket(sygap, page, ticket_page, code,
                                      form_status=st)
            self.log(f"[TO-ONE] {code} -> {res} "
                     f"({(_t.time() - _t0):.0f}s)")
            return res
        finally:
            try:
                if not ticket_page.is_closed():
                    ticket_page.close()
            except Exception:
                pass

    def check_one_ticket(self, code, jenis="dispatch"):
        """Cek 1 tiket spesifik, READ-ONLY: status tabel + koordinator form + note.

        Returns dict hasil. Tidak pernah TO/complete/dispatch.
        """
        bm, sygap = self._ensure_browser()
        page = sygap.navigate_to_dashboard()
        try:
            bm.activate_page(page)
        except Exception:
            pass
        self.log(f"[CHECK] {code} ({jenis}): coba beberapa filter...")
        row = None
        # HANYA 2 pasangan resmi: TO = ASSIGNED+All, EXECUTE = OPEN+ME.
        for status, asg in ((TO_STATUS, "ALL"), (EXEC_STATUS, "ME")):
            row = self._find_code_in_variants(sygap, page, jenis, code,
                                              status, asg)
            self.log(f"[CHECK] filter {status}+{asg}: -> "
                     f"{'KETEMU' if row else 'tidak ada'}")
            if row is not None:
                break
        if row is None:
            self.log(f"[CHECK] {code} TIDAK ketemu di semua filter. "
                     f"Mungkin sudah COMPLETED/CLOSED.")
            return {"code": code, "found": False}
        allowed, reason = check_assigned_for_to(row)
        self.log(f"[CHECK] tabel: status={row.get('status')} solver={row.get('solver') or '-'} "
                 f"-> {'SIAP-TO' if allowed else 'SKIP'} ({reason})")
        ticket_page = sygap.click_ticket(page, row, log_callback=self.log)
        if ticket_page is None:
            self.log("[CHECK] form gagal dibuka")
            return {"code": code, "found": True, "opened": False}
        try:
            try:
                ticket_page.bring_to_front()
                ticket_page.wait_for_timeout(2500)
            except Exception:
                pass
            try:
                st = sygap.read_ticket_status(ticket_page) or "?"
            except Exception:
                st = "?"
            try:
                (uid, label), _st = self._read_coordinator_stable(
                    sygap, ticket_page, timeout=8)
            except Exception:
                uid, label, _st = "?", "?", False
            # Diagnostik mentah field koordinator (buru false-"mine")
            try:
                diag = ticket_page.evaluate("""() => {
                    const el = document.getElementById('id_coordinator');
                    if (!el) return {exists: false};
                    const sel = el.selectedOptions.length
                        ? el.selectedOptions[0] : null;
                    return {
                        exists: true, tag: el.tagName,
                        value: el.value,
                        selectedText: sel ? (sel.text || '') : '',
                        options: el.options ? el.options.length : -1,
                        select2text: (function(){
                            const s = document.querySelector(
                                '#select2-id_coordinator-container');
                            return s ? s.innerText : '';
                        })()
                    };
                }""")
                self.log(f"[CHECK] koordinator mentah: {diag}")
                self.log(f"[CHECK] klasifikasi saya: "
                         f"{self._classify_coordinator(uid, label)}")
            except Exception as e:
                self.log(f"[CHECK] diagnostik gagal: {e}")
            try:
                note = sygap.read_ticket_note(ticket_page) or ""
            except Exception:
                note = ""
            note_short = " ".join(note.split())[:200]
            self.log(f"[CHECK] form: status={st} koordinator uid={uid!r} label={label!r}")
            self.log(f"[CHECK] note: {note_short!r}")
            if not uid and not label:
                verdict = "KOSONG — bisa di-TO"
            else:
                verdict = f"TERISI ({label or uid}) — jangan rebut"
            self.log(f"[CHECK] KESIMPULAN: {verdict}")
            return {"code": code, "found": True, "opened": True,
                    "table_status": row.get("status"), "table_solver": row.get("solver"),
                    "form_status": st, "coord_uid": uid, "coord_label": label,
                    "verdict": verdict}
        finally:
            try:
                if not ticket_page.is_closed():
                    ticket_page.close()
            except Exception:
                pass
            try:
                page.bring_to_front()
            except Exception:
                pass

    def probe_table(self, jenis="dispatch"):
        """READ-ONLY: cetak header kolom + isi 3 baris pertama tabel.

        Untuk memastikan indeks kolom solver/koordinator yang benar
        (vs kolom pengirim/pelapor).
        """
        bm, sygap = self._ensure_browser()
        page = sygap.navigate_to_dashboard()
        try:
            bm.activate_page(page)
        except Exception:
            pass
        self._apply_notes_filter(page, JENIS_NOTES.get(jenis, "dispatch"), TO_STATUS, "ALL")
        try:
            page.wait_for_selector("#requestFulfillmentTable thead th", timeout=10000)
            page.wait_for_timeout(800)
        except Exception:
            pass
        headers = page.evaluate("""() => {
            return Array.from(document.querySelectorAll(
                "#requestFulfillmentTable thead th")).map(e => e.innerText.trim());
        }""")
        self.log(f"[PROBE] header ({len(headers)} kolom):")
        for i, h in enumerate(headers):
            self.log(f"  col {i}: {h!r}")
        rows_txt = page.evaluate("""() => {
            return Array.from(document.querySelectorAll(
                "#requestFulfillmentTable tbody tr")).slice(0, 3).map(tr =>
                Array.from(tr.querySelectorAll("td")).map(td =>
                    td.innerText.trim().slice(0, 60)));
        }""")
        for n, cells in enumerate(rows_txt):
            self.log(f"[PROBE] baris {n + 1}:")
            for i, c in enumerate(cells):
                self.log(f"  td {i}: {c!r}")
        # Siapa user login SYGAP di Chrome ini? (menentukan isi Assigned to Me)
        try:
            who = page.evaluate("""() => {
                const out = {};
                const cands = document.querySelectorAll(
                    ".username, .user-name, #userMenu, #user-info, " +
                    ".navbar .dropdown-toggle, [class*='user']");
                out.candidates = Array.from(cands).slice(0, 8).map(
                    e => (e.innerText || '').trim().slice(0, 60));
                const html = document.documentElement.innerHTML;
                const m = html.match(/CRS\\d{5,}/);
                out.crs_in_page = m ? m[0] : '';
                out.title = document.title;
                out.url = location.href;
                return out;
            }""")
            self.log(f"[PROBE] login candidates: {who}")
        except Exception as e:
            self.log(f"[PROBE] login check gagal: {e}")
        return {"headers": headers, "rows": rows_txt}

    def execute_one(self, code, jenis="dispatch", force=False):
        """Eksekusi 1 tiket spesifik (live).

        force=False: hanya jika solver = saya (anti rebut).
        force=True : lewati cek solver — HANYA atas perintah eksplisit user,
                     dicatat di log. Alur eksekusi (termasuk aturan C4/SOP)
                     tetap berlaku penuh.
        """
        code = (code or "").strip().upper()
        bm, sygap = self._ensure_browser()
        page = sygap.navigate_to_dashboard()
        try:
            bm.activate_page(page)
        except Exception:
            pass
        row = None
        for status, asg in ((EXEC_STATUS, "ME"),):
            self.log(f"[EXEC-ONE] {code}: filter notes + {status} + "
                     f"{'Assigned to Me'}...")
            row = self._find_code_in_variants(
                sygap, page, jenis, code, status, asg)
            if row is not None:
                break
        if row is None:
            self.log(f"[EXEC-ONE] {code} TIDAK ketemu (bukan milik saya / sudah selesai).")
            return "not-found"
        if not is_mine(row) and not force:
            self.log(f"[EXEC-ONE] {code} solver bukan saya "
                     f"({row.get('solver')}) — BATAL demi SOP anti rebut.")
            return "not-mine"
        if not is_mine(row) and force:
            self.log(f"[EXEC-ONE] {code} solver={row.get('solver')} — "
                     f"GUARD DILEWATI ATAS PERINTAH EKSPLISIT USER. Lanjut.")
        ticket_page = sygap.click_ticket(page, row, log_callback=self.log)
        if ticket_page is None:
            return "open-failed"
        try:
            try:
                ticket_page.bring_to_front()
                ticket_page.wait_for_timeout(2000)
            except Exception:
                pass
            try:
                note = sygap.read_ticket_note_with_retry(
                    ticket_page, retries=2, log=self.log) or ""
            except Exception:
                note = sygap.read_ticket_note(ticket_page) or ""
            if jenis == "dispatch":
                res = self._execute_dispatch(sygap, page, ticket_page, code, note)
            elif jenis == "service_id":
                res = self._execute_service_id(sygap, page, ticket_page, code, note)
            else:
                res = self._execute_gamas(sygap, page, ticket_page, code, note)
            self.log(f"[EXEC-ONE] {code} -> {res}")
            return res
        finally:
            try:
                if not ticket_page.is_closed():
                    ticket_page.close()
            except Exception:
                pass

    def start(self, max_to_per_jenis=None):
        """Mulai loop scheduler di thread background (untuk tombol GUI)."""
        import threading
        if self.running:
            try:
                self.log("Scheduler sudah berjalan.")
            except Exception:
                pass
            return
        # MyAssistance: tanpa idle time antar-siklus (default 0).
        # Hanya gunakan loop_interval dari settings jika diatur secara eksplisit > 0 oleh pemanggil.
        if self.loop_interval > 0:
            try:
                import json
                p = os.path.join(_BASE, "config", "user_settings.json")
                with open(p, encoding="utf-8") as f:
                    self.loop_interval = int(json.load(f).get("loop_interval", self.loop_interval))
            except Exception:
                pass
        else:
            self.loop_interval = 0
        self.dry_run = False
        self._max_to = max_to_per_jenis
        self._warmed_up = False  # START baru -> warmup lagi
        self.running = True
        try:
            self.log(f"[MyAssistance] engine {ENGINE_VERSION} dimulai.")
        except Exception:
            pass
        try:
            if self.gui is not None:
                self.gui.update_status("RUNNING")
        except Exception:
            pass
        threading.Thread(target=self._start_loop_guard, daemon=True).start()

    def _start_loop_guard(self):
        try:
            self.loop(max_to_per_jenis=getattr(self, "_max_to", None))
        except Exception as e:
            try:
                self.log(f"LOOP error: {e}")
            except Exception:
                pass
        finally:
            self.running = False
            try:
                if self.gui is not None:
                    self.gui.update_status("STOPPED")
            except Exception:
                pass
            try:
                if self.on_complete:
                    self.on_complete()
            except Exception:
                pass

    def list_tabs(self):
        """READ-ONLY: daftar semua tab + URL di browser ini."""
        from app.browser import BrowserManager
        bm = BrowserManager(cdp_port=self.cdp_port)
        bm.connect()
        try:
            pages = bm.get_all_pages()
            self.log(f"[TABS] {len(pages)} tab di :{self.cdp_port}:")
            for i, p in enumerate(pages):
                try:
                    self.log(f"  tab {i + 1}: {p.url[:110]}")
                except Exception:
                    self.log(f"  tab {i + 1}: (tak terbaca)")
        finally:
            try:
                bm.disconnect()
            except Exception:
                pass

    def run_exec_mine(self, jenis_list=None, max_items=None):
        """Selesaikan semua tiket milik saya TANPA TO.

        Per jenis: scan OPEN+ME -> eksekusi. TO dilewati total.
        Returns stats dict.
        """
        jenis_list = jenis_list or ("dispatch", "gamas", "service_id")
        self.running = True
        self.log("=" * 46)
        self.log("EKSEKUSI MILIK SAYA (TANPA TO)")
        self.log("=" * 46)
        done = 0
        try:
            for jenis in jenis_list:
                if not self.running:
                    break
                items = self._scan_mine(jenis)
                if max_items is not None:
                    items = items[:max_items]
                if not items:
                    continue
                self.log(f">>> Eksekusi {len(items)} tiket {jenis} milik saya <<<")
                self._execute_jenis(jenis, items)
                done += len(items)
        except Exception as e:
            self.log(f"EXEC-MINE error: {e}")
        finally:
            self.running = False
        self.log(f"STAT: {self.stats}")
        return self.stats

    def loop(self, max_cycles=None, max_to_per_jenis=None):
        if self.dry_run:
            raise RuntimeError("loop() hanya untuk live. Dry-run pakai run_once().")
        self.running = True
        n = 0
        while self.running:
            if max_cycles is not None and n >= max_cycles:
                self.log(f"[LOOP] batas {max_cycles} siklus tercapai, berhenti.")
                break
            self.run_once(max_to_per_jenis=max_to_per_jenis)
            n += 1
            if max_cycles is not None and n >= max_cycles:
                self.log(f"[LOOP] batas {max_cycles} siklus tercapai, berhenti.")
                break
            if self.loop_interval and self.loop_interval > 0:
                if self.loop_interval >= 60:
                    self.log(f"[WAITING] {self.loop_interval // 60} mnt...")
                else:
                    self.log(f"[WAITING] {self.loop_interval} dtk...")
                for sec in range(self.loop_interval):
                    if not self.running:
                        break
                    if sec > 0 and sec % 60 == 0:
                        self._keepalive_insera()
                    time.sleep(1)
            else:
                # Tanpa idle time: jeda napas 1 detik agar CPU aman & browser stabil
                time.sleep(1)

    def stop(self):
        self.running = False
        try:
            if self.gui is not None:
                self.gui.update_status("STOPPING")
        except Exception:
            pass
        try:
            if self._browser is not None:
                self._browser.disconnect()
        except Exception:
            pass
