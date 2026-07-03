"""Konfigurasjon for leadmaskinen."""

# Næringskode for eiendomsmegling i henhold til SN2007
NAERINGSKODE_EIENDOMSMEGLING = "68.310"

# Alle fylker per 2024-inndelingen (Viken/Vestfold og Telemark/Troms og
# Finnmark er splittet tilbake). Fylkesnummeret er de to første sifrene i
# kommunenummeret, som vi bruker til å filtrere Brreg-data per region.
REGIONER = {
    "Oslo": {"fylkesnummer": "03"},
    "Rogaland": {"fylkesnummer": "11"},
    "Møre og Romsdal": {"fylkesnummer": "15"},
    "Nordland": {"fylkesnummer": "18"},
    "Østfold": {"fylkesnummer": "31"},
    "Akershus": {"fylkesnummer": "32"},
    "Buskerud": {"fylkesnummer": "33"},
    "Innlandet": {"fylkesnummer": "34"},
    "Vestfold": {"fylkesnummer": "39"},
    "Telemark": {"fylkesnummer": "40"},
    "Agder": {"fylkesnummer": "42"},
    "Vestland": {"fylkesnummer": "46"},
    "Trøndelag": {"fylkesnummer": "50"},
    "Troms": {"fylkesnummer": "55"},
    "Finnmark": {"fylkesnummer": "56"},
}

# Kjeder som skal ekskluderes fra listen.
# Franchisekontorer har ofte egne AS-navn (f.eks. «AKTIV MOSS AS» eller
# «Komplett Eiendomsmegling AS» med nettside hos privatmegleren.no), så vi
# matcher både navnemønstre (regex, case-insensitive) og nettside-domener.
KJEDE_NAVN_MONSTRE = [
    r"\bdnb\s*eiendom\b",
    r"\beiendomsmegler\s*1\b",
    r"\bem\s?1\b",
    r"^aktiv\b",                 # franchisenavn som «Aktiv Moss AS»
    r"\baktiv eiendomsmegling\b",
    r"\bprivatmegleren\b",
    r"\bkrogsveen\b",
]

# Offisielle kjededomener. Et lead med nettside på et av disse domenene
# er et kjedekontor uansett hva selskapet heter. Merk eksakt vertsmatch,
# slik at f.eks. proaktiv.no IKKE rammes av aktiv.no.
KJEDE_DOMENER = [
    "dnbeiendom.no",
    "eiendomsmegler1.no",
    "em1.no",
    "aktiv.no",
    "privatmegleren.no",
    "krogsveen.no",
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

# Ansattgrupper vi jakter på. Hver gruppe er (min, maks, etikett) med
# inklusive grenser. Grensene overlapper ikke (15-30 betyr 16-30 osv.)
# slik at hvert kontor havner i nøyaktig én gruppe.
ANSATT_GRUPPER = [
    (3, 15, "3-15"),
    (16, 30, "15-30"),
    (31, 50, "30-50"),
]

# Bakoverkompatible grenser (minste og største av gruppene)
MIN_ANSATTE = ANSATT_GRUPPER[0][0]
MAKS_ANSATTE = ANSATT_GRUPPER[-1][1]

# Pause mellom oppslag mot 1881.no (sekunder) — vær skånsom
KATALOG_PAUSE_MIN = 2.0
KATALOG_PAUSE_MAX = 3.5

# Grenser for prioritetsklassifisering
PRIORITET_HOY_MIN = 80
PRIORITET_MIDDELS_MIN = 50

# CSV-utfil
CSV_UTFIL = "leads.csv"
