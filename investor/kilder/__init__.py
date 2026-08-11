"""Valg av datakilde.

Systemet skal aldri stå uten data på grunn av én leverandør. `velg_kilde()`
prøver kildene i konfigurert rekkefølge og returnerer den første som svarer.
"""

from __future__ import annotations

import logging

from .. import config
from .base import Kilde, KildeUtilgjengelig
from .fixtures import FixtureKilde
from .fmp import FmpKilde
from .yahoo import YahooKilde

log = logging.getLogger(__name__)

KILDER = {
    "fmp": FmpKilde,
    "yahoo": YahooKilde,
    "fixtures": FixtureKilde,
}


def velg_kilde(navn: str | None = None) -> Kilde:
    """Returnerer en brukbar datakilde.

    Med `navn` tvinges én bestemt kilde (og vi feiler hvis den ikke virker).
    Uten navn prøves `config.KILDE_REKKEFOLGE` i tur og orden.
    """
    if navn:
        if navn not in KILDER:
            raise KildeUtilgjengelig(
                f"Ukjent kilde «{navn}». Gyldige: {', '.join(KILDER)}"
            )
        kilde = KILDER[navn]()
        if not kilde.tilgjengelig():
            raise KildeUtilgjengelig(f"Kilden «{navn}» er ikke tilgjengelig nå")
        log.info("Bruker datakilde: %s", navn)
        return kilde

    for kandidat in config.KILDE_REKKEFOLGE:
        klasse = KILDER.get(kandidat)
        if not klasse:
            continue
        kilde = klasse()
        try:
            if kilde.tilgjengelig():
                log.info("Bruker datakilde: %s", kandidat)
                return kilde
        except Exception as feil:  # en død kilde skal aldri velte kjøringen
            log.warning("Kilden «%s» feilet under oppstart: %s", kandidat, feil)

    raise KildeUtilgjengelig(
        "Ingen datakilde tilgjengelig. Sett FMP_API_KEY (gratis nøkkel fra "
        "financialmodelingprep.com), eller kjør med --kilde fixtures for "
        "offline testdata."
    )


__all__ = ["velg_kilde", "Kilde", "KildeUtilgjengelig", "KILDER"]
