"""Konfigurasjon for leadmaskinen."""

# Næringskode for eiendomsmegling i henhold til SN2007
NAERINGSKODE_EIENDOMSMEGLING = "68.310"

# Regioner vi starter med (Oslo og Viken).
# Viken ble fra 2024 splittet tilbake til Akershus, Buskerud og Østfold,
# så vi dekker de tre fylkene sammen med Oslo.
REGIONER = {
    "Oslo": {
        "fylkesnummer": "03",
        "kommunenummer_range": (301, 301),
    },
    "Akershus": {
        "fylkesnummer": "32",
        "kommunenummer_range": (3201, 3238),
    },
    "Buskerud": {
        "fylkesnummer": "33",
        "kommunenummer_range": (3301, 3352),
    },
    "Østfold": {
        "fylkesnummer": "31",
        "kommunenummer_range": (3101, 3138),
    },
}

# Kjeder som skal ekskluderes fra listen.
# Vi matcher case-insensitive substring mot firmanavn.
EKSKLUDERTE_KJEDER = [
    "DNB Eiendom",
    "EiendomsMegler 1",
    "Eiendomsmegler 1",
    "EM1",
    "Aktiv Eiendomsmegling",
    "PrivatMegleren",
    "Privatmegleren",
    "Krogsveen",
]

# Signaturer på vanlige chatbot-widgets.
# Nøkkelen er navnet på widgeten (til rapportering), verdien er en liste
# med substrings vi leter etter i sidens HTML.
CHATBOT_SIGNATURER = {
    "Intercom": ["intercom.io", "intercomcdn.com", "widget.intercom.io"],
    "Drift": ["driftt.com", "drift.com/anonymous", "js.driftt.com"],
    "Tidio": ["tidio.co", "tidiochat.com", "code.tidio.co"],
    "Botpress": ["botpress.cloud", "botpress.io", "cdn.botpress.cloud"],
    "Kindly": ["kindly.ai", "chat.kindlycdn.com", "kindlycdn.com"],
    "Boost.ai": ["boost.ai", "boostai.com", "cdn.boost.ai"],
    "Zendesk Chat": ["zdassets.com", "zopim.com", "static.zdassets.com"],
    "LiveChat": ["livechatinc.com", "cdn.livechatinc.com"],
    "Crisp": ["crisp.chat", "client.crisp.chat"],
    "Freshchat": ["freshchat.com", "wchat.freshchat.com"],
    "HubSpot Chat": ["js.hs-scripts.com", "js.hs-banner.com", "js.usemessages.com"],
    "Tawk.to": ["tawk.to", "embed.tawk.to"],
    "Zoho SalesIQ": ["zohopublic.com/salesiq", "salesiq.zoho.com"],
    "Chatra": ["chatra.io", "call.chatra.io"],
    "Puzzel": ["puzzel.com", "chat.puzzel.com"],
}

# Pauselengder mellom forespørsler mot Proff.no (sekunder).
PROFF_PAUSE_MIN = 3.0
PROFF_PAUSE_MAX = 5.0

# Timeout for nettside-sjekk (millisekunder for Playwright)
NETTSIDE_TIMEOUT_MS = 15000

# Ansatt-filter
MIN_ANSATTE = 3
MAKS_ANSATTE = 15

# Grenser for prioritetsklassifisering
PRIORITET_HOY_MIN = 80
PRIORITET_MIDDELS_MIN = 50

# CSV-utfil
CSV_UTFIL = "leads.csv"
