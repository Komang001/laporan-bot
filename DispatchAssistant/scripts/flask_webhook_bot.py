"""Telegram Bot Webhook untuk Jadwal Piket di PythonAnywhere (Free Tier).

Menangani request langsung dari Telegram via HTTPS Webhook (Flask).
Bebas polling loop, ringan, dan gratis 24 jam di PythonAnywhere.
"""

import json
import logging
import os
import sys
import traceback
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from flask import Flask, request

# Otomatis gunakan proxy di PythonAnywhere Free Tier agar akses Google Sheet & Telegram tembus
if os.environ.get("PYTHONANYWHERE_SITE") or os.environ.get("PYTHONANYWHERE_DOMAIN") or "pythonanywhere" in os.path.expanduser("~").lower():
    os.environ["http_proxy"] = "http://proxy.server:3128"
    os.environ["https_proxy"] = "http://proxy.server:3128"

# Pastikan path modul terbaca
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from send_daily_jadwal import build_message
except ImportError:
    from DispatchAssistant.scripts.send_daily_jadwal import build_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PA_JadwalBot")

app = Flask(__name__)


def send_reply(chat_id, text, reply_to_message_id=None):
    """Kirim pesan balasan via HTTP POST langsung ke Telegram API."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        logger.error("TOKEN bot tidak diset di os.environ['TELEGRAM_BOT_TOKEN']!")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            pass
    except Exception as e:
        logger.error(f"Gagal mengirim balasan ke {chat_id}: {e}\n{traceback.format_exc()}")


@app.route("/", methods=["GET"])
def home():
    return "Bot Jadwal Piket is Active!", 200


@app.route("/webhook", methods=["POST", "GET"])
def telegram_webhook():
    if request.method == "GET":
        return "Webhook endpoint is ready!", 200

    try:
        update = request.get_json(force=True, silent=True)
        if not update:
            return "OK", 200

        message = update.get("message") or update.get("channel_post")
        if not message:
            return "OK", 200

        chat_id = message.get("chat", {}).get("id")
        msg_id = message.get("message_id")
        text = (message.get("text") or "").strip()

        if not text.startswith("/"):
            return "OK", 200

        # Ambil command dasar (misal /cekpiket@MyBot -> /cekpiket)
        cmd = text.split()[0].split("@")[0].lower()
        args = text.split()[1:]

        # WIB = UTC + 7
        wib = timezone(timedelta(hours=7))
        now = datetime.now(wib)

        if cmd in ["/start", "/help"]:
            reply = (
                "🤖 *Bot Jadwal Piket Operasional*\n\n"
                "Perintah yang tersedia:\n"
                "• /cekpiket - Lihat jadwal piket L1 & L2 hari ini\n"
                "• /allrole - Lihat jadwal piket seluruh role (L1, L2, Dev, L3)\n"
                "• /help - Bantuan ini"
            )
            send_reply(chat_id, reply, msg_id)

        elif cmd == "/cekpiket":
            role = "all" if (args and args[0].lower() == "all") else "default"
            try:
                jadwal_text = build_message(now, role=role)
                send_reply(chat_id, jadwal_text, msg_id)
            except Exception as e:
                send_reply(chat_id, f"⚠️ Gagal membaca jadwal: {e}", msg_id)

        elif cmd == "/allrole":
            try:
                jadwal_text = build_message(now, role="all")
                send_reply(chat_id, jadwal_text, msg_id)
            except Exception as e:
                send_reply(chat_id, f"⚠️ Gagal membaca jadwal: {e}", msg_id)

    except Exception as e:
        logger.error(f"Error handling webhook: {e}")

    return "OK", 200


if __name__ == "__main__":
    app.run(port=5000)
