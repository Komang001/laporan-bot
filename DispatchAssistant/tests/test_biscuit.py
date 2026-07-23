from app.browser import (
    connect_browser,
    get_biscuit_page,
    activate_page,
)


def main():

    print("=" * 60)
    print("Industrial Programmer - BISCUIT Test")
    print("=" * 60)

    connect_browser()

    page = get_biscuit_page()

    if page is None:

        print()
        print("BISCUIT tidak ditemukan.")
        return

    print()
    print("BISCUIT ditemukan")
    print("-" * 60)
    print("Title :", page.title())
    print("URL   :", page.url)

    print()
    print("Mengaktifkan Tab BISCUIT...")

    if activate_page(page):

        print("Berhasil.")

    else:

        print("Gagal.")


if __name__ == "__main__":
    main()