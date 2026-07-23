from app.browser import connect_browser
from app.services.biscuit_service import BiscuitService


def main():

    print("=" * 60)
    print("Industrial Programmer - Biscuit Service Test")
    print("=" * 60)

    connect_browser()

    biscuit = BiscuitService()

    if not biscuit.open():
        return

    biscuit.focus_command()


if __name__ == "__main__":
    main()