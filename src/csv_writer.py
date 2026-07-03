"""Skriver ferdige leads til CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

FELTER = [
    "prioritet",
    "score",
    "firmanavn",
    "daglig_leder",
    "telefon",
    "epost",
    "antall_ansatte",
    "by",
    "nettside",
    "har_chatbot",
    "chatbot_navn",
    "orgnr",
    "kilde",
]


def skriv_leads(sti: str | Path, leads: Iterable[dict]) -> int:
    """Skriv leads sortert etter score (høyeste først). Returnerer antall rader."""
    sortert = sorted(leads, key=lambda x: x.get("score", 0), reverse=True)
    with open(sti, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FELTER, extrasaction="ignore")
        writer.writeheader()
        for lead in sortert:
            # Konverter lister til semikolon-separert streng for CSV-vennlighet
            rad = dict(lead)
            if isinstance(rad.get("chatbot_navn"), list):
                rad["chatbot_navn"] = ";".join(rad["chatbot_navn"])
            writer.writerow(rad)
    return len(sortert)
