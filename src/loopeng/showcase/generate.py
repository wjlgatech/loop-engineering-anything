"""Showcase catalog generator (U3).

Renders the registry into ONE self-contained HTML file (inline CSS/JS, no
external assets). Community-contributed content is untrusted, so encoding is
context-aware (KTD7): text via ``html.escape``, attributes via ``html.escape(quote=True)``,
URLs via ``safe_url`` (scheme allow-list). No untrusted string is ever placed in
a ``<script>`` literal — client-side search/filter reads escaped ``data-*``
attributes from the DOM, closing the JS-context injection path entirely.

Each card headlines the loop outcome (KTD4) and its provenance (KTD2): an
``illustrative`` fixture is badged as not-a-verified-run so a hand-authored
trajectory can never masquerade as real engine output.
"""

from __future__ import annotations

import html
from collections import Counter
from urllib.parse import urlparse

from ..demos.registry import Registry

_GRADE_CLASS = {"A": "g-a", "B": "g-b", "C": "g-c", "D": "g-d", "F": "g-f"}


def _t(s) -> str:
    """HTML text-node escape."""
    return html.escape("" if s is None else str(s))


def _a(s) -> str:
    """HTML attribute escape."""
    return html.escape("" if s is None else str(s), quote=True)


def safe_url(url) -> str | None:
    """Return the URL if it is https or repo-relative; else None.

    Rejects javascript:/data:/vbscript: and scheme-relative (//host) URLs.
    """
    if not url:
        return None
    u = str(url).strip()
    if u.startswith("//"):
        return None
    if urlparse(u).scheme in ("", "https"):
        low = u.lower()
        if low.startswith(("javascript:", "data:", "vbscript:")):
            return None
        return u
    return None


def _doc_href(base_url: str, path: str) -> str | None:
    """Build a link to a repo doc: relative when base_url is empty, else absolute
    (e.g. a GitHub blob URL) so links resolve when the catalog is hosted."""
    return safe_url(f"{base_url}{path}")


def _trajectory(result) -> str:
    return " &rarr; ".join(_t(g) for g in result.grade_trajectory)


def _proof_line(result) -> str:
    """Compact before/after summary for a verified card, from the proof pack.

    Renders e.g. "C &rarr; A · top: D3 +18 · 4 iters · 38s". All values are
    numbers/letters derived from the parsed proof pack, but they are escaped
    defensively anyway."""
    proof = getattr(result, "proof", None)
    if not proof:
        return ""
    bits = []
    before, after = proof.get("before_grade"), proof.get("after_grade")
    if before and after:
        bits.append(f"{_t(before)} &rarr; {_t(after)}")
    # Highlight the dimension with the largest positive delta.
    dim_diff = proof.get("dim_diff") or {}
    best = None
    for name, d in dim_diff.items():
        delta = d.get("delta")
        if isinstance(delta, (int, float)) and (best is None or delta > best[1]):
            best = (name, delta)
    if best and best[1] > 0:
        bits.append(f"top: {_t(best[0])} +{_t(str(round(best[1], 1)))}")
    if isinstance(proof.get("iterations"), int):
        bits.append(f"{_t(str(proof['iterations']))} iters")
    if isinstance(proof.get("elapsed_seconds"), (int, float)):
        bits.append(f"{_t(str(round(proof['elapsed_seconds'])))}s")
    if isinstance(proof.get("token_cost"), int):
        bits.append(f"{_t(str(proof['token_cost']))} tok")
    if not bits:
        return ""
    return f'<p class="proof" aria-label="before/after proof">{" &middot; ".join(bits)}</p>'


