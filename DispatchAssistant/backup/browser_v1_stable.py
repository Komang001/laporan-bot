from playwright.sync_api import sync_playwright
from pathlib import Path
import time


class BrowserManager:

    def __init__(self):

        self.playwright = None
        self.browser = None

        # page cache
        self.cache = {
            "dashboard": None,
            "biscuit": None,
            "ticket": None
        }


    # ==================================================
    # Connect Browser
    # ==================================================

    def connect(self):

        if self.browser is not None:
            return self.browser


        self.playwright = sync_playwright().start()


        self.browser = self.playwright.chromium.connect_over_cdp(
            "http://127.0.0.1:9222"
        )


        for context in self.browser.contexts:

            context.set_default_timeout(5000)


        print("=" * 50)
        print("Browser Connected")
        print("=" * 50)


        self.refresh_cache()

        return self.browser



    # ==================================================
    # Disconnect Browser
    # ==================================================

    def disconnect(self):

        self.cache = {
            "dashboard": None,
            "biscuit": None,
            "ticket": None
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


        print("Browser Disconnected")



    # ==================================================
    # Get Pages
    # ==================================================

    def get_pages(self):

        if self.browser is None:
            self.connect()


        pages = []


        for context in self.browser.contexts:

            for page in context.pages:

                pages.append(page)


        return pages



    # ==================================================
    # Check Page
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
    # Cache Refresh
    # ==================================================

    def refresh_cache(self):

        self.cache = {
            "dashboard": None,
            "biscuit": None,
            "ticket": None
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
    # Ensure Dashboard
    # ==================================================

    def ensure_dashboard(self):

        page = self.get_dashboard_page()


        if page is None:

            print("Dashboard SYGAP tidak ditemukan.")

            return False



        return self.activate_page(page)



    # ==================================================
    # Ticket Pages
    # ==================================================

    def get_ticket_pages(self):

        tickets = []


        for page in self.get_pages():

            try:

                url = page.url.lower()


                if (
                    "sygap.telkom.co.id" in url
                    and "/form/" in url
                ):

                    tickets.append(page)


            except Exception:

                continue


        return tickets



    # ==================================================
    # Active Ticket
    # ==================================================

    def get_active_ticket_page(self):

        tickets = self.get_ticket_pages()


        if not tickets:

            return None


        self.cache["ticket"] = tickets[-1]


        return tickets[-1]



    # ==================================================
    # Compatibility
    # ==================================================

    def get_sygap_page(self):

        return self.get_active_ticket_page()



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
    # Ensure Biscuit
    # ==================================================

    def ensure_biscuit(self):

        page = self.get_biscuit_page()


        if page is None:

            print("Biscuit dashboard tidak ditemukan.")

            return False



        return self.activate_page(page)



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
    # Refresh Page
    # ==================================================

    def refresh(self, page=None):

        if page is None:

            page = self.get_sygap_page()



        if not self.is_page_alive(page):

            return False


        try:

            page.reload()

            page.wait_for_load_state(
                "domcontentloaded",
                timeout=10000
            )


            return True


        except Exception as e:

            print("Refresh error:", e)

            return False



    # ==================================================
    # Activate Dashboard
    # ==================================================

    def activate_dashboard(self):

        return self.ensure_dashboard()



    # ==================================================
    # Close Ticket
    # ==================================================

    def close_ticket(self):

        ticket = self.get_active_ticket_page()


        if ticket is None:

            return False


        try:

            ticket.close()

            self.refresh_cache()

            return True


        except Exception as e:

            print(e)

            return False



    # ==================================================
    # Save HTML
    # ==================================================

    def save_html(self, filename="sygap.html"):

        page = self.get_active_ticket_page()


        if page is None:

            print("SYGAP page not found.")

            return False



        try:

            print()
            print("Saving...")
            print("Title :", page.title())
            print("URL   :", page.url)



            html = page.content()


            Path(filename).write_text(
                html,
                encoding="utf-8"
            )


            print("HTML saved.")


            return True



        except Exception as e:

            print("Save HTML error:", e)

            return False




# ======================================================
# Singleton
# ======================================================

browser_manager = BrowserManager()



# ======================================================
# Compatibility Functions
# ======================================================

def connect_browser():

    return browser_manager.connect()



def close_browser():

    return browser_manager.disconnect()



def get_sygap_page():

    return browser_manager.get_sygap_page()



def get_biscuit_page():

    return browser_manager.get_biscuit_page()



def activate_page(page):

    return browser_manager.activate_page(page)



def save_html(filename="sygap.html"):

    return browser_manager.save_html(filename)