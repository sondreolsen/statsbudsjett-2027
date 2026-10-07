"""Setter sammen forsiden: nøkkeltall, dokumentliste, ikoner og nettstedsdata."""
import datetime as dt
import html
import json
import re
import time

from common import DATA, DIST, PAGES_DIR, SITE, read_json, write_json

MONTHS = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
          "september", "oktober", "november", "desember"]
TYPE_ORDER = ["Nasjonalbudsjettet", "Gul bok", "Prop. 1 S", "Prop. 1 LS", "Grønt hefte", "Grønn bok"]
SHORT = {"nb": "Nasjonalbudsjettet", "gulbok": "Gul bok"}
NNBSP = " "


def no_date(iso, with_time=False):
    if not iso:
        return ""
    s = iso.replace("Z", "+00:00")
    if re.search(r"[+-]\d{4}$", s):
        s = s[:-2] + ":" + s[-2:]
    d = dt.datetime.fromisoformat(s if "T" in s else s + "T00:00:00")
    out = f"{d.day}. {MONTHS[d.month - 1]} {d.year}"
    return out + (f" kl. {d.hour:02d}.{d.minute:02d}" if with_time else "")


def no_int(n):
    return f"{n:,}".replace(",", NNBSP)


def page_label(doc_id, pdfside):
    path = PAGES_DIR / f"{doc_id}.jsonl"
    if path.exists():
        for line in open(path, encoding="utf-8"):
            p = json.loads(line)
            if p["page"] == pdfside:
                return p.get("label") or pdfside
    return pdfside


def resolve_figures(manifest):
    """Fyll inn lenke, trykt sidetall og dokumentnavn fra manifestet."""
    data = read_json(DATA / "nokkeltall.json", {"tall": []})
    docs = {d["id"]: d for d in manifest["documents"]}
    for t in data["tall"]:
        k = t.get("kilde")
        if t.get("verdi") and k and k.get("doc") in docs:
            d = docs[k["doc"]]
            k["url"] = f"{d['pdf_url']}#page={k['pdfside']}"
            k["side"] = page_label(d["id"], k["pdfside"])
            k["dokument"] = SHORT.get(d["id"], d["title"])
        elif t.get("verdi") and not (k and k.get("url")):
            t["kilde"] = None
    return data


def icon(name, cls="i"):
    return f'<svg class="{cls}" aria-hidden="true"><use href="#i-{name}"/></svg>'


def render_figures(data):
    e = lambda s: html.escape(str(s if s is not None else ""))
    out = []
    for t in data["tall"]:
        if not t.get("verdi"):
            out.append(f'<article class="figure missing"><span class="figure-name">{e(t["navn"])}</span>'
                       f'<span class="figure-value">ikke funnet</span>'
                       f'<span class="figure-desc">{e(t.get("forklaring"))}</span></article>')
            continue
        change = ""
        if t.get("endring"):
            c = t["endring"]
            up = c.get("retning") == "opp"
            change = (f'<span class="figure-change {"up" if up else "down"}">{icon("arrow-up" if up else "arrow-down")}'
                      f'<span class="sr-only">{"Økning" if up else "Nedgang"}: </span>{e(c["verdi"])}&nbsp;{e(c.get("enhet"))} '
                      f'<span class="ctx">{e(c.get("tekst"))}</span></span>')
        elif t.get("sammenligning"):
            change = f'<span class="figure-compare">{e(t["sammenligning"])}</span>'
        k = t.get("kilde") or {}
        src = ""
        if k.get("url"):
            tab = f', {e(k["tabell"])}' if k.get("tabell") else ""
            src = (f'<span class="figure-source"><a href="{e(k["url"])}" title="{e(t.get("sitat"))}">'
                   f'{icon("file-text")}<span>{e(k["dokument"])}, s.&nbsp;{e(k["side"])}{tab}</span></a></span>')
        out.append(f'<article class="figure"><span class="figure-name">{e(t["navn"])}</span>'
                   f'<span class="figure-value">{e(t["verdi"]).replace(" ", NNBSP)}'
                   f'<span class="figure-unit">{e(t.get("enhet"))}</span></span>'
                   f'<span class="figure-desc">{e(t.get("forklaring"))}</span>{change}{src}</article>')
    return "\n".join(out)


