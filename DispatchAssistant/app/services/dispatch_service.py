from app.reader import read_ticket
from app.automation.insera import check_insera


def dispatch():

    ticket = read_ticket()

    if ticket is None:

        print("Ticket tidak ditemukan.")
        return

    print()
    print("=" * 50)
    print("Dispatch Assistant")
    print("=" * 50)

    print(f"Request Number : {ticket.request_number}")
    print(f"Ticket ID      : {ticket.ticket_id}")
    print(f"Status         : {ticket.status}")
    print(f"Owner Group    : {ticket.owner_group}")

    check_insera()

    print()
    print("Ready for Dispatch...")