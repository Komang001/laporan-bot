import re
import sys
import time

from app.parser import (
    extract_owner_group,
    extract_inc_number,
    is_bulk_og_change,
    extract_bulk_og_target,
    extract_bulk_inc_list,
    extract_service_id,
    extract_service_type,
)
from config.settings import USER_ID, USER_NAME, SKIP_COORDINATOR_USER_IDS
from app.services.history_service import log_history
import os
import json

LOOP_INTERVAL = 180

# File untuk ingat tiket yang pernah di-SKIP (permanen, tidak pernah dibuka lagi) — anti duplikat bulanan
_PERSISTENT_SKIPPED_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "skipped_tickets.json")


class SygapService:

    def __init__(self, browser_manager=None, stop_check=None):
        self.processed_ids = set()
        self.related_ids = set()      # tiket yg relasi GAMAS-nya sudah di-submit (cegah duplikat)
        self.gamas_fail_count = {}    # code -> jumlah gagal complete (batas retry)
        self.skipped_ids = {}         # code -> timestamp terakhir di-SKIP (cooldown LOOP_INTERVAL)
        self.persistent_skipped = set()  # tiket yang pernah di-SKIP permanen (tidak pernah dibuka lagi)
        self._load_persistent_skipped()
        self.browser_manager = browser_manager
        self.stop_check = stop_check

    def _load_persistent_skipped(self):
        try:
            if os.path.exists(_PERSISTENT_SKIPPED_PATH):
                with open(_PERSISTENT_SKIPPED_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.persistent_skipped = set(data.keys())
                    elif isinstance(data, list):
                        self.persistent_skipped = set(data)
        except Exception:
            self.persistent_skipped = set()

    def _save_persistent_skipped(self, code):
        try:
            self.persistent_skipped.add(code)
            os.makedirs(os.path.dirname(_PERSISTENT_SKIPPED_PATH), exist_ok=True)
            # Simpan sebagai dict code -> timestamp
            data = {}
            if os.path.exists(_PERSISTENT_SKIPPED_PATH):
                try:
                    with open(_PERSISTENT_SKIPPED_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            data = {k: "" for k in data}
                except Exception:
                    data = {}
            data[code] = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(_PERSISTENT_SKIPPED_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _is_persistent_skipped(self, code):
        return code in self.persistent_skipped

    def _stopped(self):
        return bool(self.stop_check and self.stop_check())

    def get_dashboard_page(self):
        page = self.browser_manager.get_dashboard_page()
        if page is None:
            raise Exception("Dashboard SYGAP tidak ditemukan. Buka /req_fulfillment dulu.")
        return page

    def navigate_to_dashboard(self):
        page = self.get_dashboard_page()
        self.browser_manager.activate_page(page)
        current = page.url.lower()
        if "/req_fulfillment" in current and "/form/" not in current:
            return page
        page.goto("https://sygap.telkom.co.id/req_fulfillment")
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        page.wait_for_timeout(3000)
        return page

    def get_incident_dashboard_page(self):
        page = self.browser_manager.get_incident_dashboard_page()
        if page is None:
            raise Exception("Dashboard INCIDENT tidak ditemukan. Buka /incident dulu.")
        return page

    def _wait_for_sygap_login(self, page, log, timeout=180):
        """Tunggu user login SYGAP manual jika masih di halaman login."""
        try:
            if "login" not in page.url.lower():
                return True
        except Exception:
            return True
        log("SYGAP belum login! Silakan login manual di tab SYGAP (maks 180 detik)...")
        log(f"Buka tab SYGAP lalu login ke {page.url[:60]}")
        waited = 0
        while waited < timeout:
            if self._stopped():
                log("STOP requested - aborting")
                return False
            page.wait_for_timeout(5000)
            waited += 5
            try:
                url = page.url.lower()
                if "login" not in url and "sygap.telkom.co.id" in url:
                    log(f"Login berhasil setelah {waited}s - lanjut.")
                    page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue
            if waited % 30 == 0:
                log(f"  Menunggu login... ({waited}s/{timeout}s)")
        log("Waktu tunggu login habis. Silakan login manual lalu START lagi.")
        return False

    def _wait_for_biscuit_login(self, log, timeout=180):
        """Tunggu user login BISCUIT manual jika masih di halaman login."""
        try:
            page = self.browser_manager.get_biscuit_page()
            if not page or not self.browser_manager.is_page_alive(page):
                return True  # tidak ada tab biscuit -> biar flow yang tangani
            if "login" not in page.url.lower():
                return True
        except Exception:
            return True
        log("BISCUIT belum login! Silakan login manual di tab BISCUIT (maks 180 detik)...")
        waited = 0
        while waited < timeout:
            if self._stopped():
                return False
            page.wait_for_timeout(5000)
            waited += 5
            try:
                url = page.url.lower()
                if "login" not in url and "biscuit-dashboard" in url:
                    log(f"BISCUIT login berhasil setelah {waited}s - lanjut.")
                    page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue
            if waited % 30 == 0:
                log(f"  Menunggu BISCUIT login... ({waited}s/{timeout}s)")
        log("Waktu tunggu BISCUIT login habis. Silakan login manual lalu START lagi.")
        return False

    def navigate_to_incident_dashboard(self):
        from config.settings import INCIDENT_DASHBOARD_URL
        # 1) coba pakai tab incident yang sudah ada (bisa masih di /login)
        try:
            page = self.browser_manager.get_incident_dashboard_page()
            if page and self.browser_manager.is_page_alive(page):
                self.browser_manager.activate_page(page)
                current = page.url.lower()
                if "/incident" in current and "/form/" not in current:
                    return page
                # ada tab SYGAP tapi belum di /incident (misal di /login) -> arahkan tab yang sama, jangan buka baru
                page.goto(INCIDENT_DASHBOARD_URL)
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                page.wait_for_timeout(3000)
                return page
        except Exception:
            pass
        # 2) cari SYGAP tab mana pun dan pakai ulang (hindari open_url baru)
        for p in self.browser_manager.get_pages():
            try:
                if "sygap.telkom.co.id" in p.url.lower():
                    self.browser_manager.activate_page(p)
                    p.goto(INCIDENT_DASHBOARD_URL)
                    p.wait_for_load_state("domcontentloaded", timeout=15000)
                    p.wait_for_timeout(3000)
                    return p
            except Exception:
                continue
        # 3) fallback: baru buka tab baru jika benar-benar tidak ada SYGAP tab
        page = self.browser_manager.open_url(INCIDENT_DASHBOARD_URL)
        if page:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            page.wait_for_timeout(3000)
            return page
        raise Exception("Gagal membuka dashboard INCIDENT")

    def _get_dispatch_table_id(self, page):
        """Deteksi table ID aktif: incidentTable vs requestFulfillmentTable."""
        for tid in ["incidentTable", "requestFulfillmentTable", "dataTable"]:
            try:
                if page.locator(f"#{tid}").count() > 0:
                    return tid
            except Exception:
                continue
        return "requestFulfillmentTable"

    def get_ticket_rows_generic(self, page):
        """Ambil rows dari table manapun (incident/request)."""
        table_id = self._get_dispatch_table_id(page)
        rows = page.locator(f"#{table_id} tbody tr")
        count = rows.count()
        result = []
        for i in range(count):
            row = rows.nth(i)
            try:
                link = row.locator("td a").first
                if link.count() == 0:
                    continue
                request_code = link.inner_text().strip()
                href = link.get_attribute("href") or ""
                # status di kolom 6 (indeks 6) untuk request, incident bisa beda — coba ambil kolom terakhir yang mengandung status
                status = ""
                try:
                    # coba kolom 6 dulu
                    status_cell = row.locator("td").nth(6)
                    raw_status = status_cell.inner_text().strip()
                    status = raw_status.split()[-1] if raw_status.split() else raw_status
                    if status.upper() not in ("OPEN","ASSIGNED","IN_PROGRESS","COMPLETED","COMPLETE","CLOSED","PENDING","RESOLVED"):
                        # fallback: cari di semua td yang mengandung status valid
                        for idx in range(row.locator("td").count()):
                            txt = row.locator("td").nth(idx).inner_text().strip().upper()
                            if txt in ("OPEN","ASSIGNED","IN_PROGRESS","COMPLETED","COMPLETE","CLOSED","PENDING","RESOLVED"):
                                status = txt
                                break
                except Exception:
                    status = ""
                result.append({
                    "row": row,
                    "link": link,
                    "request_code": request_code,
                    "href": href,
                    "status": status,
                })
            except Exception:
                continue
        return result

    def get_ticket_rows(self, page):
        rows = page.locator("#requestFulfillmentTable tbody tr")
        count = rows.count()
        result = []
        for i in range(count):
            row = rows.nth(i)
            try:
                link = row.locator("td a").first
                if link.count() == 0:
                    continue
                request_code = link.inner_text().strip()
                href = link.get_attribute("href") or ""
                status_cell = row.locator("td").nth(6)
                raw_status = status_cell.inner_text().strip()
                status = raw_status.split()[-1] if raw_status.split() else raw_status
                result.append({
                    "row": row,
                    "link": link,
                    "request_code": request_code,
                    "href": href,
                    "status": status,
                })
            except Exception:
                continue
        return result

    def click_ticket(self, page, row_info, skip_close=False):
        if not skip_close:
            self._close_extra_tabs(page)
        link = row_info["link"]
        old_count = len(page.context.pages)
        link.click()
        page.wait_for_timeout(3000)
        new_count = len(page.context.pages)
        if new_count > old_count:
            return page.context.pages[-1]
        for p in page.context.pages:
            if p != page and "/form/" in p.url:
                return p
        return None

    def _close_extra_tabs(self, dashboard_page, log_callback=None):
        log = log_callback or (lambda msg: None)
        for p in dashboard_page.context.pages:
            if p == dashboard_page:
                continue
            try:
                if not p.is_closed():
                    url = p.url.lower()
                    if "biscuit-dashboard" in url:
                        log(f"  [close_tab] SKIP biscuit-dashboard: {url[:60]}")
                        continue
                    if "biscuit" in url and "tools" in url:
                        log(f"  [close_tab] SKIP biscuit-tools: {url[:60]}")
                        continue
                    if "oss-incident" in url or "insera" in url:
                        log(f"  [close_tab] SKIP INSERA: {url[:60]}")
                        continue
                    log(f"  [close_tab] CLOSING: {url[:60]}")
                    p.close()
            except Exception:
                pass

    def read_ticket_status(self, ticket_page):
        """Quick status check from form field - support REQUEST & INCIDENT"""
        selectors = [
            "select[name*='status'] option[selected]",
            "select[name*='status']",
            "#status",
            "#select_incident_status",
            "select[id*='incident_status']",
            "select[id*='select_incident']",
        ]
        for sel in selectors:
            try:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    val = loc.first.inner_text().strip().upper()
                    if not val:
                        val = loc.first.input_value().strip().upper()
                    if "COMPLETED" in val or "COMPLETE" in val:
                        return "COMPLETED"
                    if val:
                        return val
            except Exception:
                continue
        try:
            body = ticket_page.locator("body").inner_text(timeout=3000)
            if "Request Status:" in body and "COMPLETED" in body.upper():
                return "COMPLETED"
        except Exception:
            pass
        return None

    def read_ticket_note(self, ticket_page):
        try:
            ticket_page.wait_for_load_state("domcontentloaded", timeout=15000)
            ticket_page.wait_for_timeout(3000)
        except Exception:
            pass
        note = ""
        selectors = ["textarea#note", "#note", ".note-editor textarea"]
        for sel in selectors:
            try:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    note = loc.first.input_value().strip()
                    if note:
                        return note
            except Exception:
                continue
        try:
            editors = ticket_page.locator(".ck-editor__editable")
            for i in range(editors.count()):
                text = editors.nth(i).inner_text().strip()
                if text:
                    note = text
                    break
        except Exception:
            note = ""
        return note

    def read_ticket_id(self, ticket_page):
        selectors = [
            "input[name$='_ticket_id']",
            "input[name*='ticket_id']",
        ]
        for sel in selectors:
            try:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    return loc.first.input_value().strip()
            except Exception:
                continue
        return None

    def read_own_incident_code(self, ticket_page):
        """Baca incident_code milik halaman ini sendiri (SYGAP code, BUKAN ticket BISCUIT)."""
        try:
            for sel in ["#incident_code", "input[name='incident_code']", "input[id='incident_code']"]:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    val = loc.first.input_value().strip()
                    m = re.search(r'INC\d+', val, re.IGNORECASE)
                    if m:
                        return m.group(0).upper()
        except Exception:
            pass
        return None

    def read_ticket_inc(self, ticket_page, exclude=None):
        """Read INC number from ticket page (header, input, or text content).

        exclude: nilai yg TIDAK boleh dikembalikan (biasanya incident_code halaman
        sendiri, karena itu SYGAP code bukan nomer ticket BISCUIT).
        """

        selectors = [
            "input[name$='_ticket_no']",
            "input[name*='ticket_no']",
            "input[name$='_request_no']",
            "input[name*='request_no']",
            "input[name$='_no_ticket']",
            "input[name='ticket_id']",
            "input[name$='ticket_id']",
            "#ticket_no",
            "#request_no",
        ]
        for sel in selectors:
            try:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    val = loc.first.input_value().strip()
                    if val:
                        m = re.search(r'INC\d+', val, re.IGNORECASE)
                        if m and m.group(0).upper() != exclude:
                            return m.group(0).upper()
            except Exception:
                continue

        try:
            body_text = ticket_page.locator("body").inner_text(timeout=5000)
            # Ambil INC pertama yg BUKAN incident_code halaman sendiri
            for m in re.finditer(r'INC\d+', body_text, re.IGNORECASE):
                cand = m.group(0).upper()
                if cand != exclude:
                    return cand
        except Exception:
            pass

        return None

    def read_wo_from_field(self, ticket_page):
        """Read WO number from form field below note (e.g. 'BIMA - WO Number')"""

        selectors = [
            "input[name$='_wo_number']",
            "input[name*='wo_number']",
            "input[name$='_work_order']",
            "input[name*='work_order']",
        ]
        for sel in selectors:
            try:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    val = loc.first.input_value().strip()
                    if val:
                        m = re.search(r'WO\d+', val, re.IGNORECASE)
                        if m:
                            return m.group(0).upper()
            except Exception:
                continue

        try:
            wo_labels = ticket_page.locator("label:has-text('WO Number'), label:has-text('WO')")
            for idx in range(wo_labels.count()):
                label = wo_labels.nth(idx)
                container = label.locator("xpath=ancestor::div[contains(@class,'form') or contains(@class,'field') or contains(@class,'group')][1]")
                inp = container.locator("input[type='text'], input:not([type])")
                if inp.count() > 0:
                    val = inp.first.input_value().strip()
                    if val:
                        m = re.search(r'WO\d+', val, re.IGNORECASE)
                        if m:
                            return m.group(0).upper()
        except Exception:
            pass

        try:
            body_text = ticket_page.locator("body").inner_text(timeout=5000)
            m = re.search(r'INC\d+', body_text)
            if m:
                return m.group(0).upper()
        except Exception:
            pass

        return None

    def wait_for_ticket_inc(self, ticket_page, timeout=20):
        """Poll INC number dari halaman tiket dengan retry.

        SESUAI INSTRUKSI: kalau note tidak ada nomer tiket, langsung baca
        field 'Ticket ID' (input *_ticket_id, contoh 3556174_4237379_ticket_id).
        Field ini diisi ASINKRON setelah page load, jadi di-poll sampai terisi.

        TIDAK menggunakan fallback body-text karena body berisi incident_code
        SYGAP (bukan nomer ticket BISCUIT) -> bisa salah dispatch.
        """
        start = time.time()
        own_code = self.read_own_incident_code(ticket_page)
        while time.time() - start < timeout:
            inc = self.read_ticket_id_from_field(ticket_page, exclude=own_code)
            if inc and inc != own_code:
                return inc
            try:
                ticket_page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            ticket_page.wait_for_timeout(2000)
        return None

    def read_ticket_id_from_field(self, ticket_page, exclude=None):
        """Read Ticket ID/INC from form field below note (e.g. 'INSERA - Ticket ID')"""

        selectors = [
            "input[name$='_ticket_id']",
            "input[name*='ticket_id']",
            "input[name$='_ticket_no']",
            "input[name*='ticket_no']",
        ]
        for sel in selectors:
            try:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    val = loc.first.input_value().strip()
                    if val:
                        m = re.search(r'INC\d+', val, re.IGNORECASE)
                        if m and m.group(0).upper() != exclude:
                            return m.group(0).upper()
            except Exception:
                continue

        try:
            id_labels = ticket_page.locator("label:has-text('Ticket ID'), label:has-text('Ticket No'), label:has-text('Request No')")
            for idx in range(id_labels.count()):
                label = id_labels.nth(idx)
                container = label.locator("xpath=ancestor::div[contains(@class,'form') or contains(@class,'field') or contains(@class,'group')][1]")
                inp = container.locator("input[type='text'], input:not([type])")
                if inp.count() > 0:
                    val = inp.first.input_value().strip()
                    if val:
                        m = re.search(r'INC\d+', val, re.IGNORECASE)
                        if m and m.group(0).upper() != exclude:
                            return m.group(0).upper()
        except Exception:
            pass

        # TIDAK ada fallback body-text: body berisi incident_code SYGAP,
        # bukan nomer ticket BISCUIT. Field Ticket ID di atas adalah sumber tunggal.
        return None

    def read_ticket_created_date(self, ticket_page):
        """Baca Tanggal Masuk SYGAP (Created Date / Submit Date) dari form tiket. Return string YYYY-MM-DD HH:MM:SS atau ''."""
        # Coba cari input dengan value format tanggal
        date_pat = re.compile(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(:\d{2})?')
        selectors = [
            "input[value*='-']",
        ]
        # 1) Cari input yang valuenya match tanggal dan dekat label Created/Submit
        try:
            for lbl_text in ["Created Date", "Submit Date", "Created", "Tanggal Masuk"]:
                labs = ticket_page.locator(f"label:has-text('{lbl_text}')")
                for idx in range(labs.count()):
                    try:
                        lab = labs.nth(idx)
                        cont = lab.locator("xpath=ancestor::div[contains(@class,'form') or contains(@class,'group') or contains(@class,'row')][1]")
                        inp = cont.locator("input")
                        for j in range(inp.count()):
                            v = inp.nth(j).input_value().strip()
                            if date_pat.search(v):
                                return v
                            # juga cek value attr
                            av = inp.nth(j).get_attribute("value") or ""
                            if date_pat.search(av):
                                return av.strip()
                    except Exception:
                        continue
        except Exception:
            pass
        # 2) Fallback: scan semua input dengan value tanggal, ambil yang paling awal (biasanya Created)
        try:
            all_inputs = ticket_page.locator("input")
            candidates = []
            for i in range(all_inputs.count()):
                try:
                    v = all_inputs.nth(i).input_value().strip()
                except Exception:
                    try:
                        v = all_inputs.nth(i).get_attribute("value") or ""
                    except Exception:
                        v = ""
                if date_pat.search(v):
                    candidates.append(v.strip())
            if candidates:
                # Urutkan, ambil paling awal (terkecil)
                try:
                    candidates_sorted = sorted(candidates)
                    return candidates_sorted[0]
                except Exception:
                    return candidates[0]
        except Exception:
            pass
        # 3) Fallback: cari di body text
        try:
            body = ticket_page.locator("body").inner_text(timeout=3000)
            m = date_pat.search(body)
            if m:
                return m.group(0)
        except Exception:
            pass
        return ""

    def read_ticket_selesai_date(self, ticket_page):
        """Tanggal selesai = sekarang (waktu bot menyelesaikan). Coba baca Actual End Date jika sudah terisi, fallback ke now."""
        date_pat = re.compile(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(:\d{2})?')
        try:
            for lbl_text in ["Actual End Date", "End Date", "Resolution Date"]:
                labs = ticket_page.locator(f"label:has-text('{lbl_text}')")
                for idx in range(labs.count()):
                    try:
                        lab = labs.nth(idx)
                        cont = lab.locator("xpath=ancestor::div[contains(@class,'form') or contains(@class,'group') or contains(@class,'row')][1]")
                        inp = cont.locator("input")
                        for j in range(inp.count()):
                            v = inp.nth(j).input_value().strip()
                            if date_pat.search(v):
                                return v
                    except Exception:
                        continue
        except Exception:
            pass
        from datetime import datetime as _dt
        return _dt.now().strftime("%Y-%m-%d %H:%M:%S")

    def extract_parent_gamas_from_note(self, note):
        """Extract parent GAMAS INC from note.
        
        Supports all formats:
        - 'Induk gamas : INC...', 'Induk gamas ; INC...'
        - 'INDUK GAMAS INC...'
        - 'Tiket GAMAS berikut : INC...'
        - 'GAMAS INC...' (only if not ANAK GAMAS)
        - 'IG: INC...', 'IG : INC...'
        Returns INC number or None.
        """
        if not note:
            return None

        # Pattern 1: IG keyword (short form for Induk Gamas)
        match = re.search(r'\bIG\s*[:;]\s*(INC\d+)', note, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        # Pattern 2: INDUK GAMAS dengan ":"/" ;" eksplisit — prioritas utama (mis. "INDUK GAMAS : INC...")
        # Jika ada lebih dari 1, ambil yang TERAKHIR (biasanya yang paling eksplisit di akhir note, spt kasus tiket_relasi + INDUK GAMAS : INC...)
        matches = list(re.finditer(r'\bINDUK\s+GAMAS\s*[:;]\s*(INC\d+)', note, re.IGNORECASE))
        if matches:
            return matches[-1].group(1).upper()
        # Pattern 2 fallback: INDUK GAMAS tanpa ":" (mis. "INDUK GAMAS INC...")
        match = re.search(r'\bINDUK\s+GAMAS\s+(INC\d+)', note, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        # Pattern 2b: INDUKAN (kata populer: 'INDUKAN INC...', 'INDUKAN : INC...')
        match = re.search(r'\bINDUKAN\s*[:;]?\s*(INC\d+)', note, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        # Pattern 2c: "ke induk INC..." atau "induk INC..." (induk ditandai eksplisit,
        # biasanya anak-gamas disebutkan dulu lalu "ke induk <INC>") — hanya jika tidak ada INDUK GAMAS eksplisit di atas
        match = re.search(r'(?:\bke\s+)?\binduk\s*[:;]?\s*(INC\d+)', note, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        # Pattern 3: GAMAS ... : or ; INC — but NOT if preceded by ANAK/AG
        for match in re.finditer(r'GAMAS\s*\w*\s*[:;]\s*(INC\d+)', note, re.IGNORECASE):
            pos = match.start()
            prefix = note[max(0, pos-10):pos].lower()
            if re.search(r'\b(anak|ag)\s*$', prefix):
                continue
            return match.group(1).upper()
        # Pattern 4: GAMAS INC (direct, no separator) — but NOT ANAK GAMAS
        for match in re.finditer(r'GAMAS\s+(INC\d+)', note, re.IGNORECASE):
            pos = match.start()
            prefix = note[max(0, pos-10):pos].lower()
            if re.search(r'\b(anak|ag)\s*$', prefix):
                continue
            return match.group(1).upper()
        return None

    def extract_child_incs_excluding_parent(self, note):
        """Extract child INCs from note, excluding the parent GAMAS.
        
        Supports:
        - 'AG : INC...' or 'AG: INC...' (short form for Anak Gamas)
        - 'Anak gamas ; INC...' or 'Anak gamas : INC...'
        - Fallback: all INCs excluding parent
        """
        if not note:
            return []

        parent = self.extract_parent_gamas_from_note(note)

        # Try explicit AG / Anak gamas / Anakam pattern first
        ag_match = re.search(r'\b(?:AG|Anak\s+gamas|ANAKAN)\s*[:;]?\s*((?:INC\d+[\s,]*)+)', note, re.IGNORECASE)
        if ag_match:
            incs = re.findall(r'INC\d+', ag_match.group(1), re.IGNORECASE)
            return [m.upper() for m in incs]

        # Fallback: all INCs excluding parent
        all_incs = re.findall(r'INC\d+', note, re.IGNORECASE)
        all_incs = [m.upper() for m in all_incs]

        if parent and parent in all_incs:
            all_incs.remove(parent)

        return all_incs

    def read_child_incs_from_field(self, ticket_page):
        """Read child INC numbers from 'INSERA - Ticket ID' field.
        
        Two-step approach:
        1. First check note for comma-separated INC numbers (multiple children)
        2. Then scan 'INSERA - Ticket ID And User ID' > 'Ticket ID' field (single child)
        """

        try:
            sections = ticket_page.locator("div:has-text('INSERA - Ticket ID And User ID')")
            for idx in range(sections.count()):
                section = sections.nth(idx)
                ticket_id_labels = section.locator("label:has-text('Ticket ID')")
                for lbl_idx in range(ticket_id_labels.count()):
                    label = ticket_id_labels.nth(lbl_idx)
                    container = label.locator("xpath=ancestor::div[contains(@class,'form') or contains(@class,'field') or contains(@class,'group') or contains(@class,'row')][1]")
                    inp = container.locator("input[type='text'], input:not([type])")
                    if inp.count() > 0:
                        val = inp.first.input_value().strip()
                        if val:
                            matches = re.findall(r'INC\d+', val, re.IGNORECASE)
                            if matches:
                                return [m.upper() for m in matches]
        except Exception:
            pass

        try:
            all_labels = ticket_page.locator("label:has-text('Ticket ID')")
            for idx in range(all_labels.count()):
                label = all_labels.nth(idx)
                text = label.inner_text().strip()
                if text == "Ticket ID":
                    container = label.locator("xpath=ancestor::div[contains(@class,'form') or contains(@class,'field') or contains(@class,'group') or contains(@class,'row')][1]")
                    inp = container.locator("input[type='text'], input:not([type])")
                    if inp.count() > 0:
                        val = inp.first.input_value().strip()
                        if val:
                            matches = re.findall(r'INC\d+', val, re.IGNORECASE)
                            if matches:
                                return [m.upper() for m in matches]
        except Exception:
            pass

        return []

    def find_parent_from_ticket_id_field(self, ticket_page, note):
        """Fallback: cari parent GAMAS INC di field 'Ticket ID' ketika note
        tidak memiliki pola induk (INDUK GAMAS / IG / Tiket GAMAS berikut)
        tapi mengandung 'ANAK GAMAS'. Field berisi INC yang tidak ada di note."""
        if not note:
            return None
        if not re.search(r'\banak\s+gamas\b|\bAG\b|\bANAKAN\b', note, re.IGNORECASE):
            return None
        child_incs = self.extract_child_incs_excluding_parent(note)
        if not child_incs:
            return None
        field_incs = self.read_child_incs_from_field(ticket_page)
        for inc in field_incs:
            if inc not in child_incs:
                return inc
        return None

    def take_ownership(self, ticket_page):
        from config import settings as cfg
        USER_ID = str(getattr(cfg, "USER_ID", "55654"))
        USER_NAME = str(getattr(cfg, "USER_NAME", "I Nyoman Windu"))

        try:
            ticket_page.wait_for_load_state("domcontentloaded", timeout=15000)
            ticket_page.wait_for_timeout(2000)
        except Exception:
            pass

        try:
            ticket_page.wait_for_selector("#id_coordinator, #selectSolver, #selectIncidentOwner", timeout=8000)
            ticket_page.wait_for_selector("#btn_next_stage, #btn_submit_request, #btn_wip_note, #btn_wip_inc, #btn_update_inc, #btn_redispatch_inc", timeout=8000)
            ticket_page.wait_for_timeout(1500)
        except Exception:
            pass

        js_code = f"""
        (async function() {{
            function sleep(ms) {{ return new Promise(r => setTimeout(r, ms)); }}

            for (var w = 0; w < 10; w++) {{
                if (window.jQuery && jQuery.fn.select2) break;
                await sleep(500);
            }}
            if (!window.jQuery) return 'NO_JQUERY';

            // Support REQUEST (id_coordinator) & INCIDENT (selectSolver / selectIncidentOwner)
            var ic = document.getElementById('id_coordinator') || document.getElementById('selectSolver') || document.getElementById('selectIncidentOwner');
            if (!ic) return 'NO_IC';
            var $ic = jQuery(ic);
            if ($ic.find('option[value="{USER_ID}"]').length === 0) {{
                $ic.append(new Option('{USER_NAME}', '{USER_ID}', false, false));
            }}
            $ic.val('{USER_ID}').trigger('change');
            await sleep(1500);

            var icVal = $ic.val();
            if (icVal !== '{USER_ID}') {{
                return 'VERIFY_FAIL:ic=' + icVal;
            }}

            var nextBtn = document.getElementById('btn_next_stage');
            if (nextBtn && nextBtn.offsetParent !== null) {{
                nextBtn.click(); return 'NEXT_STAGE';
            }}
            var wipNoteBtn = document.getElementById('btn_wip_note');
            if (wipNoteBtn && wipNoteBtn.offsetParent !== null) {{
                wipNoteBtn.click(); return 'WIP_NOTE_CLICKED';
            }}
            var wipBtn = document.getElementById('btn_wip_inc');
            if (wipBtn && wipBtn.offsetParent !== null) {{
                wipBtn.click(); return 'WIP_INC';
            }}
            var redispatchBtn = document.getElementById('btn_redispatch_inc');
            if (redispatchBtn && redispatchBtn.offsetParent !== null) {{
                redispatchBtn.click(); return 'REDISPATCH';
            }}
            var updateBtn = document.getElementById('btn_update_inc');
            if (updateBtn && updateBtn.offsetParent !== null) {{
                updateBtn.click(); return 'UPDATE_INC';
            }}
            var saveBtn = document.getElementById('btn_submit_request');
            if (saveBtn && saveBtn.offsetParent !== null) {{
                saveBtn.click(); return 'SAVE';
            }}
            return 'NO_BUTTON';
        }})();
        """

        try:
            result = ticket_page.evaluate(js_code)
            ticket_page.wait_for_timeout(1500)
            # INCIDENT: klik btn_wip_note hanya buka modal, perlu isi WIP dulu baru klik Work Progress di footer
            if result == 'WIP_NOTE_CLICKED':
                try:
                    ticket_page.wait_for_selector("#form_wip_inc, .modal.show", timeout=5000)
                    ticket_page.wait_for_timeout(1000)
                    # Isi Work Progress Note = WIP (CKEditor atau textarea)
                    editor = ticket_page.locator("#form_wip_inc .ck-editor__editable, .modal.show .ck-editor__editable").first
                    if editor.count() > 0:
                        editor.click()
                        ticket_page.wait_for_timeout(500)
                        ticket_page.keyboard.press("Control+a")
                        ticket_page.keyboard.press("Backspace")
                        ticket_page.wait_for_timeout(300)
                        ticket_page.keyboard.type("WIP", delay=50)
                        ticket_page.wait_for_timeout(500)
                    else:
                        ta = ticket_page.locator("#progress_note").first
                        if ta.count() > 0:
                            ticket_page.evaluate("() => { const el=document.getElementById('progress_note'); if(el) el.style.display='block'; }")
                            ta.fill("WIP")
                            ticket_page.wait_for_timeout(500)
                    # Klik Work Progress di footer modal
                    confirm = ticket_page.locator("#btn_wip_inc").first
                    if confirm.count() == 0:
                        confirm = ticket_page.locator(".modal-footer #btn_wip_inc, .modal.show #btn_wip_inc").first
                    if confirm.count() > 0:
                        confirm.scroll_into_view_if_needed()
                        ticket_page.wait_for_timeout(500)
                        confirm.click()
                        ticket_page.wait_for_timeout(3000)
                        return 'WIP_NOTE'
                    # fallback: tombol Work Progress mana pun di modal
                    btn = ticket_page.locator(".modal.show button:has-text('Work Progress')").last
                    if btn.count() > 0:
                        btn.click()
                        ticket_page.wait_for_timeout(3000)
                        return 'WIP_NOTE'
                except Exception as e:
                    print(f"WIP modal handling error: {e}")
                return 'WIP_NOTE'
            return result
        except Exception as e:
            print(f"take_ownership JS error: {e}")
            return None

    def read_coordinator_user_id(self, ticket_page):
        """Return user ID Coordinator saat ini (REQUEST #id_coordinator / INCIDENT #selectSolver)."""
        try:
            val = ticket_page.evaluate("""
                (function() {
                    var ids = ['id_coordinator','selectSolver','selectIncidentOwner'];
                    for (var i=0;i<ids.length;i++){
                        var el=document.getElementById(ids[i]);
                        if(el) return el.value || '';
                    }
                    return '';
                })();
            """)
            return str(val).strip()
        except Exception:
            return ""

    def read_coordinator_label(self, ticket_page):
        """Return teks label Coordinator (REQUEST/INCIDENT)."""
        try:
            val = ticket_page.evaluate("""
                (function() {
                    var ids = ['id_coordinator','selectSolver','selectIncidentOwner'];
                    for (var i=0;i<ids.length;i++){
                        var el=document.getElementById(ids[i]);
                        if(el){
                            var opt=el.options[el.selectedIndex];
                            return opt ? (opt.text || '') : '';
                        }
                    }
                    return '';
                })();
            """)
            return str(val).strip()
        except Exception:
            return ""

    def is_my_ticket(self, ticket_page):
        from config import settings as cfg
        return self.read_coordinator_user_id(ticket_page) == str(
            getattr(cfg, "USER_ID", "55654")
        ).strip()

    def is_coordinator_in_skip_list(self, ticket_page):
        """True jika tiket dimiliki Request Coordinator di daftar skip.

        Entri bisa berupa ID angka ('55652') atau nama/username ('Rizky Senja Budiman',
        'CRS2018192'). Teks dicocokkan sebagian (case-insensitive) terhadap label
        koordinator di form tiket.
        """
        from config import settings as cfg
        uid = self.read_coordinator_user_id(ticket_page)
        label = self.read_coordinator_label(ticket_page)
        skip_ids = getattr(cfg, "SKIP_COORDINATOR_USER_IDS", []) or []
        for item in skip_ids:
            item_s = str(item).strip()
            if not item_s:
                continue
            if item_s.isdigit():
                if uid == item_s:
                    return True
            elif item_s.lower() in label.lower():
                return True
        return False

    def change_coordinator_to_me(self, ticket_page):
        from config import settings as cfg
        USER_ID = str(getattr(cfg, "USER_ID", "55654"))
        USER_NAME = str(getattr(cfg, "USER_NAME", "I Nyoman Windu"))

        try:
            ticket_page.wait_for_load_state("domcontentloaded", timeout=15000)
            ticket_page.wait_for_timeout(2000)
        except Exception:
            pass

        js_code = f"""
        (async function() {{
            function sleep(ms) {{ return new Promise(r => setTimeout(r, ms)); }}

            for (var w = 0; w < 10; w++) {{
                if (window.jQuery && jQuery.fn.select2) break;
                await sleep(500);
            }}
            if (!window.jQuery) return 'NO_JQUERY';

            var ic = document.getElementById('id_coordinator') || document.getElementById('selectSolver') || document.getElementById('selectIncidentOwner');
            if (!ic) return 'NO_IC';
            var $ic = jQuery(ic);
            if ($ic.find('option[value="{USER_ID}"]').length === 0) {{
                $ic.append(new Option('{USER_NAME}', '{USER_ID}', false, false));
            }}
            $ic.val('{USER_ID}').trigger('change');
            await sleep(1500);

            var icVal = $ic.val();
            if (icVal !== '{USER_ID}') {{
                return 'VERIFY_FAIL:ic=' + icVal;
            }}

            var saveBtn = document.getElementById('btn_submit_request');
            if (saveBtn && saveBtn.offsetParent !== null) {{
                saveBtn.click(); return 'SAVE';
            }}
            var updateBtn = document.getElementById('btn_update_inc');
            if (updateBtn && updateBtn.offsetParent !== null) {{
                updateBtn.click(); return 'UPDATE_INC';
            }}
            return 'NO_BUTTON';
        }})();
        """

        try:
            result = ticket_page.evaluate(js_code)
            ticket_page.wait_for_timeout(3000)
            return result
        except Exception as e:
            print(f"change_coordinator JS error: {e}")
            return None

    def wait_for_in_progress(self, ticket_page, timeout=45):
        start = time.time()
        while time.time() - start < timeout:
            try:
                # REQUEST: #status , INCIDENT: #select_incident_status
                for sel in ["#status", "#select_incident_status", "select[id*='incident_status']"]:
                    try:
                        loc = ticket_page.locator(sel)
                        if loc.count() > 0:
                            raw = ""
                            try:
                                raw = loc.first.input_value().strip()
                            except Exception:
                                raw = loc.first.inner_text().strip()
                            raw_up = raw.upper()
                            if raw_up in ("IN_PROGRESS", "WIP", "WORK_IN_PROGRESS", "IN PROGRESS"):
                                return True
                            # incident ASSIGNED -> after WIP click may jadi IN_PROGRESS or ASSIGNED->WIP
                            if "IN_PROGRESS" in raw_up or raw_up == "WIP":
                                return True
                    except Exception:
                        continue
                try:
                    ticket_page.wait_for_load_state("domcontentloaded", timeout=8000)
                except Exception:
                    pass
            except Exception:
                pass
            try:
                ticket_page.wait_for_timeout(2000)
            except Exception:
                # page closed -> stop polling
                return False
        return False

    def wait_for_completed(self, ticket_page, timeout=30):
        start = time.time()
        while time.time() - start < timeout:
            try:
                for sel in ["#status", "#select_incident_status", "select[id*='incident_status']"]:
                    try:
                        loc = ticket_page.locator(sel)
                        if loc.count() > 0:
                            raw = ""
                            try:
                                raw = loc.first.input_value().strip()
                            except Exception:
                                raw = loc.first.inner_text().strip()
                            if raw.upper() in ("COMPLETED", "RESOLVED", "CLOSED"):
                                return True
                    except Exception:
                        continue
                try:
                    ticket_page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass
            except Exception:
                pass
            try:
                ticket_page.wait_for_timeout(2000)
            except Exception:
                return False
        return False

    def complete_ticket(self, ticket_page, note="", log_callback=None):
        log = log_callback or (lambda msg: print(msg))
        try:
            ticket_page.wait_for_load_state("domcontentloaded", timeout=10000)
            ticket_page.wait_for_timeout(2000)

            # INCIDENT: Resolve (#btn_resolved -> #resolve-modal) -> REQUEST: Complete
            btn = None
            for sel in [
                "#btn_resolved",
                "#btn_resolve_note",
                "#btn_resolve_inc",
                "button:has-text('Resolve')",
                "button:has-text('Complete')",
                "a:has-text('Complete')",
                "button:has-text('COMPLETED')",
                "button:has-text('Completed')",
                "#btn_close_inc",
                "button:has-text('Close Incident')",
            ]:
                loc = ticket_page.locator(sel)
                if loc.count() > 0:
                    btn = loc.first
                    log(f"    [COMPLETE] Found action button: {sel}")
                    break

            if btn is None:
                log(f"    [COMPLETE] Resolve/Complete button NOT found on ticket page!")
                return False

            btn.scroll_into_view_if_needed()
            ticket_page.wait_for_timeout(500)
            btn.click()
            ticket_page.wait_for_timeout(3500)

            # Isi Resolution Note ("Cek Kembali")
            if note:
                filled = False
                # 1) Prioritaskan CKEditor editable (field sering di-wrap CKEditor)
                ck = ticket_page.locator("#resolve-modal .ck-editor__editable, .modal.show .ck-editor__editable, .ck-editor__editable:visible")
                if ck.count() > 0:
                    try:
                        box = ck.last
                        box.scroll_into_view_if_needed()
                        box.click()
                        ticket_page.keyboard.press("Control+a")
                        ticket_page.keyboard.press("Backspace")
                        ticket_page.wait_for_timeout(300)
                        ticket_page.keyboard.type(note, delay=30)
                        ticket_page.wait_for_timeout(500)
                        filled = True
                        log(f"    [COMPLETE] Typed note into CKEditor: {note}")
                    except Exception as e:
                        log(f"    [COMPLETE] CKEditor type failed: {e}")
                # 2) Fallback: textarea #resolution (plain)
                if not filled:
                    ta = ticket_page.locator("#resolution")
                    if ta.count() > 0:
                        try:
                            ta.first.scroll_into_view_if_needed()
                            ta.first.click()
                            ticket_page.keyboard.press("Control+a")
                            ticket_page.keyboard.press("Backspace")
                            ticket_page.wait_for_timeout(300)
                            ticket_page.keyboard.type(note, delay=30)
                            ticket_page.wait_for_timeout(500)
                            filled = True
                            log(f"    [COMPLETE] Typed note into #resolution: {note}")
                        except Exception as e:
                            log(f"    [COMPLETE] #resolution type failed: {e}")
                # 3) Backup: paksa set value #resolution via JS (pastikan form value terisi)
                try:
                    ticket_page.evaluate(
                        "(n) => { const el=document.getElementById('resolution'); if(el){ el.value=n; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); } }",
                        note,
                    )
                except Exception:
                    pass
                # 4) Last resort: cari textarea/contenteditable mana pun yg terlihat di modal
                if not filled:
                    note_box = None
                    for sel in [".modal.show textarea", "[role='dialog'] textarea:visible", "textarea:visible", "[contenteditable='true']:visible"]:
                        loc = ticket_page.locator(sel)
                        if loc.count() > 0:
                            note_box = loc.last
                            break
                    if note_box:
                        try:
                            note_box.click()
                            ticket_page.keyboard.press("Control+a")
                            ticket_page.keyboard.press("Backspace")
                            ticket_page.wait_for_timeout(300)
                            ticket_page.keyboard.type(note, delay=30)
                            ticket_page.wait_for_timeout(400)
                            filled = True
                            log(f"    [COMPLETE] Typed note (last resort)")
                        except Exception:
                            pass
                if not filled:
                    log(f"    [COMPLETE] GAGAL isi note, tidak lanjut submit")
                    return False

            # Pastikan select required terisi (incident resolve)
            try:
                ticket_page.evaluate("""() => {
                    ['optimum_resolution','resolution_status_reason'].forEach(id => {
                        const sel=document.getElementById(id);
                        if(sel && !sel.value){
                            for(let i=0;i<sel.options.length;i++){
                                if(sel.options[i].value && sel.options[i].text!=='Select Resolution Message' && sel.options[i].text!=='Select Status Reason'){
                                    sel.selectedIndex=i;
                                    if(window.jQuery) jQuery(sel).trigger('change');
                                    break;
                                }
                            }
                        }
                    });
                }""")
            except Exception as e:
                log(f"    [COMPLETE] ensure selects err: {e}")

            # Submit - coba banyak selector sampai ketemu
            submitted = False
            submit_selectors = [
                "#btn_resolve_inc",
                "#btn_submit_complete",
                "#resolve-modal button[type='submit']",
                "button[type='submit']",
                "#resolve-modal button:has-text('Submit')",
                "#resolve-modal button:has-text('Resolve')",
                "button:has-text('Submit')",
                "button:has-text('Yes')",
                "button:has-text('OK')",
                "button:has-text('Confirm')",
            ]
            for ssel in submit_selectors:
                try:
                    sb = ticket_page.locator(ssel)
                    if sb.count() > 0 and sb.first.is_visible():
                        log(f"    [COMPLETE] Clicking submit: {ssel}")
                        sb.first.scroll_into_view_if_needed()
                        ticket_page.wait_for_timeout(500)
                        sb.first.click()
                        ticket_page.wait_for_timeout(3000)
                        submitted = True
                        break
                except Exception:
                    continue

            if not submitted:
                log(f"    [COMPLETE] Submit button TIDAK ditemukan, batal")
                return False

            # Verifikasi status benar-benar RESOLVED/COMPLETED sebelum return
            log(f"    [COMPLETE] Verifying status changed...")
            ok = self.wait_for_completed(ticket_page, timeout=30)
            if ok:
                log(f"    [COMPLETE] Status sudah RESOLVED/COMPLETED")
            else:
                log(f"    [COMPLETE] Status BELUM berubah setelah submit!")
            return ok
        except Exception as e:
            log(f"    [COMPLETE] Error: {e}")
        return False

    def extract_wo_number(self, note):
        match = re.search(r'WO\d+', note)
        if match:
            return match.group(0)
        return None

    def filter_canclwork(self, page):
        try:
            page.locator("#searchSelect").select_option(label="OPEN")
            page.wait_for_timeout(500)

            adv_link = page.locator('a[href="#multiCollapseExample1"]')
            if adv_link.count() > 0:
                adv_link.click()
            page.wait_for_selector("#multiCollapseExample1.show", timeout=5000)
            page.wait_for_timeout(500)

            notes_input = page.locator("#notes")
            if notes_input.count() == 0:
                notes_input = page.locator("input[name='notes']")
            if notes_input.count() > 0:
                notes_input.fill("")
                page.wait_for_timeout(300)
                notes_input.fill("CANCLWORK")
                page.wait_for_timeout(500)
            else:
                print("WARNING: Notes input field not found!")
                return

            verify_val = notes_input.input_value().strip()
            print(f"Notes filter value: '{verify_val}'")
            if "CANCLWORK" not in verify_val:
                print("FAILED to set Notes filter!")
                return

            page.locator("#btn_apply").click()
            page.wait_for_timeout(4000)

            notes_val_after = notes_input.input_value().strip()
            print(f"Notes after Apply: '{notes_val_after}'")

            rows = page.locator("#requestFulfillmentTable tbody tr")
            count = rows.count()
            print(f"Filter CANCLWORK: {count} row(s) found")
        except Exception as e:
            print(f"Filter CANCLWORK error: {e}")

    def filter_cancelwork(self, page):
        try:
            page.locator("#searchSelect").select_option(label="OPEN")
            page.wait_for_timeout(500)

            adv_link = page.locator('a[href="#multiCollapseExample1"]')
            if adv_link.count() > 0:
                adv_link.click()
            page.wait_for_selector("#multiCollapseExample1.show", timeout=5000)
            page.wait_for_timeout(500)

            notes_input = page.locator("#notes")
            if notes_input.count() == 0:
                notes_input = page.locator("input[name='notes']")
            if notes_input.count() > 0:
                notes_input.fill("")
                page.wait_for_timeout(300)
                notes_input.fill("CANCELWORK")
                page.wait_for_timeout(500)
            else:
                print("WARNING: Notes input field not found!")
                return

            verify_val = notes_input.input_value().strip()
            print(f"Notes filter value: '{verify_val}'")
            if "CANCELWORK" not in verify_val:
                print("FAILED to set Notes filter!")
                return

            page.locator("#btn_apply").click()
            page.wait_for_timeout(4000)

            notes_val_after = notes_input.input_value().strip()
            print(f"Notes after Apply: '{notes_val_after}'")

            rows = page.locator("#requestFulfillmentTable tbody tr")
            count = rows.count()
            print(f"Filter CANCELWORK: {count} row(s) found")
        except Exception as e:
            print(f"Filter CANCELWORK error: {e}")

    def process_canclwork_tickets(self, log_callback=None):
        from app.services.biscuit_service import BiscuitService
        log = log_callback or (lambda msg: None)
        results = []

        page = self.navigate_to_dashboard()
        log(f"Dashboard loaded: {page.url[:60]}")

        filters = ["CANCLWORK", "CANCELWORK"]
        filter_idx = 0
        current_filter = filters[filter_idx]

        def apply_filter(filter_name):
            if filter_name == "CANCLWORK":
                self.filter_canclwork(page)
            else:
                self.filter_cancelwork(page)
            try:
                page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
                page.wait_for_timeout(2000)
                return True
            except Exception:
                log(f"No rows found for {filter_name}")
                return False

        if not apply_filter(current_filter):
            log(f"No tickets for {current_filter}. Switching...")
            filter_idx += 1
            if filter_idx < len(filters):
                current_filter = filters[filter_idx]
                if not apply_filter(current_filter):
                    log(f"No tickets for any filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                    return results
            else:
                log(f"No tickets found. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results
        log(f"Filtered: OPEN + {current_filter}")

        total_processed = 0

        while True:
            info_text = page.locator("#requestFulfillmentTable_info").inner_text()
            log(f"--- {current_filter} | {info_text} ---")

            rows = self.get_ticket_rows(page)
            log(f"Found {len(rows)} row(s)")

            if len(rows) == 0:
                filter_idx += 1
                if filter_idx < len(filters):
                    current_filter = filters[filter_idx]
                    log(f"No {filters[filter_idx-1]} tickets. Switching to {current_filter}...")
                    if not apply_filter(current_filter):
                        log(f"No tickets for any filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                        return results
                    continue
                else:
                    log(f"No tickets found. Waiting {LOOP_INTERVAL // 60} minutes...")
                    return results

            processed_this_round = 0

            for i, row_info in enumerate(rows):
                code = row_info["request_code"]
                status = row_info["status"]

                if self._stopped():
                    log("STOP requested - aborting scan")
                    return results

                if status in ("COMPLETED", "COMPLETE"):
                    log(f"  [{i+1}] {code} - SKIP (status: {status})")
                    continue

                if code in self.processed_ids:
                    log(f"  [{i+1}] {code} - SKIP (already processed)")
                    continue

                total_processed += 1
                processed_this_round += 1
                log(f"  [{i+1}/{len(rows)}] Opening {code}...")

                ticket_page = self.click_ticket(page, row_info)
                if ticket_page is None:
                    log(f"    Failed to open {code}")
                    continue

                try:
                    quick_status = self.read_ticket_status(ticket_page)
                    if quick_status and "COMPLETED" in quick_status:
                        log(f"    SKIP: tiket sudah COMPLETED di form")
                        continue

                    note = self.read_ticket_note(ticket_page)
                    note_short = note[:100] + "..." if len(note) > 100 else note
                    log(f"    Note: {note_short}")

                    note_upper = note.upper()
                    if current_filter == "CANCLWORK" and "CANCLWORK" not in note_upper:
                        log(f"    SAFETY: No CANCLWORK in note, SKIP")
                        continue
                    if current_filter == "CANCELWORK" and "CANCELWORK" not in note_upper:
                        log(f"    SAFETY: No CANCELWORK in note, SKIP")
                        continue

                    current_solver = ticket_page.locator("#id_coordinator")
                    solver_val = ""
                    if current_solver.count() > 0:
                        solver_val = current_solver.input_value().strip()
                    my_uid = str(getattr(sys.modules["config.settings"], "USER_ID", "55654"))
                    log(f"    Solver: {solver_val} | My ID: {my_uid}")

                    if self.is_coordinator_in_skip_list(ticket_page):
                        log(f"    SKIP: solver {solver_val} di daftar skip (Rizky Senja Budiman/CRS2018192)")
                        continue

                    if solver_val != my_uid:
                        log(f"    Solver bukan saya -> TO dulu...")
                        btn_action = self.take_ownership(ticket_page)
                        log(f"    Button clicked: {btn_action}")

                        confirmed = self.wait_for_in_progress(ticket_page)
                        if not confirmed:
                            log(f"    TO FAILED: {code}")
                            continue
                        log(f"    TO CONFIRMED: {code}")
                    else:
                        log(f"    Solver sudah saya, skip TO")

                    has_osm = any(kw in note_upper for kw in ["OSM", "SOM", "TOM"])
                    if not has_osm:
                        warn = "untuk permintaan CANCLWORK pastikan status OSM sudah CANCEL COMPLETE atau ABORTED"
                        log(f"    SAFETY: No OSM/SOM/TOM in note")
                        log(f"    Complete ticket dengan note: {warn}")
                        self.complete_ticket(ticket_page, note=warn)
                        page.bring_to_front()
                        continue

                    wo_number = self.extract_wo_number(note)
                    if not wo_number:
                        wo_number = self.read_wo_from_field(ticket_page)
                        if wo_number:
                            log(f"    WO from field: {wo_number}")
                    if not wo_number:
                        log(f"    WO number not found anywhere, SKIP")
                        continue
                    log(f"    WO found: {wo_number}")

                    biscuit = BiscuitService(browser_manager=self.browser_manager)
                    if not biscuit.open():
                        log(f"    BISCUIT tab not found!")
                        continue

                    command = f"/pushmasscanclwork {wo_number}"
                    log(f"    Sending: {command}")

                    max_retries = 2
                    response = None
                    for attempt in range(1, max_retries + 1):
                        log(f"    Command sent (attempt {attempt})")
                        response = biscuit.execute(command, "BIMA")
                        log(f"    BISCUIT response: {response.status} - {response.message}")

                        if response.status != "UNKNOWN":
                            break

                        if attempt < max_retries:
                            log(f"    BISCUIT timeout, retrying...")
                            biscuit.wait_for_ready()

                    if response.status == "SUCCESS":
                        complete_note = "Cek Kembali"
                        log(f"    BISCUIT SUKSES! Complete ticket...")
                    else:
                        complete_note = response.message[:200]
                        log(f"    BISCUIT GAGAL! Complete dengan alasan error...")

                    page.bring_to_front()
                    page.wait_for_timeout(1000)
                    if not ticket_page.is_closed():
                        self.browser_manager.activate_page(ticket_page)
                        try:
                            ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                        except Exception:
                            pass
                        ticket_page.wait_for_timeout(3000)
                        completed = self.complete_ticket(ticket_page, note=complete_note)
                        if completed:
                            log(f"    Waiting COMPLETED status...")
                            is_completed = self.wait_for_completed(ticket_page)
                            if is_completed:
                                log(f"    Ticket {code} -> COMPLETED ({response.status})")
                            else:
                                log(f"    Ticket {code} status belum COMPLETED")
                        else:
                            log(f"    Gagal complete ticket {code}")

                    results.append({
                        "request_code": code,
                        "wo_number": wo_number,
                        "note": note,
                        "biscuit_status": response.status,
                    })
                    self.processed_ids.add(code)
                    try:
                        log_history(feature="CANCLWORK", ticket_code=code, ticket_id=wo_number, owner_group=wo_number, note=note, reply_sygap=complete_note if 'complete_note' in locals() else "", biscuit_status=response.status if 'response' in locals() and hasattr(response, 'status') else "", biscuit_message=response.message if 'response' in locals() and hasattr(response, 'message') else "", status=response.status if 'response' in locals() and hasattr(response, 'status') else "SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                    except Exception:
                        pass

                except Exception as e:
                    log(f"    Error: {e}")
                finally:
                    if code not in self.processed_ids and code not in self.related_ids:
                        self.skipped_ids[code] = time.time()
                        self._save_persistent_skipped(code)
                    try:
                        if not ticket_page.is_closed():
                            ticket_page.close()
                    except Exception:
                        pass
                    self._close_extra_tabs(page, log_callback=log)
                    page.wait_for_timeout(1500)

            log(f"Page done. Re-applying filter...")
            if not apply_filter(current_filter):
                log(f"No rows after filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            info_after = page.locator("#requestFulfillmentTable_info").inner_text()
            if "0 entries" in info_after or "0 of 0" in info_after:
                filter_idx += 1
                if filter_idx < len(filters):
                    current_filter = filters[filter_idx]
                    log(f"No {filters[filter_idx-1]} tickets. Switching to {current_filter}...")
                    if not apply_filter(current_filter):
                        log(f"No tickets for any filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                        return results
                    continue
                else:
                    log(f"No tickets after filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                    return results

            if processed_this_round == 0:
                filter_idx += 1
                if filter_idx < len(filters):
                    current_filter = filters[filter_idx]
                    log(f"No actionable {filters[filter_idx-1]} tickets. Switching to {current_filter}...")
                    if not apply_filter(current_filter):
                        log(f"No tickets for any filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                        return results
                    continue
                else:
                    log(f"No actionable tickets. Waiting {LOOP_INTERVAL // 60} minutes...")
                    return results

        return results

    def filter_dispatch(self, page):
        try:
            page.locator("#searchSelect").select_option(label="OPEN")
            page.wait_for_timeout(500)

            adv_link = page.locator('a[href="#multiCollapseExample1"]')
            if adv_link.count() > 0:
                adv_link.click()
            page.wait_for_selector("#multiCollapseExample1.show", timeout=5000)
            page.wait_for_timeout(500)

            notes_input = page.locator("#notes")
            if notes_input.count() == 0:
                notes_input = page.locator("input[name='notes']")
            if notes_input.count() > 0:
                notes_input.fill("")
                page.wait_for_timeout(300)
                notes_input.fill("dispatch")
                page.wait_for_timeout(500)
            else:
                print("WARNING: Notes input field not found!")
                return

            verify_val = notes_input.input_value().strip()
            print(f"Notes filter value: '{verify_val}'")
            if "dispatch" not in verify_val.lower():
                print("FAILED to set Notes filter!")
                return

            # Set Solver Group ke MO-INSERA
            from config.settings import INSERA_GROUP_ID
            js_set_og = f"""
            (function() {{
                var el = document.getElementById('solverGroupSearch');
                if (el && window.jQuery) {{
                    var $el = jQuery(el);
                    $el.empty();
                    $el.append(new Option('MO-INSERA', '{INSERA_GROUP_ID}', true, true));
                    $el.val('{INSERA_GROUP_ID}').trigger('change');
                }}
            }})();
            """
            page.evaluate(js_set_og)
            page.wait_for_timeout(1000)

            og_selected = page.locator("#select2-solverGroupSearch-container").inner_text()
            print(f"SolverGroup: '{og_selected}'")

            search_btn = page.locator("#btn_apply")
            if search_btn.count() == 0:
                search_btn = page.locator("button.btn-primary .fa-search")
                if search_btn.count() > 0:
                    search_btn = search_btn.locator("xpath=ancestor::button")
            if search_btn.count() > 0:
                search_btn.first.click()
            page.wait_for_timeout(4000)

            rows = page.locator("#requestFulfillmentTable tbody tr")
            count = rows.count()
            print(f"Filter DISPATCH: {count} row(s) found")
        except Exception as e:
            print(f"Filter DISPATCH error: {e}")

    def filter_dispatch_incident(self, page):
        """Filter untuk INCIDENT dispatch: OPEN + notes=dispatch + MO-INSERA (tabel incidentTable)."""
        try:
            # Status OPEN - incident pakai #statusSearch, fallback #searchSelect
            status_sel = None
            for sel_id in ["#statusSearch", "#searchSelect"]:
                loc = page.locator(sel_id)
                if loc.count() > 0:
                    try:
                        loc.select_option(label="OPEN")
                        page.wait_for_timeout(500)
                        status_sel = sel_id
                        print(f"Filter INCIDENT: status OPEN via {sel_id}")
                        break
                    except Exception:
                        continue
            if not status_sel:
                print("WARNING: Status select not found for INCIDENT!")

            adv_link = page.locator('a[href="#multiCollapseExample1"]')
            if adv_link.count() > 0:
                adv_link.click()
            page.wait_for_selector("#multiCollapseExample1.show", timeout=5000)
            page.wait_for_timeout(500)

            notes_input = page.locator("#notes")
            if notes_input.count() == 0:
                notes_input = page.locator("input[name='notes']")
            if notes_input.count() > 0:
                notes_input.fill("")
                page.wait_for_timeout(300)
                notes_input.fill("dispatch")
                page.wait_for_timeout(500)
            else:
                print("WARNING: Notes input field not found!")
                return

            verify_val = notes_input.input_value().strip()
            print(f"Notes filter value: '{verify_val}'")
            if "dispatch" not in verify_val.lower():
                print("FAILED to set Notes filter!")
                return

            from config.settings import INSERA_GROUP_ID
            js_set_og = f"""
            (function() {{
                var el = document.getElementById('solverGroupSearch');
                if (el && window.jQuery) {{
                    var $el = jQuery(el);
                    $el.empty();
                    $el.append(new Option('MO-INSERA', '{INSERA_GROUP_ID}', true, true));
                    $el.val('{INSERA_GROUP_ID}').trigger('change');
                }}
            }})();
            """
            page.evaluate(js_set_og)
            page.wait_for_timeout(1000)

            og_selected = page.locator("#select2-solverGroupSearch-container").inner_text()
            print(f"SolverGroup: '{og_selected}'")

            search_btn = page.locator("#btn_apply")
            if search_btn.count() == 0:
                search_btn = page.locator("button.btn-primary .fa-search")
                if search_btn.count() > 0:
                    search_btn = search_btn.locator("xpath=ancestor::button")
            if search_btn.count() > 0:
                search_btn.first.click()
            page.wait_for_timeout(4000)

            table_id = self._get_dispatch_table_id(page)
            rows = page.locator(f"#{table_id} tbody tr")
            count = rows.count()
            print(f"Filter DISPATCH INCIDENT ({table_id}): {count} row(s) found")
        except Exception as e:
            print(f"Filter DISPATCH INCIDENT error: {e}")

    def filter_change_service_id(self, page):
        try:
            page.locator("#searchSelect").select_option(label="OPEN")
            page.wait_for_timeout(500)

            # Hanya klik jika belum terbuka
            collapse = page.locator("#multiCollapseExample1")
            is_open = False
            try:
                is_open = collapse.evaluate("el => el.classList.contains('show')")
            except Exception:
                pass

            if not is_open:
                adv_link = page.locator('a[href="#multiCollapseExample1"]')
                if adv_link.count() > 0:
                    adv_link.first.click()
                try:
                    page.wait_for_selector("#multiCollapseExample1.show", timeout=5000)
                except Exception:
                    pass
            page.wait_for_timeout(500)

            notes_input = page.locator("#notes")
            if notes_input.count() == 0:
                notes_input = page.locator("input[name='notes']")
            if notes_input.count() > 0:
                notes_input.fill("")
                page.wait_for_timeout(300)
                notes_input.fill("Service")
                page.wait_for_timeout(500)
            else:
                print("WARNING: Notes input field not found!")
                return

            verify_val = notes_input.input_value().strip()
            print(f"Notes filter value: '{verify_val}'")
            if "service" not in verify_val.lower():
                print("FAILED to set Notes filter!")
                return

            # Set Solver Group ke MO-INSERA
            from config.settings import INSERA_GROUP_ID
            js_set_og = f"""
            (function() {{
                var el = document.getElementById('solverGroupSearch');
                if (el && window.jQuery) {{
                    var $el = jQuery(el);
                    $el.empty();
                    $el.append(new Option('MO-INSERA', '{INSERA_GROUP_ID}', true, true));
                    $el.val('{INSERA_GROUP_ID}').trigger('change');
                }}
            }})();
            """
            page.evaluate(js_set_og)
            page.wait_for_timeout(1000)

            og_selected = page.locator("#select2-solverGroupSearch-container").inner_text()
            print(f"SolverGroup: '{og_selected}'")

            search_btn = page.locator("#btn_apply")
            if search_btn.count() == 0:
                search_btn = page.locator("button.btn-primary .fa-search")
                if search_btn.count() > 0:
                    search_btn = search_btn.locator("xpath=ancestor::button")
            if search_btn.count() > 0:
                search_btn.first.click()
            page.wait_for_timeout(4000)

            rows = page.locator("#requestFulfillmentTable tbody tr")
            count = rows.count()
            print(f"Filter CHANGE SERVICE ID: {count} row(s) found")
        except Exception as e:
            print(f"Filter CHANGE SERVICE ID error: {e}")

    def filter_gamas_relations(self, page):
        try:
            page.locator("#searchSelect").select_option(label="OPEN")
            page.wait_for_timeout(500)

            adv_link = page.locator('a[href="#multiCollapseExample1"]')
            if adv_link.count() > 0:
                adv_link.click()
            page.wait_for_selector("#multiCollapseExample1.show", timeout=5000)
            page.wait_for_timeout(500)

            notes_input = page.locator("#notes")
            if notes_input.count() == 0:
                notes_input = page.locator("input[name='notes']")
            if notes_input.count() > 0:
                notes_input.fill("")
                page.wait_for_timeout(300)
                notes_input.fill("gamas")
                page.wait_for_timeout(500)
            else:
                print("WARNING: Notes input field not found!")
                return

            from config.settings import INSERA_GROUP_ID
            js_set_og = f"""
            (function() {{
                var el = document.getElementById('solverGroupSearch');
                if (el && window.jQuery) {{
                    var $el = jQuery(el);
                    $el.empty();
                    $el.append(new Option('MO-INSERA', '{INSERA_GROUP_ID}', true, true));
                    $el.val('{INSERA_GROUP_ID}').trigger('change');
                }}
            }})();
            """
            page.evaluate(js_set_og)
            page.wait_for_timeout(1000)

            page.locator("#btn_apply").click()
            page.wait_for_timeout(4000)

            rows = page.locator("#requestFulfillmentTable tbody tr")
            count = rows.count()
            print(f"Filter GAMAS RELATIONS: {count} row(s) found")
        except Exception as e:
            print(f"Filter GAMAS RELATIONS error: {e}")

    def _complete_gamas_reply(self, page, ticket_page, code, note, results, log):
        """Complete tiket GAMAS relations dengan reply note (tanpa membuat relasi)."""
        page.bring_to_front()
        page.wait_for_timeout(1000)
        self.browser_manager.activate_page(ticket_page)
        try:
            ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass
        ticket_page.wait_for_timeout(3000)

        completed = self.complete_ticket(ticket_page, note=note)
        if completed:
            is_completed = self.wait_for_completed(ticket_page)
            if is_completed:
                log(f"    Ticket {code} -> COMPLETED (reply: {note})")
            else:
                log(f"    Ticket {code} status belum COMPLETED")
            results.append({"request_code": code, "reply_note": note})
            # Tandai processed agar tidak di-retry (relasi memang tidak dibuat)
            self.processed_ids.add(code)
            try:
                _n = note if 'note' in locals() else ""
                log_history(feature="GAMAS", ticket_code=code, ticket_id="", owner_group="", note=_n, reply_sygap=note if 'note' in locals() else "", biscuit_status="", biscuit_message="", status="SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
            except Exception:
                pass
        else:
            log(f"    Gagal complete ticket {code} (reply)")
            self.gamas_fail_count[code] = self.gamas_fail_count.get(code, 0) + 1
            if self.gamas_fail_count[code] >= 3:
                log(f"    Complete gagal {self.gamas_fail_count[code]}x, tandai processed (give up)")
                self.processed_ids.add(code)

    def process_gamas_relations_tickets(self, log_callback=None):
        log = log_callback or (lambda msg: None)
        results = []

        page = self.navigate_to_dashboard()
        log(f"Dashboard loaded: {page.url[:60]}")

        # Check if INSERA tab already logged in
        logged_in = False
        pages = page.context.pages
        for p in pages:
            try:
                real_url = p.url.lower()
                if "oss-incident" in real_url and "login" not in real_url:
                    logged_in = True
                    log(f"INSERA sudah login! ({real_url[:60]})")
                    break
                if "insera" in real_url and "login" not in real_url:
                    logged_in = True
                    log(f"INSERA sudah login! ({real_url[:60]})")
                    break
            except Exception:
                continue

        if not logged_in:
            log("Menunggu user login ke INSERA...")
            log("Buka tab INSERA di Chrome GAMAS, lalu login.")
            for wait in range(120):
                if self._stopped():
                    log("STOP requested - aborting scan")
                    return results
                pages = page.context.pages
                if wait % 10 == 0:
                    log(f"  Tabs detected: {len(pages)}")
                    for idx, p in enumerate(pages):
                        try:
                            real_url = p.url
                            log(f"    Tab {idx+1}: {real_url[:80]}")
                        except Exception:
                            log(f"    Tab {idx+1}: (error)")
                for p in pages:
                    try:
                        real_url = p.url.lower()
                        if "oss-incident" in real_url and "login" not in real_url:
                            logged_in = True
                            break
                        if "insera" in real_url and "login" not in real_url:
                            logged_in = True
                            break
                    except Exception:
                        continue
                if logged_in:
                    log("INSERA tab terdeteksi (sudah login)! Mulai scan...")
                    break
                if wait % 10 == 0:
                    log(f"  Menunggu INSERA login... ({wait}s)")
                time.sleep(1)

        if not logged_in:
            log("INSERA belum login setelah 120 detik. Scan tetap dimulai...")

        self.filter_gamas_relations(page)
        log("Filtered: OPEN + gamas + MO-INSERA")

        try:
            page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
        except Exception:
            log("No tickets found after filter")
            return results
        page.wait_for_timeout(2000)

        total_processed = 0

        while True:
            info_text = page.locator("#requestFulfillmentTable_info").inner_text()
            log(f"--- {info_text} ---")

            if self._stopped():
                log("STOP requested - aborting scan")
                return results

            rows = self.get_ticket_rows(page)
            log(f"Found {len(rows)} row(s)")

            if len(rows) == 0:
                log(f"No tickets found. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            for i, row_info in enumerate(rows):
                code = row_info["request_code"]
                status = row_info["status"]

                if self._stopped():
                    log("STOP requested - aborting scan")
                    return results

                if status in ("COMPLETED", "COMPLETE"):
                    log(f"  [{i+1}] {code} - SKIP (status: {status})")
                    continue

                if code in self.processed_ids:
                    log(f"  [{i+1}] {code} - SKIP (already processed)")
                    continue

                if self._is_persistent_skipped(code):
                    log(f"  [{i+1}] {code} - SKIP (permanen, sudah pernah di-skip — tidak dibuka lagi)")
                    continue
                if code in self.skipped_ids and (time.time() - self.skipped_ids[code]) < LOOP_INTERVAL:
                    log(f"  [{i+1}] {code} - SKIP (recently skipped, tunggu {LOOP_INTERVAL}s)")
                    continue

                total_processed += 1
                log(f"  [{i+1}/{len(rows)}] Opening {code}...")

                ticket_page = self.click_ticket(page, row_info, skip_close=True)
                if ticket_page is None:
                    log(f"    Failed to open {code}")
                    self.skipped_ids[code] = time.time()
                    self._save_persistent_skipped(code)
                    continue

                try:
                    quick_status = self.read_ticket_status(ticket_page)
                    if quick_status and "COMPLETED" in quick_status:
                        log(f"    SKIP: tiket sudah COMPLETED di form")
                        continue

                    if self.is_coordinator_in_skip_list(ticket_page):
                        log(f"    SKIP: koordinator di daftar skip (Rizky Senja Budiman/CRS2018192)")
                        continue

                    if self.is_my_ticket(ticket_page):
                        log(f"    Sudah tiket saya, lanjut tanpa TO...")
                    else:
                        log(f"    Taking ownership...")
                        btn_action = self.take_ownership(ticket_page)
                        log(f"    Button clicked: {btn_action}")

                        confirmed = self.wait_for_in_progress(ticket_page)
                        if not confirmed:
                            log(f"    TO FAILED: {code}")
                            continue
                        log(f"    TO CONFIRMED: {code}")

                    note = self.read_ticket_note(ticket_page)
                    if note:
                        note_one_line = " ".join(note.split())[:500]
                        log(f"    Note: {note_one_line}")

                    from app.services.biscuit_service import BiscuitService
                    biscuit = BiscuitService(browser_manager=self.browser_manager)

                    parent_inc = self.extract_parent_gamas_from_note(note)
                    parser_found_parent = bool(parent_inc)
                    if parent_inc:
                        log(f"    Parent INC from note: {parent_inc}")
                    else:
                        parent_inc = self.find_parent_from_ticket_id_field(ticket_page, note)
                        if parent_inc:
                            log(f"    Parent INC from Ticket ID field: {parent_inc}")
                            parser_found_parent = True

                    if parser_found_parent:
                        # Parser menemukan induk -> anak diambil dari note/field (existing behavior)
                        child_incs = self.extract_child_incs_excluding_parent(note)
                        if not child_incs:
                            child_incs = self.read_child_incs_from_field(ticket_page)
                    else:
                        # FALLBACK: bot TIDAK menemukan parser induk -> deteksi otomatis by source.
                        all_incs = re.findall(r'INC\d+', note or '', re.IGNORECASE)
                        all_incs = [i.upper() for i in all_incs]
                        for i in self.read_child_incs_from_field(ticket_page):
                            if i not in all_incs:
                                all_incs.append(i)
                        if not all_incs:
                            log(f"    Tidak ada INC di note/field. SKIP")
                            continue
                        log(f"    FALLBACK deteksi by source untuk {len(all_incs)} INC: {','.join(all_incs[:8])}...")
                        child_check = biscuit.check_children(all_incs)
                        for ex in child_check["excluded"]:
                            log(f"    {ex['inc']} source={ex['source']} -> {ex['detail'][:90]}")
                        gamas_incs = [ex["inc"] for ex in child_check["excluded"] if ex["source"] == "GAMAS"]
                        if len(gamas_incs) >= 2:
                            log(f"    Ditemukan {len(gamas_incs)} tiket GAMAS ({gamas_incs}); COMPLETE dgn reply.")
                            self._complete_gamas_reply(page, ticket_page, code, "Harap sertakan 1 tiket Induk Gamas saja", results, log)
                            continue
                        elif len(gamas_incs) == 1:
                            parent_inc = gamas_incs[0]
                            log(f"    Induk GAMAS terdeteksi otomatis by source: {parent_inc}")
                            child_incs = [i for i in child_check["valid"] if i != parent_inc]
                        else:
                            log(f"    Tidak ada tiket GAMAS di antara INC; COMPLETE dengan reply 'harap sertakan juga induk gamas nya'.")
                            self._complete_gamas_reply(page, ticket_page, code, "harap sertakan juga induk gamas nya", results, log)
                            continue

                    if not child_incs:
                        log(f"    No child INCs found, COMPLETE dengan reply 'Harap sertakan anak gamas nya juga'.")
                        self._complete_gamas_reply(page, ticket_page, code, "Harap sertakan anak gamas nya juga", results, log)
                        continue
                    # Proteksi: anak gamas TIDAK boleh menjadi induk gamas.
                    # Buang parent dari daftar child; jika tidak ada child
                    # tersisa selain parent, jangan buat relasi.
                    child_incs = [c for c in child_incs if c != parent_inc]
                    if not child_incs:
                        log(f"    Parent {parent_inc} terdeteksi sebagai child juga. COMPLETE dengan reply 'Harap sertakan anak gamas nya juga'.")
                        self._complete_gamas_reply(page, ticket_page, code, "Harap sertakan anak gamas nya juga", results, log)
                        continue
                    log(f"    Child INCs ({len(child_incs)}): {','.join(child_incs[:5])}...")

                    if not biscuit.open():
                        log(f"    ⚠ Tab BISCUIT TIDAK TERBUKA -> pakai token cache. Jika /cekticket gagal, BUKA tab BISCUIT & LOGIN agar relasi bisa diverifikasi.")

                    if code in self.related_ids:
                        # Relasi GAMAS sudah pernah di-submit (mis. complete gagal lalu di-retry).
                        # JANGAN submit ulang (hindari relasi dobel), langsung ke complete.
                        log(f"    Relasi GAMAS sudah pernah di-submit, lewati submit INSERA -> langsung complete")
                    else:
                        log(f"    Checking induk {parent_inc} via /cekticket...")
                        check = biscuit.check_ticket(parent_inc)
                        log(f"    Cek induk {parent_inc}: {check['detail']}")
                        if not check["found"]:
                            detail = check.get("detail", "")
                            if "not found" in detail.lower() or "error" in detail.lower():
                                log(f"    ⚠ /cekticket induk GAGAL verifikasi: '{detail}'")
                                log(f"    ⚠ BUKA/KEMBALIKAN tab BISCUIT & pastikan SUDAH LOGIN (token mungkin expired/invalid). Bot akan retry otomatis.")
                                continue
                            else:
                                log(f"    Induk {parent_inc} bukan GAMAS ({detail}), coba fallback /cekticket semua INC...")
                                # Fallback: parser induk salah → cek semua INC di note/field untuk cari GAMAS yang benar
                                all_incs_fb = re.findall(r'INC\d+', note or '', re.IGNORECASE)
                                all_incs_fb = [i.upper() for i in all_incs_fb]
                                for i in self.read_child_incs_from_field(ticket_page):
                                    if i not in all_incs_fb:
                                        all_incs_fb.append(i)
                                if not all_incs_fb:
                                    log(f"    Fallback: tidak ada INC di note/field. SKIP")
                                    continue
                                log(f"    Fallback cek {len(all_incs_fb)} INC via /cekticket: {','.join(all_incs_fb[:8])}...")
                                fb_check = biscuit.check_children(all_incs_fb)
                                for ex in fb_check["excluded"]:
                                    log(f"    Fallback {ex['inc']} source={ex['source']} -> {ex['detail'][:90]}")
                                fb_gamas = [ex["inc"] for ex in fb_check["excluded"] if ex["source"] == "GAMAS"]
                                if len(fb_gamas) >= 2:
                                    log(f"    Fallback: ditemukan {len(fb_gamas)} tiket GAMAS ({fb_gamas}); COMPLETE dengan reply.")
                                    self._complete_gamas_reply(page, ticket_page, code, "Harap sertakan 1 tiket Induk Gamas saja", results, log)
                                    continue
                                elif len(fb_gamas) == 1:
                                    parent_inc = fb_gamas[0]
                                    log(f"    Fallback: induk GAMAS terdeteksi otomatis: {parent_inc} (ganti dari parser {check['detail'][:40]})")
                                    child_incs = [i for i in fb_check["valid"] if i != parent_inc]
                                    if not child_incs:
                                        log(f"    Fallback: tidak ada child valid setelah koreksi. COMPLETE dengan reply 'Harap sertakan anak gamas nya juga'.")
                                        self._complete_gamas_reply(page, ticket_page, code, "Harap sertakan anak gamas nya juga", results, log)
                                        continue
                                    log(f"    Fallback Child INCs ({len(child_incs)}): {','.join(child_incs[:5])}...")
                                    # Lanjut ke pengecekan child di bawah (jangan continue, biarkan flow ke check child)
                                else:
                                    log(f"    Fallback: tidak ada tiket GAMAS di antara INC; COMPLETE dengan reply 'harap sertakan juga induk gamas nya'.")
                                    self._complete_gamas_reply(page, ticket_page, code, "harap sertakan juga induk gamas nya", results, log)
                                    continue

                        log(f"    Checking {len(child_incs)} anak via /cekticket...")
                        child_check = biscuit.check_children(child_incs)
                        for ex in child_check["excluded"]:
                            log(f"    Anak {ex['inc']} source={ex['source']} -> jangan di-input ({ex['detail'][:90]})")
                        child_incs = child_check["valid"]
                        if not child_incs:
                            log(f"    Semua anak tidak valid (bukan CUSTOMER), COMPLETE dengan reply 'Harap sertakan anak gamas nya juga'.")
                            self._complete_gamas_reply(page, ticket_page, code, "Harap sertakan anak gamas nya juga", results, log)
                            continue
                        child_str = ",".join(child_incs)
                        log(f"    Child INCs valid ({len(child_incs)}): {child_str[:100]}...")

                        from app.services.insera_gamas_service import InseraGamasService
                        insera = InseraGamasService(browser_manager=self.browser_manager, log_callback=log)
                        if not insera.open():
                            log(f"    Tab INSERA tidak ditemukan, coba API langsung (cookie profil)...")
                        else:
                            max_nav_retries = 3
                            nav_ok = False
                            for nav_attempt in range(1, max_nav_retries + 1):
                                if not insera.navigate_to_relations():
                                    log(f"    Failed navigate to Gamas Relations (attempt {nav_attempt})")
                                    if nav_attempt < max_nav_retries:
                                        insera.get_page().wait_for_timeout(5000)
                                    continue

                                page_url = insera.get_page().url.lower()
                                page_content = ""
                                try:
                                    page_content = insera.get_page().content().lower()
                                except Exception:
                                    pass

                                if "login" in page_url:
                                    log(f"    INSERA belum login! Login manual dulu.")
                                    break

                                is_error = "system error" in page_content or (
                                    "unintended error" in page_content
                                )
                                if is_error:
                                    log(f"    Joget error at: {page_url[:60]}")
                                    if nav_attempt < max_nav_retries:
                                        log(f"    Retrying in 10s... (attempt {nav_attempt}/{max_nav_retries})")
                                        insera.get_page().wait_for_timeout(10000)
                                        insera.navigate_to_relations()
                                    continue

                                if "gamasrelations" in page_url:
                                    nav_ok = True
                                    break

                            if not nav_ok:
                                log(f"    Navigasi INSERA gagal, tetap coba API langsung...")

                        log(f"    Parent: {parent_inc}")
                        log(f"    Child: {child_str[:100]}...")

                        log(f"    Submitting relasi GAMAS...")
                        response = insera.submit_relation(parent_inc, child_str)
                        log(f"    INSERA response: {response.status} - {response.message}")
                        if response.status != "SUCCESS":
                            log(f"    INSERA FAILED, SKIP complete")
                            continue

                        # Tandai relasi sudah di-submit agar tidak dobel saat retry
                        self.related_ids.add(code)
                        log(f"    INSERA save OK, completing ticket...")

                    page.bring_to_front()
                    page.wait_for_timeout(1000)
                    self.browser_manager.activate_page(ticket_page)
                    try:
                        ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        pass
                    ticket_page.wait_for_timeout(3000)

                    completed = self.complete_ticket(ticket_page, note="Cek Kembali")
                    if completed:
                        log(f"    Waiting COMPLETED status...")
                        is_completed = self.wait_for_completed(ticket_page)
                        if is_completed:
                            log(f"    Ticket {code} -> COMPLETED")
                        else:
                            log(f"    Ticket {code} status belum COMPLETED")
                        results.append({
                            "request_code": code,
                            "parent_inc": parent_inc,
                            "child_incs": child_incs,
                        })
                        # HANYA tandai processed bila benar-benar COMPLETED,
                        # agar tiket yg gagal complete tidak skip selamanya (loop).
                        self.processed_ids.add(code)
                        try:
                            log_history(feature="GAMAS", ticket_code=code, ticket_id=parent_inc if 'parent_inc' in locals() else "", owner_group=",".join(child_incs[:3]) if 'child_incs' in locals() else "", note=note if 'note' in locals() else "", reply_sygap="Cek Kembali", biscuit_status="SUCCESS", biscuit_message=f"Parent:{parent_inc if 'parent_inc' in locals() else ''} Child:{','.join(child_incs[:3]) if 'child_incs' in locals() else ''}", status="SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                        except Exception:
                            pass
                    else:
                        log(f"    Gagal complete ticket {code}")
                        # Batas retry: kalau complete gagal terus-menerus, tandai processed
                        # agar tidak spin tiap loop (relasi sudah aman di related_ids).
                        self.gamas_fail_count[code] = self.gamas_fail_count.get(code, 0) + 1
                        if self.gamas_fail_count[code] >= 3:
                            log(f"    Complete gagal {self.gamas_fail_count[code]}x, tandai processed (give up) agar tidak spin")
                            self.processed_ids.add(code)

                except Exception as e:
                    log(f"    Error: {e}")
                finally:
                    # Catat tiket yg di-SKIP (bukan yg berhasil di-process/relasi)
                    # agar tidak dibuka berulang dalam sesi yang sama (cooldown LOOP_INTERVAL).
                    if code not in self.processed_ids and code not in self.related_ids:
                        self.skipped_ids[code] = time.time()
                        self._save_persistent_skipped(code)
                    try:
                        if not ticket_page.is_closed():
                            ticket_page.close()
                    except Exception:
                        pass
                    page.wait_for_timeout(1500)

            log(f"Page done. Re-applying filter...")
            self.filter_gamas_relations(page)
            page.wait_for_timeout(3000)

            info_after = page.locator("#requestFulfillmentTable_info").inner_text()
            if "0 entries" in info_after or "0 of 0" in info_after:
                log(f"No tickets after filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            if total_processed == 0:
                log(f"No actionable tickets. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

        return results

    def process_dispatch_tickets(self, log_callback=None):
        from app.services.biscuit_service import BiscuitService
        log = log_callback or (lambda msg: None)
        results = []

        page = self.navigate_to_dashboard()
        log(f"Dashboard loaded: {page.url[:60]}")

        self.filter_dispatch(page)
        log("Filtered: dispatch")

        try:
            page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
        except Exception:
            log("No tickets found after filter")
            return results
        page.wait_for_timeout(2000)

        total_processed = 0

        while True:
            info_text = page.locator("#requestFulfillmentTable_info").inner_text()
            log(f"--- {info_text} ---")

            if self._stopped():
                log("STOP requested - aborting scan")
                return results

            rows = self.get_ticket_rows(page)
            log(f"Found {len(rows)} row(s)")

            if len(rows) == 0:
                log(f"No tickets found. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            processed_this_round = 0

            for i, row_info in enumerate(rows):
                code = row_info["request_code"]
                status = row_info["status"]

                if self._stopped():
                    log("STOP requested - aborting scan")
                    return results

                if status in ("COMPLETED", "COMPLETE"):
                    log(f"  [{i+1}] {code} - SKIP (status: {status})")
                    continue

                if code in self.processed_ids:
                    log(f"  [{i+1}] {code} - SKIP (already processed)")
                    continue

                if self._is_persistent_skipped(code):
                    log(f"  [{i+1}] {code} - SKIP (permanen, sudah pernah di-skip — tidak dibuka lagi)")
                    continue
                if code in self.skipped_ids and (time.time() - self.skipped_ids[code]) < LOOP_INTERVAL:
                    log(f"  [{i+1}] {code} - SKIP (recently skipped, tunggu {LOOP_INTERVAL}s)")
                    continue

                total_processed += 1
                processed_this_round += 1
                log(f"  [{i+1}/{len(rows)}] Opening {code}...")

                ticket_page = self.click_ticket(page, row_info)
                if ticket_page is None:
                    log(f"    Failed to open {code}")
                    self.skipped_ids[code] = time.time()
                    self._save_persistent_skipped(code)
                    continue

                try:
                    quick_status = self.read_ticket_status(ticket_page)
                    if quick_status and "COMPLETED" in quick_status:
                        log(f"    SKIP: tiket sudah COMPLETED di form")
                        continue

                    if self.is_coordinator_in_skip_list(ticket_page):
                        log(f"    SKIP: koordinator di daftar skip (Rizky Senja Budiman/CRS2018192)")
                        continue

                    note = self.read_ticket_note(ticket_page)
                    note_short = note[:100] + "..." if len(note) > 100 else note
                    log(f"    Note: {note_short}")

                    if "dispatch" not in note.lower():
                        log(f"    SAFETY: No 'dispatch' in note, SKIP")
                        continue

                    if "workzone" in note.lower() or "work zone" in note.lower():
                        log(f"    SAFETY: 'workzone'/'work zone' found in note, SKIP")
                        continue

                    note_upper = note.upper()

                    owner_group = extract_owner_group(note)
                    inc_number = extract_inc_number(note)
                    print(f"    [DEBUG] OG={owner_group} | INC={inc_number} | C4={'C4' in note_upper}")

                    if is_bulk_og_change(note):
                        bulk_og = extract_bulk_og_target(note)
                        bulk_incs = extract_bulk_inc_list(note)
                        log(f"    BULK OG CHANGE: target={bulk_og} | INCs={len(bulk_incs)}")

                        if not bulk_og:
                            log(f"    Cannot parse bulk OG target, SKIP")
                            continue

                        if "C4" in bulk_og.upper():
                            log(f"    BULK OG is C4 ({bulk_og}) -> TO + complete, no dispatch")
                            btn_action = self.take_ownership(ticket_page)
                            log(f"    Button clicked: {btn_action}")

                            confirmed = self.wait_for_in_progress(ticket_page)
                            if not confirmed:
                                log(f"    TO FAILED: {code}")
                                continue
                            log(f"    TO CONFIRMED: {code}")

                            page.bring_to_front()
                            page.wait_for_timeout(1000)
                            self.browser_manager.activate_page(ticket_page)
                            try:
                                ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            ticket_page.wait_for_timeout(3000)

                            completed = self.complete_ticket(ticket_page, note="untuk permintaan dispatch ke C4_CONSUMER silahkan koordinasikan ke OG terkait")
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED (C4)")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED")
                                results.append({
                                    "request_code": code,
                                    "type": "C4_COMPLETE",
                                    "note": note,
                                })
                                self.processed_ids.add(code)
                                try:
                                    log_history(feature="DISPATCH", ticket_code=code, ticket_id=bulk_og if 'bulk_og' in locals() else "", owner_group=bulk_og if 'bulk_og' in locals() else "C4_CONSUMER", note=note, reply_sygap="untuk permintaan dispatch ke C4_CONSUMER silahkan koordinasikan ke OG terkait", biscuit_status="", biscuit_message="", status="SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                                except Exception:
                                    pass
                            else:
                                log(f"    Gagal complete ticket {code} (C4)")
                            continue

                        if not bulk_incs:
                            inc_from_page = self.wait_for_ticket_inc(ticket_page)
                            if inc_from_page:
                                bulk_incs = [inc_from_page]
                                log(f"    INC from page: {inc_from_page}")
                            else:
                                log(f"    No INCs found in note or page, SKIP")
                                continue

                        if status == "IN_PROGRESS":
                            if self.is_my_ticket(ticket_page):
                                log(f"    IN_PROGRESS, already my ticket -> proceed")
                            else:
                                log(f"    IN_PROGRESS, not my ticket -> change coordinator")
                                result = self.change_coordinator_to_me(ticket_page)
                                log(f"    Change coordinator: {result}")
                                if not result or "SAVE" not in str(result):
                                    log(f"    Failed change coordinator, SKIP")
                                    continue
                                log(f"    Coordinator changed to me, saved")
                        else:
                            if self.is_my_ticket(ticket_page):
                                log(f"    Sudah tiket saya, lanjut tanpa TO...")
                            else:
                                log(f"    Status: {status} -> TO ke saya dulu...")
                                btn_action = self.take_ownership(ticket_page)
                                log(f"    Button clicked: {btn_action}")

                                confirmed = self.wait_for_in_progress(ticket_page)
                                if not confirmed:
                                    log(f"    TO FAILED: {code}")
                                    continue
                                log(f"    TO CONFIRMED: {code}")

                        biscuit = BiscuitService(browser_manager=self.browser_manager)
                        if not biscuit.open():
                            log(f"    BISCUIT tab not found!")
                            continue

                        all_success = True
                        failed_incs = []
                        for idx, inc in enumerate(bulk_incs):
                            command = f"/dispatchticket {inc} {bulk_og}"
                            log(f"    [{idx+1}/{len(bulk_incs)}] Sending: {command}")

                            max_retries = 2
                            response = None
                            for attempt in range(1, max_retries + 1):
                                log(f"    Command sent (attempt {attempt})")
                                response = biscuit.execute(command, "INSERA")
                                log(f"    BISCUIT response: {response.status} - {response.message}")

                                if response.status != "UNKNOWN":
                                    break

                                if attempt < max_retries:
                                    log(f"    BISCUIT timeout, retrying...")
                                    biscuit.wait_for_ready()

                            if response.status == "SUCCESS":
                                log(f"    {inc} -> OK")
                            else:
                                log(f"    {inc} -> FAILED: {response.message}")
                                all_success = False
                                failed_incs.append(f"{inc}: {response.message}")

                            if idx < len(bulk_incs) - 1:
                                biscuit.wait_for_ready()

                        if all_success:
                            log(f"    All INCs dispatched successfully")
                            complete_note = "Cek Kembali"
                        else:
                            log(f"    Some INCs failed: {len(failed_incs)}")
                            complete_note = "; ".join(failed_incs)[:200]

                        page.bring_to_front()
                        page.wait_for_timeout(1000)
                        if not ticket_page.is_closed():
                            self.browser_manager.activate_page(ticket_page)
                            try:
                                ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            ticket_page.wait_for_timeout(3000)
                            completed = self.complete_ticket(ticket_page, note=complete_note)
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED")
                                results.append({
                                    "request_code": code,
                                    "type": "BULK_OG_CHANGE",
                                    "bulk_og": bulk_og,
                                    "total_incs": len(bulk_incs),
                                    "failed_incs": len(failed_incs),
                                })
                                self.processed_ids.add(code)
                                try:
                                    log_history(feature="DISPATCH", ticket_code=code, ticket_id=",".join(bulk_incs[:3]) if 'bulk_incs' in locals() else "", owner_group=bulk_og if 'bulk_og' in locals() else "", note=note if 'note' in locals() else "", reply_sygap=complete_note if 'complete_note' in locals() else "", biscuit_status="SUCCESS" if 'all_success' in locals() and all_success else "FAILED", biscuit_message=complete_note if 'complete_note' in locals() else "", status="SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                                except Exception:
                                    pass
                            else:
                                log(f"    Gagal complete ticket {code}")
                        continue

                    if owner_group:
                        log(f"    OG: {owner_group} | INC from note: {inc_number or 'N/A'}")

                        if "C4" in owner_group.upper():
                            log(f"    OG is C4 ({owner_group}) -> TO + complete, no dispatch")
                            btn_action = self.take_ownership(ticket_page)
                            log(f"    Button clicked: {btn_action}")

                            confirmed = self.wait_for_in_progress(ticket_page)
                            if not confirmed:
                                log(f"    TO FAILED: {code}")
                                continue
                            log(f"    TO CONFIRMED: {code}")

                            page.bring_to_front()
                            page.wait_for_timeout(1000)
                            self.browser_manager.activate_page(ticket_page)
                            try:
                                ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            ticket_page.wait_for_timeout(3000)

                            completed = self.complete_ticket(ticket_page, note="untuk permintaan dispatch ke C4_CONSUMER silahkan koordinasikan ke OG terkait")
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED (C4)")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED")
                                results.append({
                                    "request_code": code,
                                    "type": "C4_COMPLETE",
                                    "note": note,
                                })
                                self.processed_ids.add(code)
                                try:
                                    log_history(feature="DISPATCH", ticket_code=code, ticket_id=owner_group if 'owner_group' in locals() else "", owner_group=owner_group if 'owner_group' in locals() else "", note=note, reply_sygap="untuk permintaan dispatch ke C4_CONSUMER silahkan koordinasikan ke OG terkait", biscuit_status="", biscuit_message="", status="SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                                except Exception:
                                    pass
                            else:
                                log(f"    Gagal complete ticket {code} (C4)")
                            continue

                        if status == "IN_PROGRESS":
                            if self.is_my_ticket(ticket_page):
                                log(f"    IN_PROGRESS, already my ticket -> proceed")
                            else:
                                log(f"    IN_PROGRESS, not my ticket -> change coordinator")
                                result = self.change_coordinator_to_me(ticket_page)
                                log(f"    Change coordinator: {result}")
                                if not result or "SAVE" not in str(result):
                                    log(f"    Failed change coordinator, SKIP")
                                    continue
                                log(f"    Coordinator changed to me, saved")
                        else:
                            log(f"    Status: {status} -> TO ke saya dulu...")

                            log(f"    Taking ownership...")
                            btn_action = self.take_ownership(ticket_page)
                            log(f"    Button clicked: {btn_action}")

                            confirmed = self.wait_for_in_progress(ticket_page)
                            if not confirmed:
                                log(f"    TO FAILED: {code}")
                                continue
                            log(f"    TO CONFIRMED: {code}")

                        own_code = self.read_own_incident_code(ticket_page)
                        if not inc_number or inc_number == own_code:
                            if inc_number == own_code:
                                log(f"    INC from note == incident_code, abaikan (bukan ticket BISCUIT)")
                            log(f"    INC not in note (atau == incident_code), reading from Ticket ID field...")
                            inc_number = self.wait_for_ticket_inc(ticket_page)
                            if inc_number:
                                log(f"    INC from page: {inc_number}")
                            else:
                                log(f"    INC from page: NOT FOUND")

                        if not inc_number:
                            log(f"    INC number not found anywhere, SKIP")
                            continue

                        biscuit = BiscuitService(browser_manager=self.browser_manager)
                        if not biscuit.open():
                            log(f"    BISCUIT tab not found!")
                            continue

                        command = f"/dispatchticket {inc_number} {owner_group}"
                        log(f"    Sending: {command}")

                        max_retries = 2
                        response = None
                        for attempt in range(1, max_retries + 1):
                            log(f"    Command sent (attempt {attempt})")
                            response = biscuit.execute(command, "INSERA")
                            log(f"    BISCUIT response: {response.status} - {response.message}")

                            if response.status != "UNKNOWN":
                                break

                            if attempt < max_retries:
                                log(f"    BISCUIT timeout, retrying...")
                                biscuit.wait_for_ready()

                        if response.status == "SUCCESS":
                            log(f"    BISCUIT SUKSES! Complete ticket...")
                            complete_note = "Cek Kembali"
                        else:
                            log(f"    BISCUIT GAGAL! Complete dengan alasan error...")
                            complete_note = response.message[:200]

                        page.bring_to_front()
                        page.wait_for_timeout(1000)
                        if not ticket_page.is_closed():
                            self.browser_manager.activate_page(ticket_page)
                            try:
                                ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            ticket_page.wait_for_timeout(3000)
                            completed = self.complete_ticket(ticket_page, note=complete_note)
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED ({response.status})")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED")
                            else:
                                log(f"    Gagal complete ticket {code}")

                        total_processed += 1
                        results.append({
                            "request_code": code,
                            "owner_group": owner_group,
                            "note": note,
                            "biscuit_status": response.status,
                        })
                        self.processed_ids.add(code)
                        try:
                            log_history(feature="DISPATCH", ticket_code=code, ticket_id=inc_number if 'inc_number' in locals() else "", owner_group=owner_group if 'owner_group' in locals() else "", note=note, reply_sygap=complete_note if 'complete_note' in locals() else "", biscuit_status=response.status if 'response' in locals() and hasattr(response, 'status') else "", biscuit_message=response.message if 'response' in locals() and hasattr(response, 'message') else "", status=response.status if 'response' in locals() and hasattr(response, 'status') else "SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                        except Exception:
                            pass

                    elif "C4" in note_upper:
                        log(f"    No OG but C4 found -> TO dulu...")
                        btn_action = self.take_ownership(ticket_page)
                        log(f"    Button clicked: {btn_action}")

                        confirmed = self.wait_for_in_progress(ticket_page)
                        if not confirmed:
                            log(f"    TO FAILED: {code}")
                            continue
                        log(f"    TO CONFIRMED: {code}")

                        page.bring_to_front()
                        page.wait_for_timeout(1000)
                        self.browser_manager.activate_page(ticket_page)
                        try:
                            ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                        except Exception:
                            pass
                        ticket_page.wait_for_timeout(3000)

                        completed = self.complete_ticket(ticket_page, note="untuk permintaan dispatch ke C4_CONSUMER silahkan koordinasikan ke OG terkait")
                        if completed:
                            log(f"    Waiting COMPLETED status...")
                            is_completed = self.wait_for_completed(ticket_page)
                            if is_completed:
                                log(f"    Ticket {code} -> COMPLETED (C4)")
                            else:
                                log(f"    Ticket {code} status belum COMPLETED")
                            results.append({
                                "request_code": code,
                                "type": "C4_COMPLETE",
                                "note": note,
                            })
                            self.processed_ids.add(code)
                            try:
                                log_history(feature="DISPATCH", ticket_code=code, ticket_id="", owner_group="C4", note=note, reply_sygap="untuk permintaan dispatch ke C4_CONSUMER silahkan koordinasikan ke OG terkait", biscuit_status="", biscuit_message="", status="SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                            except Exception:
                                pass
                        else:
                            log(f"    Gagal complete ticket {code} (C4)")

                    else:
                        log(f"    No OG and no C4, SKIP")
                        continue

                except Exception as e:
                    log(f"    Error: {e}")
                finally:
                    if code not in self.processed_ids and code not in self.related_ids:
                        self.skipped_ids[code] = time.time()
                        self._save_persistent_skipped(code)
                    try:
                        if not ticket_page.is_closed():
                            ticket_page.close()
                    except Exception:
                        pass
                    self._close_extra_tabs(page, log_callback=log)
                    page.wait_for_timeout(1500)

            if processed_this_round == 0:
                log(f"No actionable tickets (all rows skipped/already processed). Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            log(f"Page done. Re-applying filter...")
            self.filter_dispatch(page)
            try:
                page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
                page.wait_for_timeout(2000)
            except Exception:
                pass

            info_after = page.locator("#requestFulfillmentTable_info").inner_text()
            if "0 entries" in info_after or "0 of 0" in info_after:
                log(f"No tickets after filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

        return results

    def process_dispatch_incident_tickets(self, log_callback=None):
        """Dispatch untuk kategori INCIDENT (tabel incidentTable di /incident)."""
        from app.services.biscuit_service import BiscuitService
        log = log_callback or (lambda msg: None)
        results = []

        page = self.navigate_to_incident_dashboard()
        log(f"Dashboard INCIDENT loaded: {page.url[:60]}")

        if not self._wait_for_sygap_login(page, log):
            return results
        if not self._wait_for_biscuit_login(log):
            return results
        # pastikan sudah di /incident setelah login (kadang redirect ke landing)
        try:
            if "/incident" not in page.url.lower():
                page = self.navigate_to_incident_dashboard()
                log(f"Dashboard INCIDENT reloaded: {page.url[:60]}")
                if not self._wait_for_sygap_login(page, log):
                    return results
                if not self._wait_for_biscuit_login(log):
                    return results
        except Exception:
            pass

        self.filter_dispatch_incident(page)
        log("Filtered: dispatch INCIDENT")

        table_id = self._get_dispatch_table_id(page)
        try:
            page.wait_for_selector(f"#{table_id} tbody tr", timeout=15000)
        except Exception:
            log("No INCIDENT tickets found after filter")
            return results
        page.wait_for_timeout(2000)

        total_processed = 0

        while True:
            table_id = self._get_dispatch_table_id(page)
            try:
                info_text = page.locator(f"#{table_id}_info").inner_text()
            except Exception:
                info_text = ""
            log(f"--- {info_text} [{table_id}] ---")

            if self._stopped():
                log("STOP requested - aborting scan")
                return results

            rows = self.get_ticket_rows_generic(page)
            log(f"Found {len(rows)} row(s) [incident]")

            if len(rows) == 0:
                log(f"No INCIDENT tickets found. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            processed_this_round = 0

            for i, row_info in enumerate(rows):
                code = row_info["request_code"]
                status = row_info["status"]

                if self._stopped():
                    log("STOP requested - aborting scan")
                    return results

                if status in ("COMPLETED", "COMPLETE", "CLOSED", "RESOLVED"):
                    log(f"  [{i+1}] {code} - SKIP (status: {status})")
                    continue

                if code in self.processed_ids:
                    log(f"  [{i+1}] {code} - SKIP (already processed)")
                    continue

                if self._is_persistent_skipped(code):
                    log(f"  [{i+1}] {code} - SKIP (permanen, sudah pernah di-skip — tidak dibuka lagi)")
                    continue
                if code in self.skipped_ids and (time.time() - self.skipped_ids[code]) < LOOP_INTERVAL:
                    log(f"  [{i+1}] {code} - SKIP (recently skipped, tunggu {LOOP_INTERVAL}s)")
                    continue

                total_processed += 1
                processed_this_round += 1
                log(f"  [{i+1}/{len(rows)}] Opening {code} [INCIDENT]...")

                ticket_page = self.click_ticket(page, row_info)
                if ticket_page is None:
                    log(f"    Failed to open {code}")
                    self.skipped_ids[code] = time.time()
                    self._save_persistent_skipped(code)
                    continue

                try:
                    quick_status = self.read_ticket_status(ticket_page)
                    if quick_status and any(s in quick_status for s in ("COMPLETED", "RESOLVED")):
                        log(f"    SKIP: tiket sudah COMPLETED/RESOLVED di form")
                        continue

                    if self.is_coordinator_in_skip_list(ticket_page):
                        log(f"    SKIP: koordinator di daftar skip (Rizky Senja Budiman/CRS2018192)")
                        continue

                    note = self.read_ticket_note(ticket_page)
                    note_short = note[:100] + "..." if len(note) > 100 else note
                    log(f"    Note: {note_short}")

                    if "dispatch" not in note.lower():
                        log(f"    SAFETY: No 'dispatch' in note, SKIP")
                        continue

                    if "workzone" in note.lower() or "work zone" in note.lower():
                        log(f"    SAFETY: 'workzone'/'work zone' found in note, SKIP")
                        continue

                    note_upper = note.upper()

                    owner_group = extract_owner_group(note)
                    inc_number = extract_inc_number(note)
                    print(f"    [DEBUG] OG={owner_group} | INC={inc_number} | C4={'C4' in note_upper}")

                    if is_bulk_og_change(note):
                        bulk_og = extract_bulk_og_target(note)
                        bulk_incs = extract_bulk_inc_list(note)
                        log(f"    BULK OG CHANGE: target={bulk_og} | INCs={len(bulk_incs)}")

                        if not bulk_og:
                            log(f"    Cannot parse bulk OG target, SKIP")
                            continue

                        if "C4" in bulk_og.upper():
                            log(f"    BULK OG is C4 ({bulk_og}) -> TO + complete, no dispatch")
                            btn_action = self.take_ownership(ticket_page)
                            log(f"    Button clicked: {btn_action}")
                            confirmed = self.wait_for_in_progress(ticket_page)
                            if not confirmed:
                                log(f"    TO FAILED: {code}")
                                continue
                            log(f"    TO CONFIRMED: {code}")
                            page.bring_to_front()
                            page.wait_for_timeout(1000)
                            self.browser_manager.activate_page(ticket_page)
                            try:
                                ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            ticket_page.wait_for_timeout(3000)
                            completed = self.complete_ticket(ticket_page, note="untuk permintaan dispatch ke C4_CONSUMER silahkan koordinasikan ke OG terkait")
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED (C4)")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED")
                                results.append({"request_code": code, "type": "C4_COMPLETE", "note": note})
                                try:
                                    _rr = response if 'response' in locals() and hasattr(response, 'status') else None
                                    log_history(feature="DISPATCH_INCIDENT", ticket_code=code, ticket_id=locals().get("wo_number","") or locals().get("inc_number","") or locals().get("ticket_id","") or locals().get("service_id","") or "", owner_group=locals().get("owner_group","") or locals().get("bulk_og","") or "", note=locals().get("note",""), reply_sygap=locals().get("complete_note","") or locals().get("reply_note","") or "Cek Kembali", biscuit_status=_rr.status if _rr else "", biscuit_message=_rr.message if _rr else "", status="SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                                except Exception:
                                    pass
                                self.processed_ids.add(code)
                            else:
                                log(f"    Gagal complete ticket {code} (C4)")
                            continue

                        if not bulk_incs:
                            inc_from_page = self.wait_for_ticket_inc(ticket_page)
                            if inc_from_page:
                                bulk_incs = [inc_from_page]
                                log(f"    INC from page: {inc_from_page}")
                            else:
                                log(f"    No INCs found in note or page, SKIP")
                                continue

                        if status == "IN_PROGRESS":
                            if self.is_my_ticket(ticket_page):
                                log(f"    IN_PROGRESS, already my ticket -> proceed")
                            else:
                                log(f"    IN_PROGRESS, not my ticket -> change coordinator")
                                result = self.change_coordinator_to_me(ticket_page)
                                log(f"    Change coordinator: {result}")
                                if not result or "SAVE" not in str(result):
                                    log(f"    Failed change coordinator, SKIP")
                                    continue
                                log(f"    Coordinator changed to me, saved")
                        else:
                            if self.is_my_ticket(ticket_page):
                                log(f"    Sudah tiket saya, lanjut tanpa TO...")
                            else:
                                log(f"    Status: {status} -> TO ke saya dulu...")
                                btn_action = self.take_ownership(ticket_page)
                                log(f"    Button clicked: {btn_action}")
                                confirmed = self.wait_for_in_progress(ticket_page)
                                if not confirmed:
                                    log(f"    TO FAILED: {code}")
                                    continue
                                log(f"    TO CONFIRMED: {code}")

                        biscuit = BiscuitService(browser_manager=self.browser_manager)
                        if not biscuit.open():
                            log(f"    BISCUIT tab not found!")
                            continue
                        all_success = True
                        failed_incs = []
                        for idx, inc in enumerate(bulk_incs):
                            command = f"/dispatchticket {inc} {bulk_og}"
                            log(f"    [{idx+1}/{len(bulk_incs)}] Sending: {command}")
                            max_retries = 2
                            response = None
                            for attempt in range(1, max_retries + 1):
                                log(f"    Command sent (attempt {attempt})")
                                response = biscuit.execute(command, "INSERA")
                                log(f"    BISCUIT response: {response.status} - {response.message}")
                                if response.status != "UNKNOWN":
                                    break
                                if attempt < max_retries:
                                    log(f"    BISCUIT timeout, retrying...")
                                    biscuit.wait_for_ready()
                            if response.status == "SUCCESS":
                                log(f"    {inc} -> OK")
                            else:
                                log(f"    {inc} -> FAILED: {response.message}")
                                all_success = False
                                failed_incs.append(f"{inc}: {response.message}")
                            if idx < len(bulk_incs) - 1:
                                biscuit.wait_for_ready()
                        if all_success:
                            log(f"    All INCs dispatched successfully")
                            complete_note = "Cek Kembali"
                        else:
                            log(f"    Some INCs failed: {len(failed_incs)}")
                            complete_note = "; ".join(failed_incs)[:200]
                        page.bring_to_front()
                        page.wait_for_timeout(1000)
                        if not ticket_page.is_closed():
                            self.browser_manager.activate_page(ticket_page)
                            try:
                                ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            ticket_page.wait_for_timeout(3000)
                            completed = self.complete_ticket(ticket_page, note=complete_note)
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED")
                                results.append({"request_code": code, "type": "BULK_OG_CHANGE", "bulk_og": bulk_og, "total_incs": len(bulk_incs), "failed_incs": len(failed_incs)})
                                try:
                                    _rr = response if 'response' in locals() and hasattr(response, 'status') else None
                                    log_history(feature="DISPATCH_INCIDENT", ticket_code=code, ticket_id=locals().get("wo_number","") or locals().get("inc_number","") or locals().get("ticket_id","") or locals().get("service_id","") or "", owner_group=locals().get("owner_group","") or locals().get("bulk_og","") or "", note=locals().get("note",""), reply_sygap=locals().get("complete_note","") or locals().get("reply_note","") or "Cek Kembali", biscuit_status=_rr.status if _rr else "", biscuit_message=_rr.message if _rr else "", status="SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                                except Exception:
                                    pass
                                self.processed_ids.add(code)
                            else:
                                log(f"    Gagal complete ticket {code}")
                        continue

                    if owner_group:
                        log(f"    OG: {owner_group} | INC from note: {inc_number or 'N/A'}")
                        if "C4" in owner_group.upper():
                            log(f"    OG is C4 ({owner_group}) -> TO + complete, no dispatch")
                            btn_action = self.take_ownership(ticket_page)
                            log(f"    Button clicked: {btn_action}")
                            confirmed = self.wait_for_in_progress(ticket_page)
                            if not confirmed:
                                log(f"    TO FAILED: {code}")
                                continue
                            log(f"    TO CONFIRMED: {code}")
                            page.bring_to_front()
                            page.wait_for_timeout(1000)
                            self.browser_manager.activate_page(ticket_page)
                            try:
                                ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            ticket_page.wait_for_timeout(3000)
                            completed = self.complete_ticket(ticket_page, note="untuk permintaan dispatch ke C4_CONSUMER silahkan koordinasikan ke OG terkait")
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED (C4)")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED")
                                results.append({"request_code": code, "type": "C4_COMPLETE", "note": note})
                                try:
                                    _rr = response if 'response' in locals() and hasattr(response, 'status') else None
                                    log_history(feature="DISPATCH_INCIDENT", ticket_code=code, ticket_id=locals().get("wo_number","") or locals().get("inc_number","") or locals().get("ticket_id","") or locals().get("service_id","") or "", owner_group=locals().get("owner_group","") or locals().get("bulk_og","") or "", note=locals().get("note",""), reply_sygap=locals().get("complete_note","") or locals().get("reply_note","") or "Cek Kembali", biscuit_status=_rr.status if _rr else "", biscuit_message=_rr.message if _rr else "", status="SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                                except Exception:
                                    pass
                                self.processed_ids.add(code)
                            else:
                                log(f"    Gagal complete ticket {code} (C4)")
                            continue
                        if status == "IN_PROGRESS":
                            if self.is_my_ticket(ticket_page):
                                log(f"    IN_PROGRESS, already my ticket -> proceed")
                            else:
                                log(f"    IN_PROGRESS, not my ticket -> change coordinator")
                                result = self.change_coordinator_to_me(ticket_page)
                                log(f"    Change coordinator: {result}")
                                if not result or "SAVE" not in str(result):
                                    log(f"    Failed change coordinator, SKIP")
                                    continue
                                log(f"    Coordinator changed to me, saved")
                        else:
                            log(f"    Status: {status} -> TO ke saya dulu...")
                            log(f"    Taking ownership...")
                            btn_action = self.take_ownership(ticket_page)
                            log(f"    Button clicked: {btn_action}")
                            confirmed = self.wait_for_in_progress(ticket_page)
                            if not confirmed:
                                log(f"    TO FAILED: {code}")
                                continue
                            log(f"    TO CONFIRMED: {code}")
                        own_code = self.read_own_incident_code(ticket_page)
                        if not inc_number or inc_number == own_code:
                            if inc_number == own_code:
                                log(f"    INC from note == incident_code, abaikan (bukan ticket BISCUIT)")
                            log(f"    INC not in note (atau == incident_code), reading from Ticket ID field...")
                            inc_number = self.wait_for_ticket_inc(ticket_page)
                            if inc_number:
                                log(f"    INC from page: {inc_number}")
                            else:
                                log(f"    INC from page: NOT FOUND")
                        if not inc_number:
                            log(f"    INC number not found anywhere, SKIP")
                            continue
                        biscuit = BiscuitService(browser_manager=self.browser_manager)
                        if not biscuit.open():
                            log(f"    BISCUIT tab not found!")
                            continue
                        command = f"/dispatchticket {inc_number} {owner_group}"
                        log(f"    Sending: {command}")
                        max_retries = 2
                        response = None
                        for attempt in range(1, max_retries + 1):
                            log(f"    Command sent (attempt {attempt})")
                            response = biscuit.execute(command, "INSERA")
                            log(f"    BISCUIT response: {response.status} - {response.message}")
                            if response.status != "UNKNOWN":
                                break
                            if attempt < max_retries:
                                log(f"    BISCUIT timeout, retrying...")
                                biscuit.wait_for_ready()
                        if response.status == "SUCCESS":
                            log(f"    BISCUIT SUKSES! Complete ticket...")
                            complete_note = "Cek Kembali"
                        else:
                            log(f"    BISCUIT GAGAL! Complete dengan alasan error...")
                            complete_note = response.message[:200]
                        page.bring_to_front()
                        page.wait_for_timeout(1000)
                        if not ticket_page.is_closed():
                            self.browser_manager.activate_page(ticket_page)
                            try:
                                ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            ticket_page.wait_for_timeout(3000)
                            completed = self.complete_ticket(ticket_page, note=complete_note)
                            if completed:
                                log(f"    Waiting COMPLETED status...")
                                is_completed = self.wait_for_completed(ticket_page)
                                if is_completed:
                                    log(f"    Ticket {code} -> COMPLETED ({response.status})")
                                else:
                                    log(f"    Ticket {code} status belum COMPLETED")
                            else:
                                log(f"    Gagal complete ticket {code}")
                        total_processed += 1
                        results.append({"request_code": code, "owner_group": owner_group, "note": note, "biscuit_status": response.status})
                        try:
                            _rr = response if 'response' in locals() and hasattr(response, 'status') else None
                            log_history(feature="DISPATCH_INCIDENT", ticket_code=code, ticket_id=locals().get("wo_number","") or locals().get("inc_number","") or locals().get("ticket_id","") or locals().get("service_id","") or "", owner_group=locals().get("owner_group","") or locals().get("bulk_og","") or "", note=locals().get("note",""), reply_sygap=locals().get("complete_note","") or locals().get("reply_note","") or "Cek Kembali", biscuit_status=_rr.status if _rr else "", biscuit_message=_rr.message if _rr else "", status="SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                        except Exception:
                            pass
                        self.processed_ids.add(code)
                    elif "C4" in note_upper:
                        log(f"    No OG but C4 found -> TO dulu...")
                        btn_action = self.take_ownership(ticket_page)
                        log(f"    Button clicked: {btn_action}")
                        confirmed = self.wait_for_in_progress(ticket_page)
                        if not confirmed:
                            log(f"    TO FAILED: {code}")
                            continue
                        log(f"    TO CONFIRMED: {code}")
                        page.bring_to_front()
                        page.wait_for_timeout(1000)
                        self.browser_manager.activate_page(ticket_page)
                        try:
                            ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                        except Exception:
                            pass
                        ticket_page.wait_for_timeout(3000)
                        completed = self.complete_ticket(ticket_page, note="untuk permintaan dispatch ke C4_CONSUMER silahkan koordinasikan ke OG terkait")
                        if completed:
                            log(f"    Waiting COMPLETED status...")
                            is_completed = self.wait_for_completed(ticket_page)
                            if is_completed:
                                log(f"    Ticket {code} -> COMPLETED (C4)")
                            else:
                                log(f"    Ticket {code} status belum COMPLETED")
                            results.append({"request_code": code, "type": "C4_COMPLETE", "note": note})
                            try:
                                _rr = response if 'response' in locals() and hasattr(response, 'status') else None
                                log_history(feature="DISPATCH_INCIDENT", ticket_code=code, ticket_id=locals().get("wo_number","") or locals().get("inc_number","") or locals().get("ticket_id","") or locals().get("service_id","") or "", owner_group=locals().get("owner_group","") or locals().get("bulk_og","") or "", note=locals().get("note",""), reply_sygap=locals().get("complete_note","") or locals().get("reply_note","") or "Cek Kembali", biscuit_status=_rr.status if _rr else "", biscuit_message=_rr.message if _rr else "", status="SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                            except Exception:
                                pass
                            self.processed_ids.add(code)
                        else:
                            log(f"    Gagal complete ticket {code} (C4)")
                    else:
                        log(f"    No OG and no C4, SKIP")
                        continue
                except Exception as e:
                    log(f"    Error: {e}")
                finally:
                    if code not in self.processed_ids and code not in self.related_ids:
                        self.skipped_ids[code] = time.time()
                        self._save_persistent_skipped(code)
                    try:
                        if not ticket_page.is_closed():
                            ticket_page.close()
                    except Exception:
                        pass
                    self._close_extra_tabs(page, log_callback=log)
                    page.wait_for_timeout(1500)

            if processed_this_round == 0:
                log(f"No actionable INCIDENT tickets (all rows skipped/already processed). Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            log(f"Page done. Re-applying filter...")
            self.filter_dispatch_incident(page)
            try:
                table_id = self._get_dispatch_table_id(page)
                page.wait_for_selector(f"#{table_id} tbody tr", timeout=15000)
                page.wait_for_timeout(2000)
            except Exception:
                pass
            try:
                table_id = self._get_dispatch_table_id(page)
                info_after = page.locator(f"#{table_id}_info").inner_text()
                if "0 entries" in info_after or "0 of 0" in info_after:
                    log(f"No INCIDENT tickets after filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                    return results
            except Exception:
                pass
        return results

    def process_change_service_id_tickets(self, log_callback=None):
        from app.services.biscuit_service import BiscuitService
        log = log_callback or (lambda msg: None)
        results = []

        page = self.navigate_to_dashboard()
        log(f"Dashboard loaded: {page.url[:60]}")

        self.filter_change_service_id(page)
        log("Filtered: change service id (note 'Service')")

        try:
            page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
        except Exception:
            log("No tickets found after filter")
            return results
        page.wait_for_timeout(2000)

        total_processed = 0

        while True:
            info_text = page.locator("#requestFulfillmentTable_info").inner_text()
            log(f"--- {info_text} ---")

            if self._stopped():
                log("STOP requested - aborting scan")
                return results

            rows = self.get_ticket_rows(page)
            log(f"Found {len(rows)} row(s)")

            if len(rows) == 0:
                log(f"No tickets found. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            processed_this_round = 0

            for i, row_info in enumerate(rows):
                code = row_info["request_code"]
                status = row_info["status"]

                if self._stopped():
                    log("STOP requested - aborting scan")
                    return results

                if status in ("COMPLETED", "COMPLETE"):
                    log(f"  [{i+1}] {code} - SKIP (status: {status})")
                    continue

                if code in self.processed_ids:
                    log(f"  [{i+1}] {code} - SKIP (already processed)")
                    continue

                total_processed += 1
                log(f"  [{i+1}/{len(rows)}] Opening {code}...")

                ticket_page = self.click_ticket(page, row_info)
                if ticket_page is None:
                    log(f"    Failed to open {code}")
                    continue

                try:
                    quick_status = self.read_ticket_status(ticket_page)
                    if quick_status and "COMPLETED" in quick_status:
                        log(f"    SKIP: tiket sudah COMPLETED di form")
                        continue

                    if self.is_coordinator_in_skip_list(ticket_page):
                        log(f"    SKIP: koordinator di daftar skip (Rizky Senja Budiman/CRS2018192)")
                        continue

                    note = self.read_ticket_note(ticket_page)
                    note_short = note[:100] + "..." if len(note) > 100 else note
                    log(f"    Note: {note_short}")

                    if "service" not in note.lower():
                        log(f"    SAFETY: No 'service' in note, SKIP")
                        continue

                    service_id = extract_service_id(note)
                    service_type = extract_service_type(note)
                    inc_number = extract_inc_number(note)

                    if not service_id and not service_type:
                        log(f"    Neither Service ID nor Service Type found in note, SKIP")
                        continue

                    if not inc_number:
                        log(f"    INC not in note, reading from ticket page...")
                        inc_number = self.wait_for_ticket_inc(ticket_page)
                        if inc_number:
                            log(f"    INC from page: {inc_number}")
                        else:
                            log(f"    INC from page: NOT FOUND")

                    if not inc_number:
                        log(f"    INC number not found anywhere, SKIP")
                        continue

                    if service_id and service_type:
                        log(f"    Note: Service ID dan Service Type keduanya terdeteksi -> hanya Service ID diproses (Service Type sepaket)")

                    if service_id:
                        log(f"    Target: CHANGE SERVICE ID -> INC={inc_number} | Service ID={service_id}")
                    else:
                        log(f"    Target: SERVICE TYPE REJECTED -> INC={inc_number} | Service Type={service_type} (sepaket dengan Service ID)")

                    if status == "IN_PROGRESS":
                        if self.is_my_ticket(ticket_page):
                            log(f"    IN_PROGRESS, already my ticket -> proceed")
                        else:
                            log(f"    IN_PROGRESS, not my ticket -> change coordinator")
                            result = self.change_coordinator_to_me(ticket_page)
                            log(f"    Change coordinator: {result}")
                            if not result or "SAVE" not in str(result):
                                log(f"    Failed change coordinator, SKIP")
                                continue
                            log(f"    Coordinator changed to me, saved")
                    else:
                        if self.is_my_ticket(ticket_page):
                            log(f"    Sudah tiket saya, lanjut tanpa TO...")
                        else:
                            log(f"    Status: {status} -> TO ke saya dulu...")
                            btn_action = self.take_ownership(ticket_page)
                            log(f"    Button clicked: {btn_action}")

                            confirmed = self.wait_for_in_progress(ticket_page)
                            if not confirmed:
                                log(f"    TO FAILED: {code}")
                                continue
                            log(f"    TO CONFIRMED: {code}")

                    response = None
                    if service_id:
                        biscuit = BiscuitService(browser_manager=self.browser_manager)
                        if not biscuit.open():
                            log(f"    BISCUIT tab not found!")
                            continue

                        command = f"/changeserviceid {inc_number} {service_id}"
                        log(f"    Sending via BISCUIT UI: {command}")

                        max_retries = 2
                        for attempt in range(1, max_retries + 1):
                            log(f"    Command sent via UI (attempt {attempt})")
                            response = biscuit.execute_ui(command, "INSERA")
                            log(f"    BISCUIT response: {response.status} - {response.message}")

                            if response.status != "UNKNOWN":
                                break

                            if attempt < max_retries:
                                log(f"    BISCUIT timeout, retrying...")
                                biscuit.wait_for_ready()
                    else:
                        # Service Type sudah sepaket dengan Service ID -> tidak dikerjakan, complete dengan penolakan
                        rejection_msg = "service type sudah sepaket dengan service ID, maka dari itu tidak dapat kami penuhi, silahkan request perubahan service ID"
                        log(f"    Service Type request -> tidak dikerjakan (sepaket dengan Service ID)")
                        log(f"    Complete dengan penolakan: {rejection_msg}")
                        from app.models.response import Response
                        response = Response(status="REJECTED", message=rejection_msg)

                    if response and response.status == "SUCCESS":
                        log(f"    EKSEKUSI SUKSES! Complete ticket...")
                        complete_note = "Cek Kembali"
                    elif response and response.status == "REJECTED":
                        log(f"    SERVICE TYPE DITOLAK - Complete dengan note penolakan...")
                        complete_note = response.message[:500]
                    else:
                        err_msg = response.message if response else "Unknown error"
                        log(f"    EKSEKUSI GAGAL! Complete dengan alasan error...")
                        complete_note = err_msg[:200]

                    page.bring_to_front()
                    page.wait_for_timeout(1000)
                    if not ticket_page.is_closed():
                        self.browser_manager.activate_page(ticket_page)
                        try:
                            ticket_page.reload(wait_until="domcontentloaded", timeout=15000)
                        except Exception:
                            pass
                        ticket_page.wait_for_timeout(3000)
                        completed = self.complete_ticket(ticket_page, note=complete_note, log_callback=log)
                        if completed:
                            log(f"    Waiting COMPLETED status...")
                            is_completed = self.wait_for_completed(ticket_page)
                            if is_completed:
                                log(f"    Ticket {code} -> COMPLETED ({response.status if response else 'UNKNOWN'})")
                            else:
                                log(f"    Ticket {code} status belum COMPLETED")
                        else:
                            log(f"    Gagal complete ticket {code}")

                    processed_this_round += 1
                    results.append({
                        "request_code": code,
                        "inc_number": inc_number,
                        "service_id": service_id,
                        "service_type": service_type,
                        "note": note,
                        "status": response.status if response else "FAILED",
                    })
                    try:
                        _rr = response if 'response' in locals() and hasattr(response, 'status') else None
                        log_history(feature="CHANGE_SERVICE_ID", ticket_code=code, ticket_id=locals().get("wo_number","") or locals().get("inc_number","") or locals().get("ticket_id","") or locals().get("service_id","") or "", owner_group=locals().get("owner_group","") or locals().get("bulk_og","") or "", note=locals().get("note",""), reply_sygap=locals().get("complete_note","") or locals().get("reply_note","") or "Cek Kembali", biscuit_status=_rr.status if _rr else "", biscuit_message=_rr.message if _rr else "", status="SUCCESS", solver_id=USER_ID, tgl_masuk=self.read_ticket_created_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "", tgl_selesai=self.read_ticket_selesai_date(ticket_page) if 'ticket_page' in locals() and ticket_page and not ticket_page.is_closed() else "")
                    except Exception:
                        pass
                    self.processed_ids.add(code)

                except Exception as e:
                    log(f"    Error: {e}")
                finally:
                    if code not in self.processed_ids and code not in self.related_ids:
                        self.skipped_ids[code] = time.time()
                        self._save_persistent_skipped(code)
                    try:
                        if not ticket_page.is_closed():
                            ticket_page.close()
                    except Exception:
                        pass
                    self._close_extra_tabs(page, log_callback=log)
                    page.wait_for_timeout(1500)

            if processed_this_round == 0:
                log(f"No actionable tickets (all rows skipped/already processed). Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

            log(f"Page done. Re-applying filter...")
            self.filter_change_service_id(page)
            try:
                page.wait_for_selector("#requestFulfillmentTable tbody tr", timeout=15000)
                page.wait_for_timeout(2000)
            except Exception:
                pass

            info_after = page.locator("#requestFulfillmentTable_info").inner_text()
            if "0 entries" in info_after or "0 of 0" in info_after:
                log(f"No tickets after filter. Waiting {LOOP_INTERVAL // 60} minutes...")
                return results

        return results