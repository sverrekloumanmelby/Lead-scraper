"""Sending av rapportene via Gmail.

Bruker Gmail sin SMTP-server med app-passord. Vanlig kontopassord virker ikke
— du må lage et app-passord (krever tofaktor på Google-kontoen). Se README.

Legitimasjonen leses fra miljøvariabler og skal aldri ligge i repoet.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from . import config

log = logging.getLogger(__name__)


class EpostFeil(RuntimeError):
    """Kastes når e-posten ikke kunne sendes."""


def _sjekk_oppsett() -> tuple[str, str]:
    """Henter og validerer avsenderoppsettet."""
    bruker = config.AVSENDER_EPOST
    passord = config.GMAIL_APP_PASSWORD
    if not bruker or not passord:
        raise EpostFeil(
            "Mangler GMAIL_USER og/eller GMAIL_APP_PASSWORD. Sett dem som "
            "miljøvariabler (lokalt) eller repo-secrets (GitHub Actions). "
            "Se investor/README.md for hvordan du lager et app-passord."
        )
    return bruker, passord


def bygg_melding(
    emne: str, html: str, tekst: str, *, til: str | None = None
) -> EmailMessage:
    """Bygger en multipart-melding med både ren tekst og HTML."""
    bruker, _ = _sjekk_oppsett()
    mottaker = til or config.MOTTAKER_EPOST or bruker

    melding = EmailMessage()
    melding["Subject"] = emne
    melding["From"] = formataddr(("Investeringsassistent", bruker))
    melding["To"] = mottaker
    melding["Date"] = formatdate(localtime=True)

    # Ren tekst først: klienter som ikke viser HTML faller tilbake på denne.
    melding.set_content(tekst)
    melding.add_alternative(html, subtype="html")
    return melding


def send(emne: str, html: str, tekst: str, *, til: str | None = None) -> None:
    """Sender e-posten. Kaster EpostFeil om noe går galt."""
    bruker, passord = _sjekk_oppsett()
    melding = bygg_melding(emne, html, tekst, til=til)

    kontekst = ssl.create_default_context()
    try:
        with smtplib.SMTP(config.SMTP_VERT, config.SMTP_PORT, timeout=60) as smtp:
            smtp.ehlo()
            smtp.starttls(context=kontekst)
            smtp.ehlo()
            smtp.login(bruker, passord)
            smtp.send_message(melding)
    except smtplib.SMTPAuthenticationError as feil:
        raise EpostFeil(
            "Gmail avviste innloggingen. Sjekk at GMAIL_APP_PASSWORD er et "
            "app-passord (16 tegn, ikke ditt vanlige passord) og at tofaktor "
            f"er slått på for kontoen. Detaljer: {feil}"
        ) from feil
    except (smtplib.SMTPException, OSError) as feil:
        raise EpostFeil(f"Klarte ikke sende e-post: {feil}") from feil

    log.info("Sendte «%s» til %s", emne, melding["To"])
