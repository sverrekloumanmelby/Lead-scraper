"""Oppslag av daglig leders telefonnummer i 1881.no.

1881 er en offentlig norsk nummerkatalog. Vi søker «Fornavn Etternavn Poststed»;
ved unikt treff lander vi rett på personsiden som har tel:-lenker. Ved
flertreff plukker vi resultatkortet som inneholder hele navnet. Vi holder
2–3,5 sekunders pause mellom oppslag for å være skånsomme.
"""

from __future__ import annotations

import logging
import random
import re
import time
import urllib.parse

from playwright.sync_api import Browser

from .config import KATALOG_PAUSE_MAX, KATALOG_PAUSE_MIN

logger = logging.getLogger(__name__)

SOK_URL = "https://www.1881.no/?query={query}"


def _normaliser_nummer(raatt: str) -> str:
    """Gjør «tel:004795026764» om til «95026764»."""
    siffer = re.sub(r"\D", "", raatt)
    if siffer.startswith("0047"):
        siffer = siffer[4:]
    elif siffer.startswith("47") and len(siffer) == 10:
        siffer = siffer[2:]
    return siffer


def _navn_matcher(tekst: str, navn: str) -> bool:
    """Sjekk at alle navnedeler finnes i teksten (aksent-tolerant nok)."""
    t = tekst.lower()
    deler = [d for d in navn.lower().split() if len(d) > 1]
    treff = sum(1 for d in deler if d in t)
    # Krev at nesten alle navnedeler er til stede (takler mellomnavn-avvik)
    return treff >= max(2, len(deler) - 1)


def slaa_opp_telefon(browser: Browser, navn: str, sted: str = "") -> str:
    """Returnerer telefonnummer for personen, eller tom streng."""
    if not navn:
        return ""

    context = browser.new_context(locale="nb-NO")
    page = context.new_page()
    nummer = ""
    try:
        for query in filter(None, [f"{navn} {sted}".strip(), navn if sted else None]):
            url = SOK_URL.format(query=urllib.parse.quote(query))
            try:
                page.goto(url, wait_until="load", timeout=20000)
                page.wait_for_timeout(2500)
            except Exception as e:
                logger.debug("1881-oppslag feilet for %r: %s", query, e)
                continue

            tittel = page.title()
            tel_lenker = page.locator("a[href^='tel:']").evaluate_all(
                "els => els.map(a => a.getAttribute('href'))"
            )

            # Direkte personside: tittelen inneholder navnet
            if tel_lenker and _navn_matcher(tittel, navn):
                nummer = _normaliser_nummer(tel_lenker[0])
                break

            # Resultatliste: finn kortet som matcher hele navnet
            kort = page.locator("article, li, div[class*='listing']")
            antall = min(kort.count(), 30)
            for i in range(antall):
                k = kort.nth(i)
                try:
                    tekst = k.inner_text(timeout=1000)
                except Exception:
                    continue
                if not _navn_matcher(tekst, navn):
                    continue
                tel = k.locator("a[href^='tel:']")
                if tel.count() > 0:
                    nummer = _normaliser_nummer(tel.first.get_attribute("href") or "")
                    break
            if nummer:
                break
    finally:
        context.close()
        # Skånsom pause uansett utfall
        time.sleep(random.uniform(KATALOG_PAUSE_MIN, KATALOG_PAUSE_MAX))
    return nummer
