"""Scoring og filtrering av leads."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .config import (
    ANSATT_GRUPPER,
    KJEDE_DOMENER,
    KJEDE_NAVN_MONSTRE,
    PRIORITET_HOY_MIN,
    PRIORITET_MIDDELS_MIN,
)

_KJEDE_REGEX = [re.compile(m, re.IGNORECASE) for m in KJEDE_NAVN_MONSTRE]


def _vert_fra_url(url: str) -> str:
    """Trekker ut vertsnavn (uten www.) fra en URL eller naken domenestreng."""
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    vert = (urlparse(url).hostname or "").lower()
    return vert.removeprefix("www.")


def er_kjede(firmanavn: str, nettside: str = "") -> bool:
    """Sjekker om et foretak tilhører en av kjedene vi ekskluderer.

    Vi ser både på firmanavnet og på nettside-domenet, fordi
    franchisekontorer ofte har nøytrale AS-navn men kjedens nettside.
    """
    if firmanavn and any(r.search(firmanavn) for r in _KJEDE_REGEX):
        return True
    vert = _vert_fra_url(nettside)
    if vert:
        for domene in KJEDE_DOMENER:
            if vert == domene or vert.endswith("." + domene):
                return True
    return False


def ansatt_gruppe(antall: int) -> str | None:
    """Returnerer etiketten for gruppen antallet faller i, ellers None."""
    for minst, maks, etikett in ANSATT_GRUPPER:
        if minst <= antall <= maks:
            return etikett
    return None


def passer_ansatt_filter(antall: int) -> bool:
    """Faller antallet i en av målgruppene?"""
    return ansatt_gruppe(antall) is not None


def beregn_score(lead: dict) -> int:
    """Beregner score 0–100 basert på reglene i oppgaven."""
    score = 0
    if passer_ansatt_filter(lead.get("antall_ansatte", 0)):
        score += 30
    if not lead.get("har_chatbot", False):
        score += 40
    if not er_kjede(lead.get("firmanavn", "")):
        score += 30
    return score


def prioritet(score: int) -> str:
    """Grovklassifiser scoren i HØY/MIDDELS/LAV."""
    if score >= PRIORITET_HOY_MIN:
        return "HØY"
    if score >= PRIORITET_MIDDELS_MIN:
        return "MIDDELS"
    return "LAV"
