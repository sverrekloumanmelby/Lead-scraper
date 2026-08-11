"""Felles grunnlag for datakildene.

Hver kilde implementerer `Kilde`-grensesnittet og returnerer modellene fra
`modeller.py`. Resten av systemet ser aldri leverandørspesifikke felt.
"""

from __future__ import annotations

import logging
import time
from datetime import date

import requests

from .. import config
from ..modeller import Fundamentals, Kurs, Nyhet, Resultat

log = logging.getLogger(__name__)

BRUKERAGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


class KildeUtilgjengelig(RuntimeError):
    """Kastes når en kilde ikke kan brukes (mangler nøkkel, strupet, nede)."""


class Kilde:
    """Grensesnittet alle datakilder implementerer."""

    navn = "base"

    def tilgjengelig(self) -> bool:
        """Kan denne kilden brukes akkurat nå?"""
        raise NotImplementedError

    def hent_kurs(self, ticker: str) -> Kurs | None:
        raise NotImplementedError

    def hent_fundamentals(self, ticker: str) -> Fundamentals | None:
        raise NotImplementedError

    def hent_nyheter(self, ticker: str, siden: date | None = None) -> list[Nyhet]:
        raise NotImplementedError

    def hent_resultat(self, ticker: str) -> Resultat | None:
        """Siste rapporterte kvartal (med tall) om tilgjengelig."""
        raise NotImplementedError

    def hent_neste_resultatdato(self, ticker: str) -> date | None:
        raise NotImplementedError

    def hent_univers(self) -> list[str]:
        """Tickere som er kandidater til screening, forhåndsfiltrert grovt."""
        raise NotImplementedError


class HttpKilde(Kilde):
    """Kilde med delt HTTP-session, retry og skånsom pausing."""

    def __init__(self) -> None:
        self._sesjon = requests.Session()
        self._sesjon.headers.update({"User-Agent": BRUKERAGENT})

    def _hent_json(
        self,
        url: str,
        params: dict | None = None,
        *,
        tillat_feil: bool = True,
    ):
        """GET med retry og eksponentiell backoff.

        Returnerer None ved vedvarende feil når `tillat_feil` er satt, slik at
        én ticker som feiler ikke stopper hele kjøringen.
        """
        pause = config.HTTP_BACKOFF
        for forsok in range(1, config.HTTP_RETRIES + 1):
            try:
                svar = self._sesjon.get(
                    url, params=params, timeout=config.HTTP_TIMEOUT
                )
            except requests.RequestException as feil:
                log.debug("%s: nettverksfeil (%s/%s): %s",
                          self.navn, forsok, config.HTTP_RETRIES, feil)
            else:
                if svar.status_code == 200:
                    try:
                        return svar.json()
                    except ValueError:
                        log.debug("%s: ugyldig JSON fra %s", self.navn, url)
                        return None
                # 429/5xx er verdt å prøve igjen; 4xx ellers er permanent.
                if svar.status_code not in (429, 500, 502, 503, 504):
                    log.debug("%s: HTTP %s fra %s", self.navn, svar.status_code, url)
                    if not tillat_feil:
                        raise KildeUtilgjengelig(
                            f"{self.navn}: HTTP {svar.status_code}"
                        )
                    return None
                log.debug("%s: HTTP %s (%s/%s), venter %.1fs",
                          self.navn, svar.status_code, forsok,
                          config.HTTP_RETRIES, pause)

            if forsok < config.HTTP_RETRIES:
                time.sleep(pause)
                pause *= 2

        if not tillat_feil:
            raise KildeUtilgjengelig(f"{self.navn}: ga opp etter "
                                     f"{config.HTTP_RETRIES} forsøk")
        return None

    def _pust(self) -> None:
        """Kort pause mellom kall i en batch."""
        time.sleep(config.HTTP_PAUSE)


def tall(verdi, standard=None) -> float | None:
    """Konverterer trygt til float. Tomme strenger og None gir standardverdi."""
    if verdi is None or verdi == "":
        return standard
    try:
        resultat = float(verdi)
    except (TypeError, ValueError):
        return standard
    # NaN er aldri et gyldig nøkkeltall for oss.
    if resultat != resultat:
        return standard
    return resultat


def prosent_endring(fra: float | None, til: float | None) -> float | None:
    """Endring fra->til i prosent."""
    if fra is None or til is None or fra == 0:
        return None
    return (til - fra) / abs(fra) * 100
