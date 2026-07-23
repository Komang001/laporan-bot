from config.settings import COMMAND_DISPATCH


def build_dispatch_command(ticket):

    if ticket is None:
        return None

    if not ticket.ticket_id:
        return None

    if not ticket.owner_group:
        return None

    command = (
        f"{COMMAND_DISPATCH} "
        f"{ticket.ticket_id} "
        f"{ticket.owner_group}"
    )

    return command