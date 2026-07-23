from app.browser import browser_manager


def main():

    browser = browser_manager.connect()

    print("=" * 60)
    print("CDP TARGETS")
    print("=" * 60)

    for context_index, context in enumerate(browser.contexts):

        print(f"\nContext {context_index}")

        for index, page in enumerate(context.pages):

            print("-" * 40)
            print("Index :", index)
            print("Title :", page.title())
            print("URL   :", page.url)

            try:
                session = context.new_cdp_session(page)

                info = session.send("Target.getTargetInfo")

                print("Target :", info)

            except Exception as e:
                print("CDP Error :", e)


if __name__ == "__main__":
    main()