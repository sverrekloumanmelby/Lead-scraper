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
    "moremegling.no", "utleiemegleren.no",
]
KJEDE_NAVN = re.compile(
    r"\bdnb\b|eiendomsmegler\s*1|\bem1\b|^aktiv\b|aktiv eiendomsmegling|"
    r"privatmegler|krogsveen|\bnordvik\b|\bnotar\b|sørmegler|garanti eiendom|"
    r"proaktiv|\beie\b", re.I)
# Store næringsmeglere / kommersielle kjeder (regnes som "kjede"/nedprioritert
# fordi de ikke er uavhengige boligmeglere).
NARING = re.compile(
    r"næringsmegl|naeringsmegl|næringseiendom|corporate real estate|"
    r"property advisor|leietaker|\bmalling\b|colliers|cushman|newsec|"
    r"akershus eiendom|union norsk", re.I)


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

    from collections import Counter
    c = Counter(r["type"] for r in rader)
    print(f"Totalt: {len(rader)} kontorer")
    for t in ("uavhengig", "uavklart", "kjede"):
        rr = [r for r in rader if r["type"] == t]
        m = sum(1 for r in rr if r["epost"])
        print(f"  {t:10}: {len(rr):3}  (med e-post: {m})")
    print(f"Web-sjekket så langt: {sum(1 for r in rader if r['web_sjekket'])}")


if __name__ == "__main__":
    main()
