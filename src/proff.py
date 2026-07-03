"""Proff.no-scraper.

Vi bruker Playwright fordi Proff.no laster mye innhold via JavaScript.
Hovedstrategien er:
  1. Åpne bransjelisting for eiendomsmegling filtrert på region.
  2. Iterere paginert liste og samle profil-URLer.
  3. Besøke hver profil og trekke ut nøkkelfeltene.

Vi ærer 3–5 sekunders pause mellom forespørslene for å være skånsomme.
Ved blokkering (429/403 eller captcha) løftes ProffBlokkert slik at
orkestrator kan bytte til Brreg-fallback.
"""

from __future__ import annotations

import logging
import random
import re
import time
from typing import Iterator

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

from .config import PROFF_PAUSE_MAX, PROFF_PAUSE_MIN

logger = logging.getLogger(__name__)

PROFF_SOK = (
    "https://www.proff.no/bransjes%C3%B8k?q=eiendomsmegling&location={sted}"
)


class ProffBlokkert(Exception):
    """Kastes når Proff.no returnerer blokkeringssignal."""


def _sov_litt() -> None:
    """Tilfeldig pause mellom 3–5 sekunder for å være skånsom mot Proff.no."""
    pause = random.uniform(PROFF_PAUSE_MIN, PROFF_PAUSE_MAX)
    logger.debug("Venter %.1fs før neste Proff-forespørsel", pause)
    time.sleep(pause)


def _sjekk_blokkering(page: Page) -> None:
    """Ser etter kjente blokkeringsindikatorer i den lastede siden."""
    innhold = page.content().lower()
    blokk_ord = ["captcha", "access denied", "for mange forespørsler", "cloudflare"]
    if any(o in innhold for o in blokk_ord):
        raise ProffBlokkert("Proff.no viser blokkeringsside")


def _hent_tekst(page: Page, selector: str) -> str:
    """Hjelper for å hente tekst fra en selector uten å krasje."""
    try:
        el = page.locator(selector).first
        if el.count() == 0:
            return ""
        return (el.text_content() or "").strip()
    except PWTimeout:
        return ""


def _parse_antall_ansatte(tekst: str) -> int:
    """Trekker ut første tall i strengen. 0 hvis ikke funnet."""
    m = re.search(r"\d+", tekst.replace(" ", ""))
    return int(m.group()) if m else 0


def hent_profillenker(page: Page, sted: str, maks_sider: int = 20) -> list[str]:
    """Samler URLer til alle foretaksprofiler for en gitt region."""
    lenker: list[str] = []
    for sidenr in range(1, maks_sider + 1):
        url = PROFF_SOK.format(sted=sted)
        if sidenr > 1:
            url = f"{url}&page={sidenr}"
        logger.info("Henter Proff-liste %s side %s", sted, sidenr)
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        _sjekk_blokkering(page)

        # Proff bruker gjerne en lenke til /selskap/<slug>/<orgnr>
        nye = page.locator("a[href*='/selskap/']").evaluate_all(
            "els => Array.from(new Set(els.map(a => a.href)))"
        )
        if not nye:
            break
        lenker.extend(nye)
        _sov_litt()

    # Fjern duplikater, bevar rekkefølge
    sett = set()
    unike = []
    for l in lenker:
        if l not in sett:
            sett.add(l)
            unike.append(l)
    return unike


def hent_foretaksdetaljer(page: Page, url: str) -> dict:
    """Besøker en profilside og trekker ut felter vi trenger."""
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    _sjekk_blokkering(page)

    firmanavn = _hent_tekst(page, "h1")
    telefon = _hent_tekst(page, "a[href^='tel:']")
    epost = _hent_tekst(page, "a[href^='mailto:']")

    # Nettside oppgis vanligvis som lenke merket med "www"
    nettside = ""
    try:
        el = page.locator("a[href^='http']:not([href*='proff.no'])").first
        if el.count() > 0:
            nettside = el.get_attribute("href") or ""
    except PWTimeout:
        pass

    # Antall ansatte og daglig leder ligger i faktaboksen
    fakta_tekst = _hent_tekst(page, "section:has-text('Antall ansatte')")
    antall_ansatte = _parse_antall_ansatte(fakta_tekst)

    daglig_leder = _hent_tekst(page, "section:has-text('Daglig leder') a")

    # By finnes ofte i adresseblokken
    by = ""
    adresse_tekst = _hent_tekst(page, "section:has-text('Besøksadresse')")
    m = re.search(r"\d{4}\s+([A-Za-zØÆÅøæå\- ]+)", adresse_tekst)
    if m:
        by = m.group(1).strip().title()

    return {
        "firmanavn": firmanavn,
        "telefon": telefon,
        "epost": epost,
        "nettside": nettside,
        "antall_ansatte": antall_ansatte,
        "daglig_leder": daglig_leder,
        "by": by,
        "kilde": "proff",
    }


def scrap_proff(steder: list[str]) -> Iterator[dict]:
    """Iterer over foretak i alle regioner. Kaster ProffBlokkert ved blokk."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
            ),
            locale="nb-NO",
        )
        page = context.new_page()

        try:
            for sted in steder:
                lenker = hent_profillenker(page, sted)
                logger.info("Fant %d foretak i %s", len(lenker), sted)
                for lenke in lenker:
                    try:
                        yield hent_foretaksdetaljer(page, lenke)
                    except ProffBlokkert:
                        raise
                    except Exception as e:
                        logger.warning("Feil ved henting av %s: %s", lenke, e)
                    finally:
                        _sov_litt()
        finally:
            context.close()
            browser.close()
