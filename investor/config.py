"""Konfigurasjon for investeringsassistenten.

Alle terskler og vekter samles her. De harde kvalitetskravene lengre nede er
bevisst strenge: systemet skal heller si «ingen kandidater denne uken» enn å
foreslå noe som ikke holder mål.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Datakilde
# ---------------------------------------------------------------------------

# Rekkefølgen kildene forsøkes i. Første kilde som er tilgjengelig (har nøkkel
# og svarer) vinner. "fixtures" brukes til offline testing og velges kun når
# den settes eksplisitt via --kilde.
KILDE_REKKEFOLGE = ["fmp", "yahoo"]

# Gratis API-nøkkel fra https://site.financialmodelingprep.com/developer/docs
# Settes som repo-secret / miljøvariabel. Uten nøkkel faller vi tilbake på Yahoo.
FMP_API_KEY = os.environ.get("FMP_API_KEY", "").strip()
FMP_BASE = "https://financialmodelingprep.com/api/v3"
FMP_BASE_V4 = "https://financialmodelingprep.com/api/v4"

YAHOO_BASE = "https://query1.finance.yahoo.com"

# Nettverksoppførsel — vær skånsom, og gi opp pent framfor å henge.
HTTP_TIMEOUT = 30
HTTP_RETRIES = 3
HTTP_BACKOFF = 2.0          # sekunder, dobles per forsøk
HTTP_PAUSE = 0.25           # pause mellom kall i en batch

# ---------------------------------------------------------------------------
# Portefølje og varsling
# ---------------------------------------------------------------------------

PORTEFOLJE_FIL = "portfolio.json"
STATE_FIL = "data/state.json"

# Mottaker. Faller tilbake på avsenderadressen om ikke satt.
MOTTAKER_EPOST = os.environ.get("MOTTAKER_EPOST", "").strip()
AVSENDER_EPOST = os.environ.get("GMAIL_USER", "").strip()
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
SMTP_VERT = "smtp.gmail.com"
SMTP_PORT = 587

# ---------------------------------------------------------------------------
# Hendelsesdeteksjon — hva er «genuint relevant» for den daglige e-posten?
# ---------------------------------------------------------------------------

VIKTIGHET_LAV, VIKTIGHET_MIDDELS, VIKTIGHET_HOY = 1, 2, 3

# Daglig e-post tar kun med hendelser på dette nivået eller over. Ukentlig og
# månedlig tar med alt.
DAGLIG_MIN_VIKTIGHET = VIKTIGHET_MIDDELS

# Kursbevegelse på én dag (absoluttverdi, prosent) som utløser en hendelse.
KURSBEVEGELSE_MIDDELS = 3.0
KURSBEVEGELSE_HOY = 6.0

# Resultatdato nærmere enn dette varsles i daglig e-post.
RESULTAT_VARSEL_DAGER = 7

# Nøkkelord som løfter en nyhet til «verdt å nevne». Matches case-insensitivt
# mot overskriften.
NYHET_VIKTIGE_ORD = [
    "earnings", "results", "quarterly", "guidance", "outlook", "forecast",
    "acquisition", "acquire", "merger", "takeover", "buyout",
    "upgrade", "downgrade", "price target", "initiated coverage",
    "dividend", "buyback", "share repurchase", "split",
    "ceo", "cfo", "resign", "appoint", "steps down",
    "investigation", "lawsuit", "recall", "warning", "profit warning",
    "contract", "partnership", "approval", "fda",
    # norsk
    "kvartal", "resultat", "utbytte", "oppkjøp", "fusjon", "emisjon",
    "nedgradert", "oppgradert", "kursmål", "resultatvarsel",
]

# Maks antall nyheter per selskap i rapportene.
MAKS_NYHETER_DAGLIG = 3
MAKS_NYHETER_UKENTLIG = 5
MAKS_NYHETER_MANEDLIG = 10

# ---------------------------------------------------------------------------
# Screener — univers
# ---------------------------------------------------------------------------

# Børser vi henter kandidater fra. Kun hovedbørser — ingen OTC/pink sheets.
TILLATTE_BORSER = [
    "NASDAQ", "NYSE", "AMEX",                       # USA
    "XETRA", "EURONEXT", "PARIS", "AMSTERDAM",      # Europa
    "LSE", "MILAN", "MADRID", "SIX", "BRUSSELS",
    "OSLO", "STOCKHOLM", "COPENHAGEN", "HELSINKI",  # Norden
]

# Børser som aldri skal vurderes, uansett.
FORBUDTE_BORSER = ["OTC", "PNK", "OTCBB", "PINK", "GREY"]

# Maks antall selskaper vi henter fundamentaldata for per kjøring. Holder
# kjøretid og API-kvote nede. Screeneren forhåndsfiltrerer på børsverdi/kurs/
# volum før den bruker kvote på detaljerte oppslag.
MAKS_UNIVERS = 300

# ---------------------------------------------------------------------------
# HARDE KVALITETSKRAV
# ---------------------------------------------------------------------------
# Et selskap som ikke består disse blir FORKASTET — ikke rangert lavere.
# Formålet er at systemet aldri foreslår penny stocks eller uetablerte
# selskaper, uansett hvor forlokkende nøkkeltallene ser ut.

# Ingen penny stocks: minimum børsverdi i USD.
MIN_BORSVERDI = 2_000_000_000        # 2 mrd USD — large/mid cap

# Minimum aksjekurs (i selskapets egen valuta). Filtrerer ut lavpris-aksjer.
MIN_AKSJEKURS = 10.0

# Minimum gjennomsnittlig dagsvolum (antall aksjer) — sikrer likviditet.
MIN_SNITTVOLUM = 200_000

# Dokumentert historikk: minst så mange år med børs- og regnskapsdata.
MIN_AAR_HISTORIKK = 5

# Historisk soliditet: hvor mange av de siste årene som må vise overskudd og
# positiv fri kontantstrøm. Krever konsistens over tid, ikke ett godt kvartal.
MIN_AAR_MED_OVERSKUDD = 4
MIN_AAR_MED_POSITIV_FCF = 3

# Maks gjeldsgrad (gjeld / egenkapital). Over dette forkastes selskapet.
MAKS_GJELD_EGENKAPITAL = 2.0

# Selskapet må være lønnsomt akkurat nå også.
KREV_POSITIV_PE = True

# Terskel for i det hele tatt å bli nevnt i en e-post. Kandidater under denne
# scoren vises aldri — da skriver rapporten «ingen kandidater» i stedet.
#
# Scoren er et vektet snitt av normaliserte faktorer, der 1,0 krever at
# selskapet er i toppsjiktet på *alt*. Nesten ingen reelle selskaper er det, så
# 60 tilsvarer i praksis «tydelig bedre enn snittet blant selskaper som allerede
# har bestått de harde kravene». Hev tallet for færre og mer selektive forslag.
SCORE_MIN_ANBEFALING = 60

# Minste antall konkrete, tallfestede grunner en kandidat må ha for å bli
# foreslått. Klarer vi ikke å begrunne den med tall, foreslår vi den ikke.
MIN_ANTALL_GRUNNER = 2

# Hvor mange kandidater som maksimalt vises.
MAKS_KANDIDATER_UKENTLIG = 5
MAKS_KANDIDATER_MANEDLIG = 10

# ---------------------------------------------------------------------------
# Screener — scoring
# ---------------------------------------------------------------------------

# Vekting av delscorene. Summen normaliseres, så tallene er relative.
SCORE_VEKTER = {
    "verdsettelse": 0.25,
    "kvalitet": 0.30,
    "vekst": 0.25,
    "momentum": 0.10,
    "utbytte": 0.10,
}

# Terskler som gir full delscore. Verdier mellom «bra» og «best» interpoleres.
# (bra, best) — brukes av screener._poeng()
TERSKLER = {
    "pe":                 (30.0, 12.0),    # lavere er bedre
    "pb":                 (6.0, 1.5),      # lavere er bedre
    "ev_ebitda":          (18.0, 8.0),     # lavere er bedre
    "fcf_yield":          (0.03, 0.09),    # høyere er bedre
    "roe":                (0.10, 0.25),    # høyere er bedre
    "roic":               (0.08, 0.20),
    "driftsmargin":       (0.08, 0.25),
    "gjeld_egenkapital":  (2.0, 0.3),      # lavere er bedre
    # Vekstterskler er kalibrert for *etablerte* selskaper: 8 % omsetningsvekst
    # er solid for et modent selskap, ikke svakt. Settes de for høyt, forkastes
    # gode verdiselskaper fordi de ikke vokser som vekstselskaper.
    "omsetningsvekst":    (0.02, 0.15),
    "eps_vekst":          (0.03, 0.20),
    "omsetningsvekst_3aar": (0.02, 0.12),
    "momentum":           (-0.05, 0.25),   # 12 mnd kursutvikling
    "utbytte_yield":      (0.01, 0.05),
}

# Prioritetsgrenser (samme tankegang som leadmaskinen).
PRIORITET_HOY_MIN = 78
PRIORITET_MIDDELS_MIN = 60

# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

RAPPORT_TITTEL = {
    "daily": "Daglig oppdatering",
    "weekly": "Ukentlig porteføljerapport",
    "monthly": "Månedsrapport",
}

# Månedsrapporten forklarer kvartalstall for ett selskap om gangen, og roterer
# gjennom porteføljen slik at du over tid lærer å lese alle sammen.
LAERING_ROTERER = True
