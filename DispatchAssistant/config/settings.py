

# ==================================================
# Chrome
# ==================================================

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

CHROME_PROFILE = r"C:\ChromeDebug"

# Multi-Chrome: each feature gets its own Chrome instance + CDP port + profile
CHROME_PORTS = {
    "TO": 9222,
    "CANCLWORK": 9223,
    "DISPATCH": 9224,
}

CHROME_PROFILES = {
    9222: r"C:\ChromeDebug_TO",
    9223: r"C:\ChromeDebug_CANCLWORK",
    9224: r"C:\ChromeDebug_DISPATCH",
}


# ==================================================
# URLs
# ==================================================

DASHBOARD_URL = "https://sygap.telkom.co.id/req_fulfillment"

BISCUIT_URL = (
    "https://biscuit-dashboard-dev-playground.apps.mypaas.telkom.co.id"
    "/helpdesk/tools/inseratools"
)

GAMAS_RELATIONS_URL = (
    "https://oss-incident.telkom.co.id"
    "/jw/web/userview/ticketIncidentService/ticketIncidentService/_/gamasRelations"
)


# ==================================================
# Dispatch
# ==================================================

COMMAND_DISPATCH = "/dispatchticket"

AUTO_ENTER = True


# ==================================================
# User (untuk Take Ownership)
# ==================================================

USER_NIK = "CRS2019332"

USER_NAME = "I Nyoman Windu"

USER_ID = "55654"

INSERA_GROUP_ID = "80148276"

BIMA_GROUP_ID = ""
