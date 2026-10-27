"""Telegram Bot Webhook untuk Jadwal Piket di PythonAnywhere (Free Tier).

Menangani request langsung dari Telegram via HTTPS Webhook (Flask).
Bebas polling loop, ringan, dan gratis 24 jam di PythonAnywhere.
"""

import json
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify

# Pastikan path modul terbaca
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from send_daily_jadwal import build_message
except ImportError:
    from DispatchAssistant.scripts.send_daily_jadwal import build_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PA_JadwalBot")

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def send_reply(chat_id, text, reply_to_message_id=None):
    """Kirim pesan balasan via HTTP POST langsung ke Telegram API."""
    import urllib.request
    import urllib.parse

    if not TOKEN:
        logger.error("TOKEN bot tidak diset!")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            pass
    except Exception as e:
        logger.error(f"Gagal mengirim balasan ke {chat_id}: {e}")


@app.route("/", methods=["GET"])
def home():
    return "Bot Jadwal Piket is Active!", 200


@app.route(f"/webhook", methods=["POST"])
def telegram_webhook():
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

    now = datetime.now(ZoneInfo("Asia/Jakarta"))

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

    return "OK", 200


if __name__ == "__main__":
    app.run(port=5000)
