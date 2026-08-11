# Krevla – lead-liste eiendomsmeglerkontorer

Oppdatert lead-liste over **uavhengige** eiendomsmeglerkontorer i Norge,
bygget for Krevla. Kilde: Brønnøysundregistrenes åpne API (autoritativt).

## ⚠️ To ting du må vite før du sender

1. **Det finnes ingen CLAUDE.md** i dette repoet, og ingen lagret beskrivelse
   av Krevla noe sted på maskinen (jeg søkte hele disken – «Krevla» finnes bare
   i denne samtalen). E-postteksten er derfor bygget på min tolkning av
   `README.md` og scoringen: at Krevla leverer en **AI-drevet kundedialog/chat
   for meglernettsider**. **Bekreft eller rett dette avsnittet** i
   `krevla_epost_mal.md` før utsending, så info om hva dere leverer blir riktig.

2. **150 «klare til e-post»-kontorer finnes ikke i åpne registre.** Av 326
   meglerselskaper (5–50 ansatte) er bare et mindretall både (a) uavhengige,
   (b) residensielle boligmeglere og (c) har verifiserbar kontaktinfo. Jeg har
   prioritert at info er **riktig** (ditt uttrykte krav) framfor å nå et tall
   med gjettede adresser. Se «Hvorfor ikke 150» nederst.

## Hva du får (tre filer)

| Fil | Innhold | Antall |
|-----|---------|--------|
| `krevla_eposter.csv` | **Klar til å sende** – e-post, daglig leder, ferdig personalisert mail + merknad | **16** (13 HØY / 3 MIDDELS) |
| `krevla_telefon.csv` | Uavhengige kontorer med daglig leder + telefon (mangler e-post i Brreg – ring, eller finn e-post på nettsiden) | **26** (16 HØY / 10 MIDDELS) |
| `leads_krevla.csv` | Full liste over alle kontaktbare uavhengige kontorer (e-post ELLER telefon) | **42** |

Til sammen **42 kontaktbare uavhengige boligmeglerkontorer** med korrekt,
navngitt daglig leder.

## Slik er listen kvalitetssikret

- **Kontaktperson:** daglig leder er hentet fra Brregs rolle-API – den
  offisielt registrerte DAGL-rollen. Det er personen du bør kontakte.
- **E-post:** kun **Brreg-registrert** e-post er tatt med i send-lista.
  Skrapede e-poster fra nettsider ble forkastet fordi de viste seg upålitelige
  (feil person / avkuttede adresser). Hver rad har en `merknad`-kolonne:
  «matcher daglig leder» / «generell kontoradresse» / «sjekk».
- **Uavhengige:** kjeder/franchise er luket ut i flere runder – både på navn,
  nettside-domene OG e-post-domene (mange kjedekontorer skjuler seg bak et
  lokalt AS-navn, f.eks. *Vinderen Eiendomsmegling AS* = EIE, *Halden
  Boligsenter AS* = DNB). 67 kjede-/kommersielle selskaper ble fjernet.
- **Residensielle:** ren **næringsmegling** (kommersiell) og rene
  **oppgjørs-/back-office-selskaper** er ekskludert – de betjener ikke
  boligkjøpere på nett og passer ikke pitchen.

### Merk før utsending
- `FOSS & CO EIENDOMSMEGLING AS`: Brreg-e-posten `kolbn@fossco.no` ser ut som
  en skrivefeil (trolig `kolbotn@fossco.no`), og Foss & Co er et regionalt
  kjedekontor. Dobbeltsjekk eller dropp.
- «Generell kontoradresse» (post@…): mailen når kontorets felles-innboks –
  behold hilsenen til daglig leder i teksten.

## Ansattgrupper (prioritet)

- **HØY = 3–15 ansatte.** NB: Brreg tillater av personvernhensyn ikke søk på
  1–4 ansatte, så gruppen dekkes som **5–15**. Kontorer med 3–4 ansatte kan
  altså mangle her.
- **MIDDELS = 16–50 ansatte.**

## Hvorfor ikke 150

Av 254 uavhengige kontorer (5–50 ansatte) hadde bare **102** noen kontaktkanal
registrert i Brreg; 152 hadde verken e-post, telefon eller nettside (typisk
små/passive AS). Etter å ha fjernet kjeder-i-forkledning, næringsmegling og
oppgjørsselskaper står 42 kontaktbare, residensielle, uavhengige kontorer igjen
– hvorav 16 med pålitelig e-post. Å nå 150 ville kreve manuelt websøk per
kontor, og erfaringen fra dette arbeidet er at et flertall av de gjenværende da
viser seg å være kjedekontorer eller inaktive selskaper.

**Neste steg hvis du vil ha flere e-poster:** jeg kan ta de 26 telefon-klare
(alle bekreftet uavhengige og aktive) og gjøre målrettet websøk for å finne
verifisert e-post til hver – det løfter e-post-lista mot ~40. Si fra, så kjører
jeg det.

## Reprodusere

```bash
python3 hent_kontorer.py     # henter enheter + daglig leder fra Brreg
python3 berik_epost.py       # (valgfritt) skraper nettsider for e-post
python3 bygg_leadliste.py    # filtrerer kjeder/næring og bygger CSV-ene
```
