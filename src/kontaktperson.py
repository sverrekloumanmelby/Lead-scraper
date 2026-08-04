"""Finner den beste personen å kontakte om AI-chatbot.

I et meglerkontor med 3–20 ansatte er beslutningen om et verktøy som en
chatbot nesten alltid daglig leders, men er det en markeds- eller
digitalansvarlig der, er det den som eier nettsiden i praksis og som blir
den reelle inngangen. Vi henter derfor ut alle navngitte ansatte med
tittel fra kontorets egne «om oss»/«ansatte»-sider, og rangerer dem.

Rangeringen er bevisst konservativ: finner vi ingen troverdig person på
nettsiden, faller vi tilbake på daglig leder fra Enhetsregisteret, som
alltid finnes og alltid er en gyldig inngang.
"""

from __future__ import annotations

import html as html_modul
import logging
import re

logger = logging.getLogger(__name__)

# Undersider der ansatte pleier å stå
ANSATT_NOKKELORD = [
    "om-oss", "omoss", "om_oss", "ansatte", "medarbeider", "meglere",
    "vare-meglere", "vart-team", "teamet", "team", "kontakt", "om/",
    "people", "about",
]

# Titler rangert etter hvor godt de passer som inngang for et chatbot-salg.
# Høyere tall = bedre. Markedsansvarlig slår daglig leder bare når begge
# finnes; ellers er daglig leder inngangen.
TITTEL_RANGERING: list[tuple[str, int, str]] = [
    (r"markedssjef|markedsansvarlig|marketing manager|markedsfører",
     95, "Eier nettsiden og markedsføringen"),
    (r"digitalsjef|digital ansvarlig|digitalansvarlig|teknologisjef|it-ansvarlig",
     93, "Ansvar for digitale verktøy"),
    (r"daglig leder|adm\.? ?dir|administrerende direktør|managing director|ceo",
     90, "Beslutningstaker i et kontor av denne størrelsen"),
    (r"partner|medeier|eier|gründer", 80, "Medeier med beslutningsmyndighet"),
    (r"salgssjef|salgsleder|salgsansvarlig", 70, "Ansvar for leads og salg"),
    (r"avdelingsleder|kontorleder|fagansvarlig|fagsjef", 65, "Leder for kontoret"),
    (r"eiendomsmeglerfullmektig", 20, "Meglerfullmektig"),
    (r"eiendomsmegler|megler", 30, "Megler"),
]

# Ord som avslører at «navnet» vi fant egentlig er en overskrift e.l.
IKKE_NAVN = {
    "om oss", "kontakt oss", "våre meglere", "vårt team", "ansatte",
    "personvern", "cookies", "les mer", "til salgs", "solgt", "meny",
    "eiendomsmegling", "verdivurdering", "ledige stillinger", "her finner",
    "send inn", "ring oss", "book verdivurdering", "våre kontorer",
}

# Enkeltord som aldri inngår i et norsk personnavn. Uten denne lista
# plukker skanningen opp overskrifter og firmanavn som «Om Partners»,
# «Coop Obs Bygg» og «Aure Arena» — alle observert i praksis.
IKKE_NAVNEORD = {
    "om", "oss", "vår", "våre", "vart", "vårt", "din", "ditt", "den", "det",
    "ny", "nye", "her", "les", "mer", "se", "alle", "kontakt", "kontor",
    "kontorer", "avdeling", "team", "teamet", "ansatte", "megler", "meglere",
    "eiendom", "eiendommer", "eiendomsmegling", "eiendomsmegler", "bolig",
    "boliger", "partners", "partner", "gruppen", "group", "senter", "arena",
    "bygg", "torg", "coop", "obs", "sentrum", "vest", "sør", "nord", "øst",
    "as", "asa", "ans", "avd", "salgs", "salg", "kjøp", "solgt", "visning",
    "verdivurdering", "prisantydning", "nyheter", "artikler", "personvern",
    "cookies", "informasjonskapsler", "hjem", "start", "tjenester", "priser",
    "jobb", "karriere", "stillinger", "presse", "media", "blogg",
    "januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
    "september", "oktober", "november", "desember",
}

# E-poster som tilhører firmaet, ikke en person
GENERISKE_EPOSTER = {
    "post", "kontakt", "firmapost", "info", "hei", "hallo", "mail",
    "oppgjor", "oppgjør", "faktura", "regnskap", "support", "salg",
    "booking", "noreply", "no-reply", "webmaster", "personvern",
}

