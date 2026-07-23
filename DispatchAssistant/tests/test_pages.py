from app.browser import browser_manager


def main():

    print("=" * 60)
    print("ALL PAGES")
    print("=" * 60)

    browser_manager.connect()

    pages = browser_manager.get_pages()

    print()
    print(f"Total Pages : {len(pages)}")
    print()

    for i, page in enumerate(pages):

        print("-" * 60)
        print(f"Index : {i}")

        try:
            print("URL :", page.url)
        except Exception as e:
            print("URL ERROR :", e)

        try:
            print("Is Closed :", page.is_closed())
        except Exception as e:
            print("STATE ERROR :", e)

        try:
            print("Title :", page.title(timeout=1000))
        except Exception:
            print("Title : <timeout>")


if __name__ == "__main__":
    main()