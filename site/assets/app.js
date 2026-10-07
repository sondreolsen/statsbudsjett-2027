// Statsbudsjettet: søk med Pagefind, filtre i URL-en, lys/mørk modus.
const SITE = window.SITE;
const PAGE_SIZE = 10;
const GROUPS = [
  { key: "type", label: "Dokumenttype", all: "Alle typer" },
  { key: "dep", label: "Departement", all: "Alle departementer" },
  { key: "fylke", label: "Fylke", all: "Alle fylker" },
];
const nf = new Intl.NumberFormat("nb-NO");

const $ = (s, el = document) => el.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null) n.append(c);
  return n;
};
const icon = (name, cls = "i") => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("class", cls);
  s.setAttribute("aria-hidden", "true");
  const u = document.createElementNS("http://www.w3.org/2000/svg", "use");
  u.setAttribute("href", `#i-${name}`);
  s.append(u);
  return s;
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------- Tilstand i URL ---------- */
const state = { q: "", type: "", dep: "", fylke: "" };
function readUrl() {
  const p = new URLSearchParams(location.search);
  for (const k of Object.keys(state)) state[k] = p.get(k) || "";
}
function writeUrl() {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(state)) if (v) p.set(k, v);
  const qs = p.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}
const activeFilters = () => GROUPS.filter((g) => state[g.key]);

/* ---------- Pagefind ---------- */
let pagefind = null;
let pagefindLoading = null;
let allFilters = null;
function loadPagefind() {
  if (!pagefindLoading) {
    pagefindLoading = import(new URL("../pagefind/pagefind.js", import.meta.url).href).then(async (pf) => {
      await pf.options({ excerptLength: 34 });
      await pf.init();
      pagefind = pf;
      allFilters = await pf.filters();
      renderFilterUi();
      return pf;
    });
  }
  return pagefindLoading;
}

/* ---------- Filter-UI ---------- */
function optionsFor(key, counts) {
  let names;
  if (key === "dep") names = SITE.departments;
  else if (key === "type") names = SITE.types;
  else names = (SITE.fylker || []).slice();
  const source = (allFilters && allFilters[key]) || {};
  const set = new Set([...names, ...Object.keys(source)]);
  let list = [...set];
  if (key !== "type") list.sort((a, b) => a.localeCompare(b, "nb"));
  return list.map((name) => ({ name, count: counts ? counts[key]?.[name] ?? 0 : source[name] }));
}

let lastCounts = null;
function chipFor(key, opt, after) {
  const pressed = state[key] === opt.name;
  return el("button", {
    type: "button", class: "chip", "aria-pressed": String(pressed),
    disabled: !pressed && lastCounts && opt.count === 0 ? true : null,
    onclick: () => { state[key] = pressed ? "" : opt.name; after?.(); update(); },
  }, opt.name, opt.count != null ? el("span", { class: "count" }, nf.format(opt.count)) : null);
}

function renderFilterUi() {
  // Desktop: chips med nedtrekkspanel
  const bar = $("#chips-bar");
  bar.replaceChildren();
  for (const g of GROUPS) {
    const id = `pop-${g.key}`;
    const active = state[g.key];
    const btn = el("button", {
      type: "button", class: `chip${active ? " active" : ""}`, "aria-expanded": "false", "aria-controls": id,
      onclick: (e) => {
        const pop = document.getElementById(id);
        const open = pop.hidden;
        closePopovers();
        if (open) { pop.hidden = false; e.currentTarget.setAttribute("aria-expanded", "true"); pop.querySelector("button")?.focus(); }
      },
    }, active ? `${g.label}: ${active}` : g.label, icon("chevron-down"));
    const pop = el("div", { class: "popover", id, hidden: true, role: "group", "aria-label": g.label },
      optionsFor(g.key, lastCounts).map((o) => chipFor(g.key, o, closePopovers)));
    bar.append(el("div", { class: "dropdown" }, btn, pop));
  }
  if (activeFilters().length) {
    bar.append(el("button", { type: "button", class: "chip", onclick: () => { for (const g of GROUPS) state[g.key] = ""; update(); } },
      icon("x"), "Nullstill filtre"));
  }
  // Mobil: skuff
  const body = $("#sheet-body");
  body.replaceChildren(...GROUPS.map((g) =>
    el("fieldset", {}, el("legend", {}, g.label),
      el("div", { class: "chip-grid" }, optionsFor(g.key, lastCounts).map((o) => chipFor(g.key, o))))));
  const n = activeFilters().length;
  const badge = $("#filter-count");
  badge.hidden = !n;
  badge.textContent = n;
}
function closePopovers() {
  document.querySelectorAll(".popover").forEach((p) => (p.hidden = true));
  document.querySelectorAll("#chips-bar [aria-expanded]").forEach((b) => b.setAttribute("aria-expanded", "false"));
}
document.addEventListener("click", (e) => { if (!e.target.closest(".dropdown")) closePopovers(); });
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const open = document.querySelector(".popover:not([hidden])");
    if (open) { closePopovers(); open.previousElementSibling?.focus(); }
  }
});

