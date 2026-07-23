class AppState:

    def __init__(self):

        self.last_request_number = None
        self.last_ticket_id = None

    # ==========================================
    # Save Ticket
    # ==========================================

    def save(self, ticket):

        if ticket is None:
            return

        self.last_request_number = ticket.request_number
        self.last_ticket_id = ticket.ticket_id

    # ==========================================
    # Is Duplicate
    # ==========================================

    def is_duplicate(self, ticket):

        if ticket is None:
            return False

        return (

            ticket.request_number == self.last_request_number
            and
            ticket.ticket_id == self.last_ticket_id

        )


# ==========================================
# Singleton
# ==========================================

app_state = AppState()