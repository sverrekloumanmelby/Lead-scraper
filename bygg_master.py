"""Bygg komplett masterliste for Krevla: ALLE kontorer, kjeder nedprioritert,
alltid med kontaktperson (daglig leder). Grundig web-verifisering legges inn
via web_overrides.json etterhvert som kontorer sjekkes.

Prioritet (synkende):
  1  Uavhengig 3-15 ansatte
  2  Uavhengig 16-50
  3  Uavklart 3-15   (ikke web-sjekket ennå)
  4  Uavklart 16-50
  5  Kjede 3-15      (nedprioritert)
  6  Kjede 16-50
"""
import csv
import json
import re

# Åpenbare kjeder gjenkjent på navn/domene (rask grovsortering før web-sjekk).
KJEDE_DOMENER = [
    "dnbeiendom.no", "dnb-eiendom.no", "eiendomsmegler1.no", "em1.no",
    "em1fjellmegleren.no", "aktiv.no", "aktiveiendom.no", "privatmegleren.no",
    "krogsveen.no", "nordvikbolig.no", "nordvik.no", "notar.no",
    "sormegleren.no", "eie.no", "garanti.no", "proaktiv.no",
    "proaktiveiendom.no", "partners.no", "mollerpartners.no", "exbo.no",
    "moremegling.no", "utleiemegleren.no", "terraeiendom.no", "colliers.no",
    "schalapartners.no", "gobb.no", "attentuseiendom.no", "homeeiendom.no",
    "postbanken.no", "megler-forum.no", "fossco.no", "tigereiendom.no",
]
KJEDE_NAVN = re.compile(
    r"\bdnb\b|eiendomsmegler\s*1|\bem1\b|^aktiv\b|aktiv eiendomsmegling|"
    r"privatmegler|krogsveen|\bnordvik\b|\bnotar\b|sørmegler|garanti eiendom|"
    r"proaktiv|\beie\b|re/?max|\battentus\b|^pm\s|"
    # "[Navn] & Partner(e/s/ne)" er kjede-navnekonvensjon (PrivatMegleren,
    # Partners, Aktiv). Web-verifisert: ~90% er kjede. Nedprioriteres.
    r"&\s*partner(e|s|ne|ere)?\b|^ask\s", re.I)
# Store næringsmeglere / kommersielle kjeder (regnes som "kjede"/nedprioritert
# fordi de ikke er uavhengige boligmeglere).
# Off-target for Krevlas boligsalg-pitch: næringsmegling, oppgjør, utleie.
NARING = re.compile(
    r"næringsmegl|naeringsmegl|næringseiendom|corporate real estate|"
    r"property advisor|leietaker|\bmalling\b|colliers|cushman|newsec|"
    r"akershus eiendom|union norsk|realkapital|"
    r"\butleie\b|boligutleie|eiendomsoppgj|oppgjør|oppgjor", re.I)


def domene(s):
    s = re.sub(r"\s+", "", (s or "").lower())
    s = re.sub(r"^https?://", "", s).lstrip("www.").split("/")[0]
    return s


def grov_type(k):
    """Grovsortering uten web: kjede | uavklart. (uavhengig krever positivt
    signal: eget domene, eller web-verifisering.)"""
    navn = k.get("firmanavn", "")
    if KJEDE_NAVN.search(navn) or NARING.search(navn):
        return "kjede"
    for felt in (k.get("hjemmeside", ""), k.get("epost", "")):
        d = domene(felt.split("@")[-1] if "@" in felt else felt)
        for kd in KJEDE_DOMENER:
            if d == kd or d.endswith("." + kd):
                return "kjede"
    # eget domene (nettside eller e-post som ikke er kjede) => trolig uavhengig
    egen = domene(k.get("hjemmeside", "")) or domene(
        k.get("epost", "").split("@")[-1] if k.get("epost") else "")
    if egen:
        return "uavhengig"
    return "uavklart"


