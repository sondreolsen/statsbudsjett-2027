"""Steg 1: Les samlesiden for statsbudsjettet, finn dokumentene ved å følge
lenkene, last ned PDF-ene til cache og skriv data/manifest.json.

Ingen URL-er konstrueres: alt hentes fra lenker på sidene.
"""
import re

import pymupdf as fitz

from bs4 import BeautifulSoup

from common import (CACHE, CONFIG, DATA, HTML_DIR, PDF_DIR, SOURCE_URL, YEAR, get, links,
                    meta, normalize, now_iso, read_json, soup, url_key, write_json)

SESSION = f"({YEAR - 1}–{YEAR})"          # f.eks. (2025–2026)
SESSION_ALT = f"({YEAR - 1}-{YEAR})"

missing = []   # [(kategori, beskrivelse)]


def log_missing(cat, text):
    missing.append({"kategori": cat, "tekst": text})
    print(f"  MANGLER [{cat}] {text}")


def find_link(lst, *patterns, in_url=None):
    for text, url in lst:
        t = text.lower()
        if any(p in t for p in patterns) or (in_url and in_url in url):
            return url
    return None


def pick_pdf(s, base):
    """Velg hoved-PDF på en dokumentside: «Dokumentet i PDF format», ellers
    «Opprinnelig utgave», ellers første PDF som ikke er rettebrev."""
    pdfs = [(t, u) for t, u in links(s, base) if u.lower().endswith(".pdf")]
    for want in ("dokumentet i pdf", "opprinnelig utgave"):
        for t, u in pdfs:
            if t.lower().startswith(want):
                return u
    for t, u in pdfs:
        if "rettebrev" not in t.lower():
            return u
    return None


def classify(title, creator, pdf_url):
    t = title
    if SESSION not in t and SESSION_ALT not in t:
        return None
    if t.startswith("Meld. St. 1 ") and "asjonalbudsjett" in t:
        return ("nb", "Nasjonalbudsjettet")
    if t.startswith("Prop. 1 LS"):
        return ("ls", "Prop. 1 LS")
    if t.startswith("Prop. 1 S"):
        if "gul bok" in t.lower() or (pdf_url and "gul" in pdf_url.rsplit("/", 1)[-1]):
            return ("gulbok", "Gul bok")
        return ("prop1s", "Prop. 1 S")
    return None


def doc_page(url):
    s, final = soup(url)
    title = meta(s, "DC.Title") or meta(s, "title")
    creator = meta(s, "DC.Creator")
    pdf = pick_pdf(s, final)
    main = s.find("main") or s
    lines = [l for l in main.get_text("\n", strip=True).split("\n") if l]
    return {
        "page_url": final,
        "title": title,
        "creator": creator,
        "short": meta(s, "authorshortname"),
        "date": meta(s, "DC.Date"),
        "lang": meta(s, "DC.Language"),
        "dc_type": meta(s, "DC.Type"),
        "pdf_url": pdf,
        "lead": lines[:6],
    }


def download(url):
    path = PDF_DIR / f"{url_key(url)}.pdf"
    if not path.exists() or path.stat().st_size == 0:
        print(f"  laster ned {url}")
        path.write_bytes(get(url).content)
    return path


def section_text(s):
    """Hovedinnhold fra en artikkelside som [(overskrift, tekst)]."""
    main = s.find("main") or s
    for junk in main.select("nav, script, style, footer, .share, .related"):
        junk.decompose()
    sections, cur_h, cur = [], "", []
    for el in main.find_all(["h2", "h3", "p", "li", "td"]):
        if el.name in ("h2", "h3"):
            if cur:
                sections.append((cur_h, " ".join(cur)))
            cur_h, cur = el.get_text(" ", strip=True), []
        else:
            if el.find_parent(["li", "td"]) and el.name == "p":
                continue
            txt = " ".join(el.get_text(" ").split())
            if txt:
                cur.append(txt)
    if cur:
        sections.append((cur_h, " ".join(cur)))
    return sections


def check_statsbudsjettet_no():
    """Brukeren ba oss sjekke om statsbudsjettet.no har bevilgningstall som CSV/Excel."""
    try:
        r = get("https://www.statsbudsjettet.no/")
    except Exception as e:  # noqa: BLE001
        log_missing("statsbudsjettet.no", f"Siden svarte ikke ({e}).")
        return
    s = BeautifulSoup(r.content, "html.parser")
    files = [a["href"] for a in s.find_all("a", href=True) if a["href"].lower().endswith((".csv", ".xlsx", ".xls"))]
    if not files:
        log_missing("statsbudsjettet.no", f"Ingen CSV/Excel-filer funnet (siden videresender til {r.url}). "
                    "Kapittel/post-navn hentes fra tallgrunnlaget til Gul bok i stedet.")


