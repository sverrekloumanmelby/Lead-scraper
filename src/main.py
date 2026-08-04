"""Leadmaskin for AI-chatbot-salg mot norske eiendomsmeglerkontorer.

Kjøres i tre faser:

1. **Grunndata** — henter alle foretak med næringskode 68.310 fra
   Enhetsregisteret, filtrerer på ansattall og luker ut kjedekontorer og
   selskaper under avvikling. Daglig leder hentes fra rolleregisteret.
2. **Nettside** — finner foretakets nettside (registrert hjemmeside,
   navnegjetting eller 1881) og sjekker rå HTML for chat-widgets.
3. **Nettleser** — rendrer nettsiden i Chromium for å fange widgets som
   lastes via tag manager, og leser ut ansatte med navn og tittel fra
   «om oss»-sidene for å finne rett kontaktperson.

Mellomresultatene lagres underveis, slik at en avbrutt kjøring kan tas
opp igjen uten å laste ned alt på nytt.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from . import brreg
from .chat_detector import (
    analyser_html,
    analyser_med_nettleser,
    finn_undersider,
    rens_url,
)
from .config import ANSATT_GRUPPER, CSV_UTFIL, MAKS_ANSATTE, MIN_ANSATTE
from .csv_writer import skriv_leads
from .kontaktperson import (
    ANSATT_NOKKELORD,
    _epost_passer_navn,
    personer_fra_html,
    velg_kontakt,
)
from .nettside_finder import HEADERE, finn_nettside
from .rapport import skriv_rapport
from .scoring import ansatt_gruppe, beregn_score, er_kjede, prioritet, segment

logger = logging.getLogger("leadmaskin")

MELLOMLAGER = Path("mellomlager.json")


# --------------------------------------------------------------------------
# Fase 1: grunndata fra Enhetsregisteret
# --------------------------------------------------------------------------
def hent_grunndata(maks: int | None = None) -> list[dict]:
    """Henter og filtrerer foretak fra Brreg."""
    logger.info("Henter eiendomsmeglerforetak fra Enhetsregisteret …")
    raa = list(brreg.hent_enheter())
    logger.info("  %s foretak med næringskode eiendomsmegling", len(raa))

    leads: list[dict] = []
    for enhet in raa:
        antall = enhet.get("antallAnsatte") or 0
        if not MIN_ANSATTE <= antall <= MAKS_ANSATTE:
            continue
        if enhet.get("konkurs") or enhet.get("underAvvikling"):
            continue
        if enhet.get("slettedato"):
            continue
        lead = brreg.normaliser_enhet(enhet)
        if er_kjede(lead["firmanavn"], lead["nettside"]):
            continue
        leads.append(lead)

    logger.info("  %s foretak innenfor %s–%s ansatte og uten kjedetilknytning",
                len(leads), MIN_ANSATTE, MAKS_ANSATTE)
    if maks:
        leads = leads[:maks]
    return leads


def berik_daglig_leder(leads: list[dict], arbeidere: int = 8) -> None:
    """Slår opp daglig leder for hvert foretak (parallelt)."""
    logger.info("Slår opp daglig leder for %s foretak …", len(leads))

    def jobb(lead: dict) -> None:
        lead["daglig_leder"] = brreg.hent_daglig_leder(lead["orgnr"]) or ""

    with ThreadPoolExecutor(max_workers=arbeidere) as ex:
        list(ex.map(jobb, leads))
    logger.info("  fant daglig leder for %s",
                sum(1 for x in leads if x["daglig_leder"]))


# --------------------------------------------------------------------------
# Fase 2: nettside + rask chat-sjekk
# --------------------------------------------------------------------------
def finn_nettsider(leads: list[dict], arbeidere: int = 10) -> None:
    """Finner nettside for hvert foretak og gjør en første chat-sjekk."""
    logger.info("Leter etter nettsider …")

    def jobb(lead: dict) -> None:
        url, html, metode = finn_nettside(
            lead["firmanavn"], lead.get("nettside", ""),
            lead.get("by", ""), lead["orgnr"],
        )
        lead["nettside"] = url
        lead["nettside_kilde"] = metode
        if url:
            har, kategori, navn, boer_rendres = analyser_html(html)
            lead["har_chatbot"] = har
            lead["chatbot_kategori"] = kategori
            lead["chatbot_navn"] = navn
            lead["_boer_rendres"] = boer_rendres
            lead["_html"] = html if len(html) < 400_000 else ""
        else:
            lead["har_chatbot"] = False
            lead["chatbot_kategori"] = "ukjent (fant ikke nettside)"
            lead["chatbot_navn"] = ""
            lead["_boer_rendres"] = False
            lead["_html"] = ""

    with ThreadPoolExecutor(max_workers=arbeidere) as ex:
        list(ex.map(jobb, leads))

    med = sum(1 for x in leads if x["nettside"])
    logger.info("  fant nettside for %s av %s", med, len(leads))

    # Kjedesjekk på nytt: nå kjenner vi domenet
    før = len(leads)
    leads[:] = [x for x in leads if not er_kjede(x["firmanavn"], x["nettside"])]
    if før != len(leads):
        logger.info("  luket ut %s kjedekontorer etter domenesjekk",
                    før - len(leads))


# --------------------------------------------------------------------------
# Fase 3: nettleser — chat-widgets og ansatte
# --------------------------------------------------------------------------
def _hent_side(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERE, timeout=15)
        return r.text if r.status_code < 400 else ""
    except requests.RequestException:
        return ""


def _samle_personer(sider: list[tuple[str, str]], firmanavn: str) -> list[dict]:
    """Slår sammen personfunn fra flere sider, beste treff per navn."""
    beste: dict[str, dict] = {}
    for html, url in sider:
        if not html:
            continue
        for p in personer_fra_html(html, firmanavn, url):
            n = p["navn"].lower()
            if n not in beste or p["score"] > beste[n]["score"]:
                beste[n] = p
    return sorted(beste.values(), key=lambda p: p["score"], reverse=True)


async def _behandle_i_nettleser(context, lead: dict, semafor) -> None:
    """Rendrer nettsiden: bekreft chat-widget og finn ansatte."""
    url = rens_url(lead["nettside"])
    async with semafor:
        try:
            har, kategori, navn, _ = await analyser_med_nettleser(context, url)
        except Exception as e:
            logger.debug("Nettleserfeil for %s: %s", url, e)
            return

        # Nettleseren ser mer enn rå HTML, så den overstyrer et negativt funn
        if har:
            lead["har_chatbot"] = True
            lead["chatbot_kategori"] = kategori
            lead["chatbot_navn"] = navn
        elif kategori != "ukjent" and not lead.get("har_chatbot"):
            lead["chatbot_kategori"] = "ingen"

        html = lead.get("_html") or _hent_side(url)
        if not html:
            return
        undersider = finn_undersider(html, url, ANSATT_NOKKELORD, maks=4)

    # Ansatt-sidene hentes med vanlig HTTP; de er som regel server-rendret,
    # og vi slipper å okkupere nettleseren.
    sider = [(html, url)]
    for u in undersider:
        sider.append((await asyncio.to_thread(_hent_side, u), u))

    # Er sidene JS-rendret, fant vi ingen — da rendrer vi dem i nettleseren
    firmanavn = lead["firmanavn"]
    personer = _samle_personer(sider, firmanavn)
    if not personer and undersider:
        async with semafor:
            for u in undersider[:2]:
                side = await context.new_page()
                try:
                    await side.goto(u, wait_until="load", timeout=20000)
                    await side.wait_for_timeout(2500)
                    personer += personer_fra_html(
                        await side.content(), firmanavn, u)
                except Exception:
                    pass
                finally:
                    try:
                        await side.close()
                    except Exception:
                        pass
        personer.sort(key=lambda p: p["score"], reverse=True)

    lead["_personer"] = personer[:8]


async def nettleserfase(leads: list[dict], samtidige: int = 6) -> None:
    """Kjører nettleserfasen for alle leads som har en nettside."""
    from playwright.async_api import async_playwright

    from .browser_util import launch_argumenter

    med_side = [x for x in leads if x.get("nettside")]
    if not med_side:
        return
    logger.info("Rendrer %s nettsider i Chromium …", len(med_side))

    semafor = asyncio.Semaphore(samtidige)
    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_argumenter())
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
            ),
            locale="nb-NO",
        )
        oppgaver = [_behandle_i_nettleser(context, x, semafor) for x in med_side]
        ferdig = 0
        for oppgave in asyncio.as_completed(oppgaver):
            await oppgave
            ferdig += 1
            if ferdig % 20 == 0:
                logger.info("  %s/%s sider ferdig", ferdig, len(med_side))
        await browser.close()


# --------------------------------------------------------------------------
# Sammenstilling
# --------------------------------------------------------------------------
def sluttfor(leads: list[dict]) -> list[dict]:
    """Velger kontaktperson, regner score og rydder bort interne felter."""
    for lead in leads:
        kontakt = velg_kontakt(lead.get("_personer", []),
                               lead.get("daglig_leder", ""))
        lead["kontakt_navn"] = kontakt["navn"]
        lead["kontakt_tittel"] = (kontakt["tittel"] or "").title()

        # Personlig e-post bare når den faktisk tilhører personen. Firmaets
        # registrerte e-post blir stående i sin egen kolonne, slik at vi
        # ikke tillegger en navngitt person en adresse som ikke er hennes.
        epost = kontakt["epost"]
        if not epost:
            firma_epost = lead.get("epost", "")
            if firma_epost and kontakt["navn"] and _epost_passer_navn(
                    firma_epost, kontakt["navn"]):
                epost = firma_epost
        lead["kontakt_epost"] = epost
        lead["kontakt_telefon"] = kontakt["telefon"] or lead.get("telefon", "")
        lead["kontakt_kilde"] = kontakt["kilde"]
        lead["hvorfor_denne"] = kontakt["begrunnelse"]

        lead["ansattgruppe"] = ansatt_gruppe(lead["antall_ansatte"]) or ""
        lead["segment"] = segment(lead["firmanavn"])
        lead["score"] = beregn_score(lead)
        lead["prioritet"] = prioritet(lead["score"])

        for felt in ("_html", "_personer", "_boer_rendres"):
            lead.pop(felt, None)
    return leads


def lagre_mellomlager(leads: list[dict]) -> None:
    rene = [{k: v for k, v in x.items() if k != "_html"} for x in leads]
    MELLOMLAGER.write_text(json.dumps(rene, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--utfil", default=CSV_UTFIL, help="CSV-fil å skrive til")
    parser.add_argument("--maks", type=int, default=None,
                        help="Begrens antall foretak (til testing)")
    parser.add_argument("--uten-nettleser", action="store_true",
                        help="Hopp over Chromium-fasen (raskere, mindre presist)")
    parser.add_argument("--samtidige", type=int, default=6,
                        help="Antall nettsider som rendres samtidig")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S", stream=sys.stdout,
    )

    leads = hent_grunndata(args.maks)
    berik_daglig_leder(leads)
    finn_nettsider(leads)
    lagre_mellomlager(leads)

    if not args.uten_nettleser:
        asyncio.run(nettleserfase(leads, args.samtidige))

    leads = sluttfor(leads)
    antall = skriv_leads(args.utfil, leads)
    rapportfil = Path(args.utfil).with_suffix(".md")
    skriv_rapport(rapportfil, leads)

    logger.info("Skrev %s leads til %s og %s", antall, args.utfil, rapportfil)
    for _, _, etikett in ANSATT_GRUPPER:
        logger.info("  %s: %s", etikett,
                    sum(1 for x in leads if x["ansattgruppe"] == etikett))
    logger.info("  uten chat: %s | live-chat: %s | AI-bot: %s | ukjent: %s",
                sum(1 for x in leads if x["chatbot_kategori"] == "ingen"),
                sum(1 for x in leads if "Live" in x["chatbot_kategori"]),
                sum(1 for x in leads if "AI" in x["chatbot_kategori"]),
                sum(1 for x in leads if "ukjent" in x["chatbot_kategori"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
