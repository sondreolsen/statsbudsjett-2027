"""Steg 4: Bygg statisk Pagefind-indeks (én post per PDF-side) og sett sammen
nettstedet i dist/."""
import asyncio
import json
import shutil

from pagefind.index import IndexConfig, PagefindIndex

from common import DATA, DIST, HTML_DIR, PAGES_DIR, SITE, read_json, url_key
from render import render_site

LANG = "no"  # Pagefind/Snowball norsk stemming


def kap_label(kap, chapters, post=None):
    c = chapters.get(kap)
    if not c:
        return None
    s = f"Kap. {kap} {c['navn']}"
    if post and post in c["poster"]:
        s += f", post {post} {c['poster'][post]['navn']}"
    return s


def page_records(manifest, chapters, page_fylker, only=None):
    for doc in manifest["documents"]:
        if only and doc["type"] not in only:
            continue
        path = PAGES_DIR / f"{doc['id']}.jsonl"
        for line in open(path, encoding="utf-8"):
            p = json.loads(line)
            if len(p["text"]) < 40:
                continue
            kaps = []
            if p.get("kap_context"):
                kaps.append(kap_label(p["kap_context"], chapters))
            for r in p["kap_refs"]:
                kap, _, post = r.partition(".")
                if post:
                    kaps.append(kap_label(kap, chapters, post))
                elif not any(k and k.startswith(f"Kap. {kap} ") for k in kaps):
                    kaps.append(kap_label(kap, chapters))
            kaps = [k for k in dict.fromkeys(kaps) if k][:3]
            label = str(p["label"]) if p.get("label") else str(p["page"])
            fylker = page_fylker.get(f"{doc['id']}:{p['page']}", [])
            content = p["text"]
            if p.get("kap_context"):
                content = kap_label(p["kap_context"], chapters) + "\n" + content
            yield {
                "url": f"{doc['pdf_url']}#page={p['page']}",
                "content": content,
                "meta": {
                    "title": doc["title"], "doc": doc["id"], "side": label, "pdfside": str(p["page"]),
                    "kap": " · ".join(kaps), "type": doc["type_label"], "dep": doc["department"],
                    "url": f"{doc['pdf_url']}#page={p['page']}",
                },
                "filters": {"dep": [doc["department"]], "type": [doc["type_label"]],
                            **({"fylke": fylker} if fylker else {})},
            }


def fylke_records(manifest):
    for f in manifest.get("fylkessaker", []):
        data = read_json(HTML_DIR / f"fylke-{url_key(f['url'])}.json")
        if not data:
            continue
        content = "\n".join(f"{h}\n{t}" if h else t for h, t in data["sections"])
        yield {
            "url": f["url"], "content": content,
            "meta": {"title": f["title"], "doc": "fylke", "side": "", "pdfside": "", "kap": "",
                     "type": "Fylkesoversikt", "dep": "Regjeringen", "url": f["url"]},
            "filters": {"type": ["Fylkesoversikt"], "dep": ["Regjeringen"], "fylke": [f["fylke"]]},
        }


async def build_index(records, out):
    cfg = IndexConfig(output_path=str(out / "pagefind"), force_language=LANG)
    n = 0
    async with PagefindIndex(config=cfg) as index:
        batch = 100
        for i in range(0, len(records), batch):
            await asyncio.gather(*(index.add_custom_record(url=r["url"], content=r["content"], language=LANG,
                                                           meta=r["meta"], filters=r["filters"])
                                   for r in records[i:i + batch]))
            n += len(records[i:i + batch])
        await index.write_files(output_path=str(out / "pagefind"))
    return n


def build(only=None):
    manifest = read_json(DATA / "manifest.json")
    chapters = read_json(DATA / "kapitler.json", {})
    page_fylker = read_json(PAGES_DIR / "fylker.json", {})
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(SITE, DIST)

    records = list(page_records(manifest, chapters, page_fylker, only))
    if not only or "fylke" in only:
        records += list(fylke_records(manifest))
    n = asyncio.run(build_index(records, DIST))

    docs = [d for d in manifest["documents"] if not only or d["type"] in only]
    render_site(manifest, docs, chapters, with_fylker=not only or "fylke" in only)
    size = sum(f.stat().st_size for f in (DIST / "pagefind").rglob("*") if f.is_file())
    files = sum(1 for f in (DIST / "pagefind").rglob("*") if f.is_file())
    print(f"Indeks: {n} poster, {files} filer, {size / 1e6:.1f} MB totalt i {DIST / 'pagefind'}")
    return {"records": n, "index_bytes": size, "index_files": files}


if __name__ == "__main__":
    import sys
    build(set(sys.argv[1:]) or None)
