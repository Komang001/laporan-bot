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

            bot_messages = self.page.locator(
                "div.bg-\\[\\#182533\\]"
            )

            timeout = 20
            start = time.time()

            while True:

                count = bot_messages.count()

                if count > self.old_count:
                    break

                if time.time() - start > timeout:

                    return Response(
                        status="UNKNOWN",
                        message="Timeout menunggu response BISCUIT BOT."
                    )

                time.sleep(0.5)

            latest_msg = bot_messages.last

            green_icon = latest_msg.locator("svg.text-green-400")
            green_text = latest_msg.locator("div.text-green-300")
            content = latest_msg.inner_text()

            if green_icon.count() > 0 or green_text.count() > 0:
                status = "SUCCESS"
            elif "berhasil" in content.lower() or "successfully" in content.lower():
                status = "SUCCESS"
            elif "gagal" in content.lower() or "failed" in content.lower():
                status = "FAILED"
            else:
                status = "UNKNOWN"

            return Response(
                status=status,
                message=content[:200]
            )

        except Exception as e:

            return Response(
                status="UNKNOWN",
                message=str(e)
            )