NAVN_MONSTER = re.compile(
    r"\b([A-ZÆØÅ][a-zæøåéèü]{1,20}(?:[- ][A-ZÆØÅ][a-zæøåéèü]{1,20}){1,3})\b"
)
EPOST_MONSTER = re.compile(r"[\w.\-+]+@[\w\-]+\.[\w.\-]+")
TLF_MONSTER = re.compile(r"(?:\+47[\s.]?)?(?:\d{2}[\s.]?){4}\d{0,2}")


def _tekst(html: str) -> str:
    """HTML til lesbar tekst, med skilletegn der taggene sto."""
    html = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html,
                  flags=re.DOTALL | re.IGNORECASE)
    tekst = re.sub(r"<[^>]+>", " | ", html)
    tekst = html_modul.unescape(tekst)
    return re.sub(r"[ \t]+", " ", tekst)


def _tittel_score(tekst: str) -> tuple[int, str, str]:
    """Returnerer (score, funnet_tittel, begrunnelse) for en tekstbit."""
    lav = tekst.lower()
    beste = (0, "", "")
    for monster, score, begrunnelse in TITTEL_RANGERING:
        treff = re.search(monster, lav)
        if treff and score > beste[0]:
            beste = (score, treff.group(0), begrunnelse)
    return beste


def _rens_telefon(raa: str) -> str:
    siffer = re.sub(r"\D", "", raa)
    if siffer.startswith("0047"):
        siffer = siffer[4:]
    elif siffer.startswith("47") and len(siffer) == 10:
        siffer = siffer[2:]
    return siffer if len(siffer) == 8 else ""


def _gyldig_navn(navn: str, firmanavn: str = "") -> bool:
    """Ser dette ut som et ekte personnavn — og ikke en overskrift?"""
    lav = navn.lower().strip()
    if lav in IKKE_NAVN or any(u in lav for u in IKKE_NAVN):
        return False

    deler = [d for d in re.split(r"[\s-]+", lav) if d]
    if not 2 <= len(deler) <= 4:
        return False

    # Ett eneste ikke-navneord diskvalifiserer hele frasen
    if any(d in IKKE_NAVNEORD for d in deler):
        return False
    if any(len(d) < 2 for d in deler):
        return False

    # «Bakke Sørvik» på bakkesorvik.no er firmanavnet, ikke en person
    if firmanavn:
        firmaord = {
            o for o in re.split(r"[^\wæøå]+", firmanavn.lower())
            if len(o) > 2
        }
        if firmaord and sum(1 for d in deler if d in firmaord) >= 2:
            return False

    return True


def _epost_passer_navn(epost: str, navn: str) -> bool:
    """Stemmer e-postens lokaldel overens med navnet?"""
    lokal = epost.split("@")[0].lower()
    lokal_ren = re.sub(r"[^a-zæøå]", "", _uten_aksenter(lokal))
    for del_ in re.split(r"[\s-]+", _uten_aksenter(navn.lower())):
        if len(del_) >= 4 and del_ in lokal_ren:
            return True
    # Initialer, f.eks. «gi@…» for Guri Istad
    initialer = "".join(d[0] for d in navn.lower().split() if d)
    return len(initialer) >= 2 and lokal_ren == _uten_aksenter(initialer)


def _uten_aksenter(tekst: str) -> str:
    for fra, til in {"æ": "ae", "ø": "o", "å": "a", "é": "e", "ü": "u"}.items():
        tekst = tekst.replace(fra, til)
    return tekst


def _samme_domene(epost: str, side_url: str) -> bool:
    """Ligger e-posten på samme domene som nettsiden?"""
    from urllib.parse import urlparse

    if not side_url:
        return True  # ingen url å sammenligne med; ikke diskvalifiser
    vert = (urlparse(side_url).hostname or "").lower().removeprefix("www.")
    edom = epost.split("@")[-1].lower()
    if not vert or not edom:
        return False
    kjerne = vert.rsplit(".", 2)[0] if vert.count(".") > 1 else vert.split(".")[0]
    return edom == vert or edom.endswith(vert) or kjerne in edom


