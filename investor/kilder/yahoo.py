"""Yahoo Finance som reservekilde.

Snakker direkte med Yahoos JSON-endepunkter via `requests`. Vi bruker bevisst
ikke yfinance: den er bygget på curl_cffi, som feiler bak proxy og gir ekstra
bruddflate uten å tilføre noe vi trenger her.

Merk at Yahoo struper forespørsler fra datasentre. Kilden er derfor en reserve,
ikke førstevalget — se `config.KILDE_REKKEFOLGE`.
"""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from .. import config
from ..modeller import Fundamentals, Kurs, Nyhet, Resultat
from .base import HttpKilde, prosent_endring, tall

log = logging.getLogger(__name__)

UNIVERS_KATALOG = Path(__file__).resolve().parent.parent / "univers"

# Modulene vi trenger fra quoteSummary.
MODULER = ",".join([
    "price", "summaryDetail", "defaultKeyStatistics", "financialData",
    "assetProfile", "calendarEvents", "incomeStatementHistory",
    "cashflowStatementHistory", "earnings",
])


def _raa(felt) -> float | None:
    """Yahoo pakker tall som {'raw': 1.23, 'fmt': '1.23'} — hent ut råverdien."""
    if isinstance(felt, dict):
        return tall(felt.get("raw"))
    return tall(felt)


