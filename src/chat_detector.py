"""Detektor for chat-widgets på foretakenes nettsider.

To ting skiller denne fra en naiv «finnes ordet chat i HTML»-sjekk:

* Vi skiller **AI-chatbot** fra **live-chat med menneske**. For et salg av
  AI-chatbot er de to helt ulike situasjoner: et kontor med Kindly eller
  boost.ai er allerede dekket, mens et kontor med bemannet LiveChat er et
  varmt lead — de har vist at de vil ha chat, men svarer manuelt.
* Widgets lastes ofte inn via Google Tag Manager og er derfor usynlige i
  rå HTML. Da rendrer vi siden i Chromium og ser hva som faktisk lastes.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable

from .config import CHATBOT_SIGNATURER, KATEGORI_AI, KATEGORI_LIVE

logger = logging.getLogger(__name__)

# Tegn på at en tag-manager kan laste inn en widget vi ikke ser i rå HTML.
TAGMANAGER_SIGNALER = [
    "googletagmanager.com/gtm.js", "gtm.start", "google-tag-manager",
    "segment.com/analytics.js", "cdn.segment.com",
]

# Generiske spor etter chat som ikke identifiserer leverandøren.
GENERISKE_CHAT_SIGNALER = [
    "chat-widget", "chatwidget", "chat-bubble", "chatbubble",
    'id="chatbot', 'class="chatbot', "livechat", "live-chat",
    "chat med oss", "snakk med oss", "chatbot",
]


def _match_signaturer(kilder: Iterable[str]) -> dict[str, str]:
    """Finner widgets i teksten. Returnerer {widgetnavn: kategori}."""
    samlet = "\n".join(kilder).lower()
    funn: dict[str, str] = {}
    for navn, (moenstre, kategori) in CHATBOT_SIGNATURER.items():
        if any(m.lower() in samlet for m in moenstre):
            funn[navn] = kategori
    return funn


def _oppsummer(funn: dict[str, str]) -> tuple[bool, str, str]:
    """Gjør funnene om til (har_chat, kategori, navneliste)."""
    if not funn:
        return False, "ingen", ""
    kategori = KATEGORI_AI if KATEGORI_AI in funn.values() else KATEGORI_LIVE
    return True, kategori, ";".join(sorted(funn))


def analyser_html(html: str) -> tuple[bool, str, str, bool]:
    """Ser etter chat-spor i rå HTML.

    Returnerer (har_chat, kategori, navn, boer_rendres) der siste flagg
    sier om siden bør sjekkes i nettleser for å være sikker.
    """
    if not html:
        return False, "ukjent", "", True

    lav = html.lower()
    funn = _match_signaturer([lav])
    har, kategori, navn = _oppsummer(funn)
    if har:
        return har, kategori, navn, False

    # Ingen kjent leverandør: kan widgeten komme via tag manager, eller
    # ligger det generiske chat-spor vi ikke klarer å tilordne?
    via_tagmanager = any(s in lav for s in TAGMANAGER_SIGNALER)
    generisk = any(s in lav for s in GENERISKE_CHAT_SIGNALER)
    return False, "ingen", "", via_tagmanager or generisk


async def analyser_med_nettleser(context, url: str, timeout_ms: int = 20000):
    """Rendrer siden i Chromium og ser hvilke ressurser som lastes.

    Chat-widgets laster nesten alltid et eksternt skript, så nettverks-
    loggen avslører dem selv når de settes inn av en tag manager.
    """
    side = await context.new_page()
    ressurser: list[str] = []
    side.on("request", lambda req: ressurser.append(req.url))
    try:
        await side.goto(url, wait_until="load", timeout=timeout_ms)
        # Chat-widgets lastes typisk et par sekunder etter sidelast
        await side.wait_for_timeout(4000)
        html = await side.content()
    except Exception as e:
        logger.debug("Kunne ikke rendre %s: %s", url, e)
        return False, "ukjent", "", []
    finally:
        try:
            await side.close()
        except Exception:
            pass

    funn = _match_signaturer([html.lower(), *[r.lower() for r in ressurser]])
    har, kategori, navn = _oppsummer(funn)
    return har, kategori, navn, ressurser


def rens_url(url: str) -> str:
    """Sørger for at URL-en har skjema."""
    if url and not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def finn_undersider(html: str, basis_url: str, nokkelord: list[str],
                    maks: int = 4) -> list[str]:
    """Plukker ut interne lenker som matcher nøkkelord (f.eks. «om-oss»)."""
    from urllib.parse import urljoin, urlparse

    basis_vert = (urlparse(basis_url).hostname or "").lower()
    treff: list[str] = []
    for href in re.findall(r'href="([^"#]+)"', html, re.IGNORECASE):
        lav = href.lower()
        if not any(n in lav for n in nokkelord):
            continue
        full = urljoin(basis_url, href)
        vert = (urlparse(full).hostname or "").lower()
        if vert != basis_vert:
            continue
        if full not in treff:
            treff.append(full)
        if len(treff) >= maks:
            break
    return treff
