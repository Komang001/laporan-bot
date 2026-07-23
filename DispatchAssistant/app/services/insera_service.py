class InseraService:

    def __init__(self):

        self.keyword = None
        self.result = []

    # ==================================================
    # Search
    # ==================================================

    def search(self, ticket_id):

        self.keyword = ticket_id

        print()
        print("=" * 50)
        print("INSERA")
        print("=" * 50)

        print(f"Mencari Incident : {ticket_id}")

        #
        # Nanti di sinilah otomatisasi INSERA dilakukan.
        #

        self.result = []

        return self.result

    # ==================================================
    # Has Result
    # ==================================================

    def has_result(self):

        return len(self.result) > 0

    # ==================================================
    # Count
    # ==================================================

    def count(self):

        return len(self.result)