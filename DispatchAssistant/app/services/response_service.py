import time
import re

from app.models.response import Response


class ResponseService:

    def __init__(self, page, old_count):

        self.page = page
        self.old_count = old_count

    def _extract_clean_message(self, content):
        """Extract clean error/success message from BISCUIT response.
        
        Format:
          ❌ dispatchticket GAGAL (...). Alasan:\n  1. INC51522441: Status CLOSED invalid (code: 403)
          -> INC51522441: Status CLOSED invalid for dispatch (code: 403)
        """
        match = re.search(r'INC\d+:\s*.+', content, re.IGNORECASE)
        if match:
            msg = match.group(0).strip()
            msg = re.sub(r'\(code:\s*\d+\)', r'(code: \1)', msg) if '(code:' in msg else msg
            return msg[:200]

        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip().lstrip('0123456789. ')
            if line and line.lower() not in ('alasan:', '❌', '❌ dispatchticket gagal'):
                return line[:200]

        return content[:200]

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
            content_lower = content.lower()

            if "gagal" in content_lower or "failed" in content_lower:
                status = "FAILED"
            elif "berhasil" in content_lower or "successfully" in content_lower:
                status = "SUCCESS"
            elif green_icon.count() > 0 or green_text.count() > 0:
                status = "SUCCESS"
            else:
                status = "UNKNOWN"

            clean_msg = self._extract_clean_message(content)

            return Response(
                status=status,
                message=clean_msg
            )

        except Exception as e:

            return Response(
                status="UNKNOWN",
                message=str(e)
            )