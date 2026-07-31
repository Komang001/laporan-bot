from config.settings import GAMAS_RELATIONS_URL
import time


class InseraGamasService:

    def __init__(self, browser_manager=None, log_callback=None):
        self.page = None
        self.browser_manager = browser_manager
        self.log = log_callback or (lambda msg: None)

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
