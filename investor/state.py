"""Historikk mellom kjøringer.

Uten dette ville hver e-post vært et øyeblikksbilde. Med det kan rapportene si
noe om *endring*: hvilke kandidater som er nye siden sist, hvordan kursene har
beveget seg siden forrige e-post, og hva som skjedde gjennom måneden.

Filen committes tilbake av GitHub Actions, siden containeren er flyktig.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

PAKKE = Path(__file__).resolve().parent

# Hvor mange historiske øyeblikksbilder vi tar vare på per modus.
MAKS_SNAPSHOTS = 24


def _sti(sti: str | Path | None = None) -> Path:
    return Path(sti) if sti else PAKKE / config.STATE_FIL


def les(sti: str | Path | None = None) -> dict:
    """Leser state-filen. Returnerer tom struktur om den ikke finnes."""
    p = _sti(sti)
    if not p.exists():
        return {"snapshots": {}, "sett_kandidater": {}}
    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as feil:
        log.warning("Kunne ikke lese %s (%s) — starter med tom historikk", p, feil)
        return {"snapshots": {}, "sett_kandidater": {}}
    data.setdefault("snapshots", {})
    data.setdefault("sett_kandidater", {})
    return data


def skriv(data: dict, sti: str | Path | None = None) -> None:
    """Skriver state-filen (oppretter katalogen ved behov)."""
    p = _sti(sti)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    log.info("Lagret historikk til %s", p)


def forrige_snapshot(data: dict, modus: str) -> dict | None:
    """Siste lagrede øyeblikksbilde for gitt rapporttype."""
    liste = data.get("snapshots", {}).get(modus) or []
    return liste[-1] if liste else None


def lagre_snapshot(data: dict, modus: str, statuser, kandidater) -> None:
    """Lagrer kurser og kandidatliste fra denne kjøringen."""
    snapshot = {
        "dato": date.today().isoformat(),
        "tidspunkt": datetime.now().isoformat(timespec="seconds"),
        "kurser": {
            s.ticker: s.kurs.pris
            for s in statuser
            if s.kurs and s.kurs.pris is not None
        },
        "kandidater": [
            {"ticker": k.ticker, "navn": k.navn, "score": k.score}
            for k in kandidater
        ],
    }
    liste = data.setdefault("snapshots", {}).setdefault(modus, [])
    liste.append(snapshot)
    del liste[:-MAKS_SNAPSHOTS]


def nye_kandidater(data: dict, modus: str, kandidater) -> set[str]:
    """Hvilke kandidater er nye siden forrige rapport av samme type?"""
    forrige = forrige_snapshot(data, modus)
    if not forrige:
        return {k.ticker for k in kandidater}
    kjente = {k.get("ticker") for k in forrige.get("kandidater", [])}
    return {k.ticker for k in kandidater if k.ticker not in kjente}


def kurs_siden_forrige(data: dict, modus: str, ticker: str, pris: float | None):
    """Prosentendring for en ticker siden forrige rapport av samme type."""
    if pris is None:
        return None
    forrige = forrige_snapshot(data, modus)
    if not forrige:
        return None
    gammel = (forrige.get("kurser") or {}).get(ticker)
    if not gammel:
        return None
    return (pris - gammel) / abs(gammel) * 100


def dato_forrige(data: dict, modus: str) -> str | None:
    """Datoen for forrige rapport av denne typen, til bruk i e-posten."""
    forrige = forrige_snapshot(data, modus)
    return forrige.get("dato") if forrige else None
