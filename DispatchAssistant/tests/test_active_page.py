from app.browser import connect_browser

browser = connect_browser()

print("=" * 60)
print("ACTIVE PAGE TEST")
print("=" * 60)

for context_index, context in enumerate(browser.contexts):

    print()
    print(f"Context {context_index}")

    for index, page in enumerate(context.pages):

        try:

            print("-" * 40)
            print("Index :", index)
            print("Title :", page.title())
            print("URL   :", page.url)

            print("Has Focus :", page.evaluate("""
                () => document.hasFocus()
            """))

            print("Visibility :", page.evaluate("""
                () => document.visibilityState
            """))

        except Exception as e:

            print(e)