import time
import re

from app.models.response import Response


class ResponseService:

    def __init__(self, page, old_count):

        self.page = page
        self.old_count = old_count

    def _extract_clean_message(self, content):
        """Extract clean error/success message from BISCUIT response.
        
        Format (with green icon even on FAIL):
          BISCUIT BOT
          ❌ dispatchticket GAGAL (28-07-2026 13:21:31).
          Alasan:
            1. INC51578241: Status RESOLVED invalid for dispatch (code: 403)
        
        -> INC51578241: Status RESOLVED invalid for dispatch (code: 403)
        """
        lines = content.strip().split('\n')
        cleaned = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("BISCUIT BOT"):
                continue
            if re.match(r'^\d{1,2}:\d{2}\s*(AM|PM)?$', line, re.IGNORECASE):
                continue
            if "dispatchticket" in line.lower() and ("gagal" in line.lower() or "berhasil" in line.lower()):
                continue
            if line.lower() == "alasan:":
                continue
            cleaned.append(line)
        
        for line in cleaned:
            line_clean = re.sub(r'^\d+\.\s*', '', line).strip()
            if re.match(r'INC\d+', line_clean, re.IGNORECASE):
                return line_clean[:200]
        
        for line in cleaned:
            line_clean = re.sub(r'^\d+\.\s*', '', line).strip()
            if line_clean:
                return line_clean[:200]
        
        return content[:200]

    # ==================================================
    # Read Dispatch Result
    # ==================================================

    def read(self):

        try:

            bot_messages = self.page.locator(
                "div.bg-\\[\\#182533\\]"
            )

            timeout = 15
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
            content = latest_msg.inner_text()
            content_lower = content.lower()

            if "gagal" in content_lower or "failed" in content_lower:
                status = "FAILED"
            elif "berhasil" in content_lower or "successfully" in content_lower:
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