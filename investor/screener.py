"""Screener som finner mulige kjøpskandidater blant børsnoterte selskaper.

Arbeidsgangen er bevisst todelt:

1. **Harde kvalitetskrav** (`bestaar_kvalitetskrav`) — absolutte minstekrav.
   Et selskap som ryker her blir *forkastet*, ikke rangert lavere. Dette er
   det som holder penny stocks og uetablerte selskaper helt ute av systemet.
2. **Scoring** (`beregn_score`) — først blant de som består vurderer vi hvor
   attraktive de er, langs verdsettelse, kvalitet, vekst, momentum og utbytte.

Til slutt kreves det at vi klarer å skrive minst to *konkrete, tallfestede*
grunner til kjøp. Klarer vi ikke det, foreslås selskapet ikke — vi vil heller
sende en tom liste enn en vag anbefaling.
"""

from __future__ import annotations

import logging

from . import config
from .kilder.base import Kilde
from .modeller import Fundamentals, Kandidat, Kurs

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Harde kvalitetskrav
# ---------------------------------------------------------------------------


def bestaar_kvalitetskrav(f: Fundamentals, kurs: Kurs | None = None) -> tuple[bool, str]:
    """Sjekker de absolutte minstekravene.

    Returnerer (består, årsak). Årsaken er maskinlesbar (f.eks.
    «forkastet:borsverdi») slik at verifiseringen kan teste hvert enkelt krav.
    """
    # --- Ingen penny stocks, kun etablerte selskaper ---
    if f.borsverdi is None or f.borsverdi < config.MIN_BORSVERDI:
        return False, "forkastet:borsverdi"

    pris = kurs.pris if kurs else None
    if pris is not None and pris < config.MIN_AKSJEKURS:
        return False, "forkastet:aksjekurs"

    if kurs and kurs.snittvolum is not None and kurs.snittvolum < config.MIN_SNITTVOLUM:
        return False, "forkastet:volum"

    # --- Kun hovedbørser: ingen OTC/pink sheets ---
    bors = (f.bors or "").upper()
    if any(forbudt in bors for forbudt in config.FORBUDTE_BORSER):
        return False, "forkastet:bors"

    # --- Dokumentert historikk ---
    if f.aar_med_data < config.MIN_AAR_HISTORIKK:
        return False, "forkastet:historikk"

    # --- Historisk soliditet: lønnsomhet og kontantstrøm over tid ---
    if f.aar_med_overskudd < config.MIN_AAR_MED_OVERSKUDD:
        return False, "forkastet:lonnsomhet"

    if f.aar_med_positiv_fcf < config.MIN_AAR_MED_POSITIV_FCF:
        return False, "forkastet:kontantstrom"

    # --- Lønnsom akkurat nå ---
    if config.KREV_POSITIV_PE and (f.pe is None or f.pe <= 0):
        return False, "forkastet:lonnsomhet"

    # --- Gjeld under kontroll ---
    if (
        f.gjeld_egenkapital is not None
        and f.gjeld_egenkapital > config.MAKS_GJELD_EGENKAPITAL
    ):
        return False, "forkastet:gjeld"

    return True, "ok"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _poeng(verdi: float | None, terskel: str) -> float | None:
    """Gir 0–1 poeng ved å interpolere mellom «bra» og «best».

    Terskelparet kan gå begge veier: for P/E er lavt best, for ROE er høyt
    best. Retningen leses ut av hvilken vei paret peker.
    """
    if verdi is None:
        return None
    par = config.TERSKLER.get(terskel)
    if not par:
        return None
    bra, best = par
    if best >= bra:                      # høyere er bedre
        if verdi <= bra:
            return 0.0
        if verdi >= best:
            return 1.0
        return (verdi - bra) / (best - bra)
    # lavere er bedre
    if verdi >= bra:
        return 0.0
    if verdi <= best:
        return 1.0
    return (bra - verdi) / (bra - best)


def _snitt(poeng: list[float | None]) -> float | None:
    """Snitt av de delpoengene vi faktisk har data for.

    Returnerer None når vi ikke har noe å måle på — da holdes dimensjonen
    utenfor vektingen i stedet for å telle som null.
    """
    gyldige = [p for p in poeng if p is not None]
    return sum(gyldige) / len(gyldige) if gyldige else None