def crawl():
    print(f"Leser samlesiden {SOURCE_URL}")
    s, base = soup(SOURCE_URL)
    top = links(s, base)

    docs_list = find_link(top, "budsjettdokumenter", in_url="dokumenter-og-pressemeldinger")
    fylker_url = find_link(top, "fylkesoversikt", in_url="fylkesoversikt")
    tallgrunnlag = find_link(top, "tallgrunnlag (gul bok)", in_url="tallgrunnlag-gul-bok")
    nokkeltall_pm = find_link(top, "nøkkeltall i nasjonalbudsjettet")

    candidates = [u for _, u in top if "/dokumenter/" in u]
    second = []
    if docs_list:
        s2, b2 = soup(docs_list)
        second = links(s2, b2)
        candidates += [u for _, u in second if "/dokumenter/" in u]
    else:
        log_missing("Samleside", "Fant ikke lenke til «Budsjettdokumenter og pressemeldinger» på samlesiden.")

    # Dokumentsider du har lagt inn manuelt i config.json (f.eks. et departement som ikke er lenket)
    candidates += [normalize(u) for u in CONFIG.get("extra_document_pages", [])]

    # Behold rekkefølge, fjern duplikater
    seen, cand = set(), []
    for u in candidates:
        if u not in seen:
            seen.add(u)
            cand.append(u)

    documents, skipped = [], []
    used_ids = set()
    for u in cand:
        d = doc_page(u)
        cls = classify(d["title"], d["creator"], d["pdf_url"])
        if not cls:
            if "klimastatus" in d["title"].lower() or "grønn bok" in " ".join(d["lead"]).lower():
                cls = ("gronnbok", "Grønn bok")
            else:
                skipped.append({"url": u, "title": d["title"]})
                continue
        kind, label = cls
        if not d["pdf_url"]:
            log_missing("PDF", f"Ingen PDF-lenke på dokumentsiden {d['title']} ({u}).")
            continue
        dept = d["creator"]
        sub = next((l for l in d["lead"] if l.startswith(("For budsjettåret", "For budsjettåret"))), "")
        m = re.search(r"under (.+)$", sub)
        if kind == "prop1s" and m:
            dept = m.group(1).strip()
        if "svalbard" in (d["title"] + " " + " ".join(d["lead"])).lower() and kind == "prop1s":
            label_title = f"Prop. 1 S {SESSION} Svalbardbudsjettet"
            base_id = "prop1s-svalbard"
        elif kind == "prop1s":
            label_title = f"Prop. 1 S {SESSION} {dept}"
            base_id = f"prop1s-{d['short'] or url_key(u)}"
        else:
            nice = {"gulbok": f"Gul bok {YEAR} (Prop. 1 S {SESSION})",
                    "nb": f"Nasjonalbudsjettet {YEAR} (Meld. St. 1 {SESSION})",
                    "ls": f"Skatter, avgifter og toll {YEAR} (Prop. 1 LS {SESSION})",
                    "gronnbok": f"Klimastatus og -plan (Grønn bok) {YEAR}"}
            label_title = nice[kind]
            base_id = kind
        did, n = base_id, 2
        while did in used_ids:
            did, n = f"{base_id}-{n}", n + 1
        used_ids.add(did)
        documents.append({
            "id": did, "type": kind, "type_label": label, "title": label_title,
            "official_title": d["title"], "department": dept,
            "source_page": d["page_url"], "pdf_url": d["pdf_url"],
            "published": d["date"], "language": d["lang"],
        })

    # Grønt hefte ligger på en temaside som lenkes fra dokumentlisten
    gh_page = find_link(second, "grønt hefte")
    if gh_page:
        s3, b3 = soup(gh_page)
        gh_pdf = None
        for t, u in links(s3, b3):
            if u.lower().endswith(".pdf") and "grønt hefte" in t.lower() and str(YEAR) in t + u:
                gh_pdf = u
                break
        if gh_pdf:
            documents.append({
                "id": "gront-hefte", "type": "gronthefte", "type_label": "Grønt hefte",
                "title": f"Grønt hefte {YEAR}: Inntektssystemet for kommunar og fylkeskommunar",
                "official_title": t, "department": "Kommunal- og distriktsdepartementet",
                "source_page": gh_page, "pdf_url": gh_pdf, "published": "", "language": "nn-NO",
            })
        else:
            log_missing("Grønt hefte", f"Temasiden for Grønt hefte ({gh_page}) har ingen PDF for {YEAR}.")
    else:
        log_missing("Grønt hefte", "Fant ikke lenke til Grønt hefte i dokumentlisten.")

    # Forventede dokumenter
    kinds = {d["type"] for d in documents}
    for k, label in [("gulbok", "Gul bok"), ("nb", "Nasjonalbudsjettet (Meld. St. 1)"), ("ls", "Prop. 1 LS")]:
        if k not in kinds:
            log_missing("Dokument", f"{label} ble ikke funnet via lenkene.")
    depts = {d["department"] for d in documents if d["type"] == "prop1s"}
    for dep in CONFIG.get("expected_departments", []):
        if dep not in depts:
            log_missing("Prop. 1 S", f"Fant ingen Prop. 1 S for {dep} via samlesiden eller dokumentlisten.")

    # Last ned og tell sider
    for d in documents:
        try:
            path = download(d["pdf_url"])
            with fitz.open(path) as pdf:
                d["pages"] = pdf.page_count
            d["cache_file"] = path.name
            d["downloaded"] = now_iso()
        except Exception as e:  # noqa: BLE001
            log_missing("Nedlasting", f"Klarte ikke å laste ned {d['title']}: {e}")
            d["pages"] = 0
    documents = [d for d in documents if d.get("pages")]

    # Fylkesvise oversikter
    fylkessaker = []
    if fylker_url:
        s4, b4 = soup(fylker_url)
        for t, u in links(s4, b4):
            if "fylkesoversikten/" in u and u.rstrip("/") != fylker_url.rstrip("/"):
                s5, b5 = soup(u)
                sections = section_text(s5)
                fylkessaker.append({
                    "fylke": t, "title": meta(s5, "DC.Title") or t, "url": b5,
                    "published": meta(s5, "DC.Date"), "downloaded": now_iso(),
                    "headings": [h for h, _ in sections if h],
                })
                write_json(HTML_DIR / f"fylke-{url_key(b5)}.json",
                           {"url": b5, "title": meta(s5, "DC.Title") or t, "sections": sections})
    else:
        log_missing("Fylker", "Fant ikke lenke til fylkesoversikten på samlesiden.")

    # Tallgrunnlag (bevilgninger per kapittel/post)
    data_files = []
    if tallgrunnlag:
        s6, b6 = soup(tallgrunnlag)
        for t, u in links(s6, b6):
            if u.lower().endswith((".xlsx", ".csv")):
                path = PDF_DIR.parent / ("tallgrunnlag" + u[u.rfind("."):])
                path.write_bytes(get(u).content)
                data_files.append({"title": f"Tallgrunnlag Gul bok ({t})", "url": u,
                                   "source_page": b6, "cache_file": path.name, "downloaded": now_iso()})
                break
    if not data_files:
        log_missing("Tallgrunnlag", "Fant ingen CSV/Excel med bevilgningstall (Gul bok tallgrunnlag).")
    check_statsbudsjettet_no()

    # Finansdepartementets nøkkeltall-pressemelding (kilde for nøkkeltall)
    press = None
    if nokkeltall_pm:
        s7, b7 = soup(nokkeltall_pm)
        press = {"title": meta(s7, "DC.Title"), "url": b7, "published": meta(s7, "DC.Date"),
                 "sections": section_text(s7), "downloaded": now_iso()}
        write_json(HTML_DIR / "nokkeltall-pressemelding.json", press)
    else:
        log_missing("Nøkkeltall", "Fant ikke Finansdepartementets «Nøkkeltall i Nasjonalbudsjettet» på samlesiden.")

    fremlagt = next((d["published"] for d in documents if d["type"] == "gulbok"), "") or \
        next((d["published"] for d in documents if d["published"]), "")
    for f in fylkessaker:
        if not f["headings"]:
            log_missing("Fylker", f"Fylkessiden for {f['fylke']} ga ingen tekst.")

    manifest = {
        "year": YEAR, "source_url": SOURCE_URL, "fremlagt": fremlagt, "crawled": now_iso(),
        "documents": documents, "fylkessaker": fylkessaker, "data_files": data_files,
        "nokkeltall_pressemelding": press and {k: press[k] for k in ("title", "url", "published")},
        "skipped_links": skipped,
    }
    write_json(DATA / "manifest.json", manifest)
    write_json(CACHE / "missing_crawl.json", missing)
    print(f"Ferdig: {len(documents)} dokumenter, {sum(d['pages'] for d in documents)} sider, "
          f"{len(fylkessaker)} fylkessider, {len(missing)} mangler.")
    return manifest


if __name__ == "__main__":
    crawl()
