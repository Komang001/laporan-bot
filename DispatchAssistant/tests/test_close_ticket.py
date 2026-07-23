from app.browser import browser_manager


def main():

    print("=" * 60)
    print("CLOSE TICKET TEST")
    print("=" * 60)

    browser_manager.connect()

    ticket = browser_manager.get_active_ticket_page()

    if ticket is None:

        print("Ticket tidak ditemukan.")
        return

    print()
    print("Ticket ditemukan.")
    print(ticket.url)

    input("\nTekan ENTER untuk menutup ticket...")

    browser_manager.close_ticket()

    print("Ticket berhasil ditutup.")

    browser_manager.activate_dashboard()

    print("Dashboard diaktifkan.")


if __name__ == "__main__":

    main()