def beregn_delscorer(f: Fundamentals, kurs: Kurs | None) -> dict[str, float]:
    """Regner ut delscore 0–1 per dimensjon.

    Dimensjoner vi mangler data for utelates helt. Det er et poeng: et
    vekstselskap uten utbytte skal ikke straffes for å ikke betale utbytte,
    bare fordi vi ikke har et tall å score på.
    """
    momentum = None
    if kurs and kurs.endring_1aar is not None:
        momentum = _poeng(kurs.endring_1aar / 100, "momentum")

    alle = {
        "verdsettelse": _snitt([
            _poeng(f.pe, "pe"),
            _poeng(f.pb, "pb"),
            _poeng(f.ev_ebitda, "ev_ebitda"),
            _poeng(f.fcf_yield, "fcf_yield"),
        ]),
        "kvalitet": _snitt([
            _poeng(f.roe, "roe"),
            _poeng(f.roic, "roic"),
            _poeng(f.driftsmargin, "driftsmargin"),
            _poeng(f.gjeld_egenkapital, "gjeld_egenkapital"),
        ]),
        "vekst": _snitt([
            _poeng(f.omsetningsvekst, "omsetningsvekst"),
            _poeng(f.eps_vekst, "eps_vekst"),
            _poeng(f.omsetningsvekst_3aar, "omsetningsvekst_3aar"),
        ]),
        "momentum": momentum,
        "utbytte": _poeng(f.utbytte_yield, "utbytte_yield"),
    }
    return {navn: verdi for navn, verdi in alle.items() if verdi is not None}


def beregn_score(delscorer: dict[str, float]) -> int:
    """Vekter delscorene sammen til en samlet score 0–100.

    Vekter kun over dimensjonene vi faktisk har, slik at manglende data verken
    løfter eller senker selskapet kunstig.
    """
    vektsum = sum(
        vekt for navn, vekt in config.SCORE_VEKTER.items() if navn in delscorer
    )
    if not vektsum:
        return 0
    total = sum(
        verdi * config.SCORE_VEKTER.get(navn, 0.0)
        for navn, verdi in delscorer.items()
    )
    return round(total / vektsum * 100)


def prioritet(score: int) -> str:
    """Grovklassifiser scoren, samme tankegang som leadmaskinen."""
    if score >= config.PRIORITET_HOY_MIN:
        return "HØY"
    if score >= config.PRIORITET_MIDDELS_MIN:
        return "MIDDELS"
    return "LAV"


# ---------------------------------------------------------------------------
# Begrunnelser
# ---------------------------------------------------------------------------


def _pst(verdi: float | None, desimaler: int = 1) -> str:
    """Formaterer en andel (0.14) som prosent («14,0 %») med norsk komma."""
    if verdi is None:
        return "–"
    return f"{verdi * 100:.{desimaler}f}".replace(".", ",") + " %"


def _tall(verdi: float | None, desimaler: int = 1) -> str:
    if verdi is None:
        return "–"
    return f"{verdi:.{desimaler}f}".replace(".", ",")


def bygg_grunner(f: Fundamentals, kurs: Kurs | None) -> list[str]:
    """Bygger konkrete, tallfestede grunner til at dette kan være et godt kjøp.

    Hver grunn peker på et faktisk måltall — aldri en generisk vurdering. Bare
    forhold som er tydelig bedre enn middelmådige kvalifiserer, slik at listen
    faktisk betyr noe.
    """
    grunner: list[str] = []

    # Verdsettelse
    if f.pe is not None and 0 < f.pe <= 18:
        grunner.append(f"prises til P/E {_tall(f.pe)}, lavt for et lønnsomt selskap")
    if f.fcf_yield is not None and f.fcf_yield >= 0.05:
        grunner.append(
            f"fri kontantstrøm tilsvarer {_pst(f.fcf_yield)} av børsverdien"
        )
    if f.ev_ebitda is not None and 0 < f.ev_ebitda <= 10:
        grunner.append(f"EV/EBITDA på {_tall(f.ev_ebitda)}")

    # Kvalitet
    if f.roe is not None and f.roe >= 0.15:
        grunner.append(f"egenkapitalavkastning (ROE) på {_pst(f.roe)}")
    if f.roic is not None and f.roic >= 0.12:
        grunner.append(f"avkastning på investert kapital (ROIC) på {_pst(f.roic)}")
    if f.driftsmargin is not None and f.driftsmargin >= 0.15:
        grunner.append(f"driftsmargin på {_pst(f.driftsmargin)}")
    if f.gjeld_egenkapital is not None and f.gjeld_egenkapital <= 0.5:
        grunner.append(
            f"lav gjeldsgrad ({_tall(f.gjeld_egenkapital, 2)} gjeld per krone egenkapital)"
        )

    # Vekst — vektlegg vedvarende vekst framfor ett godt år
    if f.omsetningsvekst_3aar is not None and f.omsetningsvekst_3aar >= 0.07:
        grunner.append(
            f"omsetningen har vokst {_pst(f.omsetningsvekst_3aar)} i året de siste tre årene"
        )
    elif f.omsetningsvekst is not None and f.omsetningsvekst >= 0.10:
        grunner.append(f"omsetningsvekst på {_pst(f.omsetningsvekst)} siste år")
    if f.eps_vekst is not None and f.eps_vekst >= 0.12:
        grunner.append(f"resultat per aksje opp {_pst(f.eps_vekst)}")

    # Historikk — dette er selve «etablert selskap»-argumentet
    if f.aar_med_overskudd >= 8:
        grunner.append(
            f"overskudd i {f.aar_med_overskudd} av de siste {f.aar_med_data} årene"
        )
    if f.aar_med_positiv_fcf >= 7:
        grunner.append(
            f"positiv fri kontantstrøm {f.aar_med_positiv_fcf} år på rad"
        )

    # Utbytte
    if f.utbytte_yield is not None and f.utbytte_yield >= 0.03:
        grunner.append(f"utbytte på {_pst(f.utbytte_yield)}")

    # Timing: rabatt mot toppen uten at driften har sviktet
    if (
        kurs
        and kurs.fra_topp_52u is not None
        and kurs.fra_topp_52u <= -15
        and (f.omsetningsvekst or 0) > 0
    ):
        grunner.append(
            f"kursen ligger {_tall(abs(kurs.fra_topp_52u))} % under 52-ukers topp "
            f"samtidig som omsetningen fortsatt vokser"
        )

    return grunner


