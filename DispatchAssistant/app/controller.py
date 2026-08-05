import time
import threading

from app.browser import BrowserManager
from app.services.sygap_service import SygapService

LOOP_INTERVAL = 180


class DispatchController:

    def __init__(self, gui, cdp_port=9222):

        self.gui = gui
        self.cdp_port = cdp_port
        self.running = False
        self.on_complete = None
        self.browser_manager = BrowserManager(cdp_port=cdp_port)

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

                sygap = SygapService(
                    browser_manager=self.browser_manager,
                    stop_check=lambda: not self.running,
                )

                tickets = sygap.find_and_process_tickets(
                    log_callback=self.gui.write_log,
                    group_label=group_label,
                    group_id=group_id,
                )

                if not self.running:
                    self.gui.write_log("STOP - scan dihentikan user.")
                    return

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

                sygap = SygapService(
                    browser_manager=self.browser_manager,
                    stop_check=lambda: not self.running,
                )

                tickets = sygap.process_canclwork_tickets(
                    log_callback=self.gui.write_log,
                )

                if not self.running:
                    self.gui.write_log("STOP - scan dihentikan user.")
                    return

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

                sygap = SygapService(
                    browser_manager=self.browser_manager,
                    stop_check=lambda: not self.running,
                )

                tickets = sygap.process_dispatch_tickets(
                    log_callback=self.gui.write_log,
                )

                if not self.running:
                    self.gui.write_log("STOP - scan dihentikan user.")
                    return

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
                self.gui.write_log("============================================")
                self.gui.write_log("LOGIN INSERA DULU sebelum mulai scan!")
                self.gui.write_log("Buka tab INSERA lalu login ke:")
                self.gui.write_log("https://oss-incident.telkom.co.id")
                self.gui.write_log("Setelah login, bot akan mulai scan.")
                self.gui.write_log("============================================")
                self.gui.write_log("")

                self.gui.write_log("Step 3: Scanning GAMAS tickets...")

                self.gui.update_status("SCANNING")

                sygap = SygapService(
                    browser_manager=self.browser_manager,
                    stop_check=lambda: not self.running,
                )

                tickets = sygap.process_gamas_relations_tickets(
                    log_callback=self.gui.write_log,
                )

                if not self.running:
                    self.gui.write_log("STOP - scan dihentikan user.")
                    return

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
