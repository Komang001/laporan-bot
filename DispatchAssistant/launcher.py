import socket
import subprocess
import sys
import time

from app.browser import browser_manager
from app.controller import Controller
from app.hotkey import HotkeyManager


# ==================================================
# Configuration
# ==================================================

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

PROFILE = r"C:\ChromeDebug"

DASHBOARD = (
    "https://sygap.telkom.co.id/req_fulfillment"
)

BISCUIT = (
    "https://biscuit-dashboard-dev-playground.apps.mypaas.telkom.co.id/helpdesk/tools/inseratools"
)



# ==================================================
# Check Chrome Debug
# ==================================================

def debug_running():

    s = socket.socket()

    try:

        s.connect(
            ("127.0.0.1", 9222)
        )

        s.close()

        return True


    except Exception:

        return False



# ==================================================
# Start Chrome Debug
# ==================================================

def start_chrome():

    if debug_running():

        print()
        print("Chrome Debug sudah berjalan.")

        return True



    print()
    print("Menjalankan Chrome Debug...")


    subprocess.Popen(
        [
            CHROME,
            "--remote-debugging-port=9222",
            f"--user-data-dir={PROFILE}"
        ]
    )



    for _ in range(15):

        if debug_running():

            print("Chrome Debug Ready")

            return True


        time.sleep(1)



    return False



# ==================================================
# Prepare Browser
# ==================================================

def prepare_browser():

    print()
    print("Menghubungkan Browser...")


    browser_manager.connect()


    print()
    print("=" * 60)
    print("Browser Connected")
    print("=" * 60)

    print()
    print("Silakan persiapkan browser:")
    print()
    print("1. Login SYGAP")
    print("2. Buka halaman Request Fulfillment")
    print("3. Buka DETAIL TICKET yang ingin diproses")
    print("4. Login dan buka Biscuit Dashboard")
    print()

    input("Jika semua sudah siap, tekan ENTER...")


    print()
    print("Refresh Browser Cache...")


    browser_manager.refresh_cache()


    print()


    if browser_manager.get_dashboard_page():

        print("SYGAP Dashboard ditemukan.")

    else:

        print("SYGAP Dashboard belum ditemukan.")



    if browser_manager.get_biscuit_page():

        print("Biscuit Dashboard ditemukan.")

    else:

        print("Biscuit Dashboard belum ditemukan.")



    print()

    print("Browser Preparation selesai.")



# ==================================================
# Start Application
# ==================================================

def main():


    print("=" * 60)
    print("Industrial Programmer Launcher")
    print("=" * 60)



    if not start_chrome():

        print(
            "Chrome gagal dijalankan."
        )

        sys.exit()



    prepare_browser()



    controller = Controller()



    hotkey = HotkeyManager()



    hotkey.register(
        controller.run
    )



    print()
    print("=" * 60)
    print("Industrial Programmer READY")
    print("=" * 60)
    print()
    print("Tekan F8 untuk Dispatch Ticket.")
    print("Tekan ESC untuk keluar.")
    print()



    try:

        hotkey.start()


    finally:

        browser_manager.disconnect()



# ==================================================
# Entry Point
# ==================================================

if __name__ == "__main__":

    main()