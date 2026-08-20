from playwright.sync_api import TimeoutError

from config.settings import AUTO_ENTER
from app.models.response import Response

import os

BISCUIT_TOKEN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "biscuit_token.txt",
)


def _load_cached_token():
    try:
        with open(BISCUIT_TOKEN_PATH, "r", encoding="utf-8") as f:
            token = f.read().strip()
        return token or None
    except Exception:
        return None


def _save_cached_token(token):
    try:
        with open(BISCUIT_TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(token)
    except Exception:
        pass


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
        """Bearer token dari localStorage tab BISCUIT, atau cache file.

        Bekerja dari browser mana pun: fitur GAMAS (9225) tidak punya tab
        BISCUIT, tapi token tersedia di cache yang di-refresh tiap kali
        API BISCUIT berhasil digunakan (DISPATCH/CANCLWORK di 9224).
        """
        if self.page is None:
            self.open()
        if self.page is not None:
            try:
                token = self.page.evaluate(
                    "localStorage.getItem('biscuit_token')"
                )
                if token:
                    _save_cached_token(token)
                    return token
            except Exception:
                pass
        return _load_cached_token()

    def _api_execute_raw(self, command, page_scope):
        """POST /api/execute. Return dict respons mentah, atau None jika gagal."""
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
                return json.loads(resp.read().decode())
        except Exception as e:
            print(f"BISCUIT API error: {e}")
            return None

    def _api_execute(self, command, page_scope):
        """Kirim command via POST /api/execute. Return Response atau None jika gagal."""
        data = self._api_execute_raw(command, page_scope)
        if data is None:
            return None

        msg = str(data.get("message") or "")
        msg_lower = msg.lower()
        if "gagal" in msg_lower or "failed" in msg_lower:
            status = "FAILED"
        elif "berhasil" in msg_lower or "successfully" in msg_lower:
            status = "SUCCESS"
        else:
            status = "UNKNOWN"
        from app.services.response_service import clean_error_message
        return Response(status=status, message=clean_error_message(msg))

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

    def check_ticket(self, ticket_id):
        """Cek tiket (mis. induk GAMAS) via /cekticket.

        Return dict: {"found": bool, "detail": str, "status": str}.
        found = tiket ditemukan DAN source_ticket == 'GAMAS'
        (induk GAMAS asli). Jika API gagal, fallback ke UI (tanpa cek source).
        """
        import json

        from app.services.response_service import clean_error_message

        data = self._api_execute_raw(f"/cekticket {ticket_id}", "INSERA")
        if data is not None:
            detail = str(data.get("message") or "")
            try:
                payload = data.get("data")
                if isinstance(payload, str):
                    payload = json.loads(payload)
                inner = (payload or {}).get("data", {}) if isinstance(payload, dict) else {}
                success = inner.get("success") or []
                failed = inner.get("failed") or []
                for item in failed:
                    if str(item.get("ticketId", "")) == ticket_id:
                        return {
                            "found": False,
                            "detail": clean_error_message(str(item.get("message", detail)))[:200],
                            "status": "FAILED",
                        }
                for item in success:
                    if str(item.get("ticketId", "")) == ticket_id:
                        d = item.get("data") or {}
                        source = str(d.get("source_ticket") or "").upper()
                        is_parent = source == "GAMAS"
                        bits = [
                            str(item.get("message", "")),
                            f"status={d.get('ticket_status')}",
                            f"og={d.get('owner_group')}",
                            f"source={d.get('source_ticket')}",
                        ]
                        return {
                            "found": is_parent,
                            "detail": " | ".join(b for b in bits if b)[:200],
                            "status": "SUCCESS" if is_parent else "UNKNOWN",
                        }
                if not success and not failed:
                    return {
                        "found": data.get("smartStatus") == "SUCCESS",
                        "detail": detail[:200],
                        "status": str(data.get("smartStatus", "UNKNOWN")),
                    }
            except Exception as e:
                return {"found": False, "detail": f"Parse error: {e}", "status": "UNKNOWN"}
            return {
                "found": False,
                "detail": detail[:200],
                "status": str(data.get("smartStatus", "UNKNOWN")),
            }

        response = self.execute(f"/cekticket {ticket_id}", "INSERA")
        if response is None:
            return {
                "found": False,
                "detail": "Gagal cek induk (BISCUIT tidak tersedia)",
                "status": "UNKNOWN",
            }
        return {
            "found": response.status == "SUCCESS",
            "detail": response.message,
            "status": response.status,
        }

    def check_children(self, child_incs):
        """Verifikasi anak gamas via /cekticket.

        Semua anak dicek dalam SATU panggilan API (dipisah koma).
        Hanya anak dengan source_ticket 'CUSTOMER' yang valid.
        Anak dengan source selain itu (GAMAS/lain), tidak ditemukan, atau tidak
        terverifikasi (API gagal) -> dibuang (jangan di-input).

        Return: {"valid": [INC...], "excluded": [{"inc", "source", "detail"}]}
        """
        import json

        from app.services.response_service import clean_error_message

        if not child_incs:
            return {"valid": [], "excluded": []}

        results = {}

        def _parse_batch(data):
            try:
                payload = data.get("data")
                if isinstance(payload, str):
                    payload = json.loads(payload)
                inner = (payload or {}).get("data", {}) if isinstance(payload, dict) else {}
                for item in inner.get("success") or []:
                    tid = str(item.get("ticketId", "")).strip()
                    d = item.get("data") or {}
                    results[tid] = {
                        "source": str(d.get("source_ticket") or "").upper(),
                        "detail": (
                            f"status={d.get('ticket_status')} | "
                            f"og={d.get('owner_group')} | "
                            f"source={d.get('source_ticket')}"
                        ),
                    }
                for item in inner.get("failed") or []:
                    tid = str(item.get("ticketId", "")).strip()
                    results[tid] = {
                        "source": "NOT_FOUND",
                        "detail": clean_error_message(str(item.get("message", ""))),
                    }
                return True
            except Exception as e:
                return e

        cmd = f"/cekticket {','.join(child_incs)}"
        data = self._api_execute_raw(cmd, "INSERA")
        if data is None or _parse_batch(data) is not True:
            # API batch gagal -> cek per anak (masing-masing 1 panggilan)
            for inc in child_incs:
                data = self._api_execute_raw(f"/cekticket {inc}", "INSERA")
                if data is None:
                    results[inc] = {"source": "UNVERIFIED", "detail": "API BISCUIT gagal"}
                elif _parse_batch(data) is not True:
                    results[inc] = {"source": "PARSE_ERROR", "detail": "Gagal parse respons"}

        valid, excluded = [], []
        for inc in child_incs:
            info = results.get(inc)
            if info and info.get("source") == "CUSTOMER":
                valid.append(inc)
            else:
                excluded.append({
                    "inc": inc,
                    "source": (info or {}).get("source", "UNKNOWN"),
                    "detail": (info or {}).get("detail", ""),
                })

        return {"valid": valid, "excluded": excluded}
