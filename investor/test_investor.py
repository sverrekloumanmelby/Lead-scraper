"""Tester for investeringsassistenten.

Kjøres uten rammeverk: `python -m investor.test_investor`.

Hovedvekten ligger på at de harde kvalitetskravene faktisk *forkaster*
selskaper, og at ingen kandidat slipper gjennom uten tallfestet begrunnelse.
Det er kravene som avgjør om systemet er til å stole på.
"""

from __future__ import annotations

import sys
from datetime import date

from . import config, laering, monitor, report, screener, state
from .kilder.fixtures import SELSKAPER, FixtureKilde
from .modeller import Beholdning, Fundamentals, Kurs

FEIL: list[str] = []


def sjekk(betingelse: bool, melding: str) -> None:
    if betingelse:
        print(f"  ok    {melding}")
    else:
        print(f"  FEIL  {melding}")
        FEIL.append(melding)


def _solid() -> Fundamentals:
    """Et selskap som består alle de harde kravene."""
    return Fundamentals(
        ticker="TEST", navn="Testselskap", borsverdi=10e9, bors="NYSE",
        pe=15.0, pb=2.0, ev_ebitda=9.0, fcf_yield=0.06, roe=0.20, roic=0.15,
        driftsmargin=0.18, gjeld_egenkapital=0.5, omsetningsvekst=0.10,
        eps_vekst=0.12, omsetningsvekst_3aar=0.09, utbytte_yield=0.03,
        aar_med_data=10, aar_med_overskudd=9, aar_med_positiv_fcf=8,
    )


def _kurs(pris: float = 50.0, snittvolum: float = 1_000_000) -> Kurs:
    return Kurs(ticker="TEST", pris=pris, snittvolum=snittvolum, endring_1aar=8.0)


# ---------------------------------------------------------------------------


def test_harde_krav_forkaster() -> None:
    """Hvert enkelt krav må kunne forkaste et ellers solid selskap."""
    print("\nHarde kvalitetskrav")

    sjekk(screener.bestaar_kvalitetskrav(_solid(), _kurs())[0],
          "et solid selskap består")

    f = _solid(); f.borsverdi = 100e6
    sjekk(screener.bestaar_kvalitetskrav(f, _kurs())[1] == "forkastet:borsverdi",
          "for lav børsverdi forkastes (penny stock)")

    sjekk(screener.bestaar_kvalitetskrav(_solid(), _kurs(pris=2.0))[1]
          == "forkastet:aksjekurs",
          "for lav aksjekurs forkastes (penny stock)")

    sjekk(screener.bestaar_kvalitetskrav(_solid(), _kurs(snittvolum=1000))[1]
          == "forkastet:volum",
          "for lavt handelsvolum forkastes")

    f = _solid(); f.bors = "OTC"
    sjekk(screener.bestaar_kvalitetskrav(f, _kurs())[1] == "forkastet:bors",
          "OTC-notering forkastes")

    f = _solid(); f.aar_med_data = 2
    sjekk(screener.bestaar_kvalitetskrav(f, _kurs())[1] == "forkastet:historikk",
          "for kort historikk forkastes")

    f = _solid(); f.aar_med_overskudd = 1
    sjekk(screener.bestaar_kvalitetskrav(f, _kurs())[1] == "forkastet:lonnsomhet",
          "for få år med overskudd forkastes")

    f = _solid(); f.aar_med_positiv_fcf = 0
    sjekk(screener.bestaar_kvalitetskrav(f, _kurs())[1] == "forkastet:kontantstrom",
          "manglende fri kontantstrøm forkastes")

    f = _solid(); f.gjeld_egenkapital = 5.0
    sjekk(screener.bestaar_kvalitetskrav(f, _kurs())[1] == "forkastet:gjeld",
          "for høy gjeld forkastes")

    f = _solid(); f.pe = -3.0
    sjekk(screener.bestaar_kvalitetskrav(f, _kurs())[1] == "forkastet:lonnsomhet",
          "negativ P/E forkastes")


def test_fixtures_forventninger() -> None:
    """Fixtures-universet skal falle ut nøyaktig slik det er merket."""
    print("\nForventet utfall for hele fixtures-universet")
    kilde = FixtureKilde()
    for ticker, data in SELSKAPER.items():
        forventet = data.get("forventet")
        if not forventet:
            continue
        kandidat, arsak = screener.vurder_selskap(
            kilde.hent_fundamentals(ticker), kilde.hent_kurs(ticker)
        )
        faktisk = "kandidat" if kandidat else arsak
        sjekk(faktisk == forventet, f"{ticker}: {faktisk} (forventet {forventet})")


