import logging
import threading
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_ALLOWED_USER_IDS,
    CHROME_PORTS,
)

logger = logging.getLogger(__name__)


class TelegramRemote:

    def __init__(self, gui=None):
        self.gui = gui
        self.app = None
        self.thread = None
        self.log_buffer = []
        self.max_buffer = 50
        self._original_write_log = None

    def start(self):
        if not TELEGRAM_BOT_TOKEN:
            logger.info("Telegram bot token not set, skipping.")
            return False

        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("stop", self._cmd_stop))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("logs", self._cmd_logs))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("to_insera", self._cmd_start_to_insera))
        self.app.add_handler(CommandHandler("to_bima", self._cmd_start_to_bima))
        self.app.add_handler(CommandHandler("canclwork", self._cmd_start_canclwork))
        self.app.add_handler(CommandHandler("dispatch", self._cmd_start_dispatch))
        self.app.add_handler(CommandHandler("gamas", self._cmd_start_gamas))

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

        self._hook_log()

        logger.info("Telegram bot started.")
        return True

    def _run(self):
        try:
            self.app.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Telegram bot error: {e}")

    def _hook_log(self):
        if self.gui and hasattr(self.gui, "write_log"):
            self._original_write_log = self.gui.write_log

            def hooked_log(message):
                self._original_write_log(message)
                self.log_buffer.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
                )
                if len(self.log_buffer) > self.max_buffer:
                    self.log_buffer.pop(0)
                self._broadcast_log(message)

            self.gui.write_log = hooked_log

    def _broadcast_log(self, message):
        if not self.app or not self.app.bot:
            return
        try:
            chat_ids = self._get_allowed_chat_ids()
            if not chat_ids:
                return
            asyncio_module = __import__("asyncio")
            for chat_id in chat_ids:
                try:
                    asyncio_module.get_event_loop().create_task(
                        self.app.bot.send_message(
                            chat_id=chat_id,
                            text=f" {message}",
                        )
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def _get_allowed_chat_ids(self):
        if not TELEGRAM_ALLOWED_USER_IDS:
            return []
        return TELEGRAM_ALLOWED_USER_IDS

    def _is_authorized(self, update: Update) -> bool:
        if not TELEGRAM_ALLOWED_USER_IDS:
            return True
        return update.effective_user.id in TELEGRAM_ALLOWED_USER_IDS

    # ==========================================
    # Commands
    # ==========================================

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return

        lines = [
            "DispatchAssistant Remote Control",
            "",
            "Perintah tersedia:",
            "/status  - Cek status semua fitur",
            "/logs    - Lihat log terakhir",
            "/help    - Lihat semua perintah",
            "",
            "Mulai fitur:",
            "/to_insera  - Start TO MO-INSERA",
            "/to_bima    - Start TO MO-BIMA",
            "/canclwork  - Start CANCLWORK WO",
            "/dispatch   - Start DISPATCH",
            "/gamas      - Start GAMAS RELATIONS",
            "",
            "/stop       - Stop semua fitur",
        ]
        await update.message.reply_text("\n".join(lines))

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        await self._cmd_start(update, ctx)

    async def _cmd_stop(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return

        if not self.gui:
            await update.message.reply_text("GUI tidak terhubung.")
            return

        stopped = []
        for key, ctrl in list(self.gui.controllers.items()):
            if ctrl.running:
                ctrl.stop()
                stopped.append(key)

        if stopped:
            await update.message.reply_text(f"Stopped: {', '.join(stopped)}")
        else:
            await update.message.reply_text("Tidak ada fitur yang sedang jalan.")

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return

        if not self.gui:
            await update.message.reply_text("GUI tidak terhubung.")
            return

        lines = ["Status Fitur:", ""]
        features = ["to_insera", "to_bima", "canclwork", "dispatch", "gamas_relations"]
        labels = {
            "to_insera": "TO MO-INSERA",
            "to_bima": "TO MO-BIMA",
            "canclwork": "CANCLWORK WO",
            "dispatch": "DISPATCH",
            "gamas_relations": "GAMAS RELATIONS",
        }
        for key in features:
            label = labels.get(key, key)
            ctrl = self.gui.controllers.get(key)
            if ctrl and ctrl.running:
                lines.append(f"  {label}: RUNNING")
            else:
                lines.append(f"  {label}: STOPPED")

        await update.message.reply_text("\n".join(lines))

    async def _cmd_logs(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return

        if not self.log_buffer:
            await update.message.reply_text("Belum ada log.")
            return

        recent = self.log_buffer[-20:]
        text = "Log terakhir:\n\n" + "\n".join(recent)

        if len(text) > 4000:
            text = text[-4000:]

        await update.message.reply_text(text)

    async def _cmd_start_to_insera(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        await self._start_feature(update, "to_insera", "MO-INSERA", INSERA_GROUP_ID)

    async def _cmd_start_to_bima(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        await self._start_feature(update, "to_bima", "MO-BIMA", None)

    async def _cmd_start_canclwork(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        await self._start_feature(update, "canclwork", None, None)

    async def _cmd_start_dispatch(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        await self._start_feature(update, "dispatch", None, None)

    async def _cmd_start_gamas(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        await self._start_feature(update, "gamas_relations", None, None)

    async def _start_feature(self, update, key, group_label, group_id):
        if not self.gui:
            await update.message.reply_text("GUI tidak terhubung.")
            return

        if key in self.gui.controllers and self.gui.controllers[key].running:
            await update.message.reply_text(f"{key} sudah running.")
            return

        port_key_map = {
            "to_insera": "TO",
            "to_bima": "TO",
            "canclwork": "CANCLWORK",
            "dispatch": "DISPATCH",
            "gamas_relations": "GAMAS",
        }
        port = CHROME_PORTS.get(port_key_map.get(key, "TO"), 9222)

        from app.controller import DispatchController

        ctrl = DispatchController(gui=self.gui, cdp_port=port)
        ctrl.on_complete = lambda k=key: self.gui._on_feature_complete(k)
        self.gui.controllers[key] = ctrl

        if key == "to_insera":
            ctrl.start_auto(group_label=group_label, group_id=group_id)
        elif key == "to_bima":
            ctrl.start_auto(group_label=group_label, group_id=group_id)
        elif key == "canclwork":
            ctrl.start_canclwork()
        elif key == "dispatch":
            ctrl.start_dispatch()
        elif key == "gamas_relations":
            ctrl.start_gamas_relations()

        await update.message.reply_text(f"Started: {key}")


from config.settings import INSERA_GROUP_ID
