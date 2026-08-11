"""Overvåking av selskapene i porteføljen.

Kjernen her er `finn_hendelser()`: den avgjør hva som er *genuint relevant*.
Den daglige e-posten skal ikke gjenta kurser du kan slå opp selv — den skal si
fra når noe faktisk har skjedd. Derfor får hver hendelse en viktighet, og den
daglige rapporten tar kun med det som når opp i `config.DAGLIG_MIN_VIKTIGHET`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from . import config
from .kilder.base import Kilde
from .modeller import Beholdning, Hendelse, Kurs, Nyhet, Resultat

log = logging.getLogger(__name__)

PAKKE = Path(__file__).resolve().parent


@dataclass
class Selskapsstatus:
    """Alt vi vet om ett porteføljeselskap på rapporttidspunktet."""

    beholdning: Beholdning
    kurs: Kurs | None = None
    resultat: Resultat | None = None
    neste_resultat: date | None = None
    nyheter: list[Nyhet] = field(default_factory=list)
    hendelser: list[Hendelse] = field(default_factory=list)
    fundamentals: object | None = None

    @property
    def ticker(self) -> str:
        return self.beholdning.ticker

    @property
    def navn(self) -> str:
        return self.beholdning.navn or self.ticker

    @property
    def avkastning(self) -> tuple[float, float] | None:
        if not self.kurs:
            return None
        return self.beholdning.avkastning(self.kurs)

    def viktigste_hendelser(self, min_viktighet: int = 1) -> list[Hendelse]:
        """Hendelser på eller over gitt viktighet, viktigste først."""
        traff = [h for h in self.hendelser if h.viktighet >= min_viktighet]
        return sorted(traff, key=lambda h: h.viktighet, reverse=True)


# ---------------------------------------------------------------------------
# Portefølje
# ---------------------------------------------------------------------------


def les_portefolje(sti: str | Path | None = None) -> tuple[list[Beholdning], list[str]]:
    """Leser portfolio.json og returnerer (beholdninger, watchlist).

    Oppføringer med placeholder-ticker hoppes over med en advarsel, slik at
    systemet fungerer selv før alle tickere er fylt inn.
    """
    sti = Path(sti) if sti else PAKKE / config.PORTEFOLJE_FIL
    if not sti.exists():
        log.error("Fant ikke porteføljefilen: %s", sti)
        return [], []

    with sti.open(encoding="utf-8") as f:
        data = json.load(f)

    beholdninger = []
    for rad in data.get("beholdninger", []):
        ticker = (rad.get("ticker") or "").strip()
        if not ticker:
            continue
        if ticker.upper().startswith("BYTT_MEG"):
            log.warning(
                "Hopper over «%s» — bytt ticker i %s for å ta den med",
                rad.get("navn") or ticker, sti.name,
            )
            continue
        beholdninger.append(
            Beholdning(
                ticker=ticker,
                navn=rad.get("navn") or ticker,
                antall=rad.get("antall"),
                kostpris=rad.get("kostpris"),
                valuta=rad.get("valuta") or "",
                notat=rad.get("notat") or "",
            )
        )

    watchlist = [t.strip() for t in data.get("watchlist", []) if str(t).strip()]
    return beholdninger, watchlist


# ---------------------------------------------------------------------------
# Hendelsesdeteksjon
# ---------------------------------------------------------------------------


def _nyhet_er_viktig(tittel: str) -> bool:
    """Treffer overskriften et av nøkkelordene vi bryr oss om?"""
    lav = tittel.lower()
    return any(ord_.lower() in lav for ord_ in config.NYHET_VIKTIGE_ORD)


def _formater_prosent(
    verdi: float | None, desimaler: int = 1, fortegn: bool = True
) -> str:
    """Prosent med norsk komma. Fortegn kan slås av når retningen allerede
    framgår av teksten rundt (f.eks. «gikk ned 7,3 %»)."""
    if verdi is None:
        return "–"
    tegn = "+" if fortegn and verdi > 0 else ""
    return f"{tegn}{verdi:.{desimaler}f}".replace(".", ",") + " %"


def finn_hendelser(status: Selskapsstatus) -> list[Hendelse]:
    """Finner det som er verdt å nevne for ett selskap.

    Viktighet styrer hvor hendelsen dukker opp: kun MIDDELS og HØY kommer med
    i den daglige e-posten, mens ukentlig og månedlig tar med alt.
    """
    hendelser: list[Hendelse] = []
    kurs = status.kurs

    # --- Store kursbevegelser på én dag ---
    if kurs and kurs.endring_1d is not None:
        bevegelse = abs(kurs.endring_1d)
        if bevegelse >= config.KURSBEVEGELSE_MIDDELS:
            retning = "opp" if kurs.endring_1d > 0 else "ned"
            viktighet = (
                config.VIKTIGHET_HOY
                if bevegelse >= config.KURSBEVEGELSE_HOY
                else config.VIKTIGHET_MIDDELS
            )
            hendelser.append(
                Hendelse(
                    ticker=status.ticker,
                    type="kursbevegelse",
                    tittel=(
                        f"Kursen gikk {retning} "
                        f"{_formater_prosent(bevegelse, fortegn=False)}"
                    ),
                    detalj=(
                        f"Står nå i {kurs.pris:.2f} {kurs.valuta}".replace(".", ",")
                        if kurs.pris
                        else ""
                    ),
                    viktighet=viktighet,
                )
            )

    # --- Kommende resultatdato ---
    if status.neste_resultat:
        dager = (status.neste_resultat - date.today()).days
        if 0 <= dager <= config.RESULTAT_VARSEL_DAGER:
            naar = "i dag" if dager == 0 else (
                "i morgen" if dager == 1 else f"om {dager} dager"
            )
            hendelser.append(
                Hendelse(
                    ticker=status.ticker,
                    type="resultat",
                    tittel=f"Legger fram kvartalstall {naar}",
                    detalj=status.neste_resultat.strftime("%d.%m.%Y"),
                    viktighet=config.VIKTIGHET_HOY,
                )
            )

    # --- Ferskt resultat med tall ---
    res = status.resultat
    if res and res.dato and (date.today() - res.dato).days <= 7:
        biter = []
        if res.omsetningsvekst is not None:
            biter.append(f"omsetning {_formater_prosent(res.omsetningsvekst)} mot i fjor")
        if res.eps_overraskelse is not None:
            over = "over" if res.eps_overraskelse >= 0 else "under"
            biter.append(
                f"resultat per aksje {abs(res.eps_overraskelse):.1f} % {over} forventning".replace(
                    ".", ","
                )
            )
        hendelser.append(
            Hendelse(
                ticker=status.ticker,
                type="resultat",
                tittel=f"La fram tall for {res.periode or 'siste kvartal'}",
                detalj="; ".join(biter),
                viktighet=config.VIKTIGHET_HOY,
            )
        )

    # --- Nyheter som treffer nøkkelordene ---
    for nyhet in status.nyheter:
        if not _nyhet_er_viktig(nyhet.tittel):
            continue
        fersk = (
            nyhet.publisert is not None
            and (date.today() - nyhet.publisert.date()).days <= 2
        )
        hendelser.append(
            Hendelse(
                ticker=status.ticker,
                type="nyhet",
                tittel=nyhet.tittel,
                detalj=nyhet.kilde,
                viktighet=(
                    config.VIKTIGHET_MIDDELS if fersk else config.VIKTIGHET_LAV
                ),
                url=nyhet.url,
            )
        )

    return hendelser


# ---------------------------------------------------------------------------
# Innsamling
# ---------------------------------------------------------------------------


def hent_status(
    kilde: Kilde,
    beholdninger: list[Beholdning],
    *,
    nyheter_siden: date | None = None,
    med_fundamentals: bool = False,
) -> list[Selskapsstatus]:
    """Henter alt vi trenger om hvert porteføljeselskap.

    Én ticker som feiler skal aldri stoppe rapporten — da rapporterer vi det vi
    har og logger resten.
    """
    statuser: list[Selskapsstatus] = []

    for beholdning in beholdninger:
        status = Selskapsstatus(beholdning=beholdning)
        ticker = beholdning.ticker

        for navn, hent in (
            ("kurs", lambda: kilde.hent_kurs(ticker)),
            ("nyheter", lambda: kilde.hent_nyheter(ticker, nyheter_siden)),
            ("resultat", lambda: kilde.hent_resultat(ticker)),
            ("resultatdato", lambda: kilde.hent_neste_resultatdato(ticker)),
        ):
            try:
                verdi = hent()
            except Exception as feil:
                log.warning("%s: klarte ikke hente %s (%s)", ticker, navn, feil)
                continue
            if navn == "kurs":
                status.kurs = verdi
            elif navn == "nyheter":
                status.nyheter = verdi or []
            elif navn == "resultat":
                status.resultat = verdi
            else:
                status.neste_resultat = verdi

        if med_fundamentals:
            try:
                status.fundamentals = kilde.hent_fundamentals(ticker)
            except Exception as feil:
                log.warning("%s: klarte ikke hente nøkkeltall (%s)", ticker, feil)

        status.hendelser = finn_hendelser(status)
        statuser.append(status)
        log.info(
            "%s: %s, %d hendelse(r)",
            ticker,
            f"{status.kurs.pris:.2f}".replace(".", ",") if status.kurs and status.kurs.pris else "ingen kurs",
            len(status.hendelser),
        )

    return statuser


def nyheter_siden_for(modus: str) -> date:
    """Hvor langt tilbake vi henter nyheter, gitt rapporttypen."""
    dager = {"daily": 2, "weekly": 8, "monthly": 32}.get(modus, 8)
    return date.today() - timedelta(days=dager)
