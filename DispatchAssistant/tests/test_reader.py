from app.reader import read_ticket


def main():

    print("=" * 50)
    print("Industrial Programmer")
    print("Reader Test")
    print("=" * 50)

    ticket = read_ticket()

    if ticket is None:

        print("Gagal membaca tiket.")
        return

    print()

    print(f"request_number      : {ticket.request_number}")
    print(f"ticket_id           : {ticket.ticket_id}")
    print(f"status              : {ticket.status}")
    print(f"note                : {ticket.note}")
    print(f"owner_group         : {ticket.owner_group}")


if __name__ == "__main__":
    main()