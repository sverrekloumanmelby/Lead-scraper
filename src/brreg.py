"""Fallback-henting av grunndata fra Brønnøysundregistrenes åpne API.

Vi bruker /enhetsregisteret/api/enheter og filtrerer på næringskode og
kommunenummer. API-et er dokumentert på data.brreg.no og krever ikke nøkkel.
"""

from __future__ import annotations

import logging
from typing import Iterable, Iterator

import requests

from .config import NAERINGSKODE_EIENDOMSMEGLING

BRREG_BASE = "https://data.brreg.no/enhetsregisteret/api/enheter"
BRREG_ROLLER_BASE = "https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}/roller"

logger = logging.getLogger(__name__)


def hent_enheter_for_kommuner(kommunenumre: Iterable[str]) -> Iterator[dict]:
    """Hent alle eiendomsmeglerforetak for en liste kommuner via Brreg.

    Vi paginerer 200 av gangen og returnerer rå enheter fra API-et.
    """
    for kommunenr in kommunenumre:
        side = 0
        while True:
            params = {
                "naeringskode": NAERINGSKODE_EIENDOMSMEGLING,
                "kommunenummer": kommunenr,
                "size": 200,
                "page": side,
            }
            try:
                r = requests.get(BRREG_BASE, params=params, timeout=20)
                r.raise_for_status()
            except requests.RequestException as e:
                logger.warning("Brreg-feil for kommune %s side %s: %s", kommunenr, side, e)
                break

            data = r.json()
            enheter = data.get("_embedded", {}).get("enheter", [])
            if not enheter:
                break

            for enhet in enheter:
                yield enhet

            # Sjekk om det er flere sider
            side_info = data.get("page", {})
            if side + 1 >= side_info.get("totalPages", 0):
                break
            side += 1


def hent_daglig_leder(orgnr: str) -> str | None:
    """Slår opp daglig leder via rolle-API-et. Returnerer navn eller None."""
    try:
        r = requests.get(BRREG_ROLLER_BASE.format(orgnr=orgnr), timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.debug("Kunne ikke hente roller for %s: %s", orgnr, e)
        return None

    data = r.json()
    for rollegruppe in data.get("rollegrupper", []):
        for rolle in rollegruppe.get("roller", []):
            rolletype = rolle.get("type", {}).get("kode", "")
            # DAGL = daglig leder
            if rolletype == "DAGL":
                person = rolle.get("person", {})
                navn = person.get("navn", {})
                fornavn = navn.get("fornavn", "")
                etternavn = navn.get("etternavn", "")
                return f"{fornavn} {etternavn}".strip() or None
    return None


def normaliser_enhet(enhet: dict) -> dict:
    """Mapper en Brreg-enhet til vårt interne format."""
    forretningsadresse = enhet.get("forretningsadresse") or {}
    postadresse = enhet.get("postadresse") or {}
    adresse = forretningsadresse or postadresse

    by = ""
    if adresse:
        poststed = adresse.get("poststed", "")
        by = poststed.title() if poststed else ""

    return {
        "orgnr": enhet.get("organisasjonsnummer", ""),
        "firmanavn": enhet.get("navn", ""),
        "antall_ansatte": enhet.get("antallAnsatte", 0) or 0,
        "by": by,
        "telefon": enhet.get("telefonnummer", "") or "",
        "epost": enhet.get("epostadresse", "") or "",
        "nettside": enhet.get("hjemmeside", "") or "",
        "daglig_leder": "",  # Fylles inn via rolle-oppslag ved behov
        "kilde": "brreg",
    }
