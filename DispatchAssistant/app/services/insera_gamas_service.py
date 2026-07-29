from config.settings import GAMAS_RELATIONS_URL


class InseraGamasService:

    def __init__(self, browser_manager=None):
        self.page = None
        self.browser_manager = browser_manager

    def open(self):
        self.page = self.browser_manager.get_insera_gamas_page()

        if self.page is None:
            print("INSERA Gamas tab tidak ditemukan.")
            return False

        self.browser_manager.activate_page(self.page)
        print("INSERA Gamas tab found.")
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
            print(f"Failed to navigate to Gamas Relations: {e}")
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
            print(f"Failed to fill parent: {e}")
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
            print(f"Failed to fill child: {e}")
            return False

    def get_page(self):
        return self.page
