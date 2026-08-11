"""Stram kjedefilter og bygg endelige leveranser for Krevla.

- Fjerner kjedekontorer som skjuler seg bak lokalt AS-navn ved å sjekke
  e-post- OG nettside-domener mot kjededomener, samt kjente kjede-orgnr
  verifisert via websøk.
- Skriver leads_krevla.csv (hovedliste) og krevla_eposter.csv (klar-til-send
  mailfletting) - kun kontorer med bekreftet uavhengig-signal og korrekt DL.
"""
import csv
import json
import re

# Domener som tilhører nasjonale kjeder/franchise -> IKKE uavhengig.
KJEDE_DOMENER = [
    "dnbeiendom.no", "dnb-eiendom.no", "eiendomsmegler1.no", "em1.no",
    "aktiv.no", "aktiveiendom.no", "privatmegleren.no", "krogsveen.no",
    "nordvikbolig.no", "nordvik.no", "notar.no", "sormegleren.no", "eie.no",
    "garanti.no", "proaktiv.no", "proaktiveiendom.no",
    "heimdaleiendomsmegling.no", "partners.no", "mollerpartners.no",
    "meglerhuset.no", "exbo.no", "sparebank1.no", "moremegling.no",
    "eiendomsmegler24.no", "utleiemegleren.no", "megler-forum.no",
    "terraeiendom.no", "colliers.no", "schalapartners.no", "gobb.no",
    "attentuseiendom.no", "homeeiendom.no", "postbanken.no",
]

# Firmatyper som IKKE passer pitchen (kommersiell næringsmegling / rene
# oppgjørs-/back-office-selskaper som ikke betjener boligkjøpere på nett).
EKSKLUDER_NAVN = re.compile(
    r"næringsmegl|naeringsmegl|næringseiendom|corporate real estate|"
    r"property advisor|leietaker|oppgjør|advokat|advisor|"
    r"\bmalling\b|akershus eiendom|\butleie\b", re.I)
# Kjede-orgnr bekreftet via websøk (lokalt AS-navn, men driver kjedekontor).
KJEDE_ORGNR = {
    "990451613",  # Halden Boligsenter -> DNB Eiendom
    "979870167",  # Valdres Eiendomskontor -> Aktiv
    "889665742",  # Vinderen Eiendomsmegling -> EIE
    "996534235",  # Brustad & Partnere -> PrivatMegleren
    "896306782",  # Soria Moria -> PrivatMegleren
    "983266584",  # Nordmøre Eiendomsmegling -> Notar
    "980407551",  # Meglerhuset Leinæs -> Partners
}
KJEDE_NAVN = re.compile(
    r"privatmegler|\bnotar\b|\beie\b|krogsveen|\bnordvik\b|sørmegler|"
    r"garanti eiendom|proaktiv|\bdnb\b|eiendomsmegler\s*1|\bem1\b|"
    r"& partners|og partners|partners\b", re.I)


def domene(s):
    s = (s or "").lower()
    s = re.sub(r"\s+", "", s)  # fjern mellomrom, f.eks. "aktiv. no"
    s = re.sub(r"^https?://", "", s).lstrip("www.").split("/")[0]
    return s


def er_kjede(k):
    if k["orgnr"] in KJEDE_ORGNR:
        return True
    if EKSKLUDER_NAVN.search(k.get("firmanavn", "")):
        return True
    for felt in (k.get("hjemmeside", ""), k.get("epost", "")):
        d = domene(felt.split("@")[-1] if "@" in felt else felt)
        for kd in KJEDE_DOMENER:
            if d == kd or d.endswith("." + kd):
                return True
    return False


def fornavn(navn):
    return navn.split()[0] if navn else ""


# ---- Krevla-verdiforslag (BEKREFT: bygget på README + scoring, ingen CLAUDE.md) ----
EMNE = "Flere av nettbesøkene deres blir til verdivurderinger"


def epost_tekst(k):
    fn = fornavn(k["daglig_leder"])
    firma = k["firmanavn"].title().replace(" As", " AS")
    hei = f"Hei {fn}," if fn else "Hei,"
    return (
        f"{hei}\n\n"
        f"Jeg tar kontakt fordi {firma} er et selvstendig meglerkontor – "
        f"nettopp de vi jobber best med i Krevla.\n\n"
        f"Vi leverer en AI-drevet kundedialog (chat) som ligger på nettsiden "
        f"deres og svarer boligkjøpere og potensielle oppdragsgivere døgnet "
        f"rundt. Den fanger opp besøkende som ellers hadde klikket videre, "
        f"kvalifiserer dem og booker verdivurderinger rett inn – så flere av "
        f"nettbesøkene blir til reelle oppdrag, uten at dere må bemanne en "
        f"chat selv.\n\n"
        f"Har du 15 minutter til en uforpliktende prat om hvordan dette "
        f"kan se ut for {firma}?\n\n"
        f"Mvh\n[DITT NAVN]\nKrevla\n[TELEFON / NETTSIDE]"
    )


