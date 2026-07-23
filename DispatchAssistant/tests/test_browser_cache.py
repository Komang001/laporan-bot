from app.browser import browser_manager


print("=" * 50)
print("Browser Cache Test")
print("=" * 50)


browser_manager.connect()


print("\nChecking Dashboard...")

dashboard = browser_manager.get_dashboard_page()

if dashboard:
    print("Dashboard FOUND")
    print(dashboard.url)

else:
    print("Dashboard NOT FOUND")



print("\nChecking Biscuit...")

biscuit = browser_manager.get_biscuit_page()

if biscuit:
    print("Biscuit FOUND")
    print(biscuit.url)

else:
    print("Biscuit NOT FOUND")



print("\nTesting Ensure Dashboard")

print(
    browser_manager.ensure_dashboard()
)



print("\nTesting Ensure Biscuit")

print(
    browser_manager.ensure_biscuit()
)



input("\nPress ENTER disconnect...")


browser_manager.disconnect()