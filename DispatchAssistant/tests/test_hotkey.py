from app.hotkey import HotkeyManager
from app.controller import Controller


controller = Controller()


def dispatch():

    print()
    print("=" * 60)
    print("F8 DITEKAN")
    print("=" * 60)

    controller.run()


def main():

    hotkey = HotkeyManager()

    hotkey.register(dispatch)

    hotkey.start()


if __name__ == "__main__":
    main()