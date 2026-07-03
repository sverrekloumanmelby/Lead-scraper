"""Scoring og filtrering av leads."""

from __future__ import annotations

from .config import (
    EKSKLUDERTE_KJEDER,
    MAKS_ANSATTE,
    MIN_ANSATTE,
    PRIORITET_HOY_MIN,
    PRIORITET_MIDDELS_MIN,
)


def er_kjede(firmanavn: str) -> bool:
    """Sjekker om et firmanavn tilhører en av kjedene vi ekskluderer."""
    if not firmanavn:
        return False
    n = firmanavn.lower()
    return any(k.lower() in n for k in EKSKLUDERTE_KJEDER)


def passer_ansatt_filter(antall: int) -> bool:
    """3–15 ansatte inklusive."""
    return MIN_ANSATTE <= antall <= MAKS_ANSATTE


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
