# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A lead-generation pipeline ("leadmaskin") that finds small, independent real-estate brokerage offices in Norway, checks their websites for chatbot widgets, looks up the managing director's phone number, scores each office 0–100, and writes the result to a sorted `leads.csv`.

## Language convention

**All code, comments, docstrings, log messages, and commit messages are in Norwegian.** Identifiers use Norwegian words (e.g. `hent_enheter`, `slaa_opp_telefon`, `er_kjede`, `skriv_leads`). Follow this convention for all new code — do not introduce English identifiers or comments.

## Commands

```bash
# Setup
pip install -r requirements.txt
python -m playwright install chromium   # not needed where Chromium is pre-installed (see browser_util.py)

# Run (whole country, all 15 counties, output leads.csv)
python -m src.main

# Limit to specific counties (names must match keys in config.REGIONER)
python -m src.main --regioner Oslo Akershus Buskerud

# Skip Proff.no and use only the Brreg registry (faster, fewer fields)
python -m src.main --kilde brreg

# Custom output file
python -m src.main --utfil mine_leads.csv
```

There are no tests, linters, or build steps configured. Verify changes by running the pipeline (a small `--regioner` selection with `--kilde brreg` is the fastest end-to-end check).

## Architecture

`src/main.py` is the orchestrator; `kjor()` runs a five-stage pipeline:

1. **Fetch base data** — primary source is `src/proff.py` (Playwright scraper for Proff.no). If Proff blocks (captcha/403/429) it raises `ProffBlokkert` and `main.py` falls back to `src/brreg.py` (Brønnøysund open API, no key required — one nationwide paginated query filtered locally by county prefix). Both sources normalize into the same lead dict shape (`firmanavn`, `antall_ansatte`, `daglig_leder`, `nettside`, `by`, `telefon`, `epost`, `kilde`, …).
2. **Pre-filter** — employee-count groups and chain exclusion (`src/scoring.py: passer_ansatt_filter`, `er_kjede`) run *before* any website visits to keep network load down. Chains are matched both by name regex and by exact website-domain match (franchise offices often have neutral AS names but the chain's website).
3. **Chatbot check** — `src/chat_detector.py` loads each lead's website in Playwright and matches known widget signatures against the HTML plus all loaded resource URLs. Parallelized with a few threads in `main.py`; each thread gets its own Playwright instance because the sync API is not thread-safe.
4. **DL phone lookup** — `src/dl_telefon.py` searches 1881.no for the managing director's number, sequentially with built-in pauses.
5. **Score & write** — `src/scoring.py` computes score (+30 employee fit, +40 no chatbot, +30 independent) and priority (HØY/MIDDELS/LAV); `src/csv_writer.py` writes rows sorted by score. When Brreg is the source, the managing director's name comes from a separate role-API lookup done only for leads that pass the pre-filter.

All tunables live in `src/config.py`: county list with Brreg county-number prefixes, chain name patterns and domains, chatbot signatures, employee groups, pause lengths, score thresholds, default output file. New chatbot widgets or excluded chains should be added there, not hardcoded elsewhere.

## Key constraints

- **Be gentle with external services.** Deliberate randomized pauses exist between requests: 3–5 s for Proff.no (`PROFF_PAUSE_*`), 2–3.5 s for 1881.no (`KATALOG_PAUSE_*`), 0.3 s between Brreg role lookups. Do not remove or shorten these.
- **Blocking detection is conservative** (`proff.py: _sjekk_blokkering`): a page counts as blocked only when expected content is missing *and* a block keyword appears, because words like "captcha" occur in legitimate pages.
- **Browser launch always goes through `src/browser_util.py: launch_argumenter()`.** It handles a pre-installed Chromium path (`/opt/pw-browsers/chromium`, overridable via `CHROMIUM_EXECUTABLE`), explicit proxy settings from `HTTPS_PROXY`, and a TLS 1.2 workaround when running behind the agent proxy (`CCR_AGENT_PROXY_ENABLED=1`). Never call `pw.chromium.launch()` with ad-hoc arguments.
- `leads.csv` is in `.gitignore` but a finished result set has been committed deliberately (force-added). Don't commit new runs unless the deliverable is an updated lead list.
- CSV columns are fixed in `csv_writer.FELTER`; list values (`chatbot_navn`) are joined with `;` for CSV friendliness.
