"""Steg 3b: Merk hver side med fylkene den nevner.

Bygger et stedsregister fra kommunenavn (SSB Klass) og data/fylker/steder.json.
Dette er ingen offisiell fylkesfordeling: treff bygger bare på stedsnavn i teksten.
"""
import json
import re
from collections import Counter, defaultdict

from common import DATA, PAGES_DIR, read_json, write_json

FYLKE_DISPLAY = {  # SSB-navn → navnet regjeringen bruker i fylkesoversikten
    "Oslo - Oslove": "Oslo", "Nordland - Nordlánnda": "Nordland", "Trøndelag - Trööndelage": "Trøndelag",
    "Troms - Romsa - Tromssa": "Troms", "Finnmark - Finnmárku - Finmarkku": "Finnmark",
}


def build_gazetteer():
    kom = read_json(DATA / "fylker" / "kommuner.json")
    steder = read_json(DATA / "fylker" / "steder.json")
    skip = set(steder["utelat"])
    name_to_fylker = defaultdict(set)

    for k in kom["kommuner"]:
        fylke = FYLKE_DISPLAY.get(k["fylke"], k["fylke"])
        for part in (p.strip() for p in k["navn"].split(" - ")):
            if len(part) >= 4 or part == "Oslo":
                name_to_fylker[part].add(fylke)
    for fylke_ssb in kom["fylker"].values():
        fylke = FYLKE_DISPLAY.get(fylke_ssb, fylke_ssb)
        if fylke != "Uoppgitt":
            name_to_fylker[fylke].add(fylke)
    for fylke, d in steder["fylker"].items():
        for s in d["steder"]:
            name_to_fylker[s].add(fylke)
    for s, fylker in steder["flere_fylker"].items():
        name_to_fylker[s].update(fylker)

    # Kommunenavn som finnes i flere fylker, eller som også er vanlige ord, brukes ikke alene
    gaz = {}
    for name, fylker in name_to_fylker.items():
        if name in skip:
            continue
        explicit = any(name in d["steder"] for d in steder["fylker"].values()) or name in steder["flere_fylker"]
        if len(fylker) > 1 and not explicit:
            continue
        gaz[name] = sorted(fylker)
    return gaz


def compile_pattern(names):
    # Lengste navn først, slik at «Møre og Romsdal» vinner over «Romsdal»
    alts = sorted(names, key=len, reverse=True)
    body = "|".join(re.escape(n).replace(r"\ ", r"\s+").replace("–", "[–-]") for n in alts)
    return re.compile(rf"(?<![\wÆØÅæøå-])({body})(?:s)?(?![\wÆØÅæøå])")


def tag_all():
    gaz = build_gazetteer()
    pat = compile_pattern(gaz.keys())
    key = lambda n: re.sub(r"\s+", " ", n).replace("-", "–")
    norm = {key(n): f for n, f in gaz.items()}
    manifest = read_json(DATA / "manifest.json")
    page_fylker, counts, notes = {}, Counter(), []
    for doc in manifest["documents"]:
        path = PAGES_DIR / f"{doc['id']}.jsonl"
        if not path.exists():
            continue
        for line in open(path, encoding="utf-8"):
            p = json.loads(line)
            found = set()
            for m in pat.finditer(p["text"]):
                found.update(norm.get(key(m.group(1)), ()))
            if found:
                page_fylker[f"{doc['id']}:{p['page']}"] = sorted(found)
                counts.update(found)
    write_json(PAGES_DIR / "fylker.json", page_fylker)
    write_json(DATA / "fylker" / "register.json", {"antall_navn": len(gaz), "navn": gaz})
    print(f"Fylkesmerking: {len(page_fylker)} sider merket, {len(gaz)} stedsnavn i registeret")
    for f, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {f}: {n}")
    fylker_i_oversikt = {f["fylke"] for f in manifest.get("fylkessaker", [])}
    for f in sorted(set(read_json(DATA / "fylker" / "steder.json")["fylker"]) - fylker_i_oversikt):
        notes.append(("Fylker", f"Fant ingen fylkesoversikt fra regjeringen for {f}."))
    return notes


if __name__ == "__main__":
    tag_all()