def test_krever_tallfestet_begrunnelse() -> None:
    """Ingen kandidat uten minst to konkrete grunner."""
    print("\nKrav om tallfestet begrunnelse")

    kilde = FixtureKilde()
    kandidater, _ = screener.finn_kandidater(kilde)
    sjekk(bool(kandidater), "screeneren finner kandidater i fixtures")
    for k in kandidater:
        sjekk(len(k.grunner) >= config.MIN_ANTALL_GRUNNER,
              f"{k.ticker} har {len(k.grunner)} grunner (krav: "
              f"{config.MIN_ANTALL_GRUNNER})")
        sjekk(all(any(tegn.isdigit() for tegn in g) for g in k.grunner),
              f"{k.ticker}: alle grunner inneholder tall")

    # Et selskap som består kravene, men som vi ikke klarer å begrunne.
    tynn = _solid()
    for felt in ("pe", "fcf_yield", "ev_ebitda", "roe", "roic", "driftsmargin",
                 "gjeld_egenkapital", "omsetningsvekst", "omsetningsvekst_3aar",
                 "eps_vekst", "utbytte_yield"):
        setattr(tynn, felt, None)
    tynn.pe = 25.0                      # lønnsom, men ikke bemerkelsesverdig
    tynn.aar_med_overskudd = 5
    tynn.aar_med_positiv_fcf = 4
    grunner = screener.bygg_grunner(tynn, _kurs())
    sjekk(len(grunner) < config.MIN_ANTALL_GRUNNER,
          "et selskap uten tall å vise til får for få grunner")
    kandidat, arsak = screener.vurder_selskap(tynn, _kurs())
    sjekk(kandidat is None, f"…og foreslås derfor ikke ({arsak})")


def test_ingen_kandidater_ved_hoy_terskel() -> None:
    """Med urimelig høy terskel skal listen bli tom, ikke fylles opp."""
    print("\nTom liste framfor svake forslag")
    original = config.SCORE_MIN_ANBEFALING
    try:
        config.SCORE_MIN_ANBEFALING = 99
        kandidater, _ = screener.finn_kandidater(FixtureKilde())
        sjekk(kandidater == [], "ingen kandidater slipper gjennom terskel 99")

        statuser = monitor.hent_status(FixtureKilde(), [Beholdning("MSFT", "Microsoft")])
        rapport = report.bygg_rapport(
            "weekly", statuser, kandidater, screener_statistikk={"vurdert": 9}
        )
        sjekk("Ingen kandidater denne uken" in rapport.html,
              "rapporten sier eksplisitt at det ikke er kandidater")
        sjekk("INGEN KANDIDATER DENNE UKEN" in rapport.tekst,
              "…også i ren tekst")
    finally:
        config.SCORE_MIN_ANBEFALING = original


def test_score_utelater_manglende_data() -> None:
    """Manglende dimensjon skal ikke telle som null."""
    print("\nScoring med manglende data")
    f = _solid(); f.utbytte_yield = None      # betaler ikke utbytte
    delscorer = screener.beregn_delscorer(f, _kurs())
    sjekk("utbytte" not in delscorer, "dimensjon uten data utelates")

    med, uten = _solid(), _solid()
    uten.utbytte_yield = None
    med.utbytte_yield = 0.0
    sjekk(screener.beregn_score(screener.beregn_delscorer(uten, _kurs()))
          > screener.beregn_score(screener.beregn_delscorer(med, _kurs())),
          "manglende utbytte straffes ikke som utbytte på null")


def test_hendelser() -> None:
    """Hendelsesdeteksjon og hva som havner i den daglige e-posten."""
    print("\nHendelsesdeteksjon")
    kilde = FixtureKilde()
    statuser = monitor.hent_status(
        kilde, [Beholdning("VRT", "Vertiv"), Beholdning("MOWI.OL", "Mowi")]
    )
    vrt = next(s for s in statuser if s.ticker == "VRT")

    kurshendelser = [h for h in vrt.hendelser if h.type == "kursbevegelse"]
    sjekk(bool(kurshendelser), "stort kursfall gir en hendelse")
    sjekk(kurshendelser[0].viktighet == config.VIKTIGHET_HOY,
          "fall på 7,3 % regnes som viktig")
    sjekk("+" not in kurshendelser[0].tittel,
          "retningen står i teksten uten motstridende fortegn")

    mowi = next(s for s in statuser if s.ticker == "MOWI.OL")
    sjekk(not mowi.viktigste_hendelser(config.DAGLIG_MIN_VIKTIGHET),
          "rolig selskap gir ingen hendelser i daglig rapport")


