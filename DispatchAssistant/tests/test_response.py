from app.reader import read_ticket
from app.command_builder import build_dispatch_command

from app.services.biscuit_service import BiscuitService
from app.services.response_service import ResponseService


def main():

    print("=" * 60)
    print("Industrial Programmer - Response Test")
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

    response = ResponseService(
        biscuit.get_page(),
        biscuit.get_response_count_before()
    )

    result = response.read()

    print()
    print("=" * 50)
    print("Dispatch Result")
    print("=" * 50)

    print("Status  :", result.status)
    print("Message :", result.message)


if __name__ == "__main__":
    main()