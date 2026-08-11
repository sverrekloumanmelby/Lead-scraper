"""Investeringsassistent — kommandolinje og orkestrering.

Kjøres av GitHub Actions på tre ulike timeplaner:

    python -m investor.main --mode daily      # hverdager, kort
    python -m investor.main --mode weekly     # mandager, portefølje + kandidater
    python -m investor.main --mode monthly    # den 1., dyp gjennomgang

Til utprøving:

    python -m investor.main --mode weekly --dry-run --kilde fixtures
    python -m investor.main --mode daily --send-test din@epost.no
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import config, email_send, monitor, report, screener, state
from .kilder import KildeUtilgjengelig, velg_kilde

log = logging.getLogger("investor")

PAKKE = Path(__file__).resolve().parent

# Screeneren kjøres ikke daglig: den koster mange API-kall, og nye
# kjøpskandidater dukker ikke opp i et tempo som gjør daglig screening nyttig.
MODUS_MED_SCREENER = {"weekly", "monthly"}

MAKS_KANDIDATER = {
    "weekly": config.MAKS_KANDIDATER_UKENTLIG,
    "monthly": config.MAKS_KANDIDATER_MANEDLIG,
}


def kjor(
    modus: str,
    *,
    kildenavn: str | None = None,
    torrkjor: bool = False,
    test_mottaker: str | None = None,
    hopp_over_screener: bool = False,
) -> int:
    """Kjører én rapport fra ende til ende. Returnerer exit-kode."""
    try:
        kilde = velg_kilde(kildenavn)
    except KildeUtilgjengelig as feil:
        log.error("%s", feil)
        return 2

    # --- Portefølje ---
    beholdninger, watchlist = monitor.les_portefolje()
    if not beholdninger:
        log.error(
            "Ingen beholdninger å overvåke. Fyll inn tickere i %s",
            config.PORTEFOLJE_FIL,
        )
        return 2
    log.info("Overvåker %d selskap(er)", len(beholdninger))

    historikk = state.les()

    # --- Porteføljestatus ---
    statuser = monitor.hent_status(
        kilde,
        beholdninger,
        nyheter_siden=monitor.nyheter_siden_for(modus),
        med_fundamentals=(modus == "monthly"),
    )

    # --- Screening ---
    kandidater: list = []
    statistikk = None
    if modus in MODUS_MED_SCREENER and not hopp_over_screener:
        eier = {b.ticker for b in beholdninger} | set(watchlist)
        try:
            kandidater, statistikk = screener.finn_kandidater(
                kilde, ekskluder=eier, maks=MAKS_KANDIDATER.get(modus)
            )
        except Exception as feil:
            # En feilende screener skal ikke hindre porteføljerapporten.
            log.exception("Screeningen feilet: %s", feil)
            statistikk = {"vurdert": 0, "feil": 1}

    # --- Rapport ---
    rapport = report.bygg_rapport(
        modus,
        statuser,
        kandidater,
        historikk=historikk,
        screener_statistikk=statistikk,
    )

    if torrkjor:
        sti = report.skriv_til_fil(rapport, PAKKE / "out")
        log.info("Tørrkjøring — skrev rapport til %s", sti)
        log.info("Emne ville vært: %s", rapport.emne)
        return 0

    # --- Send ---
    try:
        email_send.send(
            rapport.emne, rapport.html, rapport.tekst, til=test_mottaker
        )
    except email_send.EpostFeil as feil:
        log.error("%s", feil)
        return 3

    # Historikken oppdateres kun når rapporten faktisk gikk ut, slik at en
    # mislykket kjøring ikke «bruker opp» hendelsene.
    if not test_mottaker:
        state.lagre_snapshot(historikk, modus, statuser, kandidater)
        state.skriv(historikk)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="investor",
        description="Porteføljeovervåking og aksjescreening på e-post.",
    )
    parser.add_argument(
        "--mode",
        choices=["daily", "weekly", "monthly"],
        default="daily",
        help="Hvilken rapport som skal lages (standard: daily)",
    )
    parser.add_argument(
        "--kilde",
        choices=["fmp", "yahoo", "fixtures"],
        help="Tving en bestemt datakilde. Uten dette velges første "
             "tilgjengelige. «fixtures» gir offline testdata.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skriv rapporten til investor/out/ i stedet for å sende e-post",
    )
    parser.add_argument(
        "--send-test",
        metavar="EPOST",
        help="Send rapporten til denne adressen uten å oppdatere historikken",
    )
    parser.add_argument(
        "--uten-screener",
        action="store_true",
        help="Hopp over screeningen (kun porteføljedelen)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Mer detaljert logging"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("Starter %s-rapport", args.mode)
    return kjor(
        args.mode,
        kildenavn=args.kilde,
        torrkjor=args.dry_run,
        test_mottaker=args.send_test,
        hopp_over_screener=args.uten_screener,
    )


if __name__ == "__main__":
    sys.exit(main())
