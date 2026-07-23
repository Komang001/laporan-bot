from app.browser import connect_browser

browser = connect_browser()

print("=" * 60)
print("CDP TARGET INFO")
print("=" * 60)

session = browser.new_browser_cdp_session()

targets = session.send("Target.getTargets")

for target in targets["targetInfos"]:

    print("-" * 60)
    print("Target ID :", target.get("targetId"))
    print("Type      :", target.get("type"))
    print("Title     :", target.get("title"))
    print("URL       :", target.get("url"))
    print("Attached  :", target.get("attached"))
    print("Opener ID :", target.get("openerId"))
    print("Browser Context :", target.get("browserContextId"))

    # Tampilkan semua field lain jika ada
    extra = {
        k: v for k, v in target.items()
        if k not in {
            "targetId",
            "type",
            "title",
            "url",
            "attached",
            "openerId",
            "browserContextId"
        }
    }

    if extra:
        print("Extra :", extra)