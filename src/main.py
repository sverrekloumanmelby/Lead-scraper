"""Orkestrator for leadmaskinen.

Kjøring:
    python -m src.main            # Standard: Oslo + Viken (Akershus/Buskerud/Østfold)
    python -m src.main --hele-landet   # Utvid (kun etter avtale med bruker)
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import Iterable

from playwright.sync_api import sync_playwright

from . import brreg
from .chat_detector import sjekk_nettside
from .config import CSV_UTFIL, REGIONER
from .csv_writer import skriv_leads
from .proff import ProffBlokkert, scrap_proff
from .scoring import beregn_score, er_kjede, passer_ansatt_filter, prioritet

logger = logging.getLogger(__name__)


def _kommunenumre_for_regioner(regioner: Iterable[str]) -> list[str]:
    """Slår opp kommunenummerintervall for hver region og lager komplett liste."""
    numre: list[str] = []
    for navn in regioner:
        cfg = REGIONER.get(navn)
        if not cfg:
            continue
        start, slutt = cfg["kommunenummer_range"]
        for n in range(start, slutt + 1):
            # Kommunenummer skal alltid være 4 sifre
            numre.append(f"{n:04d}")
    return numre


def _steder_for_proff(regioner: Iterable[str]) -> list[str]:
    """Proff bruker vanlige stedsnavn i sitt bransjesøk."""
    return [r for r in regioner]


def hent_via_proff(regioner: list[str]) -> list[dict]:
    """Primærstrategi: Proff.no via Playwright."""
    leads: list[dict] = []
    for lead in scrap_proff(_steder_for_proff(regioner)):
        leads.append(lead)
    return leads


def hent_via_brreg(regioner: list[str]) -> list[dict]:
    """Fallback-strategi: Brønnøysundregistrenes åpne API."""
    kommunenumre = _kommunenumre_for_regioner(regioner)
    leads: list[dict] = []
    for enhet in brreg.hent_enheter_for_kommuner(kommunenumre):
        lead = brreg.normaliser_enhet(enhet)
        # Suppler daglig leder – kun for leads som kan bli aktuelle,
        # slik at vi ikke overbelaster rolle-API-et.
        if passer_ansatt_filter(lead["antall_ansatte"]) and not er_kjede(
            lead["firmanavn"]
        ):
            dagl = brreg.hent_daglig_leder(lead["orgnr"])
            if dagl:
                lead["daglig_leder"] = dagl
            time.sleep(0.3)  # skånsom med Brreg også
        leads.append(lead)
    return leads


def berik_med_chatbot_sjekk(leads: list[dict]) -> list[dict]:
    """Besøk hver nettside via Playwright og sjekk chatbot-signaturer."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for lead in leads:
                url = lead.get("nettside")
                if not url:
                    lead["har_chatbot"] = False
                    lead["chatbot_navn"] = []
                    continue
                har_chat, funn = sjekk_nettside(browser, url)
                lead["har_chatbot"] = har_chat
                lead["chatbot_navn"] = funn
                logger.info(
                    "Nettside-sjekk: %s -> chatbot=%s (%s)",
                    url,
                    har_chat,
                    ",".join(funn) if funn else "-",
                )
        finally:
            browser.close()
    return leads


def filtrer_og_scor(leads: list[dict]) -> list[dict]:
    """Bruker ansatt-filter og kjede-eksklusjon, og beregner score/prioritet."""
    resultat: list[dict] = []
    for lead in leads:
        if not passer_ansatt_filter(lead.get("antall_ansatte", 0)):
            continue
        if er_kjede(lead.get("firmanavn", "")):
            continue
        lead["score"] = beregn_score(lead)
        lead["prioritet"] = prioritet(lead["score"])
        resultat.append(lead)
    return resultat


def kjor(regioner: list[str], utfil: str = CSV_UTFIL) -> int:
    logger.info("Starter innhenting for regioner: %s", ", ".join(regioner))

    # 1. Prøv Proff.no først
    try:
        raa = hent_via_proff(regioner)
        kilde = "Proff.no"
    except ProffBlokkert as e:
        logger.warning("Proff.no blokkerte oss: %s — bytter til Brreg", e)
        raa = hent_via_brreg(regioner)
        kilde = "Brreg (fallback)"
    except Exception as e:
        logger.exception("Uventet feil under Proff-scraping: %s — prøver Brreg", e)
        raa = hent_via_brreg(regioner)
        kilde = "Brreg (fallback)"

    logger.info("Hentet %d rå oppføringer fra %s", len(raa), kilde)

    # 2. Filtrer på ansatte og kjeder før nettside-sjekk (skånsom mot nettet)
    kandidater = [
        l for l in raa
        if passer_ansatt_filter(l.get("antall_ansatte", 0))
        and not er_kjede(l.get("firmanavn", ""))
    ]
    logger.info("Etter ansatt- og kjede-filter: %d kandidater", len(kandidater))

    # 3. Nettside- og chatbot-sjekk
    kandidater = berik_med_chatbot_sjekk(kandidater)

    # 4. Scor og sorter
    ferdige = filtrer_og_scor(kandidater)
    antall = skriv_leads(utfil, ferdige)
    logger.info("Skrev %d leads til %s", antall, utfil)
    return antall


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(description="Leadmaskin for eiendomsmegling")
    p.add_argument(
        "--regioner",
        nargs="+",
        default=["Oslo", "Akershus", "Buskerud", "Østfold"],
        help="Regioner som skal søkes (standard: Oslo + Viken)",
    )
    p.add_argument(
        "--utfil",
        default=CSV_UTFIL,
        help="Sti til CSV-utfil (standard: leads.csv)",
    )
    args = p.parse_args()
    kjor(args.regioner, args.utfil)


if __name__ == "__main__":
    main()