def _demo_card(manifest, result, base_url: str = "") -> str:
    search_blob = " ".join(
        x for x in (manifest.id, manifest.domain, manifest.target, manifest.contributor) if x
    )
    head = (
        f'<article class="card" data-domain="{_a(manifest.domain)}" data-search="{_a(search_blob.lower())}">'
        f'<h3>{_t(manifest.title)}</h3>'
        f'<p class="domain">{_t(manifest.domain)}</p>'
        f'<p class="target">{_t(manifest.target)}</p>'
    )
    if result is None:
        body = (
            '<p class="traj" aria-label="not yet run">&mdash; not yet run &mdash;</p>'
            '<div class="badges">'
            '<span class="badge grade g-q" aria-label="no grade yet">?</span>'
            '<span class="badge prov draft">draft</span>'
            '</div>'
        )
    else:
        grade_cls = _GRADE_CLASS.get(result.final_grade, "g-q")
        prov = (
            '<span class="badge prov verified">verified run</span>'
            if result.verified
            else '<span class="badge prov illustrative">illustrative &mdash; not a verified run</span>'
        )
        report = ""
        href = _doc_href(base_url, f"demos/results/{result.report_ref}") if result.report_ref else None
        if href:
            report = f'<a class="report" href="{_a(href)}">report &rarr;</a>'
        body = (
            f'<p class="traj" aria-label="grade trajectory {_a(" to ".join(result.grade_trajectory))}">'
            f'{_trajectory(result)}</p>'
            f'{_proof_line(result) if result.verified else ""}'
            f'<div class="badges">'
            f'<span class="badge grade {grade_cls}">{_t(result.final_grade)}</span>'
            f'<span class="badge conv {_a(result.convergence_status)}">{_t(result.convergence_status)}</span>'
            f'{prov}</div>{report}'
        )
    foot = f'<p class="by">{_t("by @" + manifest.contributor) if manifest.contributor else ""}</p></article>'
    return head + body + foot


def _recipe_card(manifest, base_url: str = "") -> str:
    search_blob = f"{manifest.id} {manifest.domain} {manifest.target}".lower()
    href = _doc_href(base_url, f"docs/recipes/{manifest.id}.md")
    link = f'<a class="report" href="{_a(href)}">recipe &rarr;</a>' if href else ""
    return (
        f'<article class="card recipe" data-domain="{_a(manifest.domain)}" data-search="{_a(search_blob)}">'
        f'<h3>{_t(manifest.title)}</h3>'
        f'<p class="domain">{_t(manifest.domain)}</p>'
        f'<p class="goal">{_t(manifest.goal)}</p>'
        f'<div class="badges"><span class="badge prov recipe">recipe &mdash; not runnable yet</span></div>{link}</article>'
    )


def _leaderboard(reg: Registry, base_url: str = "") -> str:
    counts = Counter(m.contributor for m in reg.manifests.values() if m.contributor)
    if not counts:
        contrib = _a(_doc_href(base_url, "CONTRIBUTING-demos.md") or "CONTRIBUTING-demos.md")
        return f'<p class="empty">Be the first &mdash; see <a href="{contrib}">CONTRIBUTING-demos.md</a></p>'
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    items = "".join(f'<li>@{_t(name)} <span class="count">{n}</span></li>' for name, n in ranked)
    return f"<ol class=\"leaderboard\">{items}</ol>"


