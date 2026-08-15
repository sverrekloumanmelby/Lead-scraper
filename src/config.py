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

# Kategorier for chat-funn. Skillet er poenget med hele lista: et kontor
# som allerede har en AI-bot er dårlig prospekt, mens et kontor med
# bemannet live-chat har bevist behovet og bare mangler automatiseringen.
KATEGORI_AI = "AI-chatbot"
KATEGORI_LIVE = "Live-chat (menneske)"

# Signaturer på vanlige chat-widgets.
# Nøkkelen er widgetnavnet (til rapportering), verdien er
# (liste med substrings vi leter etter, kategori).
CHATBOT_SIGNATURER = {
    # Plattformer som primært selges som AI-/bot-løsninger
    "Kindly": (["kindly.ai", "chat.kindlycdn.com", "kindlycdn.com"], KATEGORI_AI),
    "Boost.ai": (["boost.ai", "boostai.com", "cdn.boost.ai"], KATEGORI_AI),
    "Botpress": (["botpress.cloud", "botpress.io", "cdn.botpress.cloud"], KATEGORI_AI),
    "Intercom": (["intercom.io", "intercomcdn.com", "widget.intercom.io"], KATEGORI_AI),
    "Drift": (["driftt.com", "drift.com/anonymous", "js.driftt.com"], KATEGORI_AI),
    "Dialogflow": (["dialogflow.com", "dialogflow.cloud.google.com"], KATEGORI_AI),
    "Voiceflow": (["voiceflow.com", "general-runtime.voiceflow.com"], KATEGORI_AI),
    "Certainly": (["certainly.io", "cdn.certainly.io"], KATEGORI_AI),
    "GetJenny": (["getjenny.com", "widget.getjenny.com"], KATEGORI_AI),
    "Supersales": (["supersales.no", "supersales.ai"], KATEGORI_AI),
    "Puzzel": (["puzzel.com", "chat.puzzel.com"], KATEGORI_AI),
    "ChatGPT-widget": (["chatbase.co", "chatbotkit.com", "customgpt.ai",
                        "chatsimple.ai", "denser.ai"], KATEGORI_AI),
    # Klassiske live-chat-verktøy der et menneske svarer
    "Tidio": (["tidio.co", "tidiochat.com", "code.tidio.co"], KATEGORI_LIVE),
    "Zendesk Chat": (["zdassets.com", "zopim.com", "static.zdassets.com"], KATEGORI_LIVE),
    "LiveChat": (["livechatinc.com", "cdn.livechatinc.com"], KATEGORI_LIVE),
    "Crisp": (["crisp.chat", "client.crisp.chat"], KATEGORI_LIVE),
    "Freshchat": (["freshchat.com", "wchat.freshchat.com"], KATEGORI_LIVE),
    "HubSpot Chat": (["js.hs-scripts.com", "js.hs-banner.com",
                      "js.usemessages.com"], KATEGORI_LIVE),
    "Tawk.to": (["tawk.to", "embed.tawk.to"], KATEGORI_LIVE),
    "Zoho SalesIQ": (["zohopublic.com/salesiq", "salesiq.zoho.com"], KATEGORI_LIVE),
    "Chatra": (["chatra.io", "call.chatra.io"], KATEGORI_LIVE),
    "Trengo": (["trengo.com", "static.widget.trengo.eu"], KATEGORI_LIVE),
    "Userlike": (["userlike.com", "userlike-cdn.com"], KATEGORI_LIVE),
    "Smartsupp": (["smartsupp.com", "smartsuppchat.com"], KATEGORI_LIVE),
    "Facebook Messenger": (["connect.facebook.net/en_US/sdk/xfbml.customerchat",
                            "facebook.com/plugins/customer_chat"], KATEGORI_LIVE),
}

# Timeout for nettside-sjekk (millisekunder for Playwright)
NETTSIDE_TIMEOUT_MS = 15000

# Ansattgrupper vi jakter på. Kjerneintervallet er 3–15 ansatte.
# Toleransen på ±5 tas ut oppover (16–20); nedover ville den gitt 1–2
# ansatte, som i praksis er enkeltmannsforetak uten eget kontor — og
# Brreg har uansett null meglerforetak registrert med 1–2 ansatte.
ANSATT_GRUPPER = [
    (3, 15, "3-15 (kjerne)"),
    (16, 20, "16-20 (±5)"),
]

MIN_ANSATTE = ANSATT_GRUPPER[0][0]
MAKS_ANSATTE = ANSATT_GRUPPER[-1][1]

# Grenser for prioritetsklassifisering
PRIORITET_HOY_MIN = 80
PRIORITET_MIDDELS_MIN = 50

# CSV-utfil
CSV_UTFIL = "leads.csv"
