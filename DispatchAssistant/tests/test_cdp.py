from app.browser import connect_browser

browser = connect_browser()

print("=" * 60)
print("CDP TEST")
print("=" * 60)

print()
print("Browser Type:")
print(type(browser))

print()
print("Browser Attributes:")
for name in dir(browser):

    if "cdp" in name.lower():
        print(name)

print()
print("Context Attributes:")
context = browser.contexts[0]

for name in dir(context):

    if "cdp" in name.lower():
        print(name)