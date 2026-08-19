import time
import re

from app.models.response import Response


def clean_error_message(message):
    """Bersihkan pesan error: buang judul, tanggal, dan code error;
    sisakan alasan saja. Contoh:
    'INC51578241: Status RESOLVED invalid for dispatch (code: 403)'
      -> 'INC51578241: Status RESOLVED invalid for dispatch'
    'BISCUIT BOT - dispatchticket GAGAL (28-07-2026 13:21:31). Alasan: ...'
      -> alasan saja.
    '{"errors":{"child_ticket":"Missing required value"}}'
      -> 'Missing required value'
    """
    msg = (message or "").replace("&quot;", '"').strip()
    if not msg:
        return msg

    # JSON validasi Joget/INSERA: {"errors":{field:"alasan",...}}
    m = re.search(r'"errors"\s*:\s*\{([^}]*)\}', msg)
    if m:
        pairs = re.findall(r'"([^"]+)":"([^"]*)"', m.group(1))
        reasons = [v for k, v in pairs if v]
        if reasons:
            return "; ".join(reasons)[:200]

    # tanggal (28-07-2026 13:21:31) atau (2026-07-28)
    msg = re.sub(r'\(\d{1,2}-\d{1,2}-\d{4}[^)]*\)', "", msg)
    # code error (code: 403) / (status: 403) / (HTTP 403)
    msg = re.sub(r'\(code:\s*[^)]*\)', "", msg, flags=re.I)
    msg = re.sub(r'\(status:\s*\d+\)', "", msg, flags=re.I)
    msg = re.sub(r'\(http\s*\d+\)', "", msg, flags=re.I)

    # buang baris judul: 'BISCUIT BOT', 'dispatchticket GAGAL (..)', 'Alasan:'
    lines = [l.strip() for l in msg.split("\n") if l.strip()]
    kept = []
    for line in lines:
        lower = line.lower()
        if lower.startswith("biscuit bot"):
            continue
        if re.match(r"^\d{1,2}:\d{2}\s*(AM|PM)?$", line, re.IGNORECASE):
            continue
        if re.search(r"gagal|berhasil|failed|successfully", lower) and \
           re.search(r"dispatch|pushmass|canclwork|compwork|ticket", lower):
            continue
        if lower in ("alasan:", "alasan"):
            continue
        line = re.sub(r"^\d+\.\s*", "", line).strip()
        kept.append(line)
    msg = " ".join(kept) if kept else msg

    # jika masih ada 'Alasan:', ambil bagian setelahnya
    idx = msg.lower().find("alasan:")
    if idx >= 0:
        msg = msg[idx + len("alasan:"):]

    msg = re.sub(r"^\d+\.\s*", "", msg.strip())
    msg = re.sub(r"\s+", " ", msg).strip()
    return msg[:200]


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
            if re.match(r'^\d{2}:\d{2}\s*(AM|PM)?$', line, re.IGNORECASE):
                continue
            if "dispatchticket" in line.lower() and ("gagal" in line.lower() or "berhasil" in line.lower()):
                continue
            if line.lower() == "alasan:":
                continue
            cleaned.append(line)
        
        for line in cleaned:
            line_clean = re.sub(r'^\d+\.\s*', '', line).strip()
            if re.match(r'INC\d+', line_clean, re.IGNORECASE):
                return clean_error_message(line_clean)

        for line in cleaned:
            line_clean = re.sub(r'^\d+\.\s*', '', line).strip()
            if line_clean:
                return clean_error_message(line_clean)

        return clean_error_message(content)

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