from app.browser import browser_manager
from app.models.ticket import Ticket
from app.parser import extract_owner_group



def read_ticket():

    page = browser_manager.get_active_ticket_page()


    if page is None:

        print("Halaman ticket SYGAP tidak ditemukan.")

        return None

    print()
    print("=" * 50)
    print("Reading Ticket")
    print("=" * 50)


    ticket = Ticket()



    # ==================================================
    # Wait Page Ready
    # ==================================================

    try:

        page.wait_for_load_state(
            "domcontentloaded",
            timeout=15000
        )

    except Exception:

        pass

    page.wait_for_timeout(3000)

    try:
        html = page.content()
        with open("debug_ticket.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("DEBUG: HTML saved to debug_ticket.html")
    except Exception as e:
        print(f"DEBUG: Gagal save HTML: {e}")



    # ==================================================
    # Request Number
    # ==================================================

    try:

        locator = page.locator("#request_code")

        if locator.count() == 0:
            locator = page.locator("input[name*='request']")
        if locator.count() == 0:
            locator = page.locator("input[name*='code']")

        locator.first.wait_for(state="attached", timeout=10000)

        ticket.request_number = locator.first.input_value().strip()

    except Exception as e:

        print("Gagal membaca Request Number:", e)
        ticket.request_number = None



    # ==================================================
    # Ticket ID
    # ==================================================

    try:

        locator = page.locator("input[name$='_ticket_id']")

        if locator.count() == 0:
            locator = page.locator("input[name*='ticket_id']")
        if locator.count() == 0:
            locator = page.locator("input[name*='ticket']")

        locator.first.wait_for(state="attached", timeout=10000)

        ticket.ticket_id = locator.first.input_value().strip()

    except Exception as e:

        print("Gagal membaca Ticket ID:", e)
        ticket.ticket_id = None



    # ==================================================
    # Status
    # ==================================================

    try:

        locator = page.locator("#status")

        if locator.count() == 0:
            locator = page.locator("input[name*='status']")
        if locator.count() == 0:
            locator = page.locator("select[name*='status']")

        locator.first.wait_for(state="attached", timeout=10000)

        ticket.status = locator.first.input_value().strip()

    except Exception as e:

        print("Gagal membaca Status:", e)
        ticket.status = None



    # ==================================================
    # Note
    # ==================================================

    ticket.note = ""


    try:

        editors = page.locator(
            ".ck-editor__editable"
        )


        for i in range(editors.count()):

            text = (
                editors.nth(i)
                .inner_text()
                .strip()
            )


            if text:

                ticket.note = text

                break


    except Exception:

        ticket.note = ""



    # ==================================================
    # Owner Group
    # ==================================================

    ticket.owner_group = extract_owner_group(
        ticket.note
    )


    print()
    print("Ticket Reader Result")
    print("=" * 50)
    print(ticket)


    return ticket