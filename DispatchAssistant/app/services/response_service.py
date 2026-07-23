import time

from app.models.response import Response


class ResponseService:

    def __init__(self, page, old_count):

        self.page = page
        self.old_count = old_count

    # ==================================================
    # Read Dispatch Result
    # ==================================================

    def read(self):

        try:

            bot_names = self.page.locator(
                "text=BISCUIT BOT"
            )

            timeout = 15
            start = time.time()

            while True:

                count = bot_names.count()

                if count > self.old_count:
                    break

                if time.time() - start > timeout:

                    return Response(
                        status="UNKNOWN",
                        message="Timeout menunggu response BISCUIT BOT."
                    )

                time.sleep(0.2)

            message = bot_names.nth(
                count - 1
            ).locator(
                "xpath=following::div[contains(@class,'whitespace-pre-wrap')][1]"
            ).inner_text().strip()

            upper = message.upper()

            if "GAGAL" in upper:

                status = "FAILED"

            elif "BERHASIL" in upper:

                status = "SUCCESS"

            else:

                status = "UNKNOWN"

            return Response(
                status=status,
                message=message
            )

        except Exception as e:

            return Response(
                status="UNKNOWN",
                message=str(e)
            )