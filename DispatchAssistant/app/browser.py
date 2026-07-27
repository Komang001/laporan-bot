from playwright.sync_api import sync_playwright
from pathlib import Path
import subprocess
import socket
import time


class BrowserManager:

    def __init__(self, cdp_port=9222):

        self.cdp_port = cdp_port
        self.playwright = None
        self.browser = None
        self.connected = False

        self.cache = {
            "dashboard": None,
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

    # ==================================================
    # Disconnect
    # ==================================================

    def disconnect(self):

        self.cache = {
            "dashboard": None,
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
            "biscuit": None,
            "ticket": None,
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
                    and "/form/" in url
                ):

                    self.cache["ticket"] = page

                elif "biscuit-dashboard" in url:

                    self.cache["biscuit"] = page

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
    # Save HTML
    # ==================================================

    def save_html(self, filename="sygap.html"):

        page = self.get_active_ticket_page()

        if page is None:
            return False

        try:

            html = page.content()
            Path(filename).write_text(html, encoding="utf-8")
            return True

        except Exception:
            return False
