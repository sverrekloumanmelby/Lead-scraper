"""Detektor for chat-widgets på foretakenes nettsider.

Vi laster nettsiden i Playwright, venter til nettverket roer seg, og leter
etter kjente chatbot-signaturer i både HTML og alle innlastede skript-URLer.
"""

from __future__ import annotations

import logging
from typing import Iterable

from playwright.sync_api import Browser, TimeoutError as PWTimeout

from .config import CHATBOT_SIGNATURER, NETTSIDE_TIMEOUT_MS

logger = logging.getLogger(__name__)


def _match_signaturer(kilder: Iterable[str]) -> list[str]:
    """Returnerer navn på widgets som matcher noen av de gitte strengene."""
    kilder_joined = "\n".join(kilder).lower()
    funn: list[str] = []
    for navn, moenstre in CHATBOT_SIGNATURER.items():
        for m in moenstre:
            if m.lower() in kilder_joined:
                funn.append(navn)
                break
    return funn


def sjekk_nettside(browser: Browser, url: str) -> tuple[bool, list[str]]:
    """Undersøk om nettsiden har chatbot. Returnerer (har_chat, [navn])."""
    if not url:
        return False, []

    # Sørg for skjema, ellers vil Playwright feile
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        )
    )
    page = context.new_page()
    innlastede_urler: list[str] = []

    # Loggfør alle innlastede ressurs-URLer
    page.on("request", lambda req: innlastede_urler.append(req.url))

    try:
        # «load» + kort ro-periode er raskere enn networkidle og fanger
        # likevel widgets som lastes rett etter sidelast.
        page.goto(url, wait_until="load", timeout=NETTSIDE_TIMEOUT_MS)
        page.wait_for_timeout(3000)
    except PWTimeout:
        logger.debug("Timeout ved lasting av %s (fortsetter med det vi har)", url)
    except Exception as e:
        logger.warning("Kunne ikke laste %s: %s", url, e)
        context.close()
        return False, []

    try:
        html = page.content()
    except Exception:
        html = ""

    kilder = [html, *innlastede_urler]
    funn = _match_signaturer(kilder)

    context.close()
    return bool(funn), funn
