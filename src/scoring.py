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


def segment(firmanavn: str) -> str:
    """Grovsorterer kontoret etter hva slags megling det driver.

    Skillet betyr mye for et chatbot-salg: et boligmeglerkontor har
    publikumstrafikk på nettsiden hele døgnet og mange like spørsmål,
    mens næringsmegling har få og tunge henvendelser der en bot gir
    langt mindre.
    """
    navn = firmanavn.lower()
    if "næringsmegl" in navn or "naringsmegl" in navn or "næring" in navn:
        return "Næring"
    if "landbruk" in navn or "skogbruk" in navn:
        return "Landbruk"
    if "utleie" in navn:
        return "Utleie"
    if "oppgjør" in navn or "oppgjor" in navn:
        return "Oppgjør"
    if "prosjekt" in navn:
        return "Prosjekt"
    return "Bolig"


def beregn_score(lead: dict) -> int:
    """Scorer hvor godt kontoret passer som kjøper av en AI-chatbot (0–100).

    Chat-situasjonen veier tyngst. Merk at et kontor med bemannet
    live-chat scorer *høyere* enn et helt uten: de har allerede bestemt
    seg for at chat er riktig kanal, og betaler i dag med bemanning —
    det er en kortere vei til et salg enn å overbevise noen som ikke har
    chat i det hele tatt. Har kontoret allerede en AI-bot, er det nesten
    ikke et lead.
    """
    kategori = lead.get("chatbot_kategori", "")
    if "AI" in kategori:
        score = 5
    elif "Live" in kategori:
        score = 45
    elif kategori == "ingen":
        score = 40
    else:  # ukjent — nettsiden ble ikke funnet eller lastet ikke
        score = 15

    antall = lead.get("antall_ansatte", 0)
    if 3 <= antall <= 15:
        score += 25
    elif passer_ansatt_filter(antall):
        score += 15

    if not er_kjede(lead.get("firmanavn", ""), lead.get("nettside", "")):
        score += 15

    # En navngitt kontaktperson med e-post gjør leadet direkte handlingsbart
    if lead.get("kontakt_epost"):
        score += 10
    if lead.get("kontakt_kilde", "").startswith("nettside"):
        score += 5

    # Boligmegling er den klart beste bruken for en publikumsrettet bot
    if segment(lead.get("firmanavn", "")) != "Bolig":
        score -= 10

    return max(0, min(score, 100))


def prioritet(score: int) -> str:
    """Grovklassifiser scoren i HØY/MIDDELS/LAV."""
    if score >= PRIORITET_HOY_MIN:
        return "HØY"
    if score >= PRIORITET_MIDDELS_MIN:
        return "MIDDELS"
    return "LAV"
