"""Financial Modeling Prep som datakilde.

Hovedkilden. Dekker USA, Europa og Norden (inkl. Oslo Børs), og har et
screener-endepunkt som returnerer hundrevis av selskaper i ett kall — det gjør
de harde kvalitetskravene billige å håndheve før vi bruker kvote på detaljerte
oppslag per selskap.

Krever en gratis API-nøkkel i miljøvariabelen FMP_API_KEY.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from .. import config
from ..modeller import Fundamentals, Kurs, Nyhet, Resultat
from .base import HttpKilde, prosent_endring, tall

log = logging.getLogger(__name__)


def _dato(tekst: str | None) -> date | None:
    """Parser 'YYYY-MM-DD' (eventuelt med klokkeslett) til date."""
    if not tekst:
        return None
    try:
        return datetime.fromisoformat(str(tekst)[:19].replace(" ", "T")).date()
    except ValueError:
        return None


class FmpKilde(HttpKilde):
    """Datakilde bygget på Financial Modeling Prep."""

    navn = "fmp"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self.api_key = (api_key or config.FMP_API_KEY).strip()

    def tilgjengelig(self) -> bool:
        """Kilden krever nøkkel; vi verifiserer den med ett billig kall."""
        if not self.api_key:
            log.info("FMP: ingen API-nøkkel satt (FMP_API_KEY)")
            return False
        svar = self._kall("/profile/AAPL")
        if svar is None:
            log.warning("FMP: nøkkel satt, men oppslag feilet")
            return False
        return True

    def _kall(self, sti: str, params: dict | None = None, base: str | None = None):
        p = dict(params or {})
        p["apikey"] = self.api_key
        return self._hent_json(f"{base or config.FMP_BASE}{sti}", p)

    # ------------------------------------------------------------------
    # Kurs
    # ------------------------------------------------------------------

    def hent_kurs(self, ticker: str) -> Kurs | None:
        data = self._kall(f"/quote/{ticker}")
        if not data:
            return None
        q = data[0]
        kurs = Kurs(
            ticker=ticker,
            pris=tall(q.get("price")),
            endring_1d=tall(q.get("changesPercentage")),
            volum=tall(q.get("volume")),
            snittvolum=tall(q.get("avgVolume")),
        )
        # Avstand fra 52-ukers topp sier noe om hvor «på salg» aksjen er.
        topp = tall(q.get("yearHigh"))
        if topp and kurs.pris:
            kurs.fra_topp_52u = (kurs.pris - topp) / topp * 100

        self._legg_til_historiske_endringer(kurs)
        return kurs

    def _legg_til_historiske_endringer(self, kurs: Kurs) -> None:
        """Fyller endring over 1 uke / 1 md / YTD / 1 år fra dagshistorikk."""
        historikk = self._kall(
            f"/historical-price-full/{kurs.ticker}",
            {"serietype": "line", "timeseries": 400},
        )
        rader = (historikk or {}).get("historical") or []
        if not rader or kurs.pris is None:
            return

        # FMP leverer nyeste først.
        serie: list[tuple[date, float]] = []
        for rad in rader:
            d, p = _dato(rad.get("date")), tall(rad.get("close"))
            if d and p is not None:
                serie.append((d, p))
        if not serie:
            return
        serie.sort(key=lambda r: r[0])

        def pris_for(dager_siden: int) -> float | None:
            """Nærmeste sluttkurs minst så mange handledager tilbake."""
            if len(serie) <= dager_siden:
                return serie[0][1]
            return serie[-1 - dager_siden][1]

        kurs.endring_1u = prosent_endring(pris_for(5), kurs.pris)
        kurs.endring_1m = prosent_endring(pris_for(21), kurs.pris)
        kurs.endring_1aar = prosent_endring(pris_for(252), kurs.pris)

        nyttar = date(serie[-1][0].year, 1, 1)
        for d, p in serie:
            if d >= nyttar:
                kurs.endring_ytd = prosent_endring(p, kurs.pris)
                break

    # ------------------------------------------------------------------
    # Fundamentals
    # ------------------------------------------------------------------

    def hent_fundamentals(self, ticker: str) -> Fundamentals | None:
        profil = self._kall(f"/profile/{ticker}")
        if not profil:
            return None
        p = profil[0]

        f = Fundamentals(
            ticker=ticker,
            navn=p.get("companyName") or ticker,
            borsverdi=tall(p.get("mktCap")),
            valuta=p.get("currency") or "USD",
            bors=(p.get("exchangeShortName") or "").upper(),
            sektor=p.get("sector") or "",
            bransje=p.get("industry") or "",
            land=p.get("country") or "",
        )

        self._pust()
        self._legg_til_nokkeltall(f)
        self._pust()
        self._legg_til_vekst(f)
        self._pust()
        self._legg_til_historikk_kvalitet(f)
        return f

    def _legg_til_nokkeltall(self, f: Fundamentals) -> None:
        """Verdsettelse, kvalitet og utbytte fra ratios/key-metrics (TTM)."""
        ratios = self._kall(f"/ratios-ttm/{f.ticker}")
        if ratios:
            r = ratios[0]
            f.pe = tall(r.get("peRatioTTM"))
            f.pb = tall(r.get("priceToBookRatioTTM"))
            f.roe = tall(r.get("returnOnEquityTTM"))
            f.driftsmargin = tall(r.get("operatingProfitMarginTTM"))
            f.bruttomargin = tall(r.get("grossProfitMarginTTM"))
            f.gjeld_egenkapital = tall(r.get("debtEquityRatioTTM"))
            f.rentedekning = tall(r.get("interestCoverageTTM"))
            f.utbytte_yield = tall(r.get("dividendYielTTM")) or tall(
                r.get("dividendYieldTTM")
            )

        self._pust()
        metrics = self._kall(f"/key-metrics-ttm/{f.ticker}")
        if metrics:
            m = metrics[0]
            f.ev_ebitda = tall(m.get("enterpriseValueOverEBITDATTM"))
            f.roic = tall(m.get("roicTTM"))
            if f.pb is None:
                f.pb = tall(m.get("pbRatioTTM"))
            # FCF-yield er den inverse av pris/fri kontantstrøm. Mangler den,
            # regnes yielden ut fra årsregnskapet i _legg_til_historikk_kvalitet.
            pris_fcf = tall(m.get("pfcfRatioTTM"))
            if pris_fcf and pris_fcf > 0:
                f.fcf_yield = 1 / pris_fcf

    def _legg_til_vekst(self, f: Fundamentals) -> None:
        """Omsetnings- og EPS-vekst fra financial-growth."""
        vekst = self._kall(
            f"/financial-growth/{f.ticker}", {"period": "annual", "limit": 5}
        )
        if not vekst:
            return
        siste = vekst[0]
        f.omsetningsvekst = tall(siste.get("revenueGrowth"))
        f.eps_vekst = tall(siste.get("epsgrowth"))
        f.omsetningsvekst_3aar = tall(siste.get("threeYRevenueGrowthPerShare"))

        # Fallback: regn 3-års snitt selv fra årlige vekstrater.
        if f.omsetningsvekst_3aar is None:
            rater = [tall(v.get("revenueGrowth")) for v in vekst[:3]]
            rater = [r for r in rater if r is not None]
            if rater:
                f.omsetningsvekst_3aar = sum(rater) / len(rater)

    def _legg_til_historikk_kvalitet(self, f: Fundamentals) -> None:
        """Teller år med data, overskudd og positiv fri kontantstrøm.

        Dette er grunnlaget for de harde kravene om dokumentert historikk og
        soliditet over tid — ikke bare ett godt kvartal.
        """
        resultat = self._kall(
            f"/income-statement/{f.ticker}", {"period": "annual", "limit": 10}
        )
        if resultat:
            f.aar_med_data = len(resultat)
            f.aar_med_overskudd = sum(
                1 for r in resultat if (tall(r.get("netIncome")) or 0) > 0
            )

        self._pust()
        kontant = self._kall(
            f"/cash-flow-statement/{f.ticker}", {"period": "annual", "limit": 10}
        )
        if kontant:
            f.aar_med_data = max(f.aar_med_data, len(kontant))
            f.aar_med_positiv_fcf = sum(
                1 for r in kontant if (tall(r.get("freeCashFlow")) or 0) > 0
            )
            # Regn FCF-yield fra siste år hvis vi ikke fikk den fra key-metrics.
            if f.fcf_yield is None and f.borsverdi:
                fcf = tall(kontant[0].get("freeCashFlow"))
                if fcf is not None and f.borsverdi > 0:
                    f.fcf_yield = fcf / f.borsverdi

    # ------------------------------------------------------------------
    # Nyheter og resultater
    # ------------------------------------------------------------------

    def hent_nyheter(self, ticker: str, siden: date | None = None) -> list[Nyhet]:
        data = self._kall("/stock_news", {"tickers": ticker, "limit": 25})
        nyheter = []
        for n in data or []:
            publisert = None
            try:
                publisert = datetime.fromisoformat(
                    str(n.get("publishedDate", "")).replace(" ", "T")
                )
            except ValueError:
                pass
            if siden and publisert and publisert.date() < siden:
                continue
            nyheter.append(
                Nyhet(
                    ticker=ticker,
                    tittel=n.get("title") or "",
                    url=n.get("url") or "",
                    kilde=n.get("site") or "",
                    publisert=publisert,
                    sammendrag=(n.get("text") or "")[:400],
                )
            )
        return nyheter

    def hent_resultat(self, ticker: str) -> Resultat | None:
        """Siste rapporterte kvartal, med tall til den lærende seksjonen."""
        data = self._kall(
            f"/income-statement/{ticker}", {"period": "quarter", "limit": 5}
        )
        if not data:
            return None
        siste = data[0]
        res = Resultat(
            ticker=ticker,
            dato=_dato(siste.get("date")),
            er_bekreftet=True,
            periode=f"{siste.get('period', '')} {str(siste.get('calendarYear', ''))}".strip(),
            omsetning=tall(siste.get("revenue")),
            eps=tall(siste.get("epsdiluted")) or tall(siste.get("eps")),
            driftsresultat=tall(siste.get("operatingIncome")),
            valuta=siste.get("reportedCurrency") or "USD",
        )
        # Samme kvartal i fjor ligger fire kvartaler tilbake.
        if len(data) >= 5:
            i_fjor = data[4]
            res.omsetning_i_fjor = tall(i_fjor.get("revenue"))
            res.eps_i_fjor = tall(i_fjor.get("epsdiluted")) or tall(i_fjor.get("eps"))
        if res.omsetning and res.driftsresultat is not None:
            res.driftsmargin = res.driftsresultat / res.omsetning

        self._pust()
        forventet = self._kall(
            f"/historical/earning_calendar/{ticker}", {"limit": 8}
        )
        for rad in forventet or []:
            if _dato(rad.get("date")) == res.dato:
                res.eps_forventet = tall(rad.get("epsEstimated"))
                break
        return res

    def hent_neste_resultatdato(self, ticker: str) -> date | None:
        data = self._kall(f"/historical/earning_calendar/{ticker}", {"limit": 12})
        i_dag = date.today()
        kommende = sorted(
            d for d in (_dato(r.get("date")) for r in data or []) if d and d >= i_dag
        )
        return kommende[0] if kommende else None

    # ------------------------------------------------------------------
    # Univers
    # ------------------------------------------------------------------

    def hent_univers(self) -> list[str]:
        """Henter forhåndsfiltrert univers via FMPs screener-endepunkt.

        De harde kravene om børsverdi, kurs og volum sendes med som filtre, så
        penny stocks og illikvide selskaper aldri kommer inn i systemet i det
        hele tatt. Børsfilteret sikrer at vi kun ser på hovedbørser.
        """
        tickere: list[str] = []
        sett: set[str] = set()

        for bors in config.TILLATTE_BORSER:
            if len(tickere) >= config.MAKS_UNIVERS:
                break
            data = self._kall(
                "/stock-screener",
                {
                    "marketCapMoreThan": int(config.MIN_BORSVERDI),
                    "priceMoreThan": config.MIN_AKSJEKURS,
                    "volumeMoreThan": int(config.MIN_SNITTVOLUM),
                    "exchange": bors,
                    "isActivelyTrading": "true",
                    "isEtf": "false",
                    "isFund": "false",
                    "limit": 200,
                },
            )
            for rad in data or []:
                t = (rad.get("symbol") or "").strip()
                b = (rad.get("exchangeShortName") or "").upper()
                if not t or t in sett:
                    continue
                if any(f in b for f in config.FORBUDTE_BORSER):
                    continue
                sett.add(t)
                tickere.append(t)
                if len(tickere) >= config.MAKS_UNIVERS:
                    break
            self._pust()

        log.info("FMP: univers på %d selskaper etter forhåndsfilter", len(tickere))
        return tickere
