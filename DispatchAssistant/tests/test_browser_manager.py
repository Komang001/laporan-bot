from app.browser import browser_manager


def main():

    print("=" * 60)
    print("Industrial Programmer")
    print("Browser Manager Test")
    print("=" * 60)

    browser_manager.connect()

    print()

    # ==================================================
    # Dashboard
    # ==================================================

    dashboard = browser_manager.get_dashboard_page()

    if dashboard:

        print("[OK] Dashboard ditemukan")
        print("Title :", dashboard.title())
        print("URL   :", dashboard.url)

    else:

        print("[ERROR] Dashboard tidak ditemukan")

    print()

    # ==================================================
    # BISCUIT
    # ==================================================

    biscuit = browser_manager.get_biscuit_page()

    if biscuit:

        print("[OK] BISCUIT ditemukan")
        print("Title :", biscuit.title())
        print("URL   :", biscuit.url)

    else:

        print("[ERROR] BISCUIT tidak ditemukan")

    print()

    # ==================================================
    # Ticket Aktif
    # ==================================================

    ticket = browser_manager.get_active_ticket_page()

    if ticket:

        print("[OK] Ticket aktif ditemukan")
        print("Title :", ticket.title())
        print("URL   :", ticket.url)

    else:

        print("[ERROR] Ticket aktif tidak ditemukan")


if __name__ == "__main__":

    main()