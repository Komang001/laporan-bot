from app.browser import browser_manager


def main():

    print("=" * 60)
    print("PAGE STATE")
    print("=" * 60)

    browser_manager.connect()

    pages = browser_manager.get_pages()

    for i, page in enumerate(pages):

        print("-" * 60)
        print("Index :", i)

        try:
            print("URL :", page.url)
        except Exception as e:
            print(e)

        try:
            print("Ready State :",
                  page.evaluate("document.readyState"))
        except Exception as e:
            print("ReadyState ERROR :", e)

        try:
            print("Location :",
                  page.evaluate("window.location.href"))
        except Exception as e:
            print("Location ERROR :", e)

        try:
            print("Title :",
                  page.evaluate("document.title"))
        except Exception as e:
            print("Title ERROR :", e)


if __name__ == "__main__":
    main()  