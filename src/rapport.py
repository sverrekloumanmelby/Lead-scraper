"""Skriver en lesbar markdown-liste ved siden av CSV-en.

CSV-en er for videre bearbeiding; denne fila er til å faktisk jobbe ut
fra: kontorene gruppert etter hvor gode leads de er, med kontaktperson
og begrunnelse rett i lista.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _rad(lead: dict) -> str:
    kontakt = lead.get("kontakt_navn") or "—"
    tittel = lead.get("kontakt_tittel") or ""
    if tittel:
        kontakt = f"{kontakt} ({tittel})"

    kanaler = []
    if lead.get("kontakt_epost"):
        kanaler.append(lead["kontakt_epost"])
    elif lead.get("epost"):
        kanaler.append(f"{lead['epost']} (firmapost)")
    if lead.get("kontakt_telefon"):
        kanaler.append(lead["kontakt_telefon"])
    kanal = " · ".join(kanaler) or "—"

    nettside = lead.get("nettside") or "—"
    if nettside.startswith("https://"):
        nettside = nettside[len("https://"):]
    nettside = nettside.rstrip("/")

    chat = lead.get("chatbot_kategori", "")
    if lead.get("chatbot_navn"):
        chat = f"{chat}: {lead['chatbot_navn']}"

    return (
        f"| {lead['firmanavn'].title()} | {lead.get('segment', '')} | "
        f"{lead['antall_ansatte']} | "
        f"{lead.get('by', '')} | {nettside} | {chat} | {kontakt} | "
        f"{kanal} | {lead.get('score', 0)} |"
    )


HODE = (
    "| Kontor | Segment | Ans. | Sted | Nettside | Chat i dag | Kontaktperson | "
    "E-post / telefon | Score |\n"
    "|---|---|---:|---|---|---|---|---|---:|"
)


def skriv_rapport(sti: str | Path, leads: Iterable[dict]) -> None:
    leads = sorted(leads, key=lambda x: x.get("score", 0), reverse=True)

    grupper: list[tuple[str, str, list[dict]]] = [
        ("Har bemannet live-chat — varmest",
         "Har allerede bestemt at chat er riktig kanal, og betaler i dag "
         "med bemanning. Kortest vei til et salg.",
         [x for x in leads if "Live" in x.get("chatbot_kategori", "")]),
        ("Ingen chat på nettsiden",
         "Verifisert: nettsiden ble lastet og rendret uten at noen "
         "chat-widget dukket opp.",
         [x for x in leads if x.get("chatbot_kategori") == "ingen"]),
        ("Nettside ikke funnet — chat-status uavklart",
         "Kontoret finnes og er i riktig størrelse, men vi fant ingen "
         "nettside å sjekke. Krever manuelt oppslag.",
         [x for x in leads if "ukjent" in x.get("chatbot_kategori", "")]),
        ("Har allerede AI-chatbot — lav prioritet",
         "Dekket av en konkurrerende løsning.",
         [x for x in leads if "AI" in x.get("chatbot_kategori", "")]),
    ]

    linjer = [
        "# Eiendomsmeglerkontorer i Norge — leads for AI-chatbot",
        "",
        f"**{len(leads)} kontorer**, alle uavhengige (kjedekontorer er "
        "luket ut) og med 3–20 ansatte. Kilde til grunndata er "
        "Enhetsregisteret; chat-status er sjekket ved å rendre nettsiden "
        "i en ekte nettleser.",
        "",
    ]

    for tittel, forklaring, utvalg in grupper:
        if not utvalg:
            continue
        linjer += [f"## {tittel} ({len(utvalg)})", "", forklaring, "", HODE]
        linjer += [_rad(x) for x in utvalg]
        linjer.append("")

    Path(sti).write_text("\n".join(linjer), encoding="utf-8")