_CSS = """
:root{
  --bg:#fbfbfd;--card:#ffffff;--fg:#1a1f29;--mut:#5b6573;--faint:#8a93a3;
  --acc:#3b5bdb;--acc-soft:#eef1fe;--line:#e6e8ec;--line-2:#d7dbe2;
  --ok:#1a7f37;--ok-soft:#e8f5ec;--warn:#9a6700;--warn-soft:#fbf3e0;
  --bad:#cf222e;--bad-soft:#fdeceb;--info:#1f6feb;--info-soft:#e8f1fe;
  --violet:#7048c4;--violet-soft:#f1ecfb;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0d1117;--card:#161b22;--fg:#e9edf3;--mut:#9aa4b2;--faint:#6e7888;
  --acc:#7aa2ff;--acc-soft:#18203a;--line:#262c36;--line-2:#333b47;
  --ok:#3fb950;--ok-soft:#12261a;--warn:#d29922;--warn-soft:#2a2113;
  --bad:#f0816c;--bad-soft:#2a1715;--info:#58a6ff;--info-soft:#13243d;
  --violet:#b083f0;--violet-soft:#221a33;
}}
*{box-sizing:border-box}
body{margin:0;font-family:var(--sans);font-size:15px;line-height:1.6;background:var(--bg);color:var(--fg);
  font-feature-settings:"cv05","ss01";-webkit-font-smoothing:antialiased}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px 80px}
.topbar{position:sticky;top:0;z-index:5;display:flex;align-items:center;justify-content:space-between;
  gap:16px;padding:14px 24px;background:color-mix(in srgb,var(--bg) 86%,transparent);
  backdrop-filter:saturate(1.4) blur(8px);border-bottom:1px solid var(--line)}
.topbar .brand{font-weight:650;letter-spacing:-.01em;color:var(--fg)}
.topbar nav a{color:var(--mut);margin-left:18px;font-size:.9rem}
.topbar nav a:hover{color:var(--fg);text-decoration:none}
.hero{text-align:center;padding:72px 16px 40px;max-width:720px;margin:0 auto}
.eyebrow{font-size:.72rem;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--faint)}
.hero h1{font-size:2.6rem;line-height:1.1;letter-spacing:-.03em;font-weight:720;margin:.28em 0 .25em}
.hero p{color:var(--mut);font-size:1.08rem;max-width:600px;margin:.4em auto 0}
.cta{display:inline-block;margin:22px 5px 0;padding:9px 18px;border-radius:9px;font-size:.92rem;font-weight:550}
.cta.primary{background:var(--acc);color:#fff}.cta.primary:hover{text-decoration:none;filter:brightness(1.06)}
.cta.ghost{border:1px solid var(--line-2);color:var(--fg)}.cta.ghost:hover{text-decoration:none;border-color:var(--mut)}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0 28px}
.controls input{flex:1;min-width:220px;padding:10px 14px;background:var(--card);border:1px solid var(--line);
  border-radius:10px;color:var(--fg);font-size:.92rem}
.controls input:focus{outline:none;border-color:var(--acc);box-shadow:0 0 0 3px var(--acc-soft)}
.chip{padding:7px 14px;background:var(--card);border:1px solid var(--line);border-radius:999px;color:var(--mut);
  cursor:pointer;font-size:.83rem;font-weight:500}
.chip:hover{border-color:var(--line-2);color:var(--fg)}
.chip[aria-pressed=true]{background:var(--acc-soft);border-color:transparent;color:var(--acc);font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px;
  display:flex;flex-direction:column;transition:border-color .15s,transform .15s}
.card:hover{border-color:var(--line-2);transform:translateY(-2px)}
.card h3{margin:0 0 .5em;font-size:1.06rem;font-weight:620;letter-spacing:-.01em}
.card .domain{display:inline-block;align-self:flex-start;color:var(--acc);background:var(--acc-soft);
  font-size:.72rem;font-weight:600;letter-spacing:.02em;padding:2px 9px;border-radius:999px;margin:0 0 .6em}
.card .target,.card .goal{color:var(--mut);font-size:.86rem;word-break:break-word;margin:0 0 .8em}
.traj{font-family:var(--mono);font-size:1.18rem;font-weight:600;letter-spacing:.04em;margin:.2em 0 .5em;color:var(--fg)}
.proof{font-family:var(--mono);font-size:.78rem;color:var(--mut);margin:0 0 .7em;font-variant-numeric:tabular-nums}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:.71rem;font-weight:600;margin:0 6px 0 0;letter-spacing:.01em}
.grade{font-variant-numeric:tabular-nums}
.g-a{background:var(--ok-soft);color:var(--ok)}.g-b{background:var(--ok-soft);color:var(--ok)}
.g-c{background:var(--warn-soft);color:var(--warn)}.g-d{background:var(--warn-soft);color:var(--warn)}
.g-f{background:var(--bad-soft);color:var(--bad)}.g-q{background:var(--line);color:var(--mut)}
.conv{background:var(--line);color:var(--mut)}.conv.blocked_safety{background:var(--bad-soft);color:var(--bad)}
.prov.verified{background:var(--info-soft);color:var(--info)}
.prov.illustrative{background:var(--warn-soft);color:var(--warn)}
.prov.draft{background:var(--line);color:var(--mut)}
.prov.recipe{background:var(--violet-soft);color:var(--violet)}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin-top:auto}
.report{margin-top:14px;color:var(--acc);font-size:.86rem;font-weight:550}
.by{color:var(--faint);font-size:.76rem;margin:14px 0 0}
.recipes{margin-top:64px;padding-top:8px}
.empty{color:var(--mut);text-align:center;padding:40px;border:1px dashed var(--line-2);border-radius:14px}
.leaderboard{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:10px}
.leaderboard li{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:7px 14px;font-size:.88rem}
.count{color:var(--acc);font-weight:700;font-variant-numeric:tabular-nums}
h2{font-size:1.05rem;font-weight:650;letter-spacing:-.01em;margin:56px 0 18px;padding-bottom:10px;border-bottom:1px solid var(--line)}
@media(max-width:560px){.wrap{padding:0 16px 56px}.hero{padding:48px 8px 32px}.hero h1{font-size:2.1rem}.grid{grid-template-columns:1fr}.traj{word-break:break-word}}
"""

