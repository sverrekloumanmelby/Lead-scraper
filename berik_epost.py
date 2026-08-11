"""Berik kontorer med VERIFISERT e-post ved å hente kontorets egen nettside.
Gjetter aldri adresser - trekker kun ut e-post som faktisk står på siden.
"""
import json
import re
import urllib.request
import concurrent.futures

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
SUBSIDER = ["", "/kontakt", "/kontakt-oss", "/kontaktoss", "/om-oss", "/omoss",
            "/ansatte", "/kontakt/", "/vare-meglere", "/meglere", "/team"]
SKROT = re.compile(r"(sentry|wixpress|example|domene\.no|@2x|\.png|\.jpg|\.gif|"
                   r"\.webp|\.svg|godkjenning|u003e|sentry\.io|wixpress\.com)", re.I)
EPOST = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}")


def hent(url):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA})
        return urllib.request.urlopen(r, timeout=15).read().decode("utf-8", "ignore")
    except Exception:
        return ""


def norm(u):
    u = u.strip()
    if not u:
        return ""
    if not u.startswith("http"):
        u = "https://" + u
    return u.rstrip("/")


def finn_eposter(base, domene):
    funnet = {}
    for sub in SUBSIDER:
        h = hent(base + sub)
        if not h:
            continue
        for e in EPOST.findall(h):
            e = e.lower()
            if SKROT.search(e):
                continue
            # foretrekk e-post på kontorets eget domene
            if domene and domene in e:
                funnet[e] = funnet.get(e, 0) + 3
            else:
                funnet[e] = funnet.get(e, 0) + 1
        if funnet and sub in ("/kontakt", "/kontakt-oss"):
            break
    return funnet


def velg(funnet, dl):
    if not funnet:
        return ""
    # 1) e-post som inneholder daglig leders etternavn
    if dl:
        etter = dl.split()[-1].lower()
        for e in funnet:
            if etter and etter[:5] in e:
                return e
    # 2) generell kontoradresse
    for pref in ("post@", "kontakt@", "firmapost@", "hei@", "mail@", "salg@"):
        for e in funnet:
            if e.startswith(pref):
                return e
    # 3) hyppigst / høyest scoret
    return max(funnet, key=funnet.get)


def prosesser(k):
    web = norm(k.get("hjemmeside", ""))
    if not web:
        return k
    domene = re.sub(r"^https?://", "", web).lstrip("www.").split("/")[0]
    funnet = finn_eposter(web, domene)
    k["nettside_eposter"] = sorted(funnet, key=funnet.get, reverse=True)[:5]
    valgt = velg(funnet, k.get("daglig_leder", ""))
    if valgt and not k.get("epost"):
        k["epost"] = valgt
        k["epost_kilde"] = "nettside"
    elif k.get("epost"):
        k["epost_kilde"] = "brreg"
    return k


def main():
    kontorer = json.load(open("scratch_kontorer.json"))
    med_web = [k for k in kontorer if k.get("hjemmeside")]
    print(f"Skraper {len(med_web)} nettsider for verifisert e-post ...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(prosesser, med_web))
    for k in kontorer:
        k.setdefault("epost_kilde", "brreg" if k.get("epost") else "")
    json.dump(kontorer, open("scratch_kontorer.json", "w"),
              ensure_ascii=False, indent=1)
    med_epost = [k for k in kontorer if k.get("epost")]
    klar = [k for k in kontorer if k.get("daglig_leder") and k.get("epost")]
    print(f"Kontorer med e-post nå: {len(med_epost)} (fra {sum(1 for k in kontorer if k.get('epost_kilde')=='brreg')} brreg + nettside)")
    print(f"Klar til e-post (DL + e-post): {len(klar)}")
    print(f"  HØY 3-15:     {sum(1 for k in klar if k['antall_ansatte']<=15)}")
    print(f"  MIDDELS 16-50:{sum(1 for k in klar if k['antall_ansatte']>15)}")


if __name__ == "__main__":
    main()
