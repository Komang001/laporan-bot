from time import sleep

from app.browser import connect_browser


def main():

    browser = connect_browser()

    print("=" * 50)
    print("ACTIVE TAB TEST")
    print("=" * 50)

    last_url = ""

    while True:

        for context in browser.contexts:

            for page in context.pages:

                try:

                    if page.evaluate("document.hasFocus()"):

                        if page.url != last_url:

                            last_url = page.url

                            print()
                            print("ACTIVE PAGE")
                            print("Title :", page.title())
                            print("URL   :", page.url)

                except:
                    pass

        sleep(0.5)


if __name__ == "__main__":
    main()