class YahooKilde(HttpKilde):
    """Datakilde bygget på Yahoo Finance sine offentlige endepunkter."""

    navn = "yahoo"

    def __init__(self) -> None:
        super().__init__()
        self._crumb: str | None = None
        self._crumb_forsokt = False

    def tilgjengelig(self) -> bool:
        """Sjekker at chart-endepunktet svarer — det er kjernen vi trenger."""
        data = self._hent_json(
            f"{config.YAHOO_BASE}/v8/finance/chart/AAPL", {"range": "5d", "interval": "1d"}
        )
        if not data:
            log.warning("Yahoo: svarer ikke (sannsynligvis strupet fra denne IP-en)")
            return False
        return True

    def _hent_crumb(self) -> str | None:
        """Henter cookie + crumb som quoteSummary krever.

        Feiler dette (typisk 429), faller vi tilbake på chart-endepunktet, som
        gir kurser men ikke nøkkeltall.
        """
        if self._crumb_forsokt:
            return self._crumb
        self._crumb_forsokt = True
        try:
            self._sesjon.get("https://fc.yahoo.com", timeout=config.HTTP_TIMEOUT)
        except Exception:
            pass
        try:
            svar = self._sesjon.get(
                f"{config.YAHOO_BASE}/v1/test/getcrumb", timeout=config.HTTP_TIMEOUT
            )
            if svar.status_code == 200 and svar.text and " " not in svar.text.strip():
                self._crumb = svar.text.strip()
        except Exception as feil:
            log.debug("Yahoo: kunne ikke hente crumb: %s", feil)
        if not self._crumb:
            log.info("Yahoo: ingen crumb — nøkkeltall blir utilgjengelige")
        return self._crumb

    def _quote_summary(self, ticker: str) -> dict | None:
        crumb = self._hent_crumb()
        params = {"modules": MODULER}
        if crumb:
            params["crumb"] = crumb
        data = self._hent_json(
            f"{config.YAHOO_BASE}/v10/finance/quoteSummary/{ticker}", params
        )
        try:
            return data["quoteSummary"]["result"][0]
        except (TypeError, KeyError, IndexError):
            return None

    # ------------------------------------------------------------------
    # Kurs
    # ------------------------------------------------------------------

    def hent_kurs(self, ticker: str) -> Kurs | None:
        """Kurs og endringer regnet ut fra ett års dagshistorikk."""
        data = self._hent_json(
            f"{config.YAHOO_BASE}/v8/finance/chart/{ticker}",
            {"range": "1y", "interval": "1d"},
        )
        try:
            res = data["chart"]["result"][0]
            meta = res["meta"]
            lukk = [k for k in res["indicators"]["quote"][0]["close"] if k is not None]
            tider = res.get("timestamp") or []
        except (TypeError, KeyError, IndexError):
            return None
        if not lukk:
            return None

        pris = tall(meta.get("regularMarketPrice")) or lukk[-1]
        kurs = Kurs(
            ticker=ticker,
            pris=pris,
            valuta=meta.get("currency") or "USD",
            volum=tall(meta.get("regularMarketVolume")),
        )

        def pris_for(dager: int) -> float | None:
            return lukk[-1 - dager] if len(lukk) > dager else lukk[0]

        forrige = tall(meta.get("chartPreviousClose")) or (
            lukk[-2] if len(lukk) > 1 else None
        )
        kurs.endring_1d = prosent_endring(forrige, pris)
        kurs.endring_1u = prosent_endring(pris_for(5), pris)
        kurs.endring_1m = prosent_endring(pris_for(21), pris)
        kurs.endring_1aar = prosent_endring(lukk[0], pris)
        kurs.snittvolum = sum(
            v for v in res["indicators"]["quote"][0].get("volume") or [] if v
        ) / max(len(lukk), 1) or None

        topp = tall(meta.get("fiftyTwoWeekHigh")) or max(lukk)
        if topp:
            kurs.fra_topp_52u = (pris - topp) / topp * 100

        # YTD: første handledag i inneværende år.
        if tider and len(tider) == len(res["indicators"]["quote"][0]["close"]):
            i_aar = date.today().year
            for stempel, lukkekurs in zip(tider, res["indicators"]["quote"][0]["close"]):
                if lukkekurs is None:
                    continue
                if datetime.fromtimestamp(stempel, timezone.utc).year == i_aar:
                    kurs.endring_ytd = prosent_endring(lukkekurs, pris)
                    break
        return kurs

    # ------------------------------------------------------------------
    # Fundamentals
    # ------------------------------------------------------------------

    def hent_fundamentals(self, ticker: str) -> Fundamentals | None:
        d = self._quote_summary(ticker)
        if not d:
            return None

        pris_mod = d.get("price") or {}
        sammendrag = d.get("summaryDetail") or {}
        nokkel = d.get("defaultKeyStatistics") or {}
        finans = d.get("financialData") or {}
        profil = d.get("assetProfile") or {}

        f = Fundamentals(
            ticker=ticker,
            navn=pris_mod.get("longName") or pris_mod.get("shortName") or ticker,
            borsverdi=_raa(pris_mod.get("marketCap")),
            valuta=pris_mod.get("currency") or "USD",
            bors=(pris_mod.get("exchangeName") or "").upper(),
            sektor=profil.get("sector") or "",
            bransje=profil.get("industry") or "",
            land=profil.get("country") or "",
            pe=_raa(sammendrag.get("trailingPE")),
            forward_pe=_raa(sammendrag.get("forwardPE")),
            pb=_raa(nokkel.get("priceToBook")),
            ev_ebitda=_raa(nokkel.get("enterpriseToEbitda")),
            roe=_raa(finans.get("returnOnEquity")),
            driftsmargin=_raa(finans.get("operatingMargins")),
            bruttomargin=_raa(finans.get("grossMargins")),
            omsetningsvekst=_raa(finans.get("revenueGrowth")),
            eps_vekst=_raa(nokkel.get("earningsQuarterlyGrowth")),
            utbytte_yield=_raa(sammendrag.get("dividendYield")),
        )

        gjeld = _raa(finans.get("debtToEquity"))
        if gjeld is not None:
            # Yahoo oppgir dette i prosent (f.eks. 45.2 for 0.452).
            f.gjeld_egenkapital = gjeld / 100

        fcf = _raa(finans.get("freeCashflow"))
        if fcf is not None and f.borsverdi:
            f.fcf_yield = fcf / f.borsverdi

        self._tell_historikk(f, d)
        return f

    def _tell_historikk(self, f: Fundamentals, d: dict) -> None:
        """Teller år med data, overskudd og positiv FCF fra årsregnskapene."""
        resultat = (d.get("incomeStatementHistory") or {}).get(
            "incomeStatementHistory"
        ) or []
        if resultat:
            f.aar_med_data = len(resultat)
            f.aar_med_overskudd = sum(
                1 for r in resultat if (_raa(r.get("netIncome")) or 0) > 0
            )

        kontant = (d.get("cashflowStatementHistory") or {}).get(
            "cashflowStatements"
        ) or []
        if kontant:
            f.aar_med_data = max(f.aar_med_data, len(kontant))
            positive = 0
            for r in kontant:
                drift = _raa(r.get("totalCashFromOperatingActivities"))
                invest = _raa(r.get("capitalExpenditures")) or 0
                if drift is not None and drift + invest > 0:
                    positive += 1
            f.aar_med_positiv_fcf = positive

    # ------------------------------------------------------------------
    # Nyheter og resultater
    # ------------------------------------------------------------------

    def hent_nyheter(self, ticker: str, siden: date | None = None) -> list[Nyhet]:
        data = self._hent_json(
            f"{config.YAHOO_BASE}/v1/finance/search",
            {"q": ticker, "newsCount": 20, "quotesCount": 0},
        )
        nyheter = []
        for n in (data or {}).get("news") or []:
            publisert = None
            if n.get("providerPublishTime"):
                publisert = datetime.fromtimestamp(
                    n["providerPublishTime"], timezone.utc
                )
            if siden and publisert and publisert.date() < siden:
                continue
            nyheter.append(
                Nyhet(
                    ticker=ticker,
                    tittel=n.get("title") or "",
                    url=n.get("link") or "",
                    kilde=n.get("publisher") or "",
                    publisert=publisert,
                )
            )
        return nyheter

    def hent_resultat(self, ticker: str) -> Resultat | None:
        d = self._quote_summary(ticker)
        if not d:
            return None
        kvartaler = ((d.get("earnings") or {}).get("financialsChart") or {}).get(
            "quarterly"
        ) or []
        if not kvartaler:
            return None
        siste = kvartaler[-1]
        res = Resultat(
            ticker=ticker,
            periode=siste.get("date") or "",
            er_bekreftet=True,
            omsetning=_raa(siste.get("revenue")),
            valuta=(d.get("earnings") or {}).get("financialCurrency") or "USD",
        )
        if len(kvartaler) >= 5:
            res.omsetning_i_fjor = _raa(kvartaler[-5].get("revenue"))

        # Faktisk vs. forventet EPS fra earnings-historikken.
        historikk = ((d.get("earnings") or {}).get("earningsChart") or {}).get(
            "quarterly"
        ) or []
        if historikk:
            res.eps = _raa(historikk[-1].get("actual"))
            res.eps_forventet = _raa(historikk[-1].get("estimate"))
            if len(historikk) >= 5:
                res.eps_i_fjor = _raa(historikk[-5].get("actual"))
        return res

    def hent_neste_resultatdato(self, ticker: str) -> date | None:
        d = self._quote_summary(ticker)
        if not d:
            return None
        datoer = ((d.get("calendarEvents") or {}).get("earnings") or {}).get(
            "earningsDate"
        ) or []
        for felt in datoer:
            stempel = _raa(felt)
            if stempel:
                kandidat = datetime.fromtimestamp(stempel, timezone.utc).date()
                if kandidat >= date.today():
                    return kandidat
        return None

    # ------------------------------------------------------------------
    # Univers
    # ------------------------------------------------------------------

    def hent_univers(self) -> list[str]:
        """Leser statiske indekslister fra investor/univers/*.csv.

        Yahoo har ikke noe screener-endepunkt vi kan bruke, så universet er
        bundlet. De harde kravene håndheves i stedet i screeneren, etter at
        nøkkeltallene er hentet.
        """
        tickere: list[str] = []
        sett: set[str] = set()
        for fil in sorted(UNIVERS_KATALOG.glob("*.csv")):
            try:
                with fil.open(encoding="utf-8") as f:
                    for rad in csv.DictReader(f):
                        t = (rad.get("ticker") or "").strip()
                        if t and t not in sett:
                            sett.add(t)
                            tickere.append(t)
            except OSError as feil:
                log.warning("Kunne ikke lese %s: %s", fil.name, feil)
        log.info("Yahoo: univers på %d selskaper fra statiske lister", len(tickere))
        return tickere[: config.MAKS_UNIVERS]
