"""Hjelper for å finne en brukbar Chromium-binær.

I noen kjøremiljøer er Chromium forhåndsinstallert på en fast sti i stedet
for i Playwrights egen cache. Da peker vi Playwright dit eksplisitt.
"""

from __future__ import annotations

import os
from pathlib import Path

# Kjente steder Chromium kan ligge utenfor Playwrights cache
KJENTE_STIER = [
    "/opt/pw-browsers/chromium",
]


def finn_chromium() -> str | None:
    """Returnerer sti til Chromium-binær, eller None for Playwrights standard."""
    overstyring = os.environ.get("CHROMIUM_EXECUTABLE")
    if overstyring and Path(overstyring).exists():
        return overstyring
    for sti in KJENTE_STIER:
        if Path(sti).exists():
            return sti
    return None


def proxy_innstillinger() -> dict | None:
    """Bygger Playwright-proxyoppsett fra miljøvariabler.

    Kjøremiljøer med utgående proxy setter HTTPS_PROXY; Chromium plukker
    ikke alltid opp denne selv, så vi sender den eksplisitt til launch().
    """
    server = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if not server:
        return None
    return {"server": server, "bypass": os.environ.get("NO_PROXY", "")}


def launch_argumenter() -> dict:
    """Samlede launch-argumenter for Playwright chromium.launch()."""
    args: dict = {"headless": True}
    chromium = finn_chromium()
    if chromium:
        args["executable_path"] = chromium
    proxy = proxy_innstillinger()
    if proxy:
        args["proxy"] = proxy
    # Agent-proxyen i enkelte kjøremiljøer re-terminerer TLS og tåler ikke
    # Chromiums TLS 1.3-håndtrykk (stor ClientHello). Trafikken MITM-es
    # uansett av proxyen, så vi begrenser klient-leddet til TLS 1.2 kun når
    # en slik proxy er aktiv. På vanlige maskiner endres ingenting.
    if os.environ.get("CCR_AGENT_PROXY_ENABLED") == "1":
        args["args"] = ["--ssl-version-max=tls1.2"]
    return args
