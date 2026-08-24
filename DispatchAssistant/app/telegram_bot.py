import asyncio
import logging
import re
import threading
import time
from datetime import datetime, timedelta

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_ALLOWED_USER_IDS,
    CHROME_PORTS,
    REPORT_CHAT_IDS,
    REPORT_SCHEDULE_INTERVAL_MINUTES,
    REPORT_PERSONNEL,
)

logger = logging.getLogger(__name__)


# ==========================================
# Bot per fitur: forward log live + remote control fitur itu saja
# ==========================================

class FeatureTelegramBot:

    FEATURE_LABELS = {
        "canclwork": "CANCLWORK WO",
        "dispatch": "DISPATCH",
        "dispatch_incident": "DISPATCH INCIDENT",
        "change_service_id": "CHANGE SERVICE ID",
        "gamas_relations": "GAMAS RELATIONS",
    }

    def __init__(self, gui=None, key=None, token=None, port_key=None, chat_ids=None):
        self.gui = gui
        self.key = key
        self.token = token
        self.port_key = port_key
        self.chat_ids = chat_ids or []
        self.app = None
        self.thread = None
        self.loop = None
        self.log_buffer = []
        self.max_buffer = 100
        self._original_write_log = None
        self._last_send_ts = 0
        self._min_send_interval = 0.3

    # ------------------------------------------
    # Lifecycle
    # ------------------------------------------

    def start(self):
        if not self.token:
            logger.info(f"[{self.key}] token tidak diatur, skip.")
            return False

        self.app = Application.builder().token(self.token).build()
        self.app.add_handler(CommandHandler("start", self._cmd_start_feature))
        self.app.add_handler(CommandHandler("stop", self._cmd_stop_feature))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("logs", self._cmd_logs))
        self.app.add_handler(CommandHandler("help", self._cmd_help))

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self._hook_log()
        logger.info(f"[{self.key}] Telegram bot started.")
        return True

    def _run(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.app.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"[{self.key}] Telegram bot error: {e}")

    def _hook_log(self):
        if not self.gui or not hasattr(self.gui, "write_log"):
            return
        self._original_write_log = self.gui.write_log

        def hooked_log(message, **kwargs):
            try:
                self._original_write_log(message, **kwargs)
            except Exception:
                pass
            channel = kwargs.get("channel", "all")
            if channel == self.key:
                self._forward(message)

        self.gui.write_log = hooked_log

    # ------------------------------------------
    # Forward log live ke Telegram
    # ------------------------------------------

    # Hanya forward log krusial ke Telegram: kode tiket SYGAP (INC/REQ),
    # induk/anak GAMAS, pesan/respons SYGAP-BISCUIT, dan error/failure.
    # Log status biasa (step launch, jumlah row, deteksi tab, dll) TIDAK dikirim.
    _CRITICAL_PATTERNS = (
        re.compile(r"(?i)\b(?:inc|req|tt)\d{4,}\b"),  # kode tiket SYGAP
        re.compile(r"(?i)\bincs?\b"),                 # penyebutan INC umum
        re.compile(r"(?i)\bparent\b|\binduk\b|\bchild\b|\banak\b"),  # relasi GAMAS
        re.compile(r"(?i)\berror\b|\bgagal\b|\bfail(?:ed|ure)?\b|\bskip\b|\bstop\b|\babort"),
        re.compile(r"(?i)tidak ditemukan|not found|not accessible|not visible|belum login|timeout|retry"),
        re.compile(r"(?i)biscuit response|sending:|command sent|pesan|message|note"),
        re.compile(r"(?i)-> ok|-> failed|-> completed|-> to confirmed|completed|save ok|selesai|berhasil"),
        re.compile(r"(?i)change coordinator|coordinator changed|already my ticket|proceed"),
    )

    def _is_critical(self, message):
        return any(p.search(message) for p in self._CRITICAL_PATTERNS)

    _ERROR_PATTERNS = (
        re.compile(r"(?i)\berror\b|\bgagal\b|\bfail(?:ed|ure)?\b|\bskip\b|\bstop\b|\babort"),
        re.compile(r"(?i)tidak ditemukan|not found|not accessible|not visible|belum login|timeout|retry"),
        re.compile(r"(?i)-> failed|failed:|sending.*fail|invalid|rejected"),
    )
    _SUCCESS_PATTERNS = (
        re.compile(r"(?i)-> ok|-> completed|-> to confirmed|to confirmed:|completed|save ok|selesai|berhasil|dispatched successfully"),
        re.compile(r"(?i)biscuit response:\s*success"),
    )

    def _mark(self, message):
        if any(p.search(message) for p in self._ERROR_PATTERNS):
            return "\u274c " + message
        if any(p.search(message) for p in self._SUCCESS_PATTERNS):
            return "\u2705 " + message
        return "\u2139\ufe0f " + message

    def _forward(self, message):
        if not self._is_critical(message):
            return
        message = self._mark(message)
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        self.log_buffer.append(line)
        if len(self.log_buffer) > self.max_buffer:
            self.log_buffer.pop(0)

        now = time.monotonic()
        if now - self._last_send_ts < self._min_send_interval:
            return
        self._last_send_ts = now

        parts = [p for p in line.split("\n") if p.strip()]
        for part in parts[:5]:
            self._send_text(part)

    def _send_text(self, text):
        if not self.app or not self.app.bot or self.loop is None:
            return
        text = text[:4000]
        if not text:
            return

        async def _send():
            for cid in self.chat_ids:
                try:
                    await self.app.bot.send_message(
                        chat_id=cid,
                        text=text,
                        disable_web_page_preview=True,
                    )
                except Exception as e:
                    logger.error(f"[{self.key}] send ke {cid} error: {e}")

        try:
            asyncio.run_coroutine_threadsafe(_send(), self.loop)
        except Exception as e:
            logger.error(f"[{self.key}] schedule send error: {e}")

    def _is_authorized(self, update: Update) -> bool:
        if not TELEGRAM_ALLOWED_USER_IDS:
            return True
        return update.effective_user.id in TELEGRAM_ALLOWED_USER_IDS

    def _label(self):
        return self.FEATURE_LABELS.get(self.key, self.key)

    def _is_running(self):
        if not self.gui:
            return False
        ctrl = self.gui.controllers.get(self.key)
        return bool(ctrl and ctrl.running)

    # ------------------------------------------
    # Commands
    # ------------------------------------------

    async def _cmd_start_feature(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        if self._is_running():
            await update.message.reply_text(f"{self._label()} sudah running.")
            return
        if not self.gui:
            await update.message.reply_text("GUI tidak terhubung.")
            return
        self.gui._start_feature(self.key, {"port_key": self.port_key})
        await update.message.reply_text(f"Menjalankan {self._label()}...")

    async def _cmd_stop_feature(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        if not self.gui:
            await update.message.reply_text("GUI tidak terhubung.")
            return
        if not self._is_running():
            await update.message.reply_text(f"{self._label()} sedang tidak running.")
            return
        self.gui._stop_feature(self.key)
        await update.message.reply_text(f"Stopping {self._label()}...")

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        status = "RUNNING" if self._is_running() else "STOPPED"
        await update.message.reply_text(f"{self._label()}: {status}")

    async def _cmd_logs(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        if not self.log_buffer:
            await update.message.reply_text("Belum ada log.")
            return
        recent = self.log_buffer[-20:]
        text = f"Log terakhir ({self._label()}):\n\n" + "\n".join(recent)
        if len(text) > 4000:
            text = text[-4000:]
        await update.message.reply_text(text)

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        lines = [
            f"Bot {self._label()}",
            "",
            "/start  - Mulai fitur",
            "/stop   - Stop fitur",
            "/status - Status fitur",
            "/logs   - Log terakhir",
            "/help   - Bantuan ini",
        ]
        await update.message.reply_text("\n".join(lines))


class TelegramRemote:

    def __init__(self, gui=None):
        self.gui = gui
        self.app = None
        self.thread = None
        self.loop = None
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
        self.app.add_handler(CommandHandler("report", self._cmd_report))
        self.app.add_handler(CommandHandler("piket", self._cmd_piket))
        self.app.add_handler(CommandHandler("cekpiket", self._cmd_cekpiket))
        self.app.add_handler(CommandHandler("to_insera", self._cmd_start_to_insera))
        self.app.add_handler(CommandHandler("to_bima", self._cmd_start_to_bima))
        self.app.add_handler(CommandHandler("canclwork", self._cmd_start_canclwork))
        self.app.add_handler(CommandHandler("dispatch", self._cmd_start_dispatch))
        self.app.add_handler(CommandHandler("dispatch_incident", self._cmd_start_dispatch_incident))
        self.app.add_handler(CommandHandler("gamas", self._cmd_start_gamas))

        self._setup_report_schedule()

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

        self._hook_log()

        logger.info("Telegram bot started.")
        return True

    # ------------------------------------------
    # Command suggestion (muncul di atas keyboard Telegram)
    # ------------------------------------------

    async def _post_init(self, application):
        commands = [
            BotCommand("start", "Tampilkan menu & daftar perintah"),
            BotCommand("help", "Tampilkan semua perintah"),
            BotCommand("status", "Cek status semua fitur"),
            BotCommand("logs", "Lihat log terakhir"),
            BotCommand("report", "Kirim laporan harian sekarang"),
            BotCommand("piket", "Set/lihat piket (@nama1 @nama2 ...)"),
            BotCommand("cekpiket", "Cek piket shift aktif & PIC hari ini"),
            BotCommand("to_insera", "Start TO MO-INSERA"),
            BotCommand("to_bima", "Start TO MO-BIMA"),
            BotCommand("canclwork", "Start CANCLWORK WO"),
            BotCommand("dispatch", "Start DISPATCH"),
            BotCommand("dispatch_incident", "Start DISPATCH INCIDENT"),
            BotCommand("gamas", "Start GAMAS RELATIONS"),
            BotCommand("stop", "Stop semua fitur"),
        ]
        try:
            await application.bot.set_my_commands(commands)
            logger.info("Command suggestion Telegram terdaftar (%d perintah).", len(commands))
        except Exception as e:
            logger.error(f"Gagal set_my_commands: {e}")

    def _run(self):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.app.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Telegram bot error: {e}")

    def _hook_log(self):
        if self.gui and hasattr(self.gui, "write_log"):
            self._original_write_log = self.gui.write_log

            def hooked_log(message, **kwargs):
                self._original_write_log(message, **kwargs)
                self.log_buffer.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
                )
                if len(self.log_buffer) > self.max_buffer:
                    self.log_buffer.pop(0)

            self.gui.write_log = hooked_log

    def _get_allowed_chat_ids(self):
        if not TELEGRAM_ALLOWED_USER_IDS:
            return []
        return TELEGRAM_ALLOWED_USER_IDS

    # ==========================================
    # Report Harian
    # ==========================================

    def _setup_report_schedule(self):
        if not self.app:
            return
        interval = int(REPORT_SCHEDULE_INTERVAL_MINUTES or 0)
        if interval <= 0:
            logger.warning("REPORT_SCHEDULE_INTERVAL_MINUTES tidak valid, jadwal dilewati.")
            return
        now = datetime.now()
        # Jangan pakai datetime naive utk 'first' (PTB menganggapnya UTC).
        # Gunakan timedelta relatif: hitung detik ke boundary interval berikutnya.
        interval_sec = interval * 60
        secs_to_next = interval_sec - (now.minute % interval) * 60 - now.second
        if secs_to_next <= 0:
            secs_to_next += interval_sec
        first = timedelta(seconds=secs_to_next)
        next_run = now + first
        try:
            self.app.job_queue.run_repeating(
                self._job_daily_report,
                interval=interval_sec,
                first=first,
                name="daily_report_interval",
            )
            logger.info(
                f"Schedule report: tiap {interval} menit (24 jam), "
                f"mulai {next_run:%H:%M:%S} (boundary 00:00 + kelipatan {interval} menit)"
            )
        except Exception as e:
            logger.error(f"Gagal daftar jadwal report: {e}")

    async def _job_daily_report(self, context: ContextTypes.DEFAULT_TYPE):
        chat_ids = REPORT_CHAT_IDS or self._get_allowed_chat_ids()
        if not chat_ids:
            logger.warning("REPORT_CHAT_IDS kosong, report terjadwal dilewati.")
            return
        try:
            text = await self._build_report_async()
        except Exception as e:
            text = f"⚠️ Gagal membuat laporan: {e}"
        for chat_id in chat_ids:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                logger.error(f"Send report ke {chat_id} error: {e}")

    async def _cmd_report(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        await update.message.reply_text("Menyusun laporan... mohon tunggu 🔄")
        try:
            text = await self._build_report_async()
        except Exception as e:
            logger.error(f"Report error: {e}")
            text = f"⚠️ Gagal membuat laporan: {e}"
        await update.message.reply_text(text, disable_web_page_preview=True)

    async def _cmd_piket(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Set/lihat/hapus piket harian.

        /piket                 -> lihat piket hari ini
        /piket @u1 @u2 @u3     -> set piket hari ini
        /piket YYYY-MM-DD ...  -> set piket untuk tanggal tertentu
        /piket clear           -> hapus piket hari ini (kembali ke settings)
        """
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return

        from app.services.report_service import clear_piket, get_piket, save_piket

        args = ctx.args or []
        today = datetime.now().strftime("%Y-%m-%d")

        if not args:
            names = get_piket(today)
            if names:
                await update.message.reply_text(
                    f"Piket {today} ({len(names)} orang):\n" + "\n".join(names)
                )
            else:
                await update.message.reply_text(
                    f"Piket {today} belum diset. Fallback ke settings:\n"
                    + "\n".join(REPORT_PERSONNEL)
                    + f"\n\nSet dengan: /piket nama1 nama2 nama3 (mis: /piket windu dika rizky)"
                )
            return

        if args[0].lower() in ("clear", "reset", "hapus"):
            if clear_piket(today):
                await update.message.reply_text(
                    f"Piket {today} dihapus. Report kembali pakai settings:\n"
                    + "\n".join(REPORT_PERSONNEL)
                )
            else:
                await update.message.reply_text(f"Piket {today} memang belum diset.")
            return

        target_date = today
        rest = args
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", args[0]):
            target_date = args[0]
            rest = args[1:]

        names = [n for n in rest if n.strip()]
        if not names:
            await update.message.reply_text(
                "Format salah. Contoh:\n"
                "/piket windu dika rizky\n"
                "/piket 2026-08-07 windu dika rizky\n"
                "(bisa juga pakai @tag)"
            )
            return

        saved = save_piket(names, target_date)
        await update.message.reply_text(
            f"✅ Piket {target_date} disimpan ({len(saved)} orang):\n"
            + "\n".join(saved)
        )

    async def _cmd_cekpiket(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Tampilkan piket shift aktif dan PIC hari ini dari jadwal sheet."""
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        await update.message.reply_text("Menyusun info piket... 🔄")
        try:
            text = await asyncio.to_thread(self._cekpiket_sync)
        except Exception as e:
            logger.error(f"Cekpiket error: {e}")
            text = f"⚠️ Gagal membaca jadwal: {e}"
        await update.message.reply_text(text, disable_web_page_preview=True)

    def _cekpiket_sync(self):
        from app.services.report_service import build_jadwal_piket_text

        text = build_jadwal_piket_text(datetime.now())
        if text is None:
            return "⚠️ Gagal membaca jadwal piket dari Google Sheet."
        return text

    async def _build_report_async(self):
        loop = asyncio.get_running_loop()
        fut = loop.create_future()

        def runner():
            # Jalankan laporan di THREAD SEGAR (bukan pool executor).
            # Playwright sync memakai greenlet + loop per thread; kalau sebuah
            # run gagal di tengah jalan, loop thread itu bisa tetap "running"
            # dan meracuni thread pool untuk run berikutnya.
            try:
                text = self._build_report_sync()
                loop.call_soon_threadsafe(fut.set_result, text)
            except Exception as e:
                loop.call_soon_threadsafe(fut.set_exception, e)

        threading.Thread(target=runner, daemon=True, name="report-worker").start()
        return await fut

    def _build_report_sync(self):
        from app.services.report_service import generate_report

        return generate_report(log_callback=self._report_log)

    def _report_log(self, message):
        logger.info(f"[report] {message}")
        if self.gui and hasattr(self.gui, "write_log"):
            try:
                self.gui.write_log(message, channel="report")
            except Exception:
                pass

    def send_report_text(self, text):
        """Kirim laporan ke REPORT_CHAT_IDS dari thread lain (GUI)."""
        if not self.app or not self.app.bot or self.loop is None:
            return False
        try:

            async def _send():
                chat_ids = REPORT_CHAT_IDS or self._get_allowed_chat_ids()
                for cid in chat_ids:
                    try:
                        await self.app.bot.send_message(
                            chat_id=cid,
                            text=text,
                            disable_web_page_preview=True,
                        )
                    except Exception as e:
                        logger.error(f"Send report ke {cid} error: {e}")

            asyncio.run_coroutine_threadsafe(_send(), self.loop)
            return True
        except Exception as e:
            logger.error(f"send_report_text error: {e}")
            return False

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
            "/status   - Cek status semua fitur",
            "/logs     - Lihat log terakhir",
            "/report   - Kirim laporan harian sekarang",
            "/piket    - Set/lihat piket hari ini (@user1 @user2 ...)",
            "/cekpiket - Cek piket shift aktif & PIC hari ini",
            "/help     - Lihat semua perintah",
            "",
            "Mulai fitur:",
            "/to_insera  - Start TO MO-INSERA",
            "/to_bima    - Start TO MO-BIMA",
            "/canclwork  - Start CANCLWORK WO",
            "/dispatch   - Start DISPATCH",
            "/dispatch_incident - Start DISPATCH INCIDENT",
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
        features = ["to_insera", "to_bima", "canclwork", "dispatch", "dispatch_incident", "gamas_relations"]
        labels = {
            "to_insera": "TO MO-INSERA",
            "to_bima": "TO MO-BIMA",
            "canclwork": "CANCLWORK WO",
            "dispatch": "DISPATCH",
            "dispatch_incident": "DISPATCH INCIDENT",
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

    async def _cmd_start_dispatch_incident(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("Akses ditolak.")
            return
        await self._start_feature(update, "dispatch_incident", None, None)

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
            "dispatch_incident": "DISPATCH_INCIDENT",
            "gamas_relations": "GAMAS",
        }
        port = CHROME_PORTS.get(port_key_map.get(key, "TO"), 9222)

        from app.controller import DispatchController

        ctrl = DispatchController(
            gui=self.gui._make_feature_adapter(key),
            cdp_port=port,
        )
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
        elif key == "dispatch_incident":
            ctrl.start_dispatch_incident()
        elif key == "gamas_relations":
            ctrl.start_gamas_relations()

        await update.message.reply_text(f"Started: {key}")


from config.settings import INSERA_GROUP_ID