_JS = """
const q=document.getElementById('q');const grid=document.getElementById('grid');
let domain='';
function apply(){const term=(q.value||'').toLowerCase();let shown=0;
 document.querySelectorAll('.card').forEach(c=>{
  const okD=!domain||c.dataset.domain===domain;
  const okS=!term||(c.dataset.search||'').includes(term);
  const vis=okD&&okS;c.style.display=vis?'':'none';if(vis)shown++;});
 document.getElementById('noresults').style.display=shown?'none':'';}
document.querySelectorAll('.chip').forEach(ch=>ch.addEventListener('click',()=>{
 document.querySelectorAll('.chip').forEach(x=>x.setAttribute('aria-pressed','false'));
 ch.setAttribute('aria-pressed','true');domain=ch.dataset.domain||'';apply();}));
q.addEventListener('input',apply);
"""


def render_catalog(reg: Registry, base_url: str = "") -> str:
    demos = reg.demos()
    recipes = reg.recipes()
    domains = sorted({m.domain for m in demos})
    contrib = _a(_doc_href(base_url, "CONTRIBUTING-demos.md") or "CONTRIBUTING-demos.md")

    chips = '<button class="chip" data-domain="" aria-pressed="true">All</button>' + "".join(
        f'<button class="chip" data-domain="{_a(d)}" aria-pressed="false">{_t(d)}</button>' for d in domains
    )
    if demos:
        cards = "".join(_demo_card(m, reg.result_for(m), base_url) for m in demos)
        grid = f'<div class="grid" id="grid" aria-live="polite">{cards}</div>'
        noresults = '<p class="empty" id="noresults" style="display:none">No demos match &mdash; clear the filter.</p>'
    else:
        grid = '<div class="grid" id="grid" aria-live="polite"></div>'
        noresults = f'<p class="empty" id="noresults">No demos yet &mdash; see <a href="{contrib}">CONTRIBUTING-demos.md</a>.</p>'

    recipes_section = ""
    if recipes:
        recipe_cards = "".join(_recipe_card(m, base_url) for m in recipes)
        recipes_section = (
            '<section class="recipes"><h2>Loop recipes (not runnable yet)</h2>'
            f'<div class="grid">{recipe_cards}</div></section>'
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>loop-engineering-anything &mdash; demo showcase</title>
<style>{_CSS}</style></head>
<body>
<div class="topbar">
<span class="brand">&#9851;&#65039; loop-anything-hub</span>
<nav><a href="#grid">Demos</a><a href="https://github.com/wjlgatech/loop-engineering-anything">GitHub</a><a href="{contrib}">Contribute</a></nav>
</div>
<div class="wrap">
<header class="hero">
<p class="eyebrow">loop-engineering-anything</p>
<h1>Tools that grade themselves better</h1>
<p>Each demo is a real target our loop made agent-native, then refactored toward Grade A &mdash; generate &rarr; judge &rarr; refactor, with the grade trajectory shown.</p>
<a class="cta primary" href="#grid">Browse demos</a>
<a class="cta ghost" href="{contrib}">Add your own</a>
</header>
<div class="controls" role="search">
{chips}
<input id="q" type="search" placeholder="Search demos&hellip;" aria-label="Search demos">
</div>
{noresults}
{grid}
{recipes_section}
<h2>Contributors</h2>
{_leaderboard(reg, base_url)}
</div>
<script>{_JS}</script>
</body></html>
"""