def test_rapporter_bygges() -> None:
    """Alle tre modus skal bygge både HTML og tekst."""
    print("\nRapportbygging")
    kilde = FixtureKilde()
    beholdninger = [Beholdning("MSFT", "Microsoft"), Beholdning("VRT", "Vertiv")]
    statuser = monitor.hent_status(kilde, beholdninger, med_fundamentals=True)
    kandidater, statistikk = screener.finn_kandidater(kilde)

    for modus in ("daily", "weekly", "monthly"):
        rapport = report.bygg_rapport(
            modus, statuser, kandidater, screener_statistikk=statistikk
        )
        sjekk(len(rapport.html) > 500, f"{modus}: HTML bygget")
        sjekk(len(rapport.tekst) > 200, f"{modus}: tekst bygget")
        sjekk(bool(rapport.emne), f"{modus}: emnefelt satt")
        sjekk("{{" not in rapport.html and "{%" not in rapport.html,
              f"{modus}: ingen ubehandlede maluttrykk")


def test_daglig_er_kort() -> None:
    """Den daglige rapporten skal filtrere bort uviktige hendelser."""
    print("\nDaglig rapport er selektiv")
    kilde = FixtureKilde()
    statuser = monitor.hent_status(kilde, [Beholdning("MOWI.OL", "Mowi")])
    daglig = report.bygg_rapport("daily", statuser, [])
    ukentlig = report.bygg_rapport("weekly", statuser, [])
    sjekk(daglig.antall_hendelser <= ukentlig.antall_hendelser,
          "daglig tar med færre eller like mange hendelser som ukentlig")
    sjekk("Rolig dag" in daglig.html or daglig.antall_hendelser > 0,
          "stille dag formuleres eksplisitt")


def test_laering() -> None:
    """Læringsseksjonen skal ha riktige tall og lesbar formatering."""
    print("\nLærende seksjon")
    kilde = FixtureKilde()
    statuser = monitor.hent_status(
        kilde, [Beholdning("VRT", "Vertiv")], med_fundamentals=True
    )
    laer = laering.bygg(statuser[0])
    sjekk(laer is not None, "bygges når vi har kvartalstall")
    sjekk(len(laer.nokkeltall) >= 3, "forklarer flere nøkkeltall")

    margin = next((n for n in laer.nokkeltall if "Driftsresultat" in n.navn), None)
    sjekk(margin is not None and "17,0 %" in margin.tolkning,
          "driftsmargin vises som prosent, ikke som andel")
    sjekk(all("mill," not in n.verdi for n in laer.nokkeltall),
          "forkortelsen «mill.» ødelegges ikke av tallformateringen")
    sjekk(all("." not in n.verdi.replace("mill.", "") for n in laer.nokkeltall),
          "alle tall bruker norsk desimalkomma")

    uten_tall = monitor.Selskapsstatus(beholdning=Beholdning("XX", "Uten tall"))
    sjekk(laering.bygg(uten_tall) is None, "hoppes over uten kvartalstall")


def test_state(tmp="/tmp/investor-state-test.json") -> None:
    """Historikk mellom kjøringer."""
    print("\nHistorikk")
    import os
    if os.path.exists(tmp):
        os.remove(tmp)

    data = state.les(tmp)
    sjekk(data["snapshots"] == {}, "tom historikk når filen mangler")

    kilde = FixtureKilde()
    statuser = monitor.hent_status(kilde, [Beholdning("MSFT", "Microsoft")])
    kandidater, _ = screener.finn_kandidater(kilde)

    sjekk(state.nye_kandidater(data, "weekly", kandidater)
          == {k.ticker for k in kandidater},
          "alle kandidater er nye første gang")

    state.lagre_snapshot(data, "weekly", statuser, kandidater)
    state.skriv(data, tmp)
    lest = state.les(tmp)
    sjekk(state.nye_kandidater(lest, "weekly", kandidater) == set(),
          "ingen er nye ved neste kjøring")
    sjekk(state.dato_forrige(lest, "weekly") == date.today().isoformat(),
          "forrige dato lagres")
    os.remove(tmp)


def test_portefolje() -> None:
    """Placeholder-tickere skal hoppes over, ikke slå ut kjøringen."""
    print("\nPorteføljelesing")
    beholdninger, _ = monitor.les_portefolje()
    tickere = {b.ticker for b in beholdninger}
    sjekk("BYTT_MEG" not in tickere, "placeholder hoppes over")
    sjekk({"MSFT", "VRT", "MOWI.OL"} <= tickere, "de tre selskapene leses inn")


def main() -> int:
    print("=" * 64)
    print("Tester investeringsassistenten")
    print("=" * 64)

    for test in (
        test_harde_krav_forkaster,
        test_fixtures_forventninger,
        test_krever_tallfestet_begrunnelse,
        test_ingen_kandidater_ved_hoy_terskel,
        test_score_utelater_manglende_data,
        test_hendelser,
        test_rapporter_bygges,
        test_daglig_er_kort,
        test_laering,
        test_state,
        test_portefolje,
    ):
        test()

    print("\n" + "=" * 64)
    if FEIL:
        print(f"{len(FEIL)} FEIL:")
        for f in FEIL:
            print(f"  - {f}")
        return 1
    print("Alle tester passerte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
