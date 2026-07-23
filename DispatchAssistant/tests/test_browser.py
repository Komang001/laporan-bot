from app.browser import (
    connect_browser,
    save_html,
    close_browser,
)


def main():

    print("=" * 50)
    print("Industrial Programmer - Browser Test")
    print("=" * 50)

    connect_browser()

    input(
        "\nSilakan buka DETAIL TIKET di SYGAP.\n"
        "Jika halaman sudah terbuka tekan ENTER..."
    )

    save_html()

    input("\nTekan ENTER untuk disconnect...")

    close_browser()


if __name__ == "__main__":
    main()