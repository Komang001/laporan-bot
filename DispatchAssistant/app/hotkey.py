import keyboard
import threading


class HotkeyManager:

    def __init__(self):

        self.callback = None
        self.event = threading.Event()


    # ==================================================
    # Register Hotkey
    # ==================================================

    def register(self, callback):

        self.callback = callback


        keyboard.add_hotkey(
            "F8",
            self.trigger
        )


    # ==================================================
    # Trigger From Keyboard Thread
    # ==================================================

    def trigger(self):

        self.event.set()



    # ==================================================
    # Start Listener
    # ==================================================

    def start(self):

        print()
        print("=" * 50)
        print("Hotkey Manager")
        print("=" * 50)
        print("Menunggu tombol F8...")
        print("Tekan ESC untuk keluar.")
        print()


        while True:


            if self.event.is_set():

                self.event.clear()


                if self.callback:

                    self.callback()



            if keyboard.is_pressed("esc"):

                break


            self.event.wait(
                0.1
            )