/* ---------- Spesialkort ---------- */
let chapters = null;
async function kapCard(q) {
  const m = q.match(/\bkap(?:ittel|\.)?\s*(\d{1,4})\b(?:.*?\bpost\s*(\d{2})\b)?/i);
  if (!m) return null;
  if (!chapters) {
    try { chapters = await (await fetch(new URL("../data/kapitler.json", import.meta.url))).json(); } catch { return null; }
  }
  const c = chapters[m[1]];
  if (!c) return null;
  const [navn, dep, poster] = c;
  const thousands = Object.values(poster).every(([, b]) => b == null || b % 1000 === 0);
  const rows = Object.entries(poster).sort(([a], [b]) => a.localeCompare(b)).filter(([p]) => !m[2] || p === m[2]).map(([p, [pn, b]]) =>
    el("tr", {}, el("td", { class: "tnum" }, p), el("td", {}, pn),
      el("td", { class: "num" }, b == null ? "–" : nf.format(thousands ? b / 1000 : b))));
  const gul = SITE.documents.find((d) => d.id === "gulbok");
  return el("div", { class: "special" },
    el("span", { class: "eyebrow" }, `Kapitteloppslag · ${dep.trim()}`),
    el("h3", {}, `Kap. ${m[1]} ${navn}`),
    el("table", { class: "kap-table" },
      el("thead", {}, el("tr", {}, el("th", {}, "Post"), el("th", {}, "Navn"),
        el("th", { class: "num" }, `Forslag ${SITE.year} (${thousands ? "1 000 kr" : "kr"})`))),
      el("tbody", {}, rows)),
    el("p", {}, "Kilde: tallgrunnlaget til Gul bok (regjeringens forslag). ",
      SITE.tallgrunnlag ? el("a", { href: SITE.tallgrunnlag }, "Last ned tallgrunnlaget") : null,
      gul ? " · " : null, gul ? el("a", { href: gul.pdf_url }, "Gul bok (PDF)") : null));
}

function fylkeCard(name) {
  const f = (SITE.fylkessaker || []).find((x) => x.fylke === name);
  if (!f) return null;
  return el("div", { class: "special" },
    el("span", { class: "eyebrow" }, "Regjeringens fylkesoversikt"),
    el("h3", {}, f.title),
    f.headings?.length ? el("ul", {}, f.headings.slice(0, 14).map((h) => el("li", {}, h))) : null,
    el("a", { class: "link", href: f.url }, "Les hele oversikten på regjeringen.no", icon("external-link")));
}

function fylkeNotice() {
  return el("div", { class: "notice", role: "note" }, icon("info"),
    el("span", {}, "Fylkesfilteret bygger på stedsnavn i teksten (kommuner, regioner og kjente prosjekter) og er ",
      el("strong", {}, "ingen offisiell fylkesfordeling"), ". Sider kan mangle eller være tatt med feilaktig."));
}

/* ---------- Resultater ---------- */
function resultItem(d) {
  const m = d.meta || {};
  const isFylke = m.type === "Fylkesoversikt";
  const fylker = (d.filters?.fylke || []).slice(0, 3);
  const pageText = isFylke ? "Les på regjeringen.no" : `s. ${m.side}${m.side !== m.pdfside ? ` (PDF-side ${m.pdfside})` : ""}`;
  return el("li", { class: "result" },
    el("h3", {}, el("a", { href: m.url || d.url }, m.title)),
    el("div", { class: "result-meta" },
      el("span", {}, m.type),
      m.dep && m.dep !== "Regjeringen" && !(m.title || "").includes(m.dep) ? el("span", {}, m.dep) : null),
    m.kap ? el("div", { class: "result-kap" }, m.kap) : null,
    el("p", { class: "result-excerpt", html: d.excerpt }),
    el("div", { class: "result-foot" },
      el("span", { class: "result-page" }, icon(isFylke ? "external-link" : "file-text"), pageText),
      fylker.length ? el("span", { class: "tag" }, icon("map-pin"), fylker.join(", ")) : null));
}

function showSkeleton(n = 3) {
  const tpl = $("#skeleton");
  $("#results").replaceChildren(...Array.from({ length: n }, () => tpl.content.cloneNode(true)));
  $("#result-count").textContent = pagefind ? "Søker …" : "Henter søkeindeksen …";
  $("#more").hidden = true;
}