PRIORITET = {
    ("uavhengig", True): (1, "1 – Uavhengig 3-15"),
    ("uavhengig", False): (2, "2 – Uavhengig 16-50"),
    ("uavklart", True): (3, "3 – Uavklart 3-15"),
    ("uavklart", False): (4, "4 – Uavklart 16-50"),
    ("kjede", True): (5, "5 – Kjede 3-15 (nedprioritert)"),
    ("kjede", False): (6, "6 – Kjede 16-50 (nedprioritert)"),
}


def main():
    kontorer = json.load(open("scratch_kontorer.json"))
    ov = json.load(open("web_overrides.json"))

    rader = []
    for k in kontorer:
        org = k["orgnr"]
        o = ov.get(org, {})
        typ = o.get("type") or grov_type(k)
        # kontaktinfo: web-override > brreg
        epost = o.get("epost") or (
            k["epost"] if k.get("epost_kilde") == "brreg" else "")
        nettside = o.get("nettside") or k.get("hjemmeside", "")
        liten = k["antall_ansatte"] <= 15
        sortnr, etikett = PRIORITET[(typ, liten)]
        rader.append({
            "sort": sortnr,
            "prioritet": etikett,
            "type": typ,
            "kjede": o.get("kjede_navn", ""),
            "firmanavn": k["firmanavn"],
            "antall_ansatte": k["antall_ansatte"],
            "daglig_leder": k["daglig_leder"],
            "epost": epost,
            "telefon": k["kontakt_telefon"],
            "nettside": nettside,
            "poststed": k["poststed"],
            "orgnr": org,
            "web_sjekket": "ja" if org in ov else "",
        })

    rader.sort(key=lambda r: (r["sort"], r["antall_ansatte"], r["firmanavn"]))
    kol = ["prioritet", "type", "kjede", "firmanavn", "antall_ansatte",
           "daglig_leder", "epost", "telefon", "nettside", "poststed",
           "orgnr", "web_sjekket"]
    with open("krevla_alle_kontorer.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=kol, extrasaction="ignore")
        w.writeheader()
        w.writerows(rader)

    # --- Klar-til-send e-postliste (kun uavhengige/uavklarte med e-post;
    #     "selvstendig kontor"-pitchen passer ikke kjeder) ---
    EMNE = "Flere av nettbesøkene deres blir til verdivurderinger"

    def epost_tekst(r):
        fn = (r["daglig_leder"].split()[0] if r["daglig_leder"] else "")
        firma = r["firmanavn"].title().replace(" As", " AS")
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

    epost_klar = [r for r in rader
                  if r["epost"] and r["daglig_leder"] and r["type"] != "kjede"]
    with open("krevla_eposter.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["til_epost", "til_navn", "firma", "type", "poststed",
                    "emne", "melding"])
        for r in epost_klar:
            w.writerow([r["epost"], r["daglig_leder"], r["firmanavn"],
                        r["type"], r["poststed"], EMNE, epost_tekst(r)])

    # --- Telefon-liste (uavhengige/uavklarte med telefon, uten e-post) ---
    tlf_klar = [r for r in rader if not r["epost"] and r["telefon"]
                and r["daglig_leder"] and r["type"] != "kjede"]
    with open("krevla_telefon.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["prioritet", "type", "firmanavn", "antall_ansatte",
                    "daglig_leder", "telefon", "nettside", "poststed", "orgnr"])
        for r in tlf_klar:
            w.writerow([r["prioritet"], r["type"], r["firmanavn"],
                        r["antall_ansatte"], r["daglig_leder"], r["telefon"],
                        r["nettside"], r["poststed"], r["orgnr"]])

    from collections import Counter
    c = Counter(r["type"] for r in rader)
    print(f"E-post-klar (ikke kjede): {len(epost_klar)}")
    print(f"Telefon-klar (ikke kjede): {len(tlf_klar)}")
    print(f"Totalt: {len(rader)} kontorer")
    for t in ("uavhengig", "uavklart", "kjede"):
        rr = [r for r in rader if r["type"] == t]
        m = sum(1 for r in rr if r["epost"])
        print(f"  {t:10}: {len(rr):3}  (med e-post: {m})")
    print(f"Web-sjekket så langt: {sum(1 for r in rader if r['web_sjekket'])}")


if __name__ == "__main__":
    main()