def main():
    kontorer = json.load(open("scratch_kontorer.json"))
    uavh, kjede = [], []
    for k in kontorer:
        (kjede if er_kjede(k) else uavh).append(k)

    # sorter HØY (3-15) først, deretter etter antall ansatte
    uavh.sort(key=lambda k: (0 if k["antall_ansatte"] <= 15 else 1,
                             k["antall_ansatte"], k["firmanavn"]))

    # Kun Brreg-registrert e-post regnes som pålitelig nok til utsending.
    for k in uavh:
        k["epost_sikker"] = k["epost"] if k.get("epost_kilde") == "brreg" else ""

    def kanal(k):
        if k["epost_sikker"]:
            return "e-post + telefon" if k["kontakt_telefon"] else "e-post"
        return "telefon" if k["kontakt_telefon"] else "kun daglig leder"

    # Hovedliste: alle uavhengige som er kontaktbare (sikker e-post eller telefon)
    kontaktbare = [k for k in uavh if k["epost_sikker"] or k["kontakt_telefon"]]

    with open("leads_krevla.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["prioritet", "firmanavn", "antall_ansatte", "daglig_leder",
                    "epost", "telefon", "nettside", "poststed",
                    "kommune", "orgnr", "kontaktbar_via"])
        for k in kontaktbare:
            w.writerow([k["prioritet"], k["firmanavn"], k["antall_ansatte"],
                        k["daglig_leder"], k["epost_sikker"],
                        k["kontakt_telefon"], k["hjemmeside"], k["poststed"],
                        k["kommune"], k["orgnr"], kanal(k)])

    # Mailfletting: kun de med PÅLITELIG e-post (Brreg-registrert) + daglig leder.
    # Nettside-skrapede e-poster droppes til send-lista fordi de viste seg
    # upålitelige (feil person / avkuttet adresse).
    epost_klar = [k for k in kontaktbare
                  if k["epost_sikker"] and k["daglig_leder"]]

    def merknad(k):
        if k["orgnr"] == "937205139":  # Foss & Co
            return ("Brreg-e-post ser ut som skrivefeil (kolbn -> kolbotn?) "
                    "OG Foss & Co er et regionalt kjedekontor - dobbeltsjekk")
        etter = k["daglig_leder"].split()[-1].lower()
        lokal = k["epost_sikker"].split("@")[0].lower()
        if lokal.startswith(("post", "firmapost", "kontakt", "hei", "mail",
                             "salg", "eiendom", "oppgjor", "gl", "jhs")):
            return "Generell kontoradresse - merk mailen til daglig leder"
        if etter[:4] not in lokal and k["daglig_leder"].split()[0].lower()[:4] not in lokal:
            return "E-post ser ut til å gå til en annen enn daglig leder - sjekk"
        return "E-post matcher daglig leder"

    with open("krevla_eposter.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["til_epost", "til_navn", "firma", "poststed", "prioritet",
                    "emne", "melding", "merknad"])
        for k in epost_klar:
            w.writerow([k["epost_sikker"], k["daglig_leder"], k["firmanavn"],
                        k["poststed"], k["prioritet"], EMNE, epost_tekst(k),
                        merknad(k)])

    # Telefon-klar tier (uavhengige, DL + telefon, ingen sikker e-post)
    tlf_klar = [k for k in kontaktbare if not k["epost_sikker"]
                and k["kontakt_telefon"] and k["daglig_leder"]]
    tlf_klar.sort(key=lambda k: (0 if k["antall_ansatte"] <= 15 else 1,
                                 k["antall_ansatte"]))
    with open("krevla_telefon.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["prioritet", "firmanavn", "antall_ansatte", "daglig_leder",
                    "telefon", "nettside", "poststed", "orgnr"])
        for k in tlf_klar:
            w.writerow([k["prioritet"], k["firmanavn"], k["antall_ansatte"],
                        k["daglig_leder"], k["kontakt_telefon"],
                        k["hjemmeside"], k["poststed"], k["orgnr"]])

    print(f"Uavhengige kontorer:        {len(uavh)}")
    print(f"  herav kontaktbare:        {len(kontaktbare)}")
    print(f"  herav e-post-klar:        {len(epost_klar)}")
    print(f"    HØY 3-15:               {sum(1 for k in epost_klar if k['antall_ansatte']<=15)}")
    print(f"    MIDDELS 16-50:          {sum(1 for k in epost_klar if k['antall_ansatte']>15)}")
    print(f"Fjernet som kjede/franchise:{len(kjede)}")
    print("  eksempler fjernet:", ", ".join(k["firmanavn"] for k in kjede[:8]))
    # telefon-only tier
    tlf_only = [k for k in kontaktbare if not k["epost"]]
    print(f"Telefon-klar (uten e-post): {len(tlf_only)}")


if __name__ == "__main__":
    main()
