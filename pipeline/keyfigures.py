"""Steg 3: Finn kandidatsider for nøkkeltallene i Nasjonalbudsjettet og Gul bok.

Scriptet foreslår bare sider og utdrag (skrives til cache/nokkeltall_kandidater.md).
Selve tallene i data/nokkeltall.json legges inn og kontrolleres manuelt mot PDF-en:
et feillest tall er verre enn «ikke funnet».
"""
import json
import re

from common import CACHE, DATA, PAGES_DIR, read_json

FIGURES = {
    "underskudd": [r"strukturelt?,? oljekorrigert (?:budsjett)?underskudd"],
    "fondsandel": [r"prosent av (?:kapitalen|verdien) i Statens pensjonsfond utland", r"Uttak fra SPU"],
    "utgifter": [r"Utgifter i alt", r"Statsbudsjettets utgifter", r"[Ss]amlede utgifter"],
    "utgiftsvekst": [r"[Uu]nderliggende utgiftsvekst"],
    "bnp": [r"Bruttonasjonalprodukt Fastlands-Norge", r"BNP for Fastlands-Norge"],
    "ledighet": [r"[Aa]rbeidsledighet(?:srate|en)?,? registrert", r"Registrerte helt ledige", r"AKU-ledighet"],
    "kpi": [r"Konsumprisindeksen \(KPI\)", r"\bKPI\b"],
    "skatt": [r"skatte- og avgiftsopplegget", r"skatte- og avgiftsendringer", r"lettelser? i skatter og avgifter"],
    "fondsverdi": [r"[Vv]erdien av Statens pensjonsfond utland"],
}


def candidates(doc_ids=("nb", "gulbok"), per_figure=8):
    out = {}
    for did in doc_ids:
        path = PAGES_DIR / f"{did}.jsonl"
        if not path.exists():
            continue
        for line in open(path, encoding="utf-8"):
            p = json.loads(line)
            flat = " ".join(p["text"].split())
            for key, pats in FIGURES.items():
                for pat in pats:
                    for m in re.finditer(pat, flat):
                        snippet = flat[max(0, m.start() - 150): m.end() + 250]
                        nums = len(re.findall(r"\d+,\d", snippet))
                        out.setdefault(key, []).append((nums, did, p["page"], p.get("label"), snippet))
    with open(CACHE / "nokkeltall_kandidater.md", "w", encoding="utf-8") as f:
        for key, lst in out.items():
            f.write(f"\n## {key}\n")
            lst.sort(key=lambda x: -x[0])
            for nums, did, page, label, snip in lst[:per_figure]:
                f.write(f"- {did} pdf-side {page} (trykt {label}): …{snip}…\n")
    print(f"Kandidater skrevet til {CACHE / 'nokkeltall_kandidater.md'}")


def check():
    """Rapporter tall som mangler kilde eller er «ikke funnet»."""
    data = read_json(DATA / "nokkeltall.json", {"tall": []})
    docs = {d["id"]: d for d in read_json(DATA / "manifest.json", {"documents": []})["documents"]}
    from common import YEAR
    if data.get("aar") != YEAR:
        return [f"data/nokkeltall.json gjelder {data.get('aar')}, ikke {YEAR}. Alle nøkkeltall vises som «ikke funnet» "
                "til de er kontrollert og lagt inn for riktig år."]
    missing = []
    for t in data["tall"]:
        k = t.get("kilde") or {}
        if t.get("verdi") in (None, "", "ikke funnet"):
            missing.append(f"Nøkkeltall «{t['navn']}» ble ikke funnet i Nasjonalbudsjettet, Gul bok "
                           f"eller Finansdepartementets pressemelding.")
        elif k.get("url"):
            continue
        elif k.get("doc") not in docs or not (1 <= int(k.get("pdfside") or 0) <= docs[k["doc"]]["pages"]):
            missing.append(f"Nøkkeltall «{t['navn']}» har ugyldig kilde ({k.get('doc')}, side {k.get('pdfside')}).")
    return missing


if __name__ == "__main__":
    candidates()
