"""Bygg kvalitetssikret lead-liste for Krevla fra Brønnøysundregistrenes åpne API.

Autoritativ kilde:
- Firmanavn, orgnr, antall ansatte, adresse: Enhetsregisteret
- Daglig leder (hvem du skal kontakte): roller-API-et (offisielt registrert rolle)
- Registrert e-post / mobil / telefon: Enhetsregisteret

Krav fra oppdraget:
- Eiendomsmeglerkontorer (næringskode 68.310)
- 3-15 ansatte = HØY prioritet (Brreg tillater ikke søk 1-4, så dekkes som 5-15)
- 16-50 ansatte = MIDDELS prioritet (ta med, men lavere)
- Hovedsakelig uavhengige kontorer -> ekskluder kjeder
- "Klar til kontakt" = har navngitt daglig leder OG minst e-post eller telefon
"""
import json
import re
import time
import urllib.request
import urllib.error

API = "https://data.brreg.no/enhetsregisteret/api"
NAERING = "68.310"

# Kjeder / franchise som ekskluderes (hovedsakelig uavhengige kontorer ønskes).
KJEDE_MONSTRE = [
    r"\bdnb\b", r"eiendomsmegler\s*1", r"\bem\s?1\b", r"^aktiv\b",
    r"aktiv eiendomsmegling", r"privatmegleren", r"privatmegler\b",
    r"krogsveen", r"\bnordvik\b", r"\bnotar\b", r"sørmegleren", r"sormegleren",
    r"\beie eiendom", r"garanti eiendom", r"\bheimdal\b", r"proaktiv eiendom",
    r"m2 eiendom", r"\bexbo\b", r"\bhelt hjem\b", r"meglerhuset & partners",
    r"\bfredensborg\b", r"\bin-est\b",
]
KJEDE_DOMENER = [
    "dnbeiendom.no", "eiendomsmegler1.no", "em1.no", "aktiv.no",
    "privatmegleren.no", "krogsveen.no", "nordvikbolig.no", "nordvik.no",
    "notar.no", "sormegleren.no", "eie.no", "garanti.no", "proaktiv.no",
    "heimdaleiendomsmegling.no",
]


def er_kjede(navn, hjemmeside):
    n = (navn or "").lower()
    for m in KJEDE_MONSTRE:
        if re.search(m, n):
            return True
    h = (hjemmeside or "").lower()
    h = re.sub(r"^https?://", "", h).lstrip("www.").split("/")[0]
    for d in KJEDE_DOMENER:
        if h == d or h.endswith("." + d):
            return True
    return False


def hent(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "krevla-leads/1.0"})
    for forsok in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (forsok + 1))
        except Exception:
            time.sleep(2 * (forsok + 1))
    return None


def hent_enheter(fra, til):
    """Hent alle enheter i et ansattintervall (paginert)."""
    ut = []
    side = 0
    while True:
        url = (f"{API}/enheter?naeringskode={NAERING}"
               f"&fraAntallAnsatte={fra}&tilAntallAnsatte={til}"
               f"&size=100&page={side}")
        d = hent(url)
        if not d or "_embedded" not in d:
            break
        ut.extend(d["_embedded"]["enheter"])
        tot = d["page"]["totalPages"]
        side += 1
        if side >= tot:
            break
        time.sleep(0.3)
    return ut


def daglig_leder(orgnr):
    d = hent(f"{API}/enheter/{orgnr}/roller")
    if not d:
        return None
    for grp in d.get("rollegrupper", []):
        if grp.get("type", {}).get("kode") == "DAGL":
            for r in grp.get("roller", []):
                p = r.get("person", {})
                navn = p.get("navn")
                if not navn:
                    n = p.get("navn", {})
                if isinstance(navn, dict):
                    deler = [navn.get("fornavn"), navn.get("mellomnavn"),
                             navn.get("etternavn")]
                    navn = " ".join(x for x in deler if x)
                if navn:
                    return navn.strip()
    return None


def main():
    print("Henter enheter 5-50 ansatte, næringskode 68.310 ...")
    alle = hent_enheter(5, 50)
    print(f"  {len(alle)} enheter totalt før filtrering")

    kontorer = []
    for e in alle:
        navn = e.get("navn", "")
        hjemmeside = e.get("hjemmeside", "")
        if e.get("konkurs") or e.get("underAvvikling"):
            continue
        if er_kjede(navn, hjemmeside):
            continue
        ansatte = e.get("antallAnsatte")
        if ansatte is None:
            continue
        adr = e.get("forretningsadresse", {}) or {}
        kontorer.append({
            "orgnr": e.get("organisasjonsnummer"),
            "firmanavn": navn,
            "antall_ansatte": ansatte,
            "epost": e.get("epostadresse", "") or "",
            "mobil": e.get("mobil", "") or "",
            "telefon": e.get("telefon", "") or "",
            "hjemmeside": hjemmeside or "",
            "poststed": (adr.get("poststed") or "").title(),
            "kommune": (adr.get("kommune") or "").title(),
        })

    print(f"  {len(kontorer)} uavhengige kontorer etter kjede/konkurs-filter")

    # Slå opp daglig leder for hver (autoritativ kontaktperson).
    # Prioriter 5-15 først så vi rekker de viktigste.
    kontorer.sort(key=lambda k: (0 if k["antall_ansatte"] <= 15 else 1,
                                 k["antall_ansatte"]))
    ferdige = []
    for i, k in enumerate(kontorer):
        dl = daglig_leder(k["orgnr"])
        k["daglig_leder"] = dl or ""
        telefon = k["mobil"] or k["telefon"]
        k["kontakt_telefon"] = telefon
        # Klar til kontakt: navngitt DL + minst e-post eller telefon
        k["klar"] = bool(dl and (k["epost"] or telefon))
        k["prioritet"] = "HØY (3-15)" if k["antall_ansatte"] <= 15 else "MIDDELS (16-50)"
        ferdige.append(k)
        if (i + 1) % 25 == 0:
            klare = sum(1 for x in ferdige if x["klar"])
            print(f"  behandlet {i+1}/{len(kontorer)} - {klare} klare til kontakt")
        time.sleep(0.15)

    with open("scratch_kontorer.json", "w", encoding="utf-8") as f:
        json.dump(ferdige, f, ensure_ascii=False, indent=1)
    klare = [k for k in ferdige if k["klar"]]
    print(f"\nFERDIG: {len(ferdige)} kontorer, {len(klare)} klare til kontakt")
    print(f"  HØY (3-15):    {sum(1 for k in klare if k['antall_ansatte']<=15)}")
    print(f"  MIDDELS(16-50):{sum(1 for k in klare if k['antall_ansatte']>15)}")


if __name__ == "__main__":
    main()
