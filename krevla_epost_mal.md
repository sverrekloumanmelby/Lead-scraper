# Krevla – e-postmal (kald henvendelse til meglerkontor)

De ferdig personaliserte mailene ligger i **`krevla_eposter.csv`** (kolonnen
`melding`, én rad per kontor). Lim inn i e-postklienten din, eller bruk CSV-en
til mailfletting. Under er malen de er bygget på.

---

## ⚠️ Bekreft dette først

Avsnitt 2 beskriver **hva Krevla leverer**. Det er min tolkning (AI-chat for
meglernettsider) fordi jeg ikke fant noen CLAUDE.md eller lagret beskrivelse av
Krevla. **Rett teksten så den stemmer med det dere faktisk leverer** – gjør det
her i malen, så oppdaterer jeg alle radene i CSV-en på nytt hvis du vil.

Bytt også ut `[DITT NAVN]` og `[TELEFON / NETTSIDE]`.

---

## Emne
> Flere av nettbesøkene deres blir til verdivurderinger

## Melding

```
Hei {{fornavn}},

Jeg tar kontakt fordi {{firma}} er et selvstendig meglerkontor – nettopp de
vi jobber best med i Krevla.

Vi leverer en AI-drevet kundedialog (chat) som ligger på nettsiden deres og
svarer boligkjøpere og potensielle oppdragsgivere døgnet rundt. Den fanger opp
besøkende som ellers hadde klikket videre, kvalifiserer dem og booker
verdivurderinger rett inn – så flere av nettbesøkene blir til reelle oppdrag,
uten at dere må bemanne en chat selv.

Har du 15 minutter til en uforpliktende prat om hvordan dette kan se ut for
{{firma}}?

Mvh
[DITT NAVN]
Krevla
[TELEFON / NETTSIDE]
```

## Flettefelt
- `{{fornavn}}` – daglig leders fornavn (kolonne `til_navn` i CSV)
- `{{firma}}` – kontornavn (kolonne `firma`)

## Tips
- Sjekk `merknad`-kolonnen per rad. «Generell kontoradresse» betyr at mailen
  går til felles-innboks – behold hilsenen til daglig leder likevel.
- Hold første setning kontor-spesifikk («selvstendig meglerkontor») – det er
  det som skiller dere fra en generisk masseutsendelse.
- Vurder én oppfølgingsmail etter 4–5 dager hvis ingen respons.
