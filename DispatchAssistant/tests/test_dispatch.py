from app.reader import read_ticket
from app.command_builder import build_dispatch_command
from app.services.biscuit_service import BiscuitService


def main():

    print("=" * 60)
    print("Industrial Programmer - Dispatch Test")
    print("=" * 60)

    ticket = read_ticket()

    if ticket is None:

        print("Ticket tidak ditemukan.")
        return

    command = build_dispatch_command(ticket)

    biscuit = BiscuitService()

    if not biscuit.open():
        return

    if not biscuit.focus_command():
        return

    biscuit.send(command)

    input("\nTekan ENTER di terminal untuk mengakhiri test...")


if __name__ == "__main__":
    main()