# ---------------------------------------------------------------------------
# Selve kjøringen
# ---------------------------------------------------------------------------


def vurder_selskap(
    f: Fundamentals, kurs: Kurs | None
) -> tuple[Kandidat | None, str]:
    """Vurderer ett selskap. Returnerer (kandidat eller None, årsak)."""
    bestaar, arsak = bestaar_kvalitetskrav(f, kurs)
    if not bestaar:
        return None, arsak

    delscorer = beregn_delscorer(f, kurs)
    score = beregn_score(delscorer)
    if score < config.SCORE_MIN_ANBEFALING:
        return None, "forkastet:score"

    grunner = bygg_grunner(f, kurs)
    if len(grunner) < config.MIN_ANTALL_GRUNNER:
        # Vi klarer ikke å begrunne kjøpet med tall — da foreslår vi det ikke.
        return None, "forkastet:for_fa_grunner"

    return (
        Kandidat(
            ticker=f.ticker,
            navn=f.navn,
            score=score,
            prioritet=prioritet(score),
            fundamentals=f,
            grunner=grunner,
            delscorer=delscorer,
            kurs=kurs,
        ),
        "ok",
    )


def finn_kandidater(
    kilde: Kilde,
    *,
    ekskluder: set[str] | None = None,
    maks: int | None = None,
) -> tuple[list[Kandidat], dict[str, int]]:
    """Kjører hele screeningen og returnerer (kandidater, statistikk).

    Statistikken forteller hvor mange som ble forkastet av hvilket krav — den
    logges, så det er mulig å se hvorfor en uke ga null forslag.
    """
    ekskluder = {t.upper() for t in (ekskluder or set())}
    univers = [t for t in kilde.hent_univers() if t.upper() not in ekskluder]
    log.info("Screener %d selskaper", len(univers))

    kandidater: list[Kandidat] = []
    statistikk: dict[str, int] = {"vurdert": 0}

    for ticker in univers:
        f = kilde.hent_fundamentals(ticker)
        if not f:
            statistikk["forkastet:manglende_data"] = (
                statistikk.get("forkastet:manglende_data", 0) + 1
            )
            continue
        statistikk["vurdert"] += 1

        # Kurs trengs til volum-, kurs- og momentumkravene.
        kurs = kilde.hent_kurs(ticker)
        kandidat, arsak = vurder_selskap(f, kurs)
        if kandidat:
            kandidater.append(kandidat)
        else:
            statistikk[arsak] = statistikk.get(arsak, 0) + 1

    kandidater.sort(key=lambda k: k.score, reverse=True)
    if maks:
        kandidater = kandidater[:maks]

    log.info(
        "Screening ferdig: %d kandidater av %d vurderte (%s)",
        len(kandidater),
        statistikk["vurdert"],
        ", ".join(
            f"{navn.removeprefix('forkastet:')}={antall}"
            for navn, antall in sorted(statistikk.items())
            if navn.startswith("forkastet:")
        )
        or "ingen forkastet",
    )
    return kandidater, statistikk
