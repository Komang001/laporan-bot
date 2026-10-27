"""Bot Telegram Mandiri untuk Jadwal Piket (L1, L2, Dev, L3).

Bisa dideploy ke Cloud 24 jam gratis (Koyeb / Render / Railway / dsb)
tanpa tergantung laptop atau browser SYGAP.

Fitur:
  /cekpiket -> Tampilkan jadwal piket hari ini (L1 & L2)
  /allrole  -> Tampilkan jadwal piket semua role (L1, L2, Dev, L3)
  /start & /help -> Bantuan

Environment Variables:
  TELEGRAM_BOT_TOKEN : Token bot dari @BotFather
  JADWAL_SHEET_URL   : (Opsional) URL Google Sheet jadwal
"""

import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# Reuse logic pembacaan sheet dari send_daily_jadwal
try:
    from DispatchAssistant.scripts.send_daily_jadwal import build_message
except ImportError:
    try:
        from scripts.send_daily_jadwal import build_message
    except ImportError:
        # Fallback jika dijalankan di root repo
        sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
        from DispatchAssistant.scripts.send_daily_jadwal import build_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("JadwalBot")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


async def post_init(application: Application):
    commands = [
        BotCommand("cekpiket", "Cek jadwal piket hari ini (L1 & L2)"),
        BotCommand("allrole", "Cek jadwal piket semua role (L1, L2, Dev, L3)"),
        BotCommand("help", "Bantuan & daftar perintah"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered.")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *Bot Jadwal Piket Operasional*\n\n"
        "Perintah yang tersedia:\n"
        "• /cekpiket - Lihat jadwal piket L1 & L2 hari ini\n"
        "• /allrole - Lihat jadwal piket seluruh role (L1, L2, Dev, L3)\n"
        "• /help - Bantuan ini"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_cekpiket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    role = "all" if (args and args[0].lower() == "all") else "default"
    await update.message.reply_text("Sedang mengambil jadwal dari Google Sheet... 🔄")
    try:
        now = datetime.now(ZoneInfo("Asia/Jakarta"))
        text = build_message(now, role=role)
        await update.message.reply_text(text, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error cekpiket: {e}")
        await update.message.reply_text(f"⚠️ Gagal membaca jadwal: {e}")


async def cmd_allrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sedang mengambil seluruh jadwal role... 🔄")
    try:
        now = datetime.now(ZoneInfo("Asia/Jakarta"))
        text = build_message(now, role="all")
        await update.message.reply_text(text, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error allrole: {e}")
        await update.message.reply_text(f"⚠️ Gagal membaca jadwal: {e}")


def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN belum diset di environment variables!")
        sys.exit(1)

    logger.info("Memulai Bot Jadwal Piket...")
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("cekpiket", cmd_cekpiket))
    app.add_handler(CommandHandler("allrole", cmd_allrole))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
