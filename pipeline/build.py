"""Kjør hele pipelinen:  python pipeline/build.py

  --mvp          bare Gul bok og Nasjonalbudsjettet (minste versjon)
  --skip-crawl   bruk eksisterende manifest og nedlastede PDF-er
  --publish      publiser dist/ til gh-pages etterpå

Bytte år: endre "year" og "source_url" i config.json og kjør på nytt.
"""
import argparse
import time

import crawl
import extract
import index
import keyfigures
from common import CACHE, DATA, DIST, YEAR, now_iso, read_json


def write_mangler(extra=()):
    missing = read_json(CACHE / "missing_crawl.json", [])
    lines = [f"# Mangler: statsbudsjettet {YEAR}", "",
             f"Generert {now_iso()}. Dette er ting pipelinen forventet å finne, men ikke fant. "
             "Ingen hull er fylt med antatte verdier.", ""]
    groups = {}
    for m in missing:
        groups.setdefault(m["kategori"], []).append(m["tekst"])
    for t in keyfigures.check():
        groups.setdefault("Nøkkeltall", []).append(t)
    for cat, t in extra:
        groups.setdefault(cat, []).append(t)
    if not groups:
        lines.append("Ingenting mangler.")
    for cat, items in groups.items():
        lines.append(f"## {cat}")
        lines += [f"- {t}" for t in items]
        lines.append("")
    (DATA / "mangler.md").write_text("\n".join(lines), encoding="utf-8")
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mvp", action="store_true")
    ap.add_argument("--skip-crawl", action="store_true")
    ap.add_argument("--publish", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    only = {"gulbok", "nb"} if args.mvp else None

    if not args.skip_crawl:
        crawl.crawl()
    print("Trekker ut tekst …")
    extract.extract(only)
    keyfigures.candidates()
    extra = []
    if not args.mvp:
        try:
            import places
            extra += places.tag_all()
        except ImportError:
            pass
    print("Bygger indeks og nettsted …")
    stats = index.build(only)
    groups = write_mangler(extra)
    print(f"\nFerdig på {time.time() - t0:.0f} s. Nettstedet ligger i {DIST}")
    print(f"mangler.md: {sum(len(v) for v in groups.values())} punkter")
    if args.publish:
        import publish
        publish.publish()
    return stats


if __name__ == "__main__":
    main()
