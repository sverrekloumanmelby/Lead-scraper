# Investeringsassistent

Overvåker selskapene du eier og leter etter nye kjøpskandidater blant
børsnoterte selskaper i USA, Europa og Norden. Sender resultatet på e-post i
tre nivåer med økende dybde.

Dette er et **eget prosjekt** i repoet, uavhengig av leadmaskinen i `src/`. De
deler ingen kode.

---

## Hva du får

| Rapport | Når | Innhold |
|---|---|---|
| **Daglig** | hverdager ~07:30 | Kort. Kun det som faktisk har skjedd: store kursbevegelser, resultater, viktige nyheter. Er det stille, sier e-posten det. |
| **Ukentlig** | mandager ~08:00 | Porteføljen samlet, ukens hendelser, og nye kjøpskandidater med tallfestet begrunnelse. |
| **Månedlig** | den 1. ~09:00 | Måneden i dybden per selskap, hva som er verdt å følge framover, utvidet kandidatliste — og en lærende gjennomgang av ett selskaps kvartalstall. |

Månedsrapportens læringsdel roterer gjennom porteføljen, slik at du over tid
lærer å lese kvartalsrapporter med tall fra selskaper du selv eier.

---

## Slik foreslås aksjer

Kravene er strenge med vilje. **Systemet foreslår heller ingenting enn noe
middelmådig** — en tom liste er et gyldig svar.

**Harde krav** (bryter selskapet ett av disse, forkastes det helt — det blir
ikke bare rangert lavere):

- Børsverdi minst 2 mrd USD, aksjekurs minst 10, og reell handelsvolum.
  Ingen penny stocks.
- Kun hovedbørser. Ingen OTC eller pink sheets.
- Minst 5 års børs- og regnskapshistorikk. Uetablerte selskaper foreslås ikke.
- Overskudd i minst 4 av de siste årene og positiv fri kontantstrøm i minst 3.
  Lønnsomhet over tid, ikke ett godt kvartal.
- Gjeldsgrad under 2,0.
- Lønnsomt akkurat nå (positiv P/E).

**Deretter** scores de gjenværende 0–100 på verdsettelse, kvalitet, vekst,
momentum og utbytte. Kun selskaper over terskelen (`SCORE_MIN_ANBEFALING`,
standard 60) kommer med.

**Til slutt** må systemet klare å skrive minst to *konkrete, tallfestede*
grunner — «prises til P/E 13,0», «fri kontantstrøm tilsvarer 7,5 % av
børsverdien», «overskudd i 9 av de siste 10 årene». Klarer det ikke det,
foreslås selskapet ikke. Ingen vage begrunnelser.

Alle terskler ligger øverst i [`config.py`](config.py) og kan justeres.

---

## Oppsett

### 1. Fyll inn porteføljen

Rediger [`portfolio.json`](portfolio.json). `MSFT`, `VRT` og `MOWI.OL` ligger
inne fra før. Den fjerde oppføringen har `"ticker": "BYTT_MEG"` — bytt den til
det faktiske symbolet for det medisinske holdingselskapet, eller slett
oppføringen. Systemet hopper over den og advarer så lenge den står.

Tickerformat: amerikanske aksjer bruker rent symbol (`MSFT`), Oslo Børs bruker
`.OL` (`MOWI.OL`), øvrige europeiske børser har egne suffiks (`.DE`, `.PA`,
`.L`, `.CO`, `.ST`).

`antall` og `kostpris` er valgfrie. Fyller du dem inn, regner rapportene ut
urealisert gevinst; ellers vises kun kursutvikling.

### 2. Lag et Gmail app-passord

Vanlig kontopassord virker ikke mot Gmails SMTP.

1. Slå på tofaktor på Google-kontoen (kreves for app-passord).
2. Gå til <https://myaccount.google.com/apppasswords>.
3. Lag et passord (navngi det f.eks. «Investeringsassistent»).
4. Kopier de 16 tegnene — de vises bare én gang.

### 3. Skaff en gratis API-nøkkel (anbefalt)

Systemet bruker Financial Modeling Prep som hovedkilde. Den dekker USA, Europa
og Oslo Børs, og henter hele screener-universet i ett kall.

