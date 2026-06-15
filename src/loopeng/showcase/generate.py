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
            '<span class="badge grade g-q" aria-label="no grade yet">?</span>'
            '<span class="badge prov draft">draft</span>'
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
            f'<span class="badge grade {grade_cls}">{_t(result.final_grade)}</span>'
            f'<span class="badge conv {_a(result.convergence_status)}">{_t(result.convergence_status)}</span>'
            f'{prov}{report}'
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
        f'<span class="badge prov recipe">recipe &mdash; not runnable yet</span>{link}</article>'
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
:root{--bg:#0d1117;--card:#161b22;--fg:#e6edf3;--mut:#8b949e;--acc:#58a6ff;--line:#30363d}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg)}
.wrap{max-width:1080px;margin:0 auto;padding:24px}
.hero{text-align:center;padding:48px 16px 24px}.hero h1{font-size:2.2rem;margin:.2em 0}
.hero p{color:var(--mut);max-width:640px;margin:.4em auto}
.cta{display:inline-block;margin:12px 6px 0;padding:8px 16px;border:1px solid var(--line);border-radius:8px;color:var(--acc);text-decoration:none}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:24px 0}
.controls input{flex:1;min-width:200px;padding:8px 12px;background:var(--card);border:1px solid var(--line);border-radius:8px;color:var(--fg)}
.chip{padding:6px 12px;background:var(--card);border:1px solid var(--line);border-radius:20px;color:var(--fg);cursor:pointer;font-size:.85rem}
.chip[aria-pressed=true]{border-color:var(--acc);color:var(--acc)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h3{margin:.1em 0;font-size:1.05rem}.card .domain{color:var(--acc);font-size:.8rem;margin:.2em 0}
.card .target,.card .goal{color:var(--mut);font-size:.85rem;word-break:break-word}
.traj{font-size:1.3rem;font-weight:600;letter-spacing:1px;margin:.4em 0}
.badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:.72rem;margin:2px 4px 2px 0}
.grade{font-weight:700}.g-a{background:#1a7f37;color:#fff}.g-b{background:#2f6f4f;color:#fff}.g-c{background:#9e6a03;color:#fff}.g-d{background:#bb5a00;color:#fff}.g-f{background:#cf222e;color:#fff}.g-q{background:#30363d;color:var(--mut)}
.conv{background:#21262d;color:var(--mut)}.conv.blocked_safety{background:#cf222e;color:#fff}
.prov.verified{background:#1f6feb;color:#fff}.prov.illustrative{background:#30363d;color:#d29922;border:1px solid #d29922}
.prov.draft{background:#30363d;color:var(--mut)}.prov.recipe{background:#30363d;color:#a371f7;border:1px solid #a371f7}
.report{display:block;margin-top:8px;color:var(--acc);font-size:.85rem;text-decoration:none}
.by{color:var(--mut);font-size:.78rem;margin:.5em 0 0}
.recipes{margin-top:48px;border-top:1px dashed var(--line);padding-top:24px}
.empty{color:var(--mut);text-align:center;padding:32px}
.leaderboard{list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:8px}.leaderboard li{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 12px}
.count{color:var(--acc);font-weight:700}
h2{border-bottom:1px solid var(--line);padding-bottom:6px;margin-top:40px}
@media(max-width:560px){.grid{grid-template-columns:1fr}.traj{word-break:break-word}}
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
<body><div class="wrap">
<header class="hero">
<h1>Tools that grade themselves better</h1>
<p>Each demo is a real target our loop made agent-native, then refactored toward Grade A &mdash; generate &rarr; judge &rarr; refactor, with the grade trajectory shown.</p>
<a class="cta" href="#grid">Browse demos</a>
<a class="cta" href="{contrib}">Add your own</a>
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
