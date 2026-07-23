from app.services.biscuit_service import BiscuitService


def main():

    biscuit = BiscuitService()

    if not biscuit.open():
        return

    page = biscuit.get_page()

    print()
    print("=" * 60)
    print("BISCUIT BOT MESSAGE TEST")
    print("=" * 60)

    bot_names = page.locator("text=BISCUIT BOT")

    count = bot_names.count()

    print("Jumlah Message :", count)

    if count == 0:
        return

    print()

    last_name = bot_names.nth(count - 1)

    message = last_name.locator(
        "xpath=following::div[contains(@class,'whitespace-pre-wrap')][1]"
    )

    print(message.inner_text())


if __name__ == "__main__":
    main()