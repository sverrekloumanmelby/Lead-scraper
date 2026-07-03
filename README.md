# Leadmaskin – eiendomsmegling

Enkel pipeline som finner små, uavhengige eiendomsmeglerkontorer i Norge og
scorer dem etter hvor gode salgsleads de er.

## Hva den gjør

1. Søker på **Proff.no** etter bransjen `eiendomsmegling` i valgte regioner.
2. Trekker ut firmanavn, daglig leder, telefon, e-post, antall ansatte,
   by og nettside-URL for hvert foretak.
3. Filtrerer bort kontorer med færre enn 3 eller flere enn 15 ansatte.
4. Ekskluderer store kjeder (DNB Eiendom, EiendomsMegler 1, Aktiv,
   PrivatMegleren, Krogsveen).
5. Besøker nettsiden til hvert kontor og ser etter kjente chatbot-widgets
   (Intercom, Drift, Tidio, Botpress, Kindly, boost.ai m.fl.).
6. Scorer hvert kontor 0–100:
   - `+30` for 3–15 ansatte
   - `+40` hvis nettsiden ikke har chatbot
   - `+30` hvis kontoret er uavhengig
7. Lagrer alt i `leads.csv` sortert etter score med kolonnen `prioritet`
   (HØY / MIDDELS / LAV).

## Skånsomt mot Proff.no

- 3–5 sekunders tilfeldig pause mellom hver forespørsel til Proff.no.
- Ved blokkering (captcha/403/429) faller pipeline automatisk over til
  **Brønnøysundregistrenes åpne API** for grunndata, og fortsetter
  nettside-sjekken derfra.

## Installasjon

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Kjøring

Standard er hele landet (alle 15 fylker):

```bash
python -m src.main
```

Begrens til utvalgte fylker:

```bash
python -m src.main --regioner Oslo Akershus Buskerud Østfold
```

Utfil:

```bash
python -m src.main --utfil mine_leads.csv
```

## Struktur

```
src/
  config.py        # regioner, kjeder, chatbot-signaturer, tersker
  brreg.py         # fallback via Brønnøysundregistrenes åpne API
  proff.py         # Playwright-scraper for Proff.no
  chat_detector.py # laster nettsider og speider etter chatbot-scripts
  scoring.py       # filtrering + poengberegning + prioritet
  csv_writer.py    # CSV-eksport
  main.py          # orkestrator/CLI
```

## Merk

- Sjekk at bruken av Proff.no er i tråd med deres vilkår før du kjører
  ved høyt volum.
- Chatbot-listen i `config.py` er ikke uttømmende — legg gjerne til flere
  signaturer etter behov.
