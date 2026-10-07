# Statsbudsjettet: søkbar oversikt

Uoffisiell, statisk søkeside for statsbudsjettet. Alt innhold hentes fra regjeringen.no,
og hvert treff lenker til riktig side i original-PDF-en. PDF-ene ligger ikke i repoet.

## Bytte år

1. Endre `year` og `source_url` (samlesiden for statsbudsjettet på regjeringen.no) i `config.json`.
2. Kjør `python pipeline/build.py --publish`.
3. Kontroller nøkkeltallene: se kandidatsidene i `~/.statsbudsjett-cache/<år>/nokkeltall_kandidater.md`,
   rett `data/nokkeltall.json` (dokument-ID + PDF-side), og kjør `python pipeline/build.py --skip-crawl --publish`.

## Steg

| Fil | Gjør |
| --- | --- |
| `pipeline/crawl.py` | Leser samlesiden og følger lenkene, laster ned PDF-er til cache, skriver `data/manifest.json` |
| `pipeline/extract.py` | Tekst per side (PyMuPDF), kapittel/post-gjenkjenning, kapitteloppslag fra Gul bok-tallgrunnlaget |
| `pipeline/places.py` | Merker sider med fylker ut fra kommunenavn, regioner og prosjekter (`data/fylker/`) |
| `pipeline/keyfigures.py` | Foreslår kandidatsider for nøkkeltall; tallene ligger i `data/nokkeltall.json` |
| `pipeline/index.py` | Pagefind-indeks (norsk stemming) og ferdig nettsted i cache-mappen `dist/` |
| `pipeline/publish.py` | Force-pusher `dist/` til `gh-pages` |

`data/mangler.md` lister alt pipelinen forventet å finne, men ikke fant.

Avhengigheter: `pip install pymupdf "pagefind[extended]" requests beautifulsoup4 openpyxl`.
