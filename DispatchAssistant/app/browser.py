from playwright.sync_api import sync_playwright
import subprocess
import socket
import time
import os


class BrowserManager:

    def __init__(self, cdp_port=9222):

        self.cdp_port = cdp_port
        self.playwright = None
        self.browser = None
        self.connected = False
        self.chrome_process = None

        self.cache = {
            "dashboard": None,
            "incident_dashboard": None,
            "biscuit": None,
            "ticket": None,
        }

    # ==================================================
    # Check Chrome CDP Running
    # ==================================================

    def is_chrome_running(self):

        s = socket.socket()

        try:

            s.connect(("127.0.0.1", self.cdp_port))
            s.close()
            return True

        except Exception:

            return False

    # ==================================================
    # Launch Chrome with CDP
    # ==================================================

    def launch(self, chrome_path=None, profile_dir=None, log_callback=None):

        log = log_callback or (lambda msg: None)

        if self.is_chrome_running():
            log(f"Chrome CDP port {self.cdp_port} sudah jalan.")
            return True

        from config.settings import CHROME, CHROME_PROFILES

        if chrome_path is None:
            chrome_path = CHROME

        if profile_dir is None:
            profile_dir = CHROME_PROFILES.get(self.cdp_port, f"C:\\ChromeDebug_{self.cdp_port}")

        os.makedirs(profile_dir, exist_ok=True)

        log(f"Launching Chrome on port {self.cdp_port}...")
        log(f"Profile: {profile_dir}")

        args = [
            chrome_path,
            f"--remote-debugging-port={self.cdp_port}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-default-apps",
            "--disable-popup-blocking",
            "--disable-extensions",
        ]

        # Buka langsung halaman kerja supaya window tidak about:blank
        # (dan sesi login mudah dicek/diisi manual).
        try:
            from config.settings import DASHBOARD_URL, INCIDENT_DASHBOARD_URL, CHROME_PORTS

            if self.cdp_port == CHROME_PORTS.get("DISPATCH_INCIDENT"):
                args.append(INCIDENT_DASHBOARD_URL)
            else:
                args.append(DASHBOARD_URL)
        except Exception:
            pass

        try:
            self.chrome_process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            log(f"ERROR: Chrome tidak ditemukan: {chrome_path}")
            return False
        except Exception as e:
            log(f"ERROR: Gagal launch Chrome: {e}")
            return False

        log(f"Menunggu Chrome CDP ready...")
        for i in range(30):
            time.sleep(1)
            if self.is_chrome_running():
                log(f"Chrome CDP ready! (port {self.cdp_port})")
                return True
            if i % 5 == 4:
                log(f"  waiting... ({i+1}s)")

        log(f"ERROR: Chrome CDP tidak ready setelah 30 detik")
        return False

    # ==================================================
    # Connect (CDP only, TANPA launch Chrome)
    # ==================================================

    def connect(self):

        if self.connected and self.browser:

            try:

                _ = self.browser.contexts
                return self.browser

            except Exception:

                self.connected = False
                self.browser = None

        if not self.is_chrome_running():

            raise Exception(
                f"Chrome CDP belum berjalan di port {self.cdp_port}.\n"
                f"Jalankan: start_browser.bat\n"
                f"atau buka Chrome dengan --remote-debugging-port={self.cdp_port}"
            )

        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{self.cdp_port}"
        )

        self.connected = True

        for context in self.browser.contexts:

            context.set_default_timeout(10000)

        self.refresh_cache()

        return self.browser

    def connect_to(self, port):
        """Sambungkan ke port CDP lain pakai Playwright yang SAMA.

        Dipakai saat satu ReportService butuh membaca dua profil Chrome
        berbeda (mis. TO untuk Incident, DISPATCH untuk Request) tanpa
        membuat dua instance `sync_playwright()` di thread yang sama
        (yang memicu error "Sync API inside asyncio loop").
        """
        # Sudah terhubung ke port yang sama -> jangan sambung ulang (menghindari
        # dua session CDP ke browser yang sama yang bikin tabel tidak load).
        if self.connected and self.cdp_port == port and self.browser is not None:
            try:
                _ = self.browser.contexts
                return self.browser
            except Exception:
                pass
        try:
            s = socket.socket()
            s.connect(("127.0.0.1", port))
            s.close()
        except Exception:
            raise Exception(
                f"Chrome CDP belum berjalan di port {port}.\n"
                f"Jalankan Chrome dengan --remote-debugging-port={port}"
            )

        if getattr(self, "playwright", None) is None:
            self.playwright = sync_playwright().start()
        self.cdp_port = port
        self.browser = self.playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{port}"
        )
        self.connected = True
        for context in self.browser.contexts:
            context.set_default_timeout(10000)
        self.refresh_cache()
        return self.browser

    # ==================================================
    # Disconnect
    # ==================================================

    def disconnect(self):

        self.cache = {
            "dashboard": None,
            "incident_dashboard": None,
            "biscuit": None,
            "ticket": None,
        }

        if self.browser:

            try:
                self.browser.close()
            except Exception:
                pass

            self.browser = None

        if self.playwright:

            try:
                self.playwright.stop()
            except Exception:
                pass

            self.playwright = None

        self.connected = False

    # ==================================================
    # Is Connected
    # ==================================================

    def is_connected(self):

        if not self.connected or not self.browser:
            return False

        try:

            _ = self.browser.contexts
            return True

        except Exception:

            self.connected = False
            return False

    # ==================================================
    # Get All Pages
    # ==================================================

    def get_all_pages(self):

        if not self.is_connected():
            return []

        result = []

        for context in self.browser.contexts:

            for page in context.pages:

                try:

                    _ = page.url
                    result.append(page)

                except Exception:
                    continue

        return result

    # ==================================================
    # Get Pages (semua tab kecuali about:blank murni)
    # ==================================================

    def get_pages(self):

        pages = []

        for page in self.get_all_pages():

            try:

                url = page.url

                if url:

                    pages.append(page)

            except Exception:
                continue

        return pages

    # ==================================================
    # Is Page Alive
    # ==================================================

    def is_page_alive(self, page):

        if page is None:
            return False

        try:

            if page.is_closed():
                return False

            _ = page.url
            return True

        except Exception:
            return False

    # ==================================================
    # Refresh Cache
    # ==================================================

    def refresh_cache(self):

        self.cache = {
            "dashboard": None,
            "incident_dashboard": None,
            "biscuit": None,
            "ticket": None,
            "insera_gamas": None,
        }

        for page in self.get_pages():

            try:

                url = page.url.lower()

                if (
                    "sygap.telkom.co.id" in url
                    and "/req_fulfillment" in url
                    and "/form/" not in url
                ):

                    self.cache["dashboard"] = page

                elif (
                    "sygap.telkom.co.id" in url
                    and "/incident" in url
                    and "/form/" not in url
                ):

                    self.cache["incident_dashboard"] = page

                elif (
                    "sygap.telkom.co.id" in url
                    and "/form/" in url
                ):

                    self.cache["ticket"] = page

                elif "biscuit-dashboard" in url:

                    self.cache["biscuit"] = page

                elif "oss-incident" in url or "insera" in url:

                    self.cache["insera_gamas"] = page

            except Exception:
                continue

    # ==================================================
    # Dashboard
    # ==================================================

    def get_dashboard_page(self):

        page = self.cache.get("dashboard")

        if self.is_page_alive(page):
            return page

        self.refresh_cache()
        return self.cache.get("dashboard")

    def get_incident_dashboard_page(self):

        page = self.cache.get("incident_dashboard")

        if self.is_page_alive(page):
            return page

        self.refresh_cache()
        page = self.cache.get("incident_dashboard")
        if page and self.is_page_alive(page):
            return page
        # fallback: SYGAP tab masih di /login (belum ke /incident) — tetap anggap dashboard
        for p in self.get_pages():
            try:
                if "sygap.telkom.co.id" in p.url.lower():
                    return p
            except Exception:
                continue
        return None

    # ==================================================
    # Active Ticket
    # ==================================================

    def get_active_ticket_page(self):

        self.refresh_cache()
        return self.cache.get("ticket")

    # ==================================================
    # Biscuit
    # ==================================================

    def get_biscuit_page(self):

        page = self.cache.get("biscuit")

        if self.is_page_alive(page):
            return page

        self.refresh_cache()
        return self.cache.get("biscuit")

    # ==================================================
    # INSERA Gamas
    # ==================================================

    def get_insera_gamas_page(self):

        page = self.cache.get("insera_gamas")

        if self.is_page_alive(page):
            return page

        self.refresh_cache()
        return self.cache.get("insera_gamas")

    # ==================================================
    # Activate Page
    # ==================================================

    def activate_page(self, page):

        if not self.is_page_alive(page):
            return False

        try:

            page.bring_to_front()
            page.wait_for_timeout(500)
            return True

        except Exception:
            return False

    # ==================================================
    # Open URL in new tab
    # ==================================================

    def open_url(self, url):

        if not self.is_connected():
            return None

        try:
            context = self.browser.contexts[0]
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            self.refresh_cache()
            return page
        except Exception:
            return None

    # ==================================================
    # Open SYGAP + BISCUIT tabs (auto after launch)
    # ==================================================

    def open_required_tabs(self, log_callback=None):

        log = log_callback or (lambda msg: None)

        from config.settings import DASHBOARD_URL, BISCUIT_URL

        existing = self.get_pages()
        has_sygap = False
        has_biscuit = False

        for p in existing:
            try:
                url = p.url.lower()
                if "sygap.telkom.co.id" in url:
                    has_sygap = True
                if "biscuit-dashboard" in url:
                    has_biscuit = True
            except Exception:
                continue

        if not has_sygap:
            log(f"Opening SYGAP: {DASHBOARD_URL[:50]}...")
            page = self.open_url(DASHBOARD_URL)
            if page:
                log("SYGAP tab opened.")
            else:
                log("WARNING: Gagal buka SYGAP")

        if not has_biscuit:
            log(f"Opening BISCUIT: {BISCUIT_URL[:50]}...")
            page = self.open_url(BISCUIT_URL)
            if page:
                log("BISCUIT tab opened.")
            else:
                log("WARNING: Gagal buka BISCUIT")

        self.refresh_cache()

        if has_sygap and has_biscuit:
            log("SYGAP & BISCUIT tabs already open.")
        elif has_sygap:
            log("BISCUIT tab opened. SYGAP already open.")
        elif has_biscuit:
            log("SYGAP tab opened. BISCUIT already open.")

    def open_required_tabs_incident(self, log_callback=None):

        log = log_callback or (lambda msg: None)

        from config.settings import INCIDENT_DASHBOARD_URL, BISCUIT_URL

        existing = self.get_pages()
        has_incident = False
        has_biscuit = False
        sygap_count = 0

        for p in existing:
            try:
                url = p.url.lower()
                if "sygap.telkom.co.id" in url:
                    has_incident = True
                    sygap_count += 1
                if "biscuit-dashboard" in url:
                    has_biscuit = True
            except Exception:
                continue
        # deduplikasi: jangan biarkan >1 SYGAP tab di profil INCIDENT
        if sygap_count > 1:
            kept = False
            for p in list(existing):
                try:
                    if "sygap.telkom.co.id" not in p.url.lower():
                        continue
                    if not kept:
                        kept = True
                        continue
                    p.close()
                    log("Menutup tab SYGAP duplikat di chrome INCIDENT")
                except Exception:
                    continue

        if not has_incident:
            log(f"Opening SYGAP INCIDENT: {INCIDENT_DASHBOARD_URL[:50]}...")
            page = self.open_url(INCIDENT_DASHBOARD_URL)
            if page:
                log("SYGAP INCIDENT tab opened.")
            else:
                log("WARNING: Gagal buka SYGAP INCIDENT")

        if not has_biscuit:
            log(f"Opening BISCUIT: {BISCUIT_URL[:50]}...")
            page = self.open_url(BISCUIT_URL)
            if page:
                log("BISCUIT tab opened.")
            else:
                log("WARNING: Gagal buka BISCUIT")

        # Final dedup: pastikan hanya 1 SYGAP tab di chrome INCIDENT (tutup duplikat login/request)
        try:
            sygap_pages = [p for p in self.get_pages() if "sygap.telkom.co.id" in p.url.lower()]
            if len(sygap_pages) > 1:
                for p in sygap_pages[1:]:
                    try:
                        p.close()
                        log("Menutup tab SYGAP duplikat ekstra di chrome INCIDENT")
                    except Exception:
                        pass
        except Exception:
            pass

        self.refresh_cache()

        if has_incident and has_biscuit:
            log("SYGAP INCIDENT & BISCUIT tabs already open.")
        elif has_incident:
            log("BISCUIT tab opened. SYGAP INCIDENT already open.")
        elif has_biscuit:
            log("SYGAP INCIDENT tab opened. BISCUIT already open.")

    # ==================================================
    # Open SYGAP + INSERA tabs (for GAMAS RELATIONS)
    # ==================================================

    def open_required_tabs_gamas(self, log_callback=None):

        log = log_callback or (lambda msg: None)

        from config.settings import DASHBOARD_URL, GAMAS_RELATIONS_URL

        existing = self.get_pages()
        has_sygap = False
        has_insera = False

        for p in existing:
            try:
                url = p.url.lower()
                if "sygap.telkom.co.id" in url:
                    has_sygap = True
                if "oss-incident" in url or "insera" in url:
                    has_insera = True
            except Exception:
                continue

        if not has_sygap:
            log(f"Opening SYGAP: {DASHBOARD_URL[:50]}...")
            page = self.open_url(DASHBOARD_URL)
            if page:
                log("SYGAP tab opened.")
            else:
                log("WARNING: Gagal buka SYGAP")

        if not has_insera:
            log(f"Opening INSERA GAMAS: {GAMAS_RELATIONS_URL[:50]}...")
            page = self.open_url(GAMAS_RELATIONS_URL)
            if page:
                log("INSERA GAMAS tab opened.")
                log("Pastikan sudah login ke INSERA!")
            else:
                log("WARNING: Gagal buka INSERA GAMAS")

        self.refresh_cache()

        if has_sygap and has_insera:
            log("SYGAP & INSERA tabs already open.")
        elif has_sygap:
            log("INSERA tab opened. SYGAP already open.")
        elif has_insera:
            log("SYGAP tab opened. INSERA already open.")
