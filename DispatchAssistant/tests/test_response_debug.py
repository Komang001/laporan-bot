from app.reader import read_ticket
from app.command_builder import build_dispatch_command
from app.services.biscuit_service import BiscuitService


def main():

    print("=" * 60)
    print("Industrial Programmer - Response Debug")
    print("=" * 60)

    ticket = read_ticket()

    if ticket is None:
        print("Ticket tidak ditemukan.")
        return

    command = build_dispatch_command(ticket)

    biscuit = BiscuitService()

    if not biscuit.open():
        return

    biscuit.send(command)

    page = biscuit.get_page()

    print()
    print("Menunggu response BISCUIT...")
    page.wait_for_timeout(3000)

    print()
    print("=" * 60)
    print("SEMUA TEXT YANG MENGANDUNG 'Processed'")
    print("=" * 60)

    locator = page.locator("text=Processed")

    print("Jumlah :", locator.count())

    for i in range(locator.count()):

        try:

            print("-" * 60)
            print(locator.nth(i).inner_text())

        except Exception as e:

            print(e)


if __name__ == "__main__":
    main()