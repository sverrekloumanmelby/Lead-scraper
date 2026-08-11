"""Datamodeller for investeringsassistenten.

Alle kilder (FMP, Yahoo, fixtures) normaliseres til disse klassene, slik at
resten av systemet er uavhengig av hvilken leverandør dataene kom fra.

Feltene er bevisst `| None`: gratis datakilder mangler ofte enkeltverdier, og
vi vil heller mangle ett nøkkeltall enn å kaste hele selskapet. Screeneren
avgjør selv hva som er godt nok (se `screener.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Kurs:
    """Dagsaktuell kurs med endringer over ulike perioder (prosent)."""

    ticker: str
    pris: float | None = None
    valuta: str = "USD"
    endring_1d: float | None = None
    endring_1u: float | None = None
    endring_1m: float | None = None
    endring_ytd: float | None = None
    endring_1aar: float | None = None
    fra_topp_52u: float | None = None   # negativ = under 52-ukers topp
    volum: float | None = None
    snittvolum: float | None = None


@dataclass
class Fundamentals:
    """Nøkkeltall for ett selskap.

    Brukes både til porteføljerapporten og til screeningen. `aar_med_data`
    forteller hvor mange årsregnskap vi faktisk har sett — screeneren krever
    et minimum før et selskap i det hele tatt kan foreslås.
    """

    ticker: str
    navn: str = ""
    borsverdi: float | None = None
    valuta: str = "USD"
    bors: str = ""
    sektor: str = ""
    bransje: str = ""
    land: str = ""

    # Verdsettelse
    pe: float | None = None
    forward_pe: float | None = None
    pb: float | None = None
    ev_ebitda: float | None = None
    fcf_yield: float | None = None       # fri kontantstrøm / børsverdi (andel, ikke %)

    # Kvalitet
    roe: float | None = None
    roic: float | None = None
    driftsmargin: float | None = None
    bruttomargin: float | None = None
    gjeld_egenkapital: float | None = None
    rentedekning: float | None = None

    # Vekst
    omsetningsvekst: float | None = None       # siste år
    eps_vekst: float | None = None
    omsetningsvekst_3aar: float | None = None  # snittlig årlig, siste 3 år

    # Utbytte
    utbytte_yield: float | None = None
    utbytte_aar_pa_rad: int | None = None

    # Historikk-kvalitet (grunnlag for de harde kravene)
    aar_med_data: int = 0
    aar_med_overskudd: int = 0
    aar_med_positiv_fcf: int = 0

    def mangler(self) -> list[str]:
        """Lister nøkkeltall som mangler — brukes til logging/diagnose."""
        viktige = ("borsverdi", "pe", "roe", "omsetningsvekst", "fcf_yield")
        return [f for f in viktige if getattr(self, f) is None]


@dataclass
class Nyhet:
    """En nyhetssak knyttet til en ticker."""

    ticker: str
    tittel: str
    url: str = ""
    kilde: str = ""
    publisert: datetime | None = None
    sammendrag: str = ""


@dataclass
class Resultat:
    """Kvartalsresultat — faktiske tall og/eller planlagt rapporteringsdato."""

    ticker: str
    dato: date | None = None
    er_bekreftet: bool = False
    periode: str = ""              # f.eks. "Q3 2025"
    omsetning: float | None = None
    omsetning_i_fjor: float | None = None
    eps: float | None = None
    eps_i_fjor: float | None = None
    eps_forventet: float | None = None
    driftsresultat: float | None = None
    driftsmargin: float | None = None
    valuta: str = "USD"

    @property
    def eps_overraskelse(self) -> float | None:
        """Hvor mye EPS avvek fra analytikerforventning, i prosent."""
        if self.eps is None or not self.eps_forventet:
            return None
        return (self.eps - self.eps_forventet) / abs(self.eps_forventet) * 100

    @property
    def omsetningsvekst(self) -> float | None:
        """Vekst mot samme kvartal i fjor, i prosent."""
        if self.omsetning is None or not self.omsetning_i_fjor:
            return None
        return (self.omsetning - self.omsetning_i_fjor) / abs(self.omsetning_i_fjor) * 100


@dataclass
class Hendelse:
    """En ting som har skjedd og som er verdt å nevne i en e-post.

    `viktighet` styrer hvilke rapporter hendelsen kommer med i: den daglige
    e-posten tar kun med det som er genuint relevant (se config.VIKTIGHET_*).
    """

    ticker: str
    type: str          # "resultat" | "kursbevegelse" | "utbytte" | "analytiker" | "nyhet"
    tittel: str
    detalj: str = ""
    viktighet: int = 1     # 1 = lav, 2 = middels, 3 = høy
    url: str = ""


@dataclass
class Beholdning:
    """En posisjon fra portfolio.json."""

    ticker: str
    navn: str = ""
    antall: float | None = None
    kostpris: float | None = None
    valuta: str = ""
    notat: str = ""

    def avkastning(self, kurs: Kurs) -> tuple[float, float] | None:
        """Returnerer (kroner/valuta, prosent) urealisert gevinst, om mulig."""
        if self.antall is None or self.kostpris is None or kurs.pris is None:
            return None
        kost = self.antall * self.kostpris
        if kost == 0:
            return None
        verdi = self.antall * kurs.pris
        return verdi - kost, (verdi - kost) / kost * 100


@dataclass
class Kandidat:
    """Et selskap screeneren har vurdert som mulig kjøp.

    `grunner` er de konkrete, tallfestede begrunnelsene. Kandidater uten nok
    slike grunner slippes aldri gjennom til e-posten — se `screener.py`.
    """

    ticker: str
    navn: str
    score: int
    prioritet: str
    fundamentals: Fundamentals
    grunner: list[str] = field(default_factory=list)
    delscorer: dict[str, float] = field(default_factory=dict)
    kurs: Kurs | None = None
