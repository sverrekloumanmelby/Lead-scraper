"""Offline testkilde med deterministiske data.

Brukes med `--kilde fixtures`. To formål:

1. Verifisere hele pipelinen uten nett (nyttig i sandkasser der Yahoo struper).
2. Bevise at de harde kvalitetskravene faktisk forkaster selskaper: universet
   nedenfor inneholder med vilje penny stocks, ulønnsomme selskaper, selskaper
   uten nok historikk og OTC-noteringer, i tillegg til noen solide kandidater.

Tallene er syntetiske og skal ikke brukes til faktiske investeringsbeslutninger.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..modeller import Fundamentals, Kurs, Nyhet, Resultat
from .base import Kilde

# Hvert selskap: nøkkeltall + hva vi forventer skal skje med det i screeneren.
# «forventet» leses av testene i verifiseringen.
SELSKAPER: dict[str, dict] = {
    # --- Solide kandidater som skal slippe gjennom ------------------------
    "GOODCO": {
        "navn": "GoodCo Industries", "borsverdi": 45e9, "bors": "NASDAQ",
        "sektor": "Technology", "pris": 142.50, "pe": 16.5, "pb": 3.1,
        "ev_ebitda": 10.2, "fcf_yield": 0.068, "roe": 0.24, "roic": 0.19,
        "driftsmargin": 0.22, "bruttomargin": 0.55, "gjeld_egenkapital": 0.35,
        "omsetningsvekst": 0.14, "eps_vekst": 0.18, "omsetningsvekst_3aar": 0.12,
        "utbytte_yield": 0.021, "aar_med_data": 10, "aar_med_overskudd": 10,
        "aar_med_positiv_fcf": 9, "endring_1aar": 12.0, "fra_topp_52u": -18.0,
        "forventet": "kandidat",
    },
    "STEADY": {
        "navn": "Steady Manufacturing", "borsverdi": 12e9, "bors": "NYSE",
        "sektor": "Industrials", "pris": 88.20, "pe": 13.0, "pb": 2.2,
        "ev_ebitda": 8.5, "fcf_yield": 0.075, "roe": 0.19, "roic": 0.15,
        "driftsmargin": 0.16, "bruttomargin": 0.38, "gjeld_egenkapital": 0.55,
        "omsetningsvekst": 0.08, "eps_vekst": 0.11, "omsetningsvekst_3aar": 0.07,
        "utbytte_yield": 0.034, "aar_med_data": 10, "aar_med_overskudd": 9,
        "aar_med_positiv_fcf": 8, "endring_1aar": 5.0, "fra_topp_52u": -9.0,
        "forventet": "kandidat",
    },
    "NORDIQ": {
        "navn": "Nordiq Marine ASA", "borsverdi": 6.5e9, "bors": "OSLO",
        "sektor": "Consumer Defensive", "pris": 210.0, "valuta": "NOK",
        "pe": 14.8, "pb": 1.9, "ev_ebitda": 9.1, "fcf_yield": 0.061,
        "roe": 0.17, "roic": 0.13, "driftsmargin": 0.18, "bruttomargin": 0.31,
        "gjeld_egenkapital": 0.72, "omsetningsvekst": 0.10, "eps_vekst": 0.09,
        "omsetningsvekst_3aar": 0.08, "utbytte_yield": 0.042,
        "aar_med_data": 8, "aar_med_overskudd": 7, "aar_med_positiv_fcf": 6,
        "endring_1aar": 3.5, "fra_topp_52u": -14.0, "forventet": "kandidat",
    },
    # --- Skal forkastes av de harde kravene ------------------------------
    "PENNY": {  # penny stock: for lav kurs og for lav børsverdi
        "navn": "Penny Ventures", "borsverdi": 80e6, "bors": "NASDAQ",
        "sektor": "Technology", "pris": 0.85, "pe": 8.0, "pb": 0.9,
        "fcf_yield": 0.12, "roe": 0.30, "driftsmargin": 0.20,
        "gjeld_egenkapital": 0.4, "omsetningsvekst": 0.60, "eps_vekst": 0.9,
        "aar_med_data": 6, "aar_med_overskudd": 4, "aar_med_positiv_fcf": 3,
        "snittvolum": 5_000_000, "forventet": "forkastet:borsverdi",
    },
    "OTCJUNK": {  # riktig børsverdi, men OTC-notert
        "navn": "OTC Junk Holdings", "borsverdi": 3e9, "bors": "OTC",
        "sektor": "Financial", "pris": 25.0, "pe": 11.0, "pb": 1.2,
        "fcf_yield": 0.08, "roe": 0.18, "driftsmargin": 0.15,
        "gjeld_egenkapital": 0.5, "omsetningsvekst": 0.12, "eps_vekst": 0.14,
        "aar_med_data": 8, "aar_med_overskudd": 7, "aar_med_positiv_fcf": 6,
        "forventet": "forkastet:bors",
    },
    "NEWBIE": {  # for kort historikk
        "navn": "Newbie Tech", "borsverdi": 8e9, "bors": "NASDAQ",
        "sektor": "Technology", "pris": 55.0, "pe": 22.0, "pb": 4.0,
        "fcf_yield": 0.05, "roe": 0.20, "driftsmargin": 0.18,
        "gjeld_egenkapital": 0.3, "omsetningsvekst": 0.35, "eps_vekst": 0.4,
        "aar_med_data": 2, "aar_med_overskudd": 2, "aar_med_positiv_fcf": 2,
        "forventet": "forkastet:historikk",
    },
    "LOSSCO": {  # taper penger over tid
        "navn": "LossCo Biotech", "borsverdi": 5e9, "bors": "NASDAQ",
        "sektor": "Healthcare", "pris": 40.0, "pe": None, "pb": 6.0,
        "fcf_yield": -0.04, "roe": -0.15, "driftsmargin": -0.30,
        "gjeld_egenkapital": 0.6, "omsetningsvekst": 0.5, "eps_vekst": None,
        "aar_med_data": 9, "aar_med_overskudd": 1, "aar_med_positiv_fcf": 0,
        "forventet": "forkastet:lonnsomhet",
    },
    "DEBTCO": {  # for høy gjeld
        "navn": "DebtCo Utilities", "borsverdi": 15e9, "bors": "NYSE",
        "sektor": "Utilities", "pris": 62.0, "pe": 12.0, "pb": 1.1,
        "fcf_yield": 0.07, "roe": 0.14, "driftsmargin": 0.20,
        "gjeld_egenkapital": 3.8, "omsetningsvekst": 0.04, "eps_vekst": 0.05,
        "aar_med_data": 10, "aar_med_overskudd": 9, "aar_med_positiv_fcf": 7,
        "utbytte_yield": 0.055, "forventet": "forkastet:gjeld",
    },
    "MEHCO": {  # består kravene, men er middelmådig — skal falle på score
        "navn": "Meh Corporation", "borsverdi": 9e9, "bors": "NYSE",
        "sektor": "Consumer Cyclical", "pris": 33.0, "pe": 29.0, "pb": 5.5,
        "ev_ebitda": 17.0, "fcf_yield": 0.031, "roe": 0.105,
        "driftsmargin": 0.085, "gjeld_egenkapital": 1.8,
        "omsetningsvekst": 0.031, "eps_vekst": 0.04,
        "omsetningsvekst_3aar": 0.03, "utbytte_yield": 0.011,
        "aar_med_data": 10, "aar_med_overskudd": 8, "aar_med_positiv_fcf": 5,
        "endring_1aar": -2.0, "forventet": "forkastet:score",
    },
    # --- Porteføljeselskaper (så daglig/ukentlig rapport har innhold) -----
    "MSFT": {
        "navn": "Microsoft Corporation", "borsverdi": 3.1e12, "bors": "NASDAQ",
        "sektor": "Technology", "pris": 418.20, "pe": 34.0, "pb": 11.5,
        "ev_ebitda": 22.0, "fcf_yield": 0.026, "roe": 0.35, "roic": 0.28,
        "driftsmargin": 0.45, "bruttomargin": 0.69, "gjeld_egenkapital": 0.32,
        "omsetningsvekst": 0.16, "eps_vekst": 0.20, "omsetningsvekst_3aar": 0.14,
        "utbytte_yield": 0.007, "aar_med_data": 10, "aar_med_overskudd": 10,
        "aar_med_positiv_fcf": 10, "endring_1d": 1.2, "endring_1u": 2.4,
        "endring_1m": -3.1, "endring_ytd": 8.7, "endring_1aar": 14.2,
        "fra_topp_52u": -6.5,
    },
    "VRT": {
        "navn": "Vertiv Holdings Co", "borsverdi": 42e9, "bors": "NYSE",
        "sektor": "Industrials", "pris": 112.40, "pe": 38.0, "pb": 14.0,
        "ev_ebitda": 24.0, "fcf_yield": 0.022, "roe": 0.32, "roic": 0.21,
        "driftsmargin": 0.17, "bruttomargin": 0.36, "gjeld_egenkapital": 1.4,
        "omsetningsvekst": 0.24, "eps_vekst": 0.45, "omsetningsvekst_3aar": 0.19,
        "utbytte_yield": 0.001, "aar_med_data": 7, "aar_med_overskudd": 5,
        "aar_med_positiv_fcf": 5, "endring_1d": -7.3, "endring_1u": -9.8,
        "endring_1m": 4.2, "endring_ytd": 22.1, "endring_1aar": 48.0,
        "fra_topp_52u": -21.0,
    },
    "MOWI.OL": {
        "navn": "Mowi ASA", "borsverdi": 105e9, "bors": "OSLO", "valuta": "NOK",
        "sektor": "Consumer Defensive", "pris": 203.10, "pe": 17.5, "pb": 2.1,
        "ev_ebitda": 11.0, "fcf_yield": 0.045, "roe": 0.15, "roic": 0.11,
        "driftsmargin": 0.14, "bruttomargin": 0.26, "gjeld_egenkapital": 0.85,
        "omsetningsvekst": 0.06, "eps_vekst": -0.08, "omsetningsvekst_3aar": 0.09,
        "utbytte_yield": 0.048, "aar_med_data": 10, "aar_med_overskudd": 9,
        "aar_med_positiv_fcf": 7, "endring_1d": 0.4, "endring_1u": -1.2,
        "endring_1m": 2.8, "endring_ytd": -4.5, "endring_1aar": 1.9,
        "fra_topp_52u": -12.0,
    },
}

# Nyheter per ticker: (tittel, dager siden, kilde)
NYHETER: dict[str, list[tuple[str, int, str]]] = {
    "MSFT": [
        ("Microsoft raises quarterly dividend by 10%", 1, "Reuters"),
        ("Analysts lift price target on Azure momentum", 2, "Bloomberg"),
        ("Microsoft opens new datacenter region", 9, "TechCrunch"),
    ],
    "VRT": [
        ("Vertiv shares slide after guidance disappoints", 0, "Reuters"),
        ("Vertiv announces $600m data center contract", 4, "Barron's"),
    ],
    "MOWI.OL": [
        ("Mowi rapporterer økt slaktevolum i kvartalet", 3, "E24"),
        ("Laksepriser stiger inn i høysesongen", 6, "DN"),
    ],
    "GOODCO": [("GoodCo beats estimates and raises outlook", 2, "Reuters")],
}


def _fund(ticker: str) -> Fundamentals | None:
    d = SELSKAPER.get(ticker)
    if not d:
        return None
    return Fundamentals(
        ticker=ticker,
        navn=d.get("navn", ticker),
        borsverdi=d.get("borsverdi"),
        valuta=d.get("valuta", "USD"),
        bors=d.get("bors", ""),
        sektor=d.get("sektor", ""),
        bransje=d.get("bransje", ""),
        land=d.get("land", ""),
        pe=d.get("pe"),
        forward_pe=d.get("forward_pe"),
        pb=d.get("pb"),
        ev_ebitda=d.get("ev_ebitda"),
        fcf_yield=d.get("fcf_yield"),
        roe=d.get("roe"),
        roic=d.get("roic"),
        driftsmargin=d.get("driftsmargin"),
        bruttomargin=d.get("bruttomargin"),
        gjeld_egenkapital=d.get("gjeld_egenkapital"),
        omsetningsvekst=d.get("omsetningsvekst"),
        eps_vekst=d.get("eps_vekst"),
        omsetningsvekst_3aar=d.get("omsetningsvekst_3aar"),
        utbytte_yield=d.get("utbytte_yield"),
        aar_med_data=d.get("aar_med_data", 0),
        aar_med_overskudd=d.get("aar_med_overskudd", 0),
        aar_med_positiv_fcf=d.get("aar_med_positiv_fcf", 0),
    )


class FixtureKilde(Kilde):
    """Deterministisk offline-kilde."""

    navn = "fixtures"

    def tilgjengelig(self) -> bool:
        return True

    def hent_kurs(self, ticker: str) -> Kurs | None:
        d = SELSKAPER.get(ticker)
        if not d:
            return None
        return Kurs(
            ticker=ticker,
            pris=d.get("pris"),
            valuta=d.get("valuta", "USD"),
            endring_1d=d.get("endring_1d"),
            endring_1u=d.get("endring_1u"),
            endring_1m=d.get("endring_1m"),
            endring_ytd=d.get("endring_ytd"),
            endring_1aar=d.get("endring_1aar"),
            fra_topp_52u=d.get("fra_topp_52u"),
            volum=d.get("volum", 1_500_000),
            snittvolum=d.get("snittvolum", 1_200_000),
        )

    def hent_fundamentals(self, ticker: str) -> Fundamentals | None:
        return _fund(ticker)

    def hent_nyheter(self, ticker: str, siden: date | None = None) -> list[Nyhet]:
        ut = []
        for tittel, dager, kilde in NYHETER.get(ticker, []):
            publisert = datetime.now() - timedelta(days=dager)
            if siden and publisert.date() < siden:
                continue
            ut.append(
                Nyhet(
                    ticker=ticker,
                    tittel=tittel,
                    url=f"https://example.invalid/{ticker.lower()}/{dager}",
                    kilde=kilde,
                    publisert=publisert,
                )
            )
        return ut

    def hent_resultat(self, ticker: str) -> Resultat | None:
        d = SELSKAPER.get(ticker)
        if not d:
            return None
        # Bygg et syntetisk, men internt konsistent kvartal.
        omsetning = (d.get("borsverdi") or 1e9) * 0.06
        vekst = d.get("omsetningsvekst") or 0.05
        margin = d.get("driftsmargin") or 0.1
        return Resultat(
            ticker=ticker,
            dato=date.today() - timedelta(days=21),
            er_bekreftet=True,
            periode=f"Q{((date.today().month - 1) // 3) or 4} {date.today().year}",
            omsetning=omsetning,
            omsetning_i_fjor=omsetning / (1 + vekst),
            eps=2.85,
            eps_i_fjor=2.40,
            eps_forventet=2.71,
            driftsresultat=omsetning * margin,
            driftsmargin=margin,
            valuta=d.get("valuta", "USD"),
        )

    def hent_neste_resultatdato(self, ticker: str) -> date | None:
        if ticker not in SELSKAPER:
            return None
        # MSFT rapporterer snart — gir daglig rapport noe å varsle om.
        forskyvning = {"MSFT": 4, "VRT": 30, "MOWI.OL": 52}.get(ticker, 45)
        return date.today() + timedelta(days=forskyvning)

    def hent_univers(self) -> list[str]:
        return list(SELSKAPER.keys())
