import time
import threading

from app.browser import BrowserManager
from app.reader import read_ticket
from app.command_builder import build_dispatch_command
from app.parser import extract_owner_group
from app.services.biscuit_service import BiscuitService
from app.services.response_service import ResponseService
from app.services.sygap_service import SygapService
from app.models.ticket import Ticket
from app.logger import DispatchLogger

LOOP_INTERVAL = 600


class DispatchController:

    def __init__(self, gui, cdp_port=9222):

        self.gui = gui
        self.cdp_port = cdp_port
        self.running = False
        self.logger = DispatchLogger()
        self.on_complete = None
        self.browser_manager = BrowserManager(cdp_port=cdp_port)

    # ==========================================
    # Connect Browser (hanya cek Chrome, TANPA Playwright)
    # ==========================================

    def connect_browser(self):

        self.gui.write_log("Checking Chrome CDP...")

        self.gui.update_status("LAUNCHING")

        try:

            if not self.browser_manager.is_chrome_running():

                self.gui.write_log("Chrome belum jalan. Auto-launching...")

                launched = self.browser_manager.launch(
                    log_callback=self.gui.write_log
                )

                if not launched:

                    self.gui.write_log("ERROR: Gagal launch Chrome")

                    self.gui.update_status("ERROR")

                    return False

            self.gui.write_log("Chrome CDP OK.")

            self.gui.write_log("Opening SYGAP + BISCUIT tabs...")

            self.gui.update_status("CONNECTED")

            return True

        except Exception as e:

            self.gui.write_log(f"ERROR: {e}")

            self.gui.update_status("ERROR")

            return False

    # ==========================================
    # Disconnect Browser
    # ==========================================

    def disconnect_browser(self):

        try:

            self.browser_manager.disconnect()

            self.gui.write_log("Browser disconnected.")

            self.gui.update_status("DISCONNECTED")

        except Exception as e:

            self.gui.write_log(f"Disconnect error: {e}")

    # ==========================================
    # Start Assistant
    # ==========================================

    def start(self, ticket_id_input=None, owner_group_input=None):

        if self.running:

            self.gui.write_log("Assistant already running.")

            return

        self.running = True

        self.gui.update_status("STARTING")

        self.gui.write_log("=" * 40)

        self.gui.write_log("Starting Dispatch Assistant...")

        self.gui.write_log("=" * 40)

        thread = threading.Thread(
            target=self._run_dispatch,
            args=(ticket_id_input, owner_group_input),
            daemon=True,
        )

        thread.start()

    # ==========================================
    # Stop Assistant
    # ==========================================

    def stop(self):

        self.running = False

        self.gui.write_log("Stopping assistant...")

        self.gui.update_status("STOPPED")

    # ==========================================
    # Start Auto TO (Take Ownership)
    # ==========================================

    def start_auto(self, group_label="MO-INSERA", group_id=None):

        if self.running:

            self.gui.write_log("Assistant already running.")

            return

        self.running = True

        self.gui.update_status("STARTING")

        self.gui.write_log("=" * 40)

        self.gui.write_log(f"Starting TO: {group_label}...")

        self.gui.write_log("=" * 40)

        thread = threading.Thread(
            target=self._run_auto_to,
            args=(group_label, group_id),
            daemon=True,
        )

        thread.start()

    # ==========================================
    # Run Auto TO (Take Ownership) - Background Thread
    # ==========================================

    def _run_auto_to(self, group_label="MO-INSERA", group_id=None):

        connected_in_thread = False

        try:

            while self.running:

                self.gui.write_log("Step 1: Launching Chrome...")

                self.gui.update_status("LAUNCHING")

                if not self.browser_manager.is_chrome_running():

                    launched = self.browser_manager.launch(
                        log_callback=self.gui.write_log
                    )

                    if not launched:

                        self.gui.write_log("ERROR: Gagal launch Chrome")

                        self.gui.update_status("ERROR")

                        return

                self.gui.write_log("Step 2: Connecting browser...")

                self.gui.update_status("CONNECTING")

                try:

                    self.browser_manager.connect()

                    connected_in_thread = True

                except Exception as e:

                    self.gui.write_log(f"ERROR: Browser gagal: {e}")

                    self.gui.update_status("ERROR")

                    return

                self.gui.write_log("Browser connected.")

                self.gui.write_log("Opening SYGAP + BISCUIT tabs...")

                self.browser_manager.open_required_tabs(
                    log_callback=self.gui.write_log
                )

                self.gui.write_log(f"Step 3: Scanning {group_label} tickets...")

                self.gui.update_status("SCANNING")

                sygap = SygapService(browser_manager=self.browser_manager)

                tickets = sygap.find_and_process_tickets(
                    log_callback=self.gui.write_log,
                    group_label=group_label,
                    group_id=group_id,
                )

                if not tickets:

                    self.gui.write_log("No ASSIGNED tickets found.")

                else:

                    self.gui.write_log(f"Found {len(tickets)} ticket(s)!")

                    for idx, t in enumerate(tickets):

                        code = t["request_code"]

                        self.gui.write_log(f"  [{idx+1}] {code} -> IN_PROGRESS + {group_label}")

                self.gui.write_log("")

                self.gui.write_log("=" * 40)

                self.gui.write_log(f"AUTO TO SELESAI ({group_label})")

                self.gui.write_log("=" * 40)

                self.gui.write_log(f"Menunggu {LOOP_INTERVAL // 60} menit...")

                self.gui.update_status("WAITING")

                for _ in range(LOOP_INTERVAL):

                    if not self.running:

                        break

                    time.sleep(1)

        except Exception as e:

            self.gui.write_log(f"ERROR: {e}")

            self.gui.update_status("ERROR")

        finally:

            self.running = False

            if connected_in_thread:

                try:

                    self.browser_manager.disconnect()

                except Exception:

                    pass

            if self.on_complete:

                self.on_complete()

    # ==========================================
    # Start CANCLWORK WO
    # ==========================================

    def start_canclwork(self):

        if self.running:

            self.gui.write_log("Assistant already running.")

            return

        self.running = True

        self.gui.update_status("STARTING")

        self.gui.write_log("=" * 40)

        self.gui.write_log("Starting CANCLWORK WO...")

        self.gui.write_log("=" * 40)

        thread = threading.Thread(
            target=self._run_canclwork,
            daemon=True,
        )

        thread.start()

    # ==========================================
    # Run CANCLWORK WO - Background Thread
    # ==========================================

    def _run_canclwork(self):

        connected_in_thread = False

        try:

            while self.running:

                self.gui.write_log("Step 1: Launching Chrome...")

                self.gui.update_status("LAUNCHING")

                if not self.browser_manager.is_chrome_running():

                    launched = self.browser_manager.launch(
                        log_callback=self.gui.write_log
                    )

                    if not launched:

                        self.gui.write_log("ERROR: Gagal launch Chrome")

                        self.gui.update_status("ERROR")

                        return

                self.gui.write_log("Step 2: Connecting browser...")

                self.gui.update_status("CONNECTING")

                try:

                    self.browser_manager.connect()

                    connected_in_thread = True

                except Exception as e:

                    self.gui.write_log(f"ERROR: Browser gagal: {e}")

                    self.gui.update_status("ERROR")

                    return

                self.gui.write_log("Browser connected.")

                self.gui.write_log("Opening SYGAP + BISCUIT tabs...")

                self.browser_manager.open_required_tabs(
                    log_callback=self.gui.write_log
                )

                self.gui.write_log("Step 3: Scanning CANCLWORK tickets...")

                self.gui.update_status("SCANNING")

                sygap = SygapService(browser_manager=self.browser_manager)

                tickets = sygap.process_canclwork_tickets(
                    log_callback=self.gui.write_log,
                )

                if not tickets:

                    self.gui.write_log("No CANCLWORK tickets found.")

                else:

                    self.gui.write_log(f"Found {len(tickets)} CANCLWORK ticket(s)!")

                    for idx, t in enumerate(tickets):

                        code = t["request_code"]

                        wo = t["wo_number"]

                        self.gui.write_log(f"  [{idx+1}] {code} -> {wo} -> BISCUIT")

                self.gui.write_log("")

                self.gui.write_log("=" * 40)

                self.gui.write_log("CANCLWORK WO SELESAI")

                self.gui.write_log("=" * 40)

                self.gui.write_log(f"Menunggu {LOOP_INTERVAL // 60} menit...")

                self.gui.update_status("WAITING")

                for _ in range(LOOP_INTERVAL):

                    if not self.running:

                        break

                    time.sleep(1)

        except Exception as e:

            self.gui.write_log(f"ERROR: {e}")

            self.gui.update_status("ERROR")

        finally:

            self.running = False

            if connected_in_thread:

                try:

                    self.browser_manager.disconnect()

                except Exception:

                    pass

            if self.on_complete:

                self.on_complete()

    # ==========================================
    # Start DISPATCH
    # ==========================================

    def start_dispatch(self):

        if self.running:

            self.gui.write_log("Assistant already running.")

            return

        self.running = True

        self.gui.update_status("STARTING")

        self.gui.write_log("=" * 40)

        self.gui.write_log("Starting DISPATCH...")

        self.gui.write_log("=" * 40)

        thread = threading.Thread(
            target=self._run_auto_dispatch,
            daemon=True,
        )

        thread.start()

    # ==========================================
    # Run DISPATCH - Background Thread
    # ==========================================

    def _run_auto_dispatch(self):

        connected_in_thread = False

        try:

            while self.running:

                self.gui.write_log("Step 1: Launching Chrome...")

                self.gui.update_status("LAUNCHING")

                if not self.browser_manager.is_chrome_running():

                    launched = self.browser_manager.launch(
                        log_callback=self.gui.write_log
                    )

                    if not launched:

                        self.gui.write_log("ERROR: Gagal launch Chrome")

                        self.gui.update_status("ERROR")

                        return

                self.gui.write_log("Step 2: Connecting browser...")

                self.gui.update_status("CONNECTING")

                try:

                    self.browser_manager.connect()

                    connected_in_thread = True

                except Exception as e:

                    self.gui.write_log(f"ERROR: Browser gagal: {e}")

                    self.gui.update_status("ERROR")

                    return

                self.gui.write_log("Browser connected.")

                self.gui.write_log("Opening SYGAP + BISCUIT tabs...")

                self.browser_manager.open_required_tabs(
                    log_callback=self.gui.write_log
                )

                self.gui.write_log("Step 3: Scanning DISPATCH tickets...")

                self.gui.update_status("SCANNING")

                sygap = SygapService(browser_manager=self.browser_manager)

                tickets = sygap.process_dispatch_tickets(
                    log_callback=self.gui.write_log,
                )

                if not tickets:

                    self.gui.write_log("No DISPATCH tickets found.")

                else:

                    self.gui.write_log(f"Found {len(tickets)} DISPATCH ticket(s)!")

                    for idx, t in enumerate(tickets):

                        code = t["request_code"]

                        og = t.get("owner_group", t.get("type", ""))

                        self.gui.write_log(f"  [{idx+1}] {code} -> {og} -> BISCUIT")

                self.gui.write_log("")

                self.gui.write_log("=" * 40)

                self.gui.write_log("DISPATCH SELESAI")

                self.gui.write_log("=" * 40)

                self.gui.write_log(f"Menunggu {LOOP_INTERVAL // 60} menit...")

                self.gui.update_status("WAITING")

                for _ in range(LOOP_INTERVAL):

                    if not self.running:

                        break

                    time.sleep(1)

        except Exception as e:

            self.gui.write_log(f"ERROR: {e}")

            self.gui.update_status("ERROR")

        finally:

            self.running = False

            if connected_in_thread:

                try:

                    self.browser_manager.disconnect()

                except Exception:

                    pass

            if self.on_complete:

                self.on_complete()

    # ==========================================
    # Run Dispatch (Background Thread) - Manual
    # ==========================================

    def _run_dispatch(self, ticket_id_input, owner_group_input):

        connected_in_thread = False

        try:

            # ========================================
            # Step 1: Launch + Connect Browser
            # ========================================

            self.gui.write_log("Step 1/4: Launching Chrome...")

            self.gui.update_status("LAUNCHING")

            if not self.browser_manager.is_chrome_running():

                launched = self.browser_manager.launch(
                    log_callback=self.gui.write_log
                )

                if not launched:

                    self.gui.write_log("ERROR: Gagal launch Chrome")

                    self.gui.update_status("ERROR")

                    return

            self.gui.write_log("Step 2/4: Connecting browser...")

            self.gui.update_status("CONNECTING")

            try:

                self.browser_manager.connect()

                connected_in_thread = True

            except Exception as e:

                self.gui.write_log(f"ERROR: Browser gagal: {e}")

                self.gui.update_status("ERROR")

                return
            self.gui.write_log("Browser connected.")

            self.gui.write_log("Opening SYGAP + BISCUIT tabs...")

            self.browser_manager.open_required_tabs(
                log_callback=self.gui.write_log
            )


            pages = self.browser_manager.get_pages()

            self.gui.write_log(f"Found {len(pages)} tab(s).")

            for i, p in enumerate(pages):

                self.gui.write_log(f"  Tab {i+1}: {p.url[:70]}")

            # ========================================
            # Step 2: Tunggu Ticket Page
            # ========================================

            self.gui.write_log("Step 3/4: Waiting for ticket page...")

            self.gui.write_log("")

            self.gui.write_log("Pastikan sudah login SYGAP dan Biscuit.")

            self.gui.write_log("Buka halaman DETAIL TICKET di SYGAP.")

            self.gui.write_log("(klik ticket dari dashboard)")

            self.gui.write_log("")

            self.gui.update_status("WAITING TICKET")

            ticket_page = self._wait_for_ticket(timeout=600)

            if ticket_page is None:

                self.gui.write_log("ERROR: Ticket page tidak ditemukan.")

                self.gui.write_log("Buka detail ticket dulu lalu coba lagi.")

                self.gui.update_status("ERROR")

                return

            self.gui.write_log(f"Ticket found: {ticket_page.url[:60]}...")

            # ========================================
            # Step 3: Read Ticket
            # ========================================

            self.gui.write_log("Step 4/4: Reading ticket data...")

            self.gui.update_status("READING")

            self.gui.write_log(f"Reading from page: {ticket_page.url[:70]}")

            ticket_data = read_ticket(browser_manager=self.browser_manager)

            if ticket_data is None:

                self.gui.write_log("ERROR: Gagal membaca ticket.")

                self.gui.update_status("ERROR")

                return

            if ticket_id_input and not ticket_data.ticket_id:

                ticket_data.ticket_id = ticket_id_input

            if owner_group_input:

                ticket_data.owner_group = owner_group_input

            self.gui.write_log("---")

            self.gui.write_log(f"Request Number : {ticket_data.request_number}")

            self.gui.write_log(f"Ticket ID      : {ticket_data.ticket_id}")

            self.gui.write_log(f"Status         : {ticket_data.status}")

            self.gui.write_log(f"Owner Group    : {ticket_data.owner_group}")

            self.gui.write_log("---")

            if not ticket_data.ticket_id:

                self.gui.write_log("ERROR: Ticket ID kosong.")

                self.gui.update_status("ERROR")

                return

            if not ticket_data.owner_group:

                if owner_group_input:

                    ticket_data.owner_group = owner_group_input

                else:

                    self.gui.write_log("ERROR: Owner Group kosong.")

                    self.gui.write_log("Isi kolom Owner Group di GUI.")

                    self.gui.update_status("ERROR")

                    return

            # ========================================
            # Step 4: Dispatch
            # ========================================

            self.gui.write_log("Step 5/5: Dispatching...")

            self.gui.update_status("DISPATCHING")

            command = build_dispatch_command(ticket_data)

            if command is None:

                self.gui.write_log("ERROR: Gagal build command.")

                self.gui.update_status("ERROR")

                return

            self.gui.write_log(f"Command: {command}")

            biscuit_service = BiscuitService(browser_manager=self.browser_manager)

            if not biscuit_service.open():

                self.gui.write_log("ERROR: Biscuit tab tidak ditemukan.")

                self.gui.update_status("ERROR")

                return

            if not biscuit_service.focus_command():

                self.gui.write_log("ERROR: Command box tidak ditemukan.")

                self.gui.update_status("ERROR")

                return

            if not biscuit_service.send(command):

                self.gui.write_log("ERROR: Gagal kirim command.")

                self.gui.update_status("ERROR")

                return

            self.gui.write_log("Command sent. Waiting response...")

            self.gui.update_status("WAITING RESPONSE")

            response = ResponseService(
                biscuit_service.get_page(),
                biscuit_service.get_response_count_before(),
            ).read()

            if response:

                self.gui.write_log(f"Status  : {response.status}")

                self.gui.write_log(f"Message : {response.message}")

            self.logger.write(ticket_data, response)

            self.gui.write_log("=" * 40)

            self.gui.write_log("DISPATCH SELESAI")

            self.gui.write_log("=" * 40)

            self.gui.update_status("READY")

        except Exception as e:

            self.gui.write_log(f"ERROR: {e}")

            self.gui.update_status("ERROR")

        finally:

            self.running = False

            if connected_in_thread:

                try:

                    self.browser_manager.disconnect()

                except Exception:

                    pass

            if self.on_complete:

                self.on_complete()

    # ==========================================
    # Wait for Ticket (simple polling)
    # ==========================================

    def _wait_for_ticket(self, timeout=600):

        start = time.time()

        last_count = 0

        while time.time() - start < timeout:

            if not self.running:
                return None

            self.browser_manager.refresh_cache()

            ticket = self.browser_manager.get_active_ticket_page()

            if ticket is not None:

                return ticket

            pages = self.browser_manager.get_pages()

            if len(pages) != last_count:

                last_count = len(pages)

                self.gui.write_log(
                    f"Detected {len(pages)} tab(s). Waiting for ticket page..."
                )

                for i, p in enumerate(pages):

                    self.gui.write_log(f"  Tab {i+1}: {p.url[:70]}")

            time.sleep(3)

        return None

    # ==========================================
    # Start GAMAS RELATIONS
    # ==========================================

    def start_gamas_relations(self):

        if self.running:

            self.gui.write_log("Assistant already running.")

            return

        self.running = True

        self.gui.update_status("STARTING")

        self.gui.write_log("=" * 40)

        self.gui.write_log("Starting GAMAS RELATIONS...")

        self.gui.write_log("=" * 40)

        thread = threading.Thread(
            target=self._run_gamas_relations,
            daemon=True,
        )

        thread.start()

    # ==========================================
    # Run GAMAS RELATIONS - Background Thread
    # ==========================================

    def _run_gamas_relations(self):

        connected_in_thread = False

        try:

            while self.running:

                self.gui.write_log("Step 1: Launching Chrome...")

                self.gui.update_status("LAUNCHING")

                if not self.browser_manager.is_chrome_running():

                    launched = self.browser_manager.launch(
                        log_callback=self.gui.write_log
                    )

                    if not launched:

                        self.gui.write_log("ERROR: Gagal launch Chrome")

                        self.gui.update_status("ERROR")

                        return

                self.gui.write_log("Step 2: Connecting browser...")

                self.gui.update_status("CONNECTING")

                try:

                    self.browser_manager.connect()

                    connected_in_thread = True

                except Exception as e:

                    self.gui.write_log(f"ERROR: Browser gagal: {e}")

                    self.gui.update_status("ERROR")

                    return

                self.gui.write_log("Browser connected.")

                self.gui.write_log("Opening SYGAP tab...")

                self.browser_manager.open_required_tabs_gamas(
                    log_callback=self.gui.write_log
                )

                self.gui.write_log("")
                self.gui.write_log("Pastikan sudah login ke INSERA (oss-incident.telkom.co.id)")
                self.gui.write_log("Buka tab INSERA secara manual jika belum login.")
                self.gui.write_log("")

                self.gui.write_log("Step 3: Scanning GAMAS tickets...")

                self.gui.update_status("SCANNING")

                sygap = SygapService(browser_manager=self.browser_manager)

                tickets = sygap.process_gamas_relations_tickets(
                    log_callback=self.gui.write_log,
                )

                if not tickets:

                    self.gui.write_log("No GAMAS tickets found.")

                else:

                    self.gui.write_log(f"Found {len(tickets)} GAMAS ticket(s)!")

                    for idx, t in enumerate(tickets):

                        code = t["request_code"]

                        parent = t["parent_inc"]

                        children = len(t["child_incs"])

                        self.gui.write_log(f"  [{idx+1}] {code} -> Parent: {parent}, Children: {children}")

                self.gui.write_log("")

                self.gui.write_log("=" * 40)

                self.gui.write_log("GAMAS RELATIONS SELESAI")

                self.gui.write_log("=" * 40)

                self.gui.write_log(f"Menunggu {LOOP_INTERVAL // 60} menit...")

                self.gui.update_status("WAITING")

                for _ in range(LOOP_INTERVAL):

                    if not self.running:

                        break

                    time.sleep(1)

        except Exception as e:

            self.gui.write_log(f"ERROR: {e}")

            self.gui.update_status("ERROR")

        finally:

            self.running = False

            if connected_in_thread:

                try:

                    self.browser_manager.disconnect()

                except Exception:

                    pass

            if self.on_complete:

                self.on_complete()
