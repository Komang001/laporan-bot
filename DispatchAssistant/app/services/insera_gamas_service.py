from config.settings import GAMAS_RELATIONS_URL
import time

from app.models.response import Response


class InseraGamasService:

    def __init__(self, browser_manager=None, log_callback=None):
        self.page = None
        self.browser_manager = browser_manager
        self.log = log_callback or (lambda msg: None)

    GAMAS_FORM_URL = (
        "https://oss-incident.telkom.co.id"
        "/jw/web/userview/ticketIncidentService/ticketIncidentService/_/gamasRelations"
    )

    def open(self):
        self.page = self.browser_manager.get_insera_gamas_page()

        if self.page is None:
            self.log("INSERA Gamas tab tidak ditemukan.")
            return False

        self.browser_manager.activate_page(self.page)
        self.log("INSERA Gamas tab found.")
        return True

    def navigate_to_relations(self):
        if self.page is None:
            return False

        try:
            current = self.page.url.lower()
            if "gamasrelations" not in current:
                self.page.goto(GAMAS_RELATIONS_URL, wait_until="domcontentloaded", timeout=15000)
                self.page.wait_for_timeout(2000)
            return True
        except Exception as e:
            self.log(f"Failed to navigate to Gamas Relations: {e}")
            return False

    def wait_for_fields(self, timeout=300):
        if self.page is None:
            return False

        start = time.time()
        attempt = 0
        while time.time() - start < timeout:
            attempt += 1
            elapsed = int(time.time() - start)
            try:
                parent = self.page.locator("#parent_ticket")
                child = self.page.locator("#child_ticket")
                if parent.count() > 0 and child.count() > 0:
                    parent_vis = parent.is_visible()
                    child_vis = child.is_visible()
                    if parent_vis and child_vis:
                        self.log(f"    Fields visible after {elapsed}s (attempt {attempt})")
                        return True
                if attempt % 6 == 0:
                    self.log(f"    Still loading... ({elapsed}s elapsed, attempt {attempt})")
            except Exception as e:
                self.log(f"    Wait error (attempt {attempt}): {e}")
            time.sleep(5)

        self.log(f"    Fields not visible after {timeout}s, SKIP")
        return False

    def fill_parent(self, parent_inc):
        if self.page is None:
            return False

        try:
            field = self.page.locator("#parent_ticket")
            field.wait_for(state="visible", timeout=5000)
            field.fill("")
            field.fill(parent_inc)
            self.page.wait_for_timeout(300)
            return True
        except Exception as e:
            self.log(f"Failed to fill parent: {e}")
            return False

    def fill_child(self, child_str):
        if self.page is None:
            return False

        try:
            field = self.page.locator("#child_ticket")
            field.wait_for(state="visible", timeout=5000)
            field.fill("")
            field.fill(child_str)
            self.page.wait_for_timeout(300)
            return True
        except Exception as e:
            self.log(f"Failed to fill child: {e}")
            return False

    def click_save(self):
        if self.page is None:
            return False

        try:
            self.log("    Clicking Save button...")

            dialog_handled = {"done": False}

            def handle_dialog(dialog):
                self.log(f"    Dialog appeared: {dialog.message[:80]}")
                try:
                    dialog.accept()
                    self.log("    Dialog OK clicked")
                    dialog_handled["done"] = True
                except Exception as e:
                    self.log(f"    Dialog accept error: {e}")

            self.page.on("dialog", handle_dialog)

            save_btn = self.page.locator("#submit")
            if save_btn.count() == 0:
                save_btn = self.page.locator("button:has-text('Save')")
            if save_btn.count() == 0:
                save_btn = self.page.locator("input[type='submit']")
            if save_btn.count() == 0:
                save_btn = self.page.locator("button:has-text('Submit')")

            if save_btn.count() > 0:
                save_btn.first.scroll_into_view_if_needed()
                self.page.wait_for_timeout(500)
                save_btn.first.click()
                self.log("    Save clicked")
                self.page.wait_for_timeout(3000)
            else:
                self.log("    Save button NOT found!")
                self.page.remove_listener("dialog", handle_dialog)
                return False

            if not dialog_handled["done"]:
                self.page.wait_for_timeout(2000)

            self.page.remove_listener("dialog", handle_dialog)
            self.log("    Save completed")
            return True

        except Exception as e:
            self.log(f"Failed to click save: {e}")
            return False

    def get_page(self):
        return self.page

    # ==================================================
    # API Langsung (HTTP multipart) + Fallback UI
    # ==================================================

    def _get_cookie_header(self):
        """Cookie session dari konteks browser (oss-incident).

        Bekerja meski tab INSERA ditutup: cookie disimpan di profil Chrome,
        dibaca dari konteks halaman mana pun di browser yang sama.
        """
        ctx = None
        try:
            if self.page is not None:
                ctx = self.page.context
            elif self.browser_manager is not None:
                for pg in self.browser_manager.get_all_pages():
                    if pg.context is not None:
                        ctx = pg.context
                        break
            if ctx is None:
                self.log("    GAMAS API: konteks browser tidak tersedia (cookie tidak bisa dibaca)")
                return ""
            cookies = ctx.cookies()
            header = "; ".join(
                f"{c['name']}={c['value']}"
                for c in cookies
                if "oss-incident" in c.get("domain", "")
            )
            if not header:
                self.log("    GAMAS API: cookie oss-incident TIDAK ditemukan di profil browser (cek login INSERA)")
            return header
        except Exception as e:
            self.log(f"    GAMAS API: gagal baca cookie ({e})")
            return ""

    def _get_form_tokens(self, cookie_header):
        """GET halaman form -> ambil OWASP_CSRFTOKEN & _NONCE_TOKEN_REQUEST_HASH terbaru."""
        import re
        import urllib.request

        tokens = {"csrf": "", "nonce": ""}
        try:
            req = urllib.request.Request(
                self.GAMAS_FORM_URL,
                headers={"Cookie": cookie_header, "User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            m = (
                re.search(r'name="OWASP_CSRFTOKEN"[^>]*value="([^"]*)"', html)
                or re.search(r'value="([^"]*)"[^>]*name="OWASP_CSRFTOKEN"', html)
                or re.search(r'ConnectionManager\.tokenValue\s*=\s*"([^"]*)"', html)
            )
            if m:
                tokens["csrf"] = m.group(1)
            m = (
                re.search(r'name="_NONCE_TOKEN_REQUEST_HASH"[^>]*value="([^"]*)"', html)
                or re.search(r'value="([^"]*)"[^>]*name="_NONCE_TOKEN_REQUEST_HASH"', html)
            )
            if m:
                tokens["nonce"] = m.group(1)
        except Exception as e:
            self.log(f"    GAMAS API: gagal ambil token form ({e})")
        if not tokens["csrf"] or not tokens["nonce"]:
            self.log("    GAMAS API: CSRF/nonce TIDAK ditemukan di halaman form")
        return tokens

    def submit_via_api(self, parent_inc, child_str):
        """Submit relasi GAMAS langsung via HTTP (multipart POST form Joget).

        Return Response, atau None jika gagal (untuk fallback ke UI).
        """
        import re
        import uuid
        import urllib.request

        cookie_header = self._get_cookie_header()
        if not cookie_header:
            self.log("    GAMAS API: cookie kosong -> fallback UI")
            return None
        tokens = self._get_form_tokens(cookie_header)

        boundary = "----WebKitFormBoundary" + uuid.uuid4().hex[:16]

        def field(name, value):
            return (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            )

        body = "".join([
            field("_NONCE_TOKEN_REQUEST_HASH", tokens["nonce"]),
            field("massGamasRelations_SUBMITTED", "true"),
            field("_FORM_META_ORIGINAL_ID", ""),
            field("OWASP_CSRFTOKEN", tokens["csrf"]),
            field("parent_ticket", parent_inc),
            field("child_ticket", child_str),
            field("submit", "Save"),
            f"--{boundary}--\r\n",
        ]).encode()

        req = urllib.request.Request(
            self.GAMAS_FORM_URL + "?_action=submit",
            data=body,
            method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Cookie": cookie_header,
                "User-Agent": "Mozilla/5.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            self.log(f"    GAMAS API: POST gagal ({e}) -> fallback UI")
            return None

        # Validasi server: hidden field _FORM_ERRORS berisi {"errors":{...}}
        m = re.search(r'&quot;errors&quot;\s*:\s*\{[^}]*\}', content) or \
            re.search(r'"errors"\s*:\s*\{[^}]*\}', content)
        if m:
            from app.services.response_service import clean_error_message
            return Response(
                status="FAILED",
                message=clean_error_message(m.group(0)),
            )
        return Response(status="SUCCESS", message="Relasi GAMAS tersimpan via API")

    def submit_relation(self, parent_inc, child_str):
        """Kirim relasi: coba API langsung (HTTP), fallback ke UI lama jika gagal."""
        response = self.submit_via_api(parent_inc, child_str)
        if response is not None:
            return response

        self.log("API GAMAS gagal, fallback ke UI...")
        if not self.wait_for_fields(timeout=30):
            return Response(status="FAILED", message="INSERA fields not visible")
        if not self.fill_parent(parent_inc):
            return Response(status="FAILED", message="Failed fill parent field")
        if not self.fill_child(child_str):
            return Response(status="FAILED", message="Failed fill child field")
        if not self.click_save():
            return Response(status="FAILED", message="Failed save on INSERA")
        return Response(status="SUCCESS", message="Relasi GAMAS tersimpan via UI")
