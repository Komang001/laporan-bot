from playwright.sync_api import TimeoutError

from config.settings import AUTO_ENTER
from app.models.response import Response


class BiscuitService:

    def __init__(self, browser_manager=None):

        self.page = None
        self.response_count_before = 0
        self.browser_manager = browser_manager

    # ==================================================
    # Open BISCUIT
    # ==================================================

    def open(self):

        self.page = self.browser_manager.get_biscuit_page()

        if self.page is None:

            print()
            print("BISCUIT tidak ditemukan.")
            return False

        self.browser_manager.activate_page(self.page)

        print()
        print("=" * 50)
        print("BISCUIT")
        print("=" * 50)
        print("Tab BISCUIT berhasil dibuka.")

        return True

    # ==================================================
    # Focus Command Box
    # ==================================================

    def focus_command(self):

        if self.page is None:

            return False

        try:

        # Simpan jumlah chat BISCUIT BOT sebelum dispatch
            self.response_count_before = self.get_bot_message_count()

            command_box = self.page.locator(
                "input[placeholder*='Command for']"
            )

            command_box.click()

            print("Command Box ditemukan.")

            return True

        except Exception as e:

            print("Gagal menemukan Command Box.")
            print(e)

            return False

    # ==================================================
    # Send Command
    # ==================================================

    def send(self, command: str):

        if self.page is None:

            return False

        if not command:

            print("Command kosong.")
            return False

        try:

            command_box = self.page.locator(
                "input[placeholder*='Command for']"
            )

            command_box.wait_for(
                state="visible",
                timeout=5000
            )

            command_box.click()

            command_box.fill(command)

            print()
            print("Command :")
            print(command)

            if AUTO_ENTER:

                command_box.press("Enter")
                print("ENTER dikirim.")

            else:

                print("AUTO_ENTER = False")
                print("Command berhasil diisi.")

            return True

        except TimeoutError:

            print("Command Box tidak muncul.")
            return False

        except Exception as e:

            print("Gagal mengirim command.")
            print(e)
            return False

    # ==================================================
    # Getter
    # ==================================================

    def get_response_count_before(self):

        return self.response_count_before

    def get_page(self):

        return self.page
    
    # ==================================================
    # Get Bot Message Count
    # ==================================================

    def get_bot_message_count(self):

        if self.page is None:
            return 0

        try:

            return self.page.locator(
                "div.bg-\\[\\#182533\\]"
            ).count()

        except:

            return 0

    def wait_for_ready(self):
        if self.page is None:
            return False
        try:
            self.page.wait_for_timeout(1000)
            self.response_count_before = self.get_bot_message_count()
            return True
        except Exception:
            return False

    # ==================================================
    # API Langsung (HTTP) + Fallback UI
    # ==================================================

    BISCUIT_BASE = "https://biscuit-dashboard-dev-playground.apps.mypaas.telkom.co.id"

    def _get_token(self):
        """Bearer token dari localStorage tab BISCUIT (JWT)."""
        if self.page is None:
            self.open()
        try:
            return self.page.evaluate(
                "localStorage.getItem('biscuit_token')"
            )
        except Exception:
            return None

    def _api_execute(self, command, page_scope):
        """Kirim command via POST /api/execute. Return Response atau None jika gagal."""
        import json
        import urllib.request
        import urllib.error

        token = self._get_token()
        if not token:
            print("BISCUIT API: token kosong.")
            return None

        req = urllib.request.Request(
            self.BISCUIT_BASE + "/api/execute",
            data=json.dumps({
                "command": command,
                "currentPage": page_scope,
            }).encode(),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=185) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"BISCUIT API error: {e}")
            return None

        msg = str(data.get("message") or "")
        msg_lower = msg.lower()
        if "gagal" in msg_lower or "failed" in msg_lower:
            status = "FAILED"
        elif "berhasil" in msg_lower or "successfully" in msg_lower:
            status = "SUCCESS"
        else:
            status = "UNKNOWN"
        return Response(status=status, message=msg[:200])

    def execute(self, command, page_scope):
        """Kirim command: coba API langsung (HTTP), fallback ke UI lama jika gagal."""
        response = self._api_execute(command, page_scope)
        if response is not None:
            return response

        print("BISCUIT API gagal, fallback ke UI...")
        if not self.open():
            return Response(status="UNKNOWN", message="BISCUIT tab not found")
        if not self.focus_command():
            return Response(status="UNKNOWN", message="BISCUIT command box not found")
        self.send(command)
        from app.services.response_service import ResponseService
        return ResponseService(
            self.get_page(),
            self.get_response_count_before()
        ).read()
