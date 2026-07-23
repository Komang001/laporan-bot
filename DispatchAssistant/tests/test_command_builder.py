from app.reader import read_ticket
from app.command_builder import build_dispatch_command


def main():

    print("=" * 60)
    print("Industrial Programmer - Command Builder Test")
    print("=" * 60)

    ticket = read_ticket()

    if ticket is None:

        print("Ticket = None")
        return

    print()
    print("Ticket")
    print("-" * 60)
    print("Request Number :", ticket.request_number)
    print("Ticket ID      :", ticket.ticket_id)
    print("Status         :", ticket.status)
    print("Owner Group    :", ticket.owner_group)

    command = build_dispatch_command(ticket)

    print()
    print("Command")
    print("-" * 60)
    print(command)


if __name__ == "__main__":
    main()