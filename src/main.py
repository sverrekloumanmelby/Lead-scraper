"""Orkestrator for leadmaskinen.

Kjøring:
    python -m src.main                      # Standard: hele landet
    python -m src.main --regioner Oslo      # Begrens til utvalgte fylker
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import Iterable

from playwright.sync_api import sync_playwright

from . import brreg
from .browser_util import launch_argumenter
from .chat_detector import sjekk_nettside
from .config import CSV_UTFIL, REGIONER
from .csv_writer import skriv_leads
from .dl_telefon import slaa_opp_telefon
from .proff import ProffBlokkert, scrap_proff
from .scoring import (
    ansatt_gruppe,
    beregn_score,
    er_kjede,
    passer_ansatt_filter,
    prioritet,
)

logger = logging.getLogger(__name__)


def _fylkesprefikser_for_regioner(regioner: Iterable[str]) -> list[str]:
    """Slår opp fylkesnummer (to første sifre i kommunenummeret) per region."""
    prefikser: list[str] = []
    for navn in regioner:
        cfg = REGIONER.get(navn)
        if cfg:
            prefikser.append(cfg["fylkesnummer"])
    return prefikser


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
    # Dekker regionene alle fylker, dropper vi filteret helt
    prefikser: list[str] | None = _fylkesprefikser_for_regioner(regioner)
    if set(prefikser) == {cfg["fylkesnummer"] for cfg in REGIONER.values()}:
        prefikser = None
    leads: list[dict] = []
    for enhet in brreg.hent_enheter(prefikser):
        lead = brreg.normaliser_enhet(enhet)
        # Suppler daglig leder – kun for leads som kan bli aktuelle,
        # slik at vi ikke overbelaster rolle-API-et.
        if passer_ansatt_filter(lead["antall_ansatte"]) and not er_kjede(
            lead["firmanavn"], lead.get("nettside", "")
        ):
            dagl = brreg.hent_daglig_leder(lead["orgnr"])
            if dagl:
                lead["daglig_leder"] = dagl
            time.sleep(0.3)  # skånsom med Brreg også
        leads.append(lead)
    return leads


def berik_med_chatbot_sjekk(leads: list[dict], antall_traader: int = 4) -> list[dict]:
    """Besøk hver nettside via Playwright og sjekk chatbot-signaturer.

    Sjekkene går mot mange ulike domener (én forespørsel per nettsted),
    så vi kan trygt kjøre noen få tråder i parallell. Hver tråd har sin
    egen Playwright-instans siden sync-API-et ikke er trådsikkert.
    """
    import queue
    import threading

    ko: queue.Queue[dict] = queue.Queue()
    for lead in leads:
        if lead.get("nettside"):
            ko.put(lead)
        else:
            lead["har_chatbot"] = False
            lead["chatbot_navn"] = []

    ferdig_teller = {"n": 0}
    laas = threading.Lock()
    totalt = ko.qsize()

    def arbeider() -> None:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch_argumenter())
            try:
                while True:
                    try:
                        lead = ko.get_nowait()
                    except queue.Empty:
                        return
                    try:
                        har_chat, funn = sjekk_nettside(browser, lead["nettside"])
                    except Exception as e:
                        logger.warning(
                            "Nettside-sjekk feilet for %s: %s", lead["nettside"], e
                        )
                        har_chat, funn = False, []
                    lead["har_chatbot"] = har_chat
                    lead["chatbot_navn"] = funn
                    with laas:
                        ferdig_teller["n"] += 1
                        n = ferdig_teller["n"]
                    logger.info(
                        "Nettside-sjekk %d/%d: %s -> chatbot=%s (%s)",
                        n, totalt, lead["nettside"], har_chat,
                        ",".join(funn) if funn else "-",
                    )
            finally:
                browser.close()

    traader = [
        threading.Thread(target=arbeider, daemon=True)
        for _ in range(min(antall_traader, max(totalt, 1)))
    ]
    for t in traader:
        t.start()
    for t in traader:
        t.join()
    return leads


def filtrer_og_scor(leads: list[dict]) -> list[dict]:
    """Bruker ansatt-filter og kjede-eksklusjon, og beregner score/prioritet."""
    resultat: list[dict] = []
    for lead in leads:
        gruppe = ansatt_gruppe(lead.get("antall_ansatte", 0))
        if gruppe is None:
            continue
        if er_kjede(lead.get("firmanavn", ""), lead.get("nettside", "")):
            continue
        lead["ansattgruppe"] = gruppe
        lead["score"] = beregn_score(lead)
        lead["prioritet"] = prioritet(lead["score"])
        resultat.append(lead)
    return resultat


def berik_med_dl_telefon(leads: list[dict]) -> list[dict]:
    """Slår opp daglig leders telefonnummer i 1881.no.

    Sekvensielt med innebygd pause i oppslaget — katalogtjenesten skal
    ikke belastes hardt. Kontorets by brukes til å skille navnebrødre.
    """
    med_navn = [l for l in leads if l.get("daglig_leder")]
    logger.info("Slår opp telefon for %d daglige ledere i 1881", len(med_navn))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_argumenter())
        try:
            for i, lead in enumerate(med_navn, 1):
                nummer = slaa_opp_telefon(
                    browser, lead["daglig_leder"], lead.get("by", "")
                )
                lead["dl_telefon"] = nummer
                logger.info(
                    "DL-telefon %d/%d: %s -> %s",
                    i, len(med_navn), lead["daglig_leder"], nummer or "(ikke funnet)",
                )
        finally:
            browser.close()
    for lead in leads:
        lead.setdefault("dl_telefon", "")
    return leads


def kjor(regioner: list[str], utfil: str = CSV_UTFIL, kilde_valg: str = "auto") -> int:
    logger.info("Starter innhenting for regioner: %s", ", ".join(regioner))

    # 1. Hent grunndata. «auto» prøver Proff.no først og faller tilbake til
    #    Brreg; «brreg» hopper rett til registeret (raskere og mer komplett,
    #    men uten Proff-spesifikke felter).
    if kilde_valg == "brreg":
        raa = hent_via_brreg(regioner)
        kilde = "Brreg (valgt)"
    else:
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
        and not er_kjede(l.get("firmanavn", ""), l.get("nettside", ""))
    ]
    logger.info("Etter ansatt- og kjede-filter: %d kandidater", len(kandidater))

    # 3. Nettside- og chatbot-sjekk
    kandidater = berik_med_chatbot_sjekk(kandidater)

    # 4. Daglig leders telefonnummer fra 1881
    kandidater = berik_med_dl_telefon(kandidater)

    # 5. Scor og sorter
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
        default=list(REGIONER),
        choices=list(REGIONER),
        metavar="FYLKE",
        help=(
            "Fylker som skal søkes (standard: hele landet). "
            f"Gyldige: {', '.join(REGIONER)}"
        ),
    )
    p.add_argument(
        "--utfil",
        default=CSV_UTFIL,
        help="Sti til CSV-utfil (standard: leads.csv)",
    )
    p.add_argument(
        "--kilde",
        choices=["auto", "brreg"],
        default="auto",
        help="Datakilde: auto = Proff.no med Brreg-fallback, brreg = kun registeret",
    )
    args = p.parse_args()
    kjor(args.regioner, args.utfil, args.kilde)


if __name__ == "__main__":
    main()
