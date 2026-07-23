from pathlib import Path
from datetime import datetime


class DispatchLogger:

    def __init__(self):

        self.log_dir = Path("logs")

        self.log_dir.mkdir(exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")

        self.log_file = self.log_dir / f"dispatch_{today}.log"

    # ==================================================
    # Write Log
    # ==================================================

    def write(self, ticket, response):

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(
            self.log_file,
            "a",
            encoding="utf-8"
        ) as f:

            f.write("=" * 60 + "\n")
            f.write(now + "\n")
            f.write("=" * 60 + "\n\n")

            f.write(
                f"Request Number : {ticket.request_number}\n"
            )

            f.write(
                f"Ticket ID      : {ticket.ticket_id}\n"
            )

            f.write(
                f"Status Ticket  : {ticket.status}\n"
            )

            f.write(
                f"Owner Group    : {ticket.owner_group}\n\n"
            )

            f.write(
                f"Dispatch Status : {response.status}\n\n"
            )

            f.write("Response :\n\n")

            f.write(response.message)

            f.write("\n\n")