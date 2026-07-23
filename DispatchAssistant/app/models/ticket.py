from dataclasses import dataclass


@dataclass
class Ticket:
    """
    Model Ticket SYGAP
    """

    request_number: str | None = None
    ticket_id: str | None = None
    status: str | None = None
    note: str | None = None
    owner_group: str | None = None

    def __str__(self):

        return (
            f"\n"
            f"Request Number : {self.request_number}\n"
            f"Ticket ID      : {self.ticket_id}\n"
            f"Status         : {self.status}\n"
            f"Owner Group    : {self.owner_group}\n"
        )