def personer_fra_html(html: str, firmanavn: str = "",
                      side_url: str = "") -> list[dict]:
    """Trekker ut personer med navn, tittel, e-post og telefon fra en side.

    Vi tar utgangspunkt i mailto-lenker, fordi en ansatt med e-post på
    siden nesten alltid står med navn og tittel rett ved siden av. Så
    skanner vi i tillegg etter navn+tittel-par uten e-post.

    `firmanavn` og `side_url` brukes til å forkaste falske treff:
    firmanavnet skal ikke bli en «person», og en e-post på et helt annet
    domene enn nettsiden hører ikke til dette kontoret.
    """
    funnet: dict[str, dict] = {}

    # 1) Rundt hver mailto-lenke: se i vinduet før og etter
    for treff in re.finditer(r'mailto:([^"\'?>]+)', html, re.IGNORECASE):
        epost = html_modul.unescape(treff.group(1)).strip().lower()
        if not EPOST_MONSTER.fullmatch(epost):
            continue
        # E-post på fremmed domene hører ikke til dette kontoret
        if not _samme_domene(epost, side_url):
            continue

        lokal = epost.split("@")[0]
        generisk = lokal in GENERISKE_EPOSTER

        start = max(0, treff.start() - 1200)
        vindu = _tekst(html[start:treff.end() + 800])

        score, tittel, begrunnelse = _tittel_score(vindu)
        navn = ""
        # Navnet står oftest rett før e-posten
        for kandidat in reversed(NAVN_MONSTER.findall(vindu)):
            if _gyldig_navn(kandidat, firmanavn):
                navn = kandidat
                break
        # E-postens lokaldel avslører ofte navnet: fornavn.etternavn@
        if not navn and not generisk and "." in lokal:
            deler = [d for d in lokal.split(".") if d.isalpha() and len(d) > 1]
            if len(deler) >= 2:
                navn = " ".join(d.capitalize() for d in deler[:2])
        if not navn or not _gyldig_navn(navn, firmanavn):
            continue

        # En personlig e-post må kunne knyttes til navnet; ellers beholder
        # vi personen, men uten e-posten.
        if generisk or not _epost_passer_navn(epost, navn):
            epost_for_person = ""
        else:
            epost_for_person = epost
        if not tittel and not epost_for_person:
            continue

        tlf = ""
        for t in TLF_MONSTER.findall(vindu):
            tlf = _rens_telefon(t)
            if tlf:
                break

        nokkel = navn.lower()
        if nokkel not in funnet or score > funnet[nokkel]["score"]:
            funnet[nokkel] = {
                "navn": navn, "tittel": tittel, "epost": epost_for_person,
                "telefon": tlf, "score": score, "begrunnelse": begrunnelse,
            }

    # 2) Navn + tittel uten e-post (typisk «Kari Nordmann | Daglig leder»)
    tekst = _tekst(html)
    for monster, score, begrunnelse in TITTEL_RANGERING:
        if score < 60:
            continue
        for treff in re.finditer(monster, tekst, re.IGNORECASE):
            # Navnet står tett på tittelen i et personkort
            vindu = tekst[max(0, treff.start() - 120): treff.end() + 120]
            for kandidat in NAVN_MONSTER.findall(vindu):
                if not _gyldig_navn(kandidat, firmanavn):
                    continue
                nokkel = kandidat.lower()
                if nokkel in funnet:
                    if score > funnet[nokkel]["score"]:
                        funnet[nokkel].update(
                            score=score, tittel=treff.group(0),
                            begrunnelse=begrunnelse)
                else:
                    funnet[nokkel] = {
                        "navn": kandidat, "tittel": treff.group(0),
                        "epost": "", "telefon": "", "score": score,
                        "begrunnelse": begrunnelse,
                    }
                break

    return sorted(funnet.values(), key=lambda p: p["score"], reverse=True)


def velg_kontakt(personer: list[dict], daglig_leder_brreg: str = "") -> dict:
    """Velger den beste kontakten, med daglig leder fra Brreg som fallback."""
    if personer:
        beste = personer[0]
        # Er daglig leder fra Brreg blant personene, og ingen markeds-
        # ansvarlig slår ham/henne, foretrekk den bekreftede personen.
        if daglig_leder_brreg:
            dl_lav = daglig_leder_brreg.lower()
            for p in personer:
                if p["navn"].lower() in dl_lav or dl_lav in p["navn"].lower():
                    if p["score"] >= beste["score"] - 10:
                        return {**p, "kilde": "nettside+brreg"}
        if beste["score"] >= 20:
            return {**beste, "kilde": "nettside"}

    if daglig_leder_brreg:
        return {
            "navn": daglig_leder_brreg, "tittel": "Daglig leder",
            "epost": "", "telefon": "", "score": 90,
            "begrunnelse": "Beslutningstaker i et kontor av denne størrelsen",
            "kilde": "brreg",
        }
    return {"navn": "", "tittel": "", "epost": "", "telefon": "",
            "score": 0, "begrunnelse": "", "kilde": ""}