let current = { results: [], shown: 0, id: 0 };
async function renderMore() {
  const slice = current.results.slice(current.shown, current.shown + PAGE_SIZE);
  const id = current.id;
  const data = await Promise.all(slice.map((r) => r.data()));
  if (id !== current.id) return;
  const list = $("#results");
  if (current.shown === 0) list.replaceChildren();
  list.append(...data.map(resultItem));
  current.shown += slice.length;
  $("#more").hidden = current.shown >= current.results.length;
}

let searchId = 0;
async function runSearch() {
  const id = ++searchId;
  const q = state.q.trim();
  const filters = {};
  for (const g of GROUPS) if (state[g.key]) filters[g.key] = state[g.key];
  const searching = q || Object.keys(filters).length;
  $("#results-section").hidden = !searching;
  $("#figures-section").hidden = !!searching;
  if (!searching) { lastCounts = null; if (pagefind) renderFilterUi(); return; }

  showSkeleton();
  const notices = $("#notices");
  notices.replaceChildren(...(state.fylke ? [fylkeNotice()] : []));
  const special = $("#special");
  special.replaceChildren();
  const cards = [];
  if (state.fylke) cards.push(fylkeCard(state.fylke));
  if (q) cards.push(await kapCard(q));
  special.replaceChildren(...cards.filter(Boolean));

  await loadPagefind();
  if (id !== searchId) return;
  const t0 = performance.now();
  const res = await pagefind.search(q || null, { filters });
  if (id !== searchId || !res) return;
  current = { results: res.results, shown: 0, id };
  lastCounts = res.filters;
  renderFilterUi();
  const n = res.results.length;
  const ms = Math.round(performance.now() - t0);
  $("#result-count").textContent = n
    ? `${nf.format(n)} ${n === 1 ? "side" : "sider"} med treff${q ? ` for «${q}»` : ""}`
    : "";
  $("#result-count").title = `${ms} ms`;
  if (!n) {
    $("#results").replaceChildren(el("li", { class: "empty" },
      `Ingen treff${q ? ` for «${q}»` : ""}${activeFilters().length ? " med valgte filtre" : ""}. Prøv et annet ord eller fjern et filter.`));
    $("#more").hidden = true;
    return;
  }
  await renderMore();
}

let debounce;
function update({ immediate = false } = {}) {
  writeUrl();
  $("#clear").hidden = !state.q;
  renderFilterUi();
  clearTimeout(debounce);
  if (immediate) runSearch(); else debounce = setTimeout(runSearch, 180);
}

/* ---------- Oppstart ---------- */
function initTheme() {
  const btn = $("#theme-toggle");
  const sysDark = matchMedia("(prefers-color-scheme: dark)");
  const effective = () => document.documentElement.dataset.theme || (sysDark.matches ? "dark" : "light");
  const label = () => btn.setAttribute("aria-label", effective() === "dark" ? "Bytt til lys modus" : "Bytt til mørk modus");
  btn.addEventListener("click", () => {
    const next = effective() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch {}
    label();
  });
  sysDark.addEventListener?.("change", label);
  label();
}

function initSticky() {
  const band = $("#search-band");
  const sentinel = el("div", { "aria-hidden": "true", style: "height:1px" });
  band.before(sentinel);
  new IntersectionObserver(([e]) => band.classList.toggle("stuck", !e.isIntersecting)).observe(sentinel);
}

function init() {
  readUrl();
  const input = $("#q");
  input.value = state.q;
  if (matchMedia("(min-width: 768px)").matches) input.placeholder = input.dataset.longPlaceholder;
  input.addEventListener("input", () => { state.q = input.value; update(); });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") { input.blur(); update({ immediate: true }); } });
  input.addEventListener("focus", () => loadPagefind(), { once: true });
  $("#clear").addEventListener("click", () => { state.q = ""; input.value = ""; update({ immediate: true }); input.focus(); });
  $("#more").addEventListener("click", renderMore);

  const sheet = $("#filter-sheet");
  $("#open-filters").addEventListener("click", () => { loadPagefind(); renderFilterUi(); sheet.showModal(); });
  $("#close-filters").addEventListener("click", () => sheet.close());
  $("#apply-filters").addEventListener("click", () => sheet.close());
  $("#reset-filters").addEventListener("click", () => { for (const g of GROUPS) state[g.key] = ""; update(); });
  sheet.addEventListener("click", (e) => { if (e.target === sheet) sheet.close(); });

  initTheme();
  initSticky();
  renderFilterUi();
  if (state.q || activeFilters().length) runSearch();
  else if ("requestIdleCallback" in window) requestIdleCallback(() => loadPagefind(), { timeout: 3000 });
  else setTimeout(loadPagefind, 1500);
}
init();
