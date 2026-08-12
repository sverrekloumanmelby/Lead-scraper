# Krevla – lead-liste eiendomsmeglerkontorer

Komplett, prioritert lead-liste over eiendomsmeglerkontorer i Norge (3–50
ansatte), bygget for Krevla. Kilde: Brønnøysundregistrenes åpne API
(autoritativt) + web-verifisering av kjede/uavhengig-status og kontaktinfo.

## ⚠️ Bekreft Krevla-teksten før utsending

Det finnes **ingen CLAUDE.md** eller lagret beskrivelse av Krevla noe sted
(hele disken søkt – «Krevla» finnes bare i denne samtalen). E-postteksten er
bygget på tolkning av `README.md` + scoringen: at Krevla leverer en **AI-drevet
kundedialog/chat for meglernettsider**. **Rett dette i `krevla_epost_mal.md`**
hvis det ikke stemmer.

## Filene

| Fil | Innhold | Antall |
|-----|---------|--------|
| `krevla_alle_kontorer.csv` | **Hovedleveransen.** ALLE kontorer, prioritert, hver med kontaktperson (daglig leder). Kolonner: prioritet, type, kjede, firmanavn, ansatte, daglig_leder, epost, telefon, nettside, poststed, orgnr, web_sjekket | **254** |
| `krevla_eposter.csv` | Klar-til-send: uavhengige kontorer med verifisert e-post + ferdig personalisert mail | **16** |
| `krevla_telefon.csv` | Uavhengige/uavklarte med telefon (ingen e-post ennå) | **13** |

## Prioritetsrekkefølge (kolonnen `prioritet`)

1. **Uavhengig 3-15** ← høyest prioritet
2. **Uavhengig 16-50**
3. **Uavklart 3-15** (ikke web-verifisert ennå)
4. **Uavklart 16-50**
5. **Kjede 3-15** (nedprioritert, men med – med kontaktperson)
6. **Kjede 16-50** (nedprioritert)

Fordeling nå: 26 uavhengige · 115 uavklarte · 113 kjede.
Av alle 254 har **69 en e-postadresse** (16 uavhengige + 53 kjede) og 97 telefon.

## Hvorfor «kun» 26 uavhengige av ~780 kontorer

Norge har ~780 meglerforetak, men det **store flertallet er kjede-/franchise-
kontorer** (DNB, EiendomsMegler 1, Aktiv, PrivatMegleren, EIE, Nordvik, Notar,
Krogsveen, Partners m.fl.). Mange skjuler kjedetilhørigheten bak et lokalt
AS-navn i Brreg – f.eks.:

- *Vinderen Eiendomsmegling AS* = EIE · *Innlandet Eiendomsmegling AS* = EIE
- *Halden Boligsenter AS* = DNB · *Kvartal Eiendomsmegling AS* = PrivatMegleren
- *De Presno & Partnere* = Aktiv · *Skog Eiendomsmegling* = Nordvik

Navnemønsteret «[Navn] & Partnere/Partners» er nesten alltid en kjede
(PrivatMegleren/Partners/Aktiv). Kjedetilhørighet avsløres først ved web-oppslag
per kontor – 44 kontorer er så langt manuelt web-verifisert (kolonnen
`web_sjekket = ja`); resten (uavklart) er klassifisert på navn/domene og bør
dobbeltsjekkes før de flyttes opp fra «uavklart».

## Kvalitetssikring

- **Kontaktperson:** daglig leder fra Brregs rolle-API (offisielt registrert).
- **E-post i send-lista:** kun verifisert (Brreg-registrert eller bekreftet på
  kontorets egen nettside). Skrapede/usikre adresser er holdt utenfor.
- **Kjeder:** luket ut av send-lista (pitchen «selvstendig kontor» passer ikke),
  men beholdt i hovedlista med kontaktperson og markert med kjedenavn.

## Videre arbeid (hvis ønsket)

De 115 «uavklarte» kan web-verifiseres videre for å (a) flytte ekte uavhengige
opp og (b) finne e-post. Erfaringen så langt: ~75–90 % av de uavklarte viser seg
å være kjedekontorer, så antallet *nye ekte uavhengige* vokser sakte.

## Reprodusere

```bash
python3 hent_kontorer.py   # Brreg: enheter 5-50 ansatte + daglig leder
python3 bygg_master.py     # klassifiser + prioriter + skriv alle CSV-ene
# web_overrides.json holder de web-verifiserte kjede/uavhengig-avgjørelsene
```