def type_rank(label):
    return TYPE_ORDER.index(label) if label in TYPE_ORDER else 99


def render_docs(docs):
    e = html.escape
    docs = sorted(docs, key=lambda d: (type_rank(d["type_label"]), d["title"]))
    return "".join(
        f'<li><a href="{e(d["pdf_url"])}"><span><span class="doc-type">{e(d["type_label"])}</span>{e(d["title"])}</span>'
        f'<span class="doc-pages">{no_int(d["pages"])} s.</span></a></li>' for d in docs)


def icon_sprite():
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" style="display:none">']
    for f in sorted((SITE / "assets" / "icons").glob("*.svg")):
        inner = re.search(r"<svg[^>]*>(.*)</svg>", f.read_text(encoding="utf-8"), re.S).group(1)
        inner = re.sub(r"\s+", " ", inner).strip()
        parts.append(f'<symbol id="i-{f.stem}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                     f'stroke-linecap="round" stroke-linejoin="round">{inner}</symbol>')
    parts.append("</svg>")
    return "".join(parts)


def fylke_sort(name):
    return name.lower().replace("æ", "{").replace("ø", "|").replace("å", "}")


def render_site(manifest, docs, chapters, with_fylker):
    figures = resolve_figures(manifest)
    fylkessaker = manifest.get("fylkessaker", []) if with_fylker else []
    types = sorted({d["type_label"] for d in docs}, key=type_rank)
    if fylkessaker:
        types.append("Fylkesoversikt")
    site = {
        "year": manifest["year"], "fremlagt": manifest["fremlagt"], "built": manifest["crawled"],
        "source_url": manifest["source_url"],
        "documents": [{k: d[k] for k in ("id", "title", "type_label", "department", "pdf_url", "pages")} for d in docs],
        "fylkessaker": [{"fylke": f["fylke"], "title": f["title"], "url": f["url"],
                         "headings": [h for h in dict.fromkeys(f["headings"]) if not h.rstrip().endswith(":")]}
                        for f in fylkessaker],
        "fylker": sorted({f["fylke"] for f in fylkessaker}, key=fylke_sort),
        "departments": sorted({d["department"] for d in docs}, key=fylke_sort),
        "types": types,
        "tallgrunnlag": (manifest.get("data_files") or [{}])[0].get("url"),
    }
    (DIST / "data").mkdir(exist_ok=True)
    write_json(DIST / "data" / "nokkeltall.json", figures)
    compact = {k: [c["navn"], c["dep"], {p: [v["navn"], v["belop"]] for p, v in c["poster"].items()}]
               for k, c in chapters.items()}
    (DIST / "data" / "kapitler.json").write_text(
        json.dumps(compact, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    repl = {
        "{{YEAR}}": str(manifest["year"]),
        "{{FREMLAGT}}": no_date(manifest["fremlagt"]),
        "{{FREMLAGT_ISO}}": manifest["fremlagt"],
        "{{BUILT}}": no_date(manifest["crawled"], with_time=True),
        "{{BUILT_ISO}}": manifest["crawled"],
        "{{SOURCE_URL}}": html.escape(manifest["source_url"]),
        "{{BUILD}}": str(int(time.time())),
        "{{FIGURES}}": render_figures(figures),
        "{{DOCS}}": render_docs(docs),
        "{{DOC_COUNT}}": str(len(docs)),
        "{{PAGE_COUNT}}": no_int(sum(d["pages"] for d in docs)),
        "{{ICONS}}": icon_sprite(),
        "{{SITE_JSON}}": json.dumps(site, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
    }
    page = (SITE / "index.html").read_text(encoding="utf-8")
    for k, v in repl.items():
        page = page.replace(k, v)
    (DIST / "index.html").write_text(page, encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
