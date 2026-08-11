"""Bygger e-postrapportene.

Tre detaljnivåer, fra samme datagrunnlag:

* **daily**   — kort. Kun hendelser over `config.DAGLIG_MIN_VIKTIGHET`. Er det
  ingenting, sier e-posten det rett ut i stedet for å fylle plass.
* **weekly**  — porteføljetabell, ukens hendelser og nye kandidater.
* **monthly** — måneden samlet, selskapenes mål framover, utvidet kandidatliste
  og den lærende seksjonen om kvartalsrapporter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config, laering, state
from .modeller import Kandidat

log = logging.getLogger(__name__)

MALKATALOG = Path(__file__).resolve().parent / "templates"

MANEDER = [
    "januar", "februar", "mars", "april", "mai", "juni",
    "juli", "august", "september", "oktober", "november", "desember",
]


@dataclass
class Rapport:
    """Ferdig rapport, klar til å sendes eller skrives til fil."""

    modus: str
    emne: str
    html: str
    tekst: str
    har_innhold: bool = True
    antall_hendelser: int = 0
    antall_kandidater: int = 0


# ---------------------------------------------------------------------------
# Formatering (brukes både i maler og i tekstversjonen)
# ---------------------------------------------------------------------------


def pst(verdi: float | None, desimaler: int = 1, fortegn: bool = True) -> str:
    """Prosent med norsk komma og eventuelt fortegn."""
    if verdi is None:
        return "–"
    tegn = "+" if fortegn and verdi > 0 else ""
    return f"{tegn}{verdi:.{desimaler}f}".replace(".", ",") + " %"


def andel(verdi: float | None, desimaler: int = 1) -> str:
    """Andel (0,14) vist som prosent."""
    if verdi is None:
        return "–"
    return f"{verdi * 100:.{desimaler}f}".replace(".", ",") + " %"


def kr(verdi: float | None, valuta: str = "", desimaler: int = 2) -> str:
    if verdi is None:
        return "–"
    tekst = f"{verdi:,.{desimaler}f}".replace(",", " ").replace(".", ",")
    return f"{tekst} {valuta}".strip()


def stort_tall(verdi: float | None, valuta: str = "USD") -> str:
    if verdi is None:
        return "–"
    for grense, endelse in ((1e12, "bill."), (1e9, "mrd"), (1e6, "mill.")):
        if abs(verdi) >= grense:
            return f"{verdi / grense:.1f} {endelse} {valuta}".replace(".", ",")
    return kr(verdi, valuta, 0)


def farge(verdi: float | None) -> str:
    """Fargeklasse for opp/ned, brukt i HTML-malene."""
    if verdi is None:
        return "noytral"
    return "opp" if verdi > 0 else ("ned" if verdi < 0 else "noytral")


def _miljo() -> Environment:
    env = Environment(
        loader=FileSystemLoader(MALKATALOG),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(
        pst=pst, andel=andel, kr=kr, stort_tall=stort_tall, farge=farge
    )
    return env


# ---------------------------------------------------------------------------
# Sammendrag
# ---------------------------------------------------------------------------


def _portefoljesammendrag(statuser: list) -> dict:
    """Aggregerte tall for hele porteføljen."""
    med_kurs = [s for s in statuser if s.kurs and s.kurs.pris is not None]
    endringer = [s.kurs.endring_1d for s in med_kurs if s.kurs.endring_1d is not None]

    verdi = kostnad = 0.0
    har_verdier = False
    for s in statuser:
        b, k = s.beholdning, s.kurs
        if b.antall and b.kostpris and k and k.pris:
            verdi += b.antall * k.pris
            kostnad += b.antall * b.kostpris
            har_verdier = True

    sammendrag = {
        "antall": len(statuser),
        "snitt_endring_1d": sum(endringer) / len(endringer) if endringer else None,
        "beste": max(med_kurs, key=lambda s: s.kurs.endring_1d or -999, default=None),
        "svakeste": min(med_kurs, key=lambda s: s.kurs.endring_1d or 999, default=None),
        "har_verdier": har_verdier,
    }
    if har_verdier and kostnad:
        sammendrag.update(
            verdi=verdi,
            kostnad=kostnad,
            gevinst=verdi - kostnad,
            gevinst_pst=(verdi - kostnad) / kostnad * 100,
        )
    return sammendrag


def _maal_framover(status) -> list[str]:
    """Hva selskapet selv peker mot framover, utledet av tallene vi har.

    Vi finner ikke på ledelsens uttalelser. Dette er observerbare forhold som
    er verdt å følge i neste kvartal.
    """
    punkter: list[str] = []
    f = getattr(status, "fundamentals", None)
    res = status.resultat

    if res and res.omsetningsvekst is not None:
        retning = "vekst" if res.omsetningsvekst >= 0 else "fall"
        punkter.append(
            f"Omsetningen viste {retning} på {pst(res.omsetningsvekst)} i "
            f"{res.periode or 'siste kvartal'} — følg om trenden holder."
        )
    if res and res.driftsmargin is not None:
        punkter.append(
            f"Driftsmarginen ligger på {andel(res.driftsmargin)}. Fallende "
            "margin over to kvartaler er et varsel verdt å undersøke."
        )
    if f is not None:
        if getattr(f, "omsetningsvekst_3aar", None) is not None:
            punkter.append(
                f"Snittvekst siste tre år: {andel(f.omsetningsvekst_3aar)}."
            )
        if getattr(f, "gjeld_egenkapital", None) is not None:
            punkter.append(
                f"Gjeldsgrad {f.gjeld_egenkapital:.2f}".replace(".", ",")
                + " gjeld per krone egenkapital."
            )
    if status.neste_resultat:
        punkter.append(
            f"Neste kvartalstall ventes {status.neste_resultat.strftime('%d.%m.%Y')}."
        )
    return punkter


# ---------------------------------------------------------------------------
# Bygging
# ---------------------------------------------------------------------------


def bygg_rapport(
    modus: str,
    statuser: list,
    kandidater: list[Kandidat],
    *,
    historikk: dict | None = None,
    screener_statistikk: dict | None = None,
) -> Rapport:
    """Bygger rapporten for gitt modus."""
    historikk = historikk or {"snapshots": {}}
    i_dag = date.today()

    min_viktighet = (
        config.DAGLIG_MIN_VIKTIGHET if modus == "daily" else config.VIKTIGHET_LAV
    )
    maks_nyheter = {
        "daily": config.MAKS_NYHETER_DAGLIG,
        "weekly": config.MAKS_NYHETER_UKENTLIG,
        "monthly": config.MAKS_NYHETER_MANEDLIG,
    }.get(modus, config.MAKS_NYHETER_UKENTLIG)

    # Hendelser filtrert etter modus.
    hendelser_per_selskap = []
    totalt_hendelser = 0
    for s in statuser:
        traff = s.viktigste_hendelser(min_viktighet)
        totalt_hendelser += len(traff)
        hendelser_per_selskap.append(
            {
                "status": s,
                "hendelser": traff,
                "nyheter": s.nyheter[:maks_nyheter],
                "endring_siden_forrige": state.kurs_siden_forrige(
                    historikk, modus, s.ticker, s.kurs.pris if s.kurs else None
                ),
                "maal": _maal_framover(s) if modus == "monthly" else [],
            }
        )

    nye = state.nye_kandidater(historikk, modus, kandidater) if kandidater else set()

    kontekst = {
        "modus": modus,
        "tittel": config.RAPPORT_TITTEL.get(modus, "Investeringsrapport"),
        "dato": i_dag,
        "dato_tekst": f"{i_dag.day}. {MANEDER[i_dag.month - 1]} {i_dag.year}",
        "maned_tekst": f"{MANEDER[i_dag.month - 1]} {i_dag.year}",
        "forrige_dato": state.dato_forrige(historikk, modus),
        "selskaper": hendelser_per_selskap,
        "sammendrag": _portefoljesammendrag(statuser),
        "kandidater": kandidater,
        "nye_kandidater": nye,
        "totalt_hendelser": totalt_hendelser,
        "screener_kjort": screener_statistikk is not None,
        "screener_statistikk": screener_statistikk or {},
        "min_grunner": config.MIN_ANTALL_GRUNNER,
        "score_terskel": config.SCORE_MIN_ANBEFALING,
    }

    # Månedens lærende seksjon.
    if modus == "monthly":
        valgt = laering.velg_selskap(statuser, i_dag)
        kontekst["laering"] = laering.bygg(valgt) if valgt else None

    env = _miljo()
    html = env.get_template(f"{modus}.html.j2").render(**kontekst)
    tekst = env.get_template(f"{modus}.txt.j2").render(**kontekst)

    return Rapport(
        modus=modus,
        emne=_emne(modus, kontekst),
        html=html,
        tekst=tekst,
        har_innhold=bool(totalt_hendelser or kandidater or modus != "daily"),
        antall_hendelser=totalt_hendelser,
        antall_kandidater=len(kandidater),
    )


def _emne(modus: str, kontekst: dict) -> str:
    """Emnefelt som sier hva som faktisk er i e-posten."""
    dato = kontekst["dato"]
    if modus == "daily":
        antall = kontekst["totalt_hendelser"]
        if not antall:
            return f"Portefølje {dato.strftime('%d.%m')} — rolig dag"
        return f"Portefølje {dato.strftime('%d.%m')} — {antall} ting å vite om"
    if modus == "weekly":
        deler = [f"Ukesrapport {dato.strftime('%d.%m')}"]
        n = kontekst["antall_kandidater"] if "antall_kandidater" in kontekst else len(
            kontekst["kandidater"]
        )
        deler.append(f"{n} nye kandidater" if n else "ingen nye kandidater")
        return " — ".join(deler)
    return f"Månedsrapport {kontekst['maned_tekst']}"


def skriv_til_fil(rapport: Rapport, katalog: str | Path) -> Path:
    """Skriver rapporten til disk (brukt av --dry-run)."""
    katalog = Path(katalog)
    katalog.mkdir(parents=True, exist_ok=True)
    html_sti = katalog / f"rapport-{rapport.modus}.html"
    html_sti.write_text(rapport.html, encoding="utf-8")
    (katalog / f"rapport-{rapport.modus}.txt").write_text(
        rapport.tekst, encoding="utf-8"
    )
    return html_sti
