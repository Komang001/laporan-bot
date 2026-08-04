from playwright.sync_api import TimeoutError

from config.settings import AUTO_ENTER


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
