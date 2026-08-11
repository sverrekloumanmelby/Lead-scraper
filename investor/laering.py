"""Den lærende delen av månedsrapporten.

Formålet er å bygge forståelse for hvordan man leser en kvartalsrapport, med
tall fra et selskap du faktisk eier. Hver måned tas ett selskap for seg, og
begrepene forklares mot selskapets egne tall — det sitter bedre enn en generell
innføring.

Selskapet roterer måned for måned, slik at du over tid går gjennom hele
porteføljen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from . import config


@dataclass
class Nokkeltall:
    """Ett begrep forklart mot et konkret tall."""

    navn: str
    verdi: str
    forklaring: str
    tolkning: str = ""


@dataclass
class Laering:
    """Månedens gjennomgang av ett selskaps kvartalstall."""

    ticker: str
    navn: str
    periode: str
    tema: str
    innledning: str
    nokkeltall: list[Nokkeltall] = field(default_factory=list)
    huskeregel: str = ""
    neste_steg: str = ""


def _desimal(verdi: float, desimaler: int = 1) -> str:
    """Tall med norsk desimalkomma og mellomrom som tusenskille.

    Egen funksjon fordi vi ellers må gjøre punktum-til-komma på ferdige
    setninger, noe som fort ødelegger forkortelser som «mill.».
    """
    tekst = f"{verdi:,.{desimaler}f}"          # 1,234.5
    return tekst.replace(",", " ").replace(".", ",")


def _mill(verdi: float | None, valuta: str = "USD") -> str:
    """Formaterer store tall lesbart (millioner/milliarder)."""
    if verdi is None:
        return "–"
    for grense, endelse in ((1e9, "mrd"), (1e6, "mill.")):
        if abs(verdi) >= grense:
            return f"{_desimal(verdi / grense, 1)} {endelse} {valuta}"
    return f"{_desimal(verdi, 0)} {valuta}"


def _pst(andel: float | None, desimaler: int = 1, fortegn: bool = False) -> str:
    """Formaterer en *andel* (0,17) som prosent («17,0 %»)."""
    if andel is None:
        return "–"
    tegn = "+" if fortegn and andel > 0 else ""
    return f"{tegn}{_desimal(andel * 100, desimaler)} %"


def _pst_direkte(verdi: float | None, desimaler: int = 1, fortegn: bool = False) -> str:
    """Formaterer et tall som allerede *er* prosent (18,8 -> «18,8 %»)."""
    if verdi is None:
        return "–"
    tegn = "+" if fortegn and verdi > 0 else ""
    return f"{tegn}{_desimal(verdi, desimaler)} %"


def velg_selskap(statuser: list, i_dag: date | None = None):
    """Velger månedens selskap.

    Roterer på månedsnummer, slik at porteføljen gås gjennom over tid. Vi
    prioriterer selskaper vi faktisk har kvartalstall for.
    """
    if not statuser:
        return None
    med_tall = [s for s in statuser if s.resultat and s.resultat.omsetning]
    aktuelle = med_tall or statuser
    if not config.LAERING_ROTERER:
        return aktuelle[0]
    maned = (i_dag or date.today()).month
    return aktuelle[(maned - 1) % len(aktuelle)]


def bygg(status) -> Laering | None:
    """Bygger månedens lærende seksjon for ett selskap.

    Returnerer None hvis vi ikke har nok tall til å si noe meningsfullt — vi
    forklarer heller ingenting enn å forklare tomme felt.
    """
    res = getattr(status, "resultat", None)
    if not res or res.omsetning is None:
        return None

    valuta = res.valuta or "USD"
    tall: list[Nokkeltall] = []

    # --- Omsetning ---
    vekst = res.omsetningsvekst
    tall.append(
        Nokkeltall(
            navn="Omsetning (revenue / topplinje)",
            verdi=_mill(res.omsetning, valuta),
            forklaring=(
                "Alt selskapet solgte for i kvartalet, før noen kostnader er "
                "trukket fra. Kalles «topplinjen» fordi den står øverst i "
                "resultatregnskapet."
            ),
            tolkning=(
                f"Mot samme kvartal i fjor er dette "
                f"{_pst_direkte(vekst, fortegn=True)}. "
                "Sammenlign alltid med samme kvartal året før, ikke forrige "
                "kvartal — de fleste selskaper har sesongsvingninger."
                if vekst is not None
                else "Vi mangler fjorårstallet, så veksten kan ikke regnes ut her."
            ),
        )
    )

    # --- Driftsresultat og margin ---
    if res.driftsresultat is not None:
        tall.append(
            Nokkeltall(
                navn="Driftsresultat (operating income / EBIT)",
                verdi=_mill(res.driftsresultat, valuta),
                forklaring=(
                    "Det som er igjen av omsetningen etter driftskostnader, men "
                    "før renter og skatt. Viser om selve virksomheten tjener "
                    "penger, uavhengig av hvordan den er finansiert."
                ),
                tolkning=(
                    f"Driftsmarginen er {_pst(res.driftsmargin)} — altså at "
                    f"{_pst(res.driftsmargin)} av hver krone i omsetning blir "
                    "igjen som driftsresultat. Følg med på om marginen holder "
                    "seg når omsetningen vokser: økende omsetning med fallende "
                    "margin betyr at veksten blir kjøpt dyrt."
                    if res.driftsmargin is not None
                    else ""
                ),
            )
        )

    # --- EPS ---
    if res.eps is not None:
        eps_tolkning = []
        if res.eps_i_fjor is not None:
            endring = (res.eps - res.eps_i_fjor) / abs(res.eps_i_fjor) * 100
            eps_tolkning.append(
                f"Mot samme kvartal i fjor ({_desimal(res.eps_i_fjor, 2)}) er det "
                f"{_pst_direkte(endring, fortegn=True)}."
            )
        if res.eps_overraskelse is not None:
            over = "over" if res.eps_overraskelse >= 0 else "under"
            eps_tolkning.append(
                f"Analytikerne ventet {_desimal(res.eps_forventet, 2)}, så "
                f"resultatet kom {_pst_direkte(abs(res.eps_overraskelse))} {over} "
                "forventning. Det er ofte dette som flytter kursen på "
                "resultatdagen — ikke tallet i seg selv, men avviket fra det "
                "markedet allerede hadde priset inn."
            )
        tall.append(
            Nokkeltall(
                navn="Resultat per aksje (EPS)",
                verdi=f"{_desimal(res.eps, 2)} {valuta}",
                forklaring=(
                    "Overskuddet delt på antall aksjer. Dette er tallet «per "
                    "aksje» du eier, og det som oftest sammenlignes med "
                    "analytikernes forventninger."
                ),
                tolkning=" ".join(eps_tolkning),
            )
        )

    # --- Fundamentals-kontekst hvis vi har den ---
    f = getattr(status, "fundamentals", None)
    if f is not None and getattr(f, "pe", None):
        tall.append(
            Nokkeltall(
                navn="P/E (pris delt på fortjeneste)",
                verdi=_desimal(f.pe, 1),
                forklaring=(
                    "Hvor mange års overskudd du betaler for aksjen ved dagens "
                    "kurs. Lav P/E kan bety at aksjen er billig — eller at "
                    "markedet venter at overskuddet skal falle."
                ),
                tolkning=(
                    "P/E sier lite alene. Den er nyttig sammenlignet med "
                    "selskapets egen historikk og med konkurrenter i samme "
                    "bransje."
                ),
            )
        )

    return Laering(
        ticker=status.ticker,
        navn=status.navn,
        periode=res.periode or "siste kvartal",
        tema="Slik leser du en kvartalsrapport",
        innledning=(
            f"Denne måneden bruker vi {status.navn} som eksempel. Tallene under "
            "er selskapets faktiske kvartalstall — poenget er å kjenne igjen de "
            "samme postene neste gang du åpner en rapport selv."
        ),
        nokkeltall=tall,
        huskeregel=(
            "Rekkefølgen i et resultatregnskap er alltid den samme: omsetning "
            "øverst, så trekkes kostnadene fra nedover, til overskuddet står "
            "nederst. Derfor heter det topplinje og bunnlinje. Les ovenfra og "
            "ned, og spør ved hver linje: hva ble trukket fra her, og hvorfor?"
        ),
        neste_steg=(
            "Neste gang dette selskapet rapporterer: se om veksten i omsetning "
            "holder seg, og om driftsmarginen er stabil. To kvartaler på rad med "
            "fallende margin er et signal verdt å undersøke nærmere."
        ),
    )
