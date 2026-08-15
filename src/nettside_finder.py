"""Finner nettsiden til et foretak.

Brønnøysund har hjemmeside registrert for bare rundt hver femte enhet, så vi
må gjette resten. Strategien er tredelt:

1. Bruk `hjemmeside` fra Brreg hvis den finnes.
2. Gjett domener ut fra firmanavnet og verifiser at siden faktisk tilhører
   foretaket (navnetreff eller meglerord i innholdet).
3. Slå opp foretaket i 1881.no og les nettsiden fra oppføringen.

Verifiseringen i steg 2 er det viktigste: uten den ville vi plukket opp
parkerte domener og tilfeldige navnetreff.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

BRUKERAGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)
HEADERE = {"User-Agent": BRUKERAGENT, "Accept-Language": "nb-NO,nb;q=0.9,en;q=0.8"}

# Ord som ikke sier noe unikt om foretaket og derfor fjernes før vi
# bygger domenekandidater.
STOPPORD = {
    "as", "asa", "ans", "da", "sa", "avd", "avdeling",
    "eiendomsmegling", "eiendomsmegler", "eiendomsmeglere",
    "eiendomsmeglerforretning", "eiendomsmeglerfirma",
    "eiendom", "megling", "megler", "meglerne", "meglerhus",
    "og", "the", "gruppen", "group", "holding", "norge", "as.",
}

# Sider som svarer 200 uten å være et ekte foretaksnettsted.
PARKERINGS_SIGNALER = [
    "domenet er til salgs", "domain for sale", "this domain is for sale",
    "kjøp dette domenet", "buy this domain", "parkeringsside",
    "under construction", "kommer snart", "coming soon",
    "webhuset", "domeneshop.no/parkert", "default web site page",
    "apache2 ubuntu default page", "welcome to nginx",
    "domenesalg", "ledig domene", "dette domenet kan bli ditt",
]

# Nettsteder som aldri er et meglerkontors egen side: portaler, kataloger,
# reiseliv og statistikktjenester. Uten denne lista lander navnegjetting
# og katalogoppslag stadig på finn.no eller eiendomspriser.no.
UTELUKKEDE_VERTER = [
    "finn.no", "eiendomspriser.no", "1881.no", "gulesider.no", "proff.no",
    "brreg.no", "purehelp.no", "regnskapstall.no", "bizweb.no",
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
    "google.com", "wikipedia.org", "nef.no", "virdi.no", "boligverdi.no",
    "hjemla.no", "krogsveen.no/prisstatistikk", "visitnorway.no",
    "boligkanalen.no", "vitec.net", "webmegler.no", "meglerfront.no",
]

# Ord som bekrefter at siden faktisk handler om eiendomsmegling.
BRANSJEORD = [
    "eiendomsmegl", "boligsalg", "verdivurdering", "salgsoppgave",
    "megler", "visning", "til salgs", "boliger",
]

# Reiselivs- og kommunesider nevner både stedsnavn og «bolig», så vi
# krever at siden ikke ser ut som noe annet enn et meglerkontor.
FEIL_BRANSJE_SIGNALER = [
    "visit", "turistinformasjon", "opplevelser i", "kommune",
    "reiseliv", "hva skjer i", "arrangementer",
]


def _uten_aksenter(tekst: str) -> str:
    """æøå og aksenter til ASCII slik norske domener vanligvis skrives."""
    erstatninger = {"æ": "ae", "ø": "o", "å": "a", "ü": "u", "é": "e", "ö": "o", "ä": "a"}
    for fra, til in erstatninger.items():
        tekst = tekst.replace(fra, til)
    tekst = unicodedata.normalize("NFKD", tekst)
    return "".join(c for c in tekst if not unicodedata.combining(c))


def _ord_i_navn(firmanavn: str) -> list[str]:
    """Meningsbærende ord i firmanavnet, små bokstaver og uten aksenter."""
    rent = re.sub(r"[^\wæøåÆØÅ\s-]", " ", firmanavn.lower())
    rent = rent.replace("-", " ")
    return [o for o in rent.split() if o and o not in STOPPORD and not o.isdigit()]


def domenekandidater(firmanavn: str) -> list[str]:
    """Bygger en prioritert liste med sannsynlige domener for foretaket."""
    ord = _ord_i_navn(firmanavn)
    if not ord:
        return []

    ord_ascii = [_uten_aksenter(o) for o in ord]
    kandidater: list[str] = []

    def legg_til(navn: str) -> None:
        navn = re.sub(r"[^a-z0-9]", "", navn)
        if len(navn) < 3:
            return
        for tld in (".no", ".com"):
            d = navn + tld
            if d not in kandidater:
                kandidater.append(d)

    # Hele navnet satt sammen, f.eks. «semjohnsen.no»
    legg_til("".join(ord_ascii))
    # Bare første ord, f.eks. «exbo.no» — treffer oftest
    legg_til(ord_ascii[0])
    # To første ord
    if len(ord_ascii) >= 2:
        legg_til(ord_ascii[0] + ord_ascii[1])
    # Første ord + bransjeord, f.eks. «tinnbolig.no»
    for etterledd in ("eiendomsmegling", "eiendom", "megler", "bolig"):
        legg_til(ord_ascii[0] + etterledd)

    # Bindestrek mellom navneledd, f.eks. «vikebo-jorgensen.no».
    # legg_til() stripper bindestreker, så disse bygges direkte.
    if len(ord_ascii) >= 2:
        for sammensatt in ("-".join(ord_ascii), "-".join(ord_ascii[:2])):
            rensket = re.sub(r"[^a-z0-9-]", "", sammensatt).strip("-")
            if len(rensket) >= 5:
                for tld in (".no", ".com"):
                    if rensket + tld not in kandidater:
                        kandidater.append(rensket + tld)

    # .no først, deretter .com
    return sorted(kandidater, key=lambda d: (not d.endswith(".no"),))


def _hent(url: str, timeout: int = 12) -> requests.Response | None:
    try:
        return requests.get(url, headers=HEADERE, timeout=timeout, allow_redirects=True)
    except requests.RequestException:
        return None


def _utelukket_vert(url: str) -> bool:
    """Er URL-en en portal/katalog som aldri er meglerens egen side?"""
    vert = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return any(vert == u or vert.endswith("." + u) or u in url.lower()
               for u in UTELUKKEDE_VERTER)


def _saeregne_ord(firmanavn: str, sted: str = "") -> list[str]:
    """Navneord som faktisk peker på dette foretaket.

    Stedsnavnet tas ut: «ARENDAL EIENDOMSMEGLING» skal ikke godkjenne
    en hvilken som helst side som nevner Arendal.
    """
    sted_ascii = _uten_aksenter(sted.lower().strip())
    ord = []
    for o in _ord_i_navn(firmanavn):
        o_ascii = _uten_aksenter(o)
        if len(o_ascii) < 4:
            continue
        if sted_ascii and (o_ascii == sted_ascii or o_ascii in sted_ascii):
            continue
        ord.append(o_ascii)
    return ord


def _tittel_og_topp(html: str) -> str:
    """Tittel, meta-beskrivelse og overskrifter — der navnet faktisk står."""
    biter = re.findall(
        r"<title[^>]*>(.*?)</title>|<h1[^>]*>(.*?)</h1>|<h2[^>]*>(.*?)</h2>"
        r'|<meta[^>]+(?:name="description"|property="og:site_name")[^>]+'
        r'content="([^"]*)"',
        html, re.IGNORECASE | re.DOTALL,
    )
    tekst = " ".join(d for gruppe in biter for d in gruppe if d)
    return _uten_aksenter(re.sub(r"<[^>]+>", " ", tekst).lower())


def verifiser_side(
    url: str, firmanavn: str, sted: str = "", orgnr: str = ""
) -> tuple[bool, str, str]:
    """Sjekk at siden virkelig hører til foretaket.

    Returnerer (treff, endelig_url, html). Vi krever sterkt bevis, fordi en
    feil nettside gir både feil chatbot-svar og feil kontaktperson:

    * organisasjonsnummeret står på siden, eller
    * domenet er bygget av foretakets egne navneord, eller
    * et særegent navneord står i tittel/overskrift *og* siden handler
      om eiendomsmegling.
    """
    if _utelukket_vert(url):
        return False, "", ""

    svar = _hent(url)
    if svar is None or svar.status_code >= 400:
        return False, "", ""
    if _utelukket_vert(svar.url):
        return False, "", ""

    html = svar.text
    lav = html.lower()

    if len(html) < 800:
        return False, "", ""
    if any(s in lav for s in PARKERINGS_SIGNALER):
        return False, "", ""

    # Organisasjonsnummer på siden er utvetydig
    if orgnr:
        siffer = re.sub(r"\D", "", orgnr)
        if siffer and siffer in re.sub(r"[\s. -]", "", lav):
            return True, svar.url, html

    saeregne = _saeregne_ord(firmanavn, sted)
    if not saeregne:
        return False, "", ""

    bransjetreff = any(b in lav for b in BRANSJEORD)
    if not bransjetreff:
        return False, "", ""

    # Domenet bygget av foretakets egne navneord er et sterkt signal
    vert = (urlparse(svar.url).hostname or "").lower().removeprefix("www.")
    domenekjerne = re.sub(r"[^a-z0-9]", "", vert.rsplit(".", 1)[0])
    if domenekjerne and any(o in domenekjerne for o in saeregne):
        return True, svar.url, html

    # Ellers må navnet stå framtredende, og siden må ikke være noe annet
    topp = _tittel_og_topp(html)
    if any(o in topp for o in saeregne):
        if not any(f in topp for f in FEIL_BRANSJE_SIGNALER):
            return True, svar.url, html

    return False, "", ""


def gjett_nettside(
    firmanavn: str, sted: str = "", orgnr: str = ""
) -> tuple[str, str]:
    """Prøver domenekandidater til én verifiserer. Returnerer (url, html)."""
    for domene in domenekandidater(firmanavn)[:10]:
        for skjema in ("https://www.", "https://"):
            treff, url, html = verifiser_side(
                skjema + domene, firmanavn, sted, orgnr
            )
            if treff:
                logger.debug("Fant nettside for %s: %s", firmanavn, url)
                return url, html
    return "", ""


def _fra_1881(firmanavn: str, orgnr: str, sted: str = "") -> str:
    """Leter etter nettside-URL i 1881-oppføringen til foretaket.

    1881-sidene er fulle av annonse- og partnerlenker (eiendomspriser.no
    dukker opp på nesten hver eneste treffside), så vi godtar bare
    lenker med et domene som ligner foretakets eget navn.
    """
    svar = _hent(f"https://www.1881.no/?query={orgnr or firmanavn}", timeout=20)
    if svar is None or svar.status_code != 200:
        return ""

    saeregne = _saeregne_ord(firmanavn, sted)
    if not saeregne:
        return ""

    for u in re.findall(r'href="(https?://[^"]+)"', svar.text):
        if _utelukket_vert(u):
            continue
        vert = (urlparse(u).hostname or "").lower().removeprefix("www.")
        kjerne = re.sub(r"[^a-z0-9]", "", vert.rsplit(".", 1)[0])
        if kjerne and any(o in kjerne for o in saeregne):
            return u
    return ""


def finn_nettside(
    firmanavn: str, brreg_hjemmeside: str = "", sted: str = "", orgnr: str = ""
) -> tuple[str, str, str]:
    """Finn nettsiden til foretaket.

    Returnerer (url, html, metode) der metode er «brreg», «gjettet»,
    «1881» eller «» når ingenting ble funnet. HTML-en returneres slik at
    kallere slipper å laste siden på nytt for chatbot-sjekk.
    """
    if brreg_hjemmeside:
        url = brreg_hjemmeside.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        treff, endelig, html = verifiser_side(url, firmanavn, sted, orgnr)
        if treff:
            return endelig, html, "brreg"
        # Registrert hjemmeside kan være død; svarer den i det hele tatt?
        svar = _hent(url)
        if svar is not None and svar.status_code < 400 and len(svar.text) > 500:
            return svar.url, svar.text, "brreg"

    url, html = gjett_nettside(firmanavn, sted, orgnr)
    if url:
        return url, html, "gjettet"

    url = _fra_1881(firmanavn, orgnr, sted)
    if url:
        treff, endelig, html = verifiser_side(url, firmanavn, sted, orgnr)
        if treff:
            return endelig, html, "1881"

    return "", "", ""