Registrer deg gratis på
<https://site.financialmodelingprep.com/developer/docs> og kopier nøkkelen.

Uten nøkkel faller systemet tilbake på Yahoo Finance, som ikke krever noe —
men Yahoo struper forespørsler fra datasentre, så kjøringene i GitHub Actions
kan feile. Med nøkkel er leveringen pålitelig.

### 4. Legg inn repo-secrets

I GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Verdi | Påkrevd |
|---|---|---|
| `GMAIL_USER` | Gmail-adressen som sender | ja |
| `GMAIL_APP_PASSWORD` | De 16 tegnene fra steg 2 | ja |
| `MOTTAKER_EPOST` | Hvor rapporten skal sendes (utelates den, sendes den til deg selv) | nei |
| `FMP_API_KEY` | Nøkkelen fra steg 3 | nei, men anbefalt |

Det var alt. Workflowen kjører deretter av seg selv.

---

## Kjøre lokalt

```bash
pip install -r investor/requirements.txt

# Bygg en rapport uten å sende noe — havner i investor/out/
python -m investor.main --mode weekly --dry-run

# Uten nettverk eller API-nøkkel, med innebygde testdata
python -m investor.main --mode monthly --kilde fixtures --dry-run

# Send en ekte testmail
export GMAIL_USER="deg@gmail.com"
export GMAIL_APP_PASSWORD="16-tegns-app-passord"
python -m investor.main --mode daily --send-test deg@gmail.com
```

`--send-test` oppdaterer ikke historikken, så du kan teste fritt.

### Valg

| Flagg | Betydning |
|---|---|
| `--mode {daily,weekly,monthly}` | Hvilken rapport |
| `--kilde {fmp,yahoo,fixtures}` | Tving en datakilde (standard: første tilgjengelige) |
| `--dry-run` | Skriv til `investor/out/` i stedet for å sende |
| `--send-test EPOST` | Send til denne adressen uten å røre historikken |
| `--uten-screener` | Hopp over screeningen |
| `-v` | Mer detaljert logging |

### Manuell kjøring i GitHub

**Actions → Investeringsassistent → Run workflow**, velg rapporttype. Kryss av
for `dry_run` for å bygge rapporten uten å sende e-post — resultatet lastes opp
som artefakt på kjøringen.

---

## Hvordan det henger sammen

```
main.py              CLI og orkestrering
├── kilder/          datakilder bak ett felles grensesnitt
│   ├── fmp.py       Financial Modeling Prep (hovedkilde)
│   ├── yahoo.py     Yahoo Finance (reserve, ingen nøkkel)
│   └── fixtures.py  offline testdata
├── monitor.py       porteføljestatus og hendelsesdeteksjon
├── screener.py      harde kvalitetskrav, scoring og begrunnelser
├── laering.py       månedens gjennomgang av kvartalstall
├── report.py        bygger HTML og ren tekst
├── email_send.py    Gmail SMTP
├── state.py         historikk mellom kjøringer
├── config.py        alle terskler og vekter
└── templates/       e-postmaler (jinja2)
```

`data/state.json` holder øyeblikksbilder mellom kjøringene, slik at rapportene
kan si hva som er *nytt* siden sist. Containeren i GitHub Actions er flyktig,
så filen committes tilbake etter hver kjøring.

---

## Justere hvor strengt det skal være

I `config.py`:

- **Færre og bedre forslag:** øk `SCORE_MIN_ANBEFALING` (60 → 70).
- **Kun store selskaper:** øk `MIN_BORSVERDI`.
- **Mindre støy daglig:** øk `KURSBEVEGELSE_MIDDELS` (3,0 %) eller sett
  `DAGLIG_MIN_VIKTIGHET = VIKTIGHET_HOY`.
- **Andre børser:** rediger `TILLATTE_BORSER`.
- **Vektlegge annerledes:** juster `SCORE_VEKTER` (f.eks. mer vekt på
  `verdsettelse` hvis du er verdiorientert).

---

## Merk

Rapportene er automatisk genererte og er **ikke investeringsrådgivning**.
Tallene kommer fra offentlige kilder og kan inneholde feil eller være
forsinkede. Kontroller alltid mot selskapets egen rapportering før du handler.
