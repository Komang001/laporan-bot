from app.browser import browser_manager

print("=" * 60)
print("NEW PAGE TEST")
print("=" * 60)

browser = browser_manager.connect()

context = browser.contexts[0]

print()
print("Total Page Sebelum :", len(context.pages))

page = context.new_page()

page.goto("https://example.com")

print("Title :", page.title())

print("URL   :", page.url)

print()

print("Total Page Sesudah :", len(context.pages))

input("\nENTER untuk selesai...")