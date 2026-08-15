# Leadmaskin – eiendomsmegling

Finner små, uavhengige eiendomsmeglerkontorer i Norge, sjekker om nettsiden
deres allerede har en chatbot, og peker ut hvem på kontoret som er rett
person å kontakte om AI-chatbot.

## Hva den gjør

1. Henter alle foretak med næringskode `68.310` (eiendomsmegling) fra
   **Enhetsregisteret**.
2. Beholder kontorer med **3–20 ansatte** — kjernemålet er 3–15, og
   toleransen på ±5 tas ut oppover. Konkurs og selskaper under avvikling
   luker vi bort.
3. Luker ut **kjedekontorer** (DNB Eiendom, EiendomsMegler 1, Aktiv,
   PrivatMegleren, Krogsveen) både på navn og på nettside-domene, siden en
   franchisefilial sjelden kjøper verktøy selv.
4. **Finner nettsiden** til hvert kontor: registrert hjemmeside i Brreg,
   ellers domenegjetting ut fra firmanavnet, ellers oppslag i 1881.
5. **Sjekker etter chat-widget** — først i rå HTML, deretter ved å rendre
   siden i Chromium, som fanger widgets lastet via Google Tag Manager.
6. **Finner kontaktpersonen** ved å lese kontorets egne «om oss»- og
   «ansatte»-sider, og rangere de ansatte etter hvem som er rett inngang.
7. Scorer og sorterer leadene, og skriver både `leads.csv` og `leads.md`.

## De to viktigste designvalgene

**AI-chatbot skilles fra bemannet live-chat.** Et kontor med Kindly eller
boost.ai er allerede dekket og scorer lavt. Et kontor med bemannet LiveChat
scorer *høyest* av alle: de har allerede bestemt at chat er riktig kanal og
betaler i dag med bemanning, så veien til et salg er kort.

**«Fant ingen chatbot» og «fant ingen nettside» er ikke det samme.**
Kontorer vi ikke fant nettside for havner i kategorien `ukjent`, ikke blant
dem uten chatbot. Ellers ville lista påstått noe vi ikke har sjekket.

## Verifisering av nettsider

Domenegjetting alene gir mange falske treff — `kursiv.no` er et grafisk
byrå, ikke Kursiv Eiendomsmegling, og `valkyrien.no` er et kjøpesenter.
Derfor godtas et domene bare når organisasjonsnummeret står på siden,
domenet er bygget av foretakets egne navneord, eller navnet står i
tittel/overskrift *og* siden handler om eiendomsmegling. Portaler som
finn.no og eiendomspriser.no avvises alltid.

Tilsvarende for kontaktpersoner: et navn forkastes hvis det inneholder ord
som ikke finnes i personnavn (`Om Partners`, `Coop Obs Bygg`), eller hvis
det bare er firmanavnet igjen. En e-post knyttes til en person først når
lokaldelen faktisk matcher navnet — ellers blir den stående som firmapost.

## Installasjon

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Kjøring

```bash
python -m src.main                      # hele landet
python -m src.main --maks 25            # testkjøring
python -m src.main --uten-nettleser     # raskere, mindre presist
python -m src.main --utfil mine.csv     # egen utfil
```

## Struktur

```
src/
  config.py          # næringskode, kjeder, chatbot-signaturer, ansattgrupper
  brreg.py           # Enhetsregisteret: foretak og daglig leder
  nettside_finder.py # finner og verifiserer foretakets nettside
  chat_detector.py   # chat-widgets i rå HTML og i rendret side
  kontaktperson.py   # ansatte fra nettsiden + valg av rett kontakt
  scoring.py         # filtrering, score og prioritet
  csv_writer.py      # CSV-eksport
  rapport.py         # lesbar markdown-liste
  main.py            # orkestrator/CLI
```

## Merk

- Rekkevidden er begrenset av at bare rundt hvert femte foretak har
  hjemmeside registrert i Brreg. Resten avhenger av navnegjetting, så en
  del kontorer blir stående uten nettside og med `ukjent` chat-status.
- Chatbot-listen i `config.py` er ikke uttømmende — legg til flere
  signaturer etter behov.
- Sjekk vilkårene til 1881.no før kjøring i stort volum.
