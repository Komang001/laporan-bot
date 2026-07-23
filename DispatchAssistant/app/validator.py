class Validator:

    @staticmethod
    def validate_ticket(ticket):

        if ticket is None:

            return False, "Ticket tidak ditemukan."

        if not ticket.request_number:

            return False, "Request Number kosong."

        if not ticket.ticket_id:

            return False, "Ticket ID kosong."

        if not ticket.owner_group:

            return False, "Owner Group tidak ditemukan."

        return True, "OK"