#!/usr/bin/env python3
"""Measure trigger reliability as a function of installed-skill count.

WHY THIS EXISTS
---------------
The @skills paper (arXiv:2608.12610, Yin et al., 12 Aug 2026) argues that agent
skills compete for "fewer than 100 reliable auto-trigger slots per agent" and is
explicit that this number is NOT measured:

    "Our central quantity, the number of reliable auto-trigger slots, is bounded
     by argument and by the literature rather than measured by us"

and it names the missing experiment as future work:

    "The measurements this argument invites are trigger reliability as a function
     of installed-skill count"

This script runs that experiment against a REAL skill corpus (the operator's own
installed skills), not a synthetic one.

DESIGN
------
For each trial: build a menu of N skill (name, description) pairs that always
contains one target, hand the subject model a first-person user request that the
target is meant to serve, and ask which single skill should fire. Score top-1.

Two independent model families, so a result is not one vendor's quirk:
  * generator (writes the probe requests) — Gemini, never sees the distractors
  * subject   (picks the skill)           — Groq/gpt-oss, never sees the target label
That split is maker != checker applied to the data itself.

DECLARED BIAS (read before quoting any number)
----------------------------------------------
Probe requests are generated FROM the target's own description, so the target's
trigger wording leaks into the request. That makes every trial EASIER than reality,
where a user's phrasing is not derived from the description at all. So the accuracy
reported here is an OPTIMISTIC UPPER BOUND: whatever degradation appears, the real
degradation is at least that large. This is stated in the output, not buried.

HONESTY RULES
-------------
* A failed API call is recorded as an error and excluded from the denominator --
  never silently scored as a miss (that would manufacture the paper's conclusion).
* Every response is cached to disk keyed by its exact prompt, so a re-run is free
  and the numbers are reproducible rather than re-sampled.
* If fewer than MIN_TRIALS usable trials land for an N, that N reports "insufficient
  data" instead of a number.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import random
import re
import sys
import time
import urllib.error
import urllib.request

from skillmeta import distinct as _distinct
from skillmeta import load_skills as _load_skills

HERE = pathlib.Path(__file__).resolve().parent
CACHE = HERE / ".cache"
CACHE.mkdir(exist_ok=True)

SUBJECT_MODEL = "openai/gpt-oss-120b"          # Groq
GENERATOR_MODEL = "gemini-3.6-flash"           # Google
FALLBACK_GENERATOR = "claude-haiku-4-5-20251001"  # Anthropic - only if Gemini quota is spent
GENERATOR_USED: set[str] = set()
N_SWEEP = [10, 40, 80, 176]
SEEDS = [11, 22]
MIN_TRIALS = 8


# ----- skill corpus -------------------------------------------------------


def load_skills() -> dict[str, str]:
    """Distinct {name: description} via the shared frontmatter reader.

    A local regex here once captured YAML block-scalar INDICATORS ("|", ">-") as the
    description, which handed several unrelated targets the same meaningless probe.
    See skillmeta.py."""
    readable, _ = _load_skills(pathlib.Path.home() / ".claude")
    return {n: r["desc"] for n, r in _distinct(readable).items() if r["desc"]}


# ----- transport ----------------------------------------------------------


class ProviderError(RuntimeError):
    """A provider call failed. Recorded, never scored as a model miss."""


class RateLimited(ProviderError):
    """429. Carries the server's own Retry-After when it supplies one."""

    def __init__(self, retry_after: float | None, msg: str):
        super().__init__(msg)
        self.retry_after = retry_after


def with_backoff(fn, tries: int = 7):
    """Retry ONLY rate limits, waiting the duration the server asks for. A free tier
    that says 'wait 20s' is not an error to report -- it is an instruction."""
    delay = 5.0
    for attempt in range(tries):
        try:
            return fn()
        except RateLimited as e:
            if attempt == tries - 1:
                raise
            time.sleep(e.retry_after if e.retry_after else delay)
            delay = min(delay * 1.8, 90)
    raise ProviderError("unreachable")


# Groq sits behind Cloudflare, which 403s (error 1010) on urllib's default
# User-Agent. Measured, not guessed: the identical payload succeeds under curl.
_UA = "attention-budget-research/1.0 (+loop-engineering-anything)"


def _post(url: str, key: str, payload: dict, timeout: int = 90, extra: dict | None = None) -> dict:
    body = json.dumps(payload).encode()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": _UA,
        "Accept": "application/json",
    }
    headers.update(extra or {})
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read()[:200]
        if e.code == 429:
            wait = e.headers.get("retry-after")
            raise RateLimited(float(wait) if wait and wait.replace('.','',1).isdigit() else None,
                              f"HTTP 429: {detail!r}") from e
        raise ProviderError(f"HTTP {e.code}: {detail!r}") from e
    except Exception as e:  # noqa: BLE001 -- transport is diverse; report precisely
        raise ProviderError(str(e)) from e


def _cached(tag: str, prompt_key: str, fn):
    h = hashlib.sha256(f"{tag}\0{prompt_key}".encode()).hexdigest()[:20]
    f = CACHE / f"{tag}-{h}.json"
    if f.exists():
        return json.loads(f.read_text())["value"]
    value = fn()
    f.write_text(json.dumps({"value": value}))
    return value


def ask_subject(prompt: str) -> str:
    """Groq. Needs a generous max_tokens: reasoning tokens are billed to the same
    budget and a small cap yields an EMPTY content field (measured, not assumed)."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise ProviderError("GROQ_API_KEY not set")

    def call():
        d = _post(
            "https://api.groq.com/openai/v1/chat/completions", key,
            {"model": SUBJECT_MODEL, "temperature": 0, "max_tokens": 500,
             "messages": [{"role": "user", "content": prompt}]},
        )
        return (d["choices"][0]["message"].get("content") or "").strip()

    return _cached("subject", prompt, lambda: with_backoff(call))


def ask_generator(prompt: str) -> str:
    """Probe writer.

    max_tokens is 1200, not 200. MEASURED 2026-08-13: at 200 the Gemini response came
    back as a 15-28 char FRAGMENT ("Hey, can you pull"), because reasoning tokens are
    billed against the same budget -- so several unrelated targets received identical,
    meaningless probes and the resulting accuracy measured nothing but this bug. The
    same trap hit the subject model on a different provider. If an answer looks
    truncated, suspect the token budget before the model. Deliberately a DIFFERENT model family from the subject, so the
    request wording is not authored by the same model that has to route it.

    Chain: Gemini first (free tier); on quota exhaustion fall back to Claude Haiku.
    A fallback is recorded in the output -- never silently substituted."""
    errors = []

    gkey = os.environ.get("GEMINI_API_KEY")
    if gkey:
        def gemini():
            d = _post(
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", gkey,
                {"model": GENERATOR_MODEL, "temperature": 0.7, "max_tokens": 1200,
                 "messages": [{"role": "user", "content": prompt}]},
            )
            return (d["choices"][0]["message"].get("content") or "").strip()
        try:
            return _cached("gen", prompt, lambda: with_backoff(gemini, tries=2))
        except ProviderError as e:
            errors.append(f"gemini: {e}")

    akey = os.environ.get("ANTHROPIC_API_KEY")
    if akey:
        def claude():
            d = _post(
                "https://api.anthropic.com/v1/messages", akey,
                {"model": FALLBACK_GENERATOR, "max_tokens": 1200, "temperature": 1.0,
                 "messages": [{"role": "user", "content": prompt}]},
                extra={"x-api-key": akey, "anthropic-version": "2023-06-01"},
            )
            parts = [b.get("text", "") for b in d.get("content", []) if b.get("type") == "text"]
            GENERATOR_USED.add(FALLBACK_GENERATOR)
            return "".join(parts).strip()
        try:
            return _cached("gen2", prompt, lambda: with_backoff(claude))
        except ProviderError as e:
            errors.append(f"claude: {e}")

    raise ProviderError("; ".join(errors) or "no generator key set")


# ----- the experiment -----------------------------------------------------


def make_probe(name: str, desc: str) -> str:
    """A realistic first-person request the target skill is meant to serve."""
    out = ask_generator(
        "Below is the description of a tool available to an AI assistant.\n"
        "Write ONE realistic first-person message a busy engineer would type to the\n"
        "assistant that this tool is meant to handle. Rules: do NOT name the tool, do\n"
        "NOT use the word 'skill', write it the way a person actually types (one or two\n"
        f"sentences, no preamble, no quotes).\n\nTOOL DESCRIPTION:\n{desc[:900]}"
    )
    # BUG FIXED 2026-08-13: this used to be `.split("\n")[0]`, which kept only the
    # FIRST LINE of a wrapped generation. That produced truncated, generic requests
    # ("Hey, can you pull") that were IDENTICAL across unrelated targets, so the
    # ground truth was corrupt and the measured accuracy was measuring this bug.
    # Collapse whitespace instead, and keep the whole request.
    return " ".join(out.replace("\n", " ").split()).strip('"').strip()[:400]


def menu_prompt(menu: list[tuple[str, str]], request: str) -> str:
    lines = "\n".join(f"- {n}: {d[:160]}" for n, d in menu)
    return (
        "You route a user's message to at most one tool.\n\n"
        f"AVAILABLE TOOLS ({len(menu)}):\n{lines}\n\n"
        f"USER MESSAGE:\n{request}\n\n"
        "Which single tool should handle this? Answer with the tool name exactly as "
        "written above, or the word NONE. Output only that one token."
    )


def parse_pick(raw: str, valid: set[str]) -> str | None:
    t = raw.strip().strip("`*.,:;\"' ").split()
    if not t:
        return None
    for tok in (t[-1], t[0]):
        c = tok.strip("`*.,:;\"' ")
        if c in valid or c.upper() == "NONE":
            return "NONE" if c.upper() == "NONE" else c
    for name in valid:  # last resort: the answer mentions exactly one valid name
        if re.search(rf"\b{re.escape(name)}\b", raw):
            return name
    return None


def _one_trial(target: str, request: str, names: list[str], skills: dict[str, str],
               cap: int, rng: random.Random) -> tuple[str, str | None, str | None]:
    """Run a single trial. Returns (outcome, pick, error_detail)."""
    pool = [x for x in names if x != target]
    menu_names = rng.sample(pool, cap - 1) + [target]
    rng.shuffle(menu_names)
    menu = [(x, skills[x]) for x in menu_names]
    try:
        raw = ask_subject(menu_prompt(menu, request))
    except ProviderError as e:
        return "error", None, str(e)[:120]
    pick = parse_pick(raw, set(menu_names))
    if pick == target:
        return "hit", pick, None
    if pick == "NONE":
        return "none", pick, None
    if pick is None:
        return "unparsed", pick, None
    return "wrong", pick, None


def _build_probes(targets: list[str], skills: dict[str, str]) -> dict[str, str]:
    probes: dict[str, str] = {}
    for t in targets:
        try:
            probes[t] = make_probe(t, skills[t])
        except ProviderError as e:
            print(f"  ! probe generation failed for {t}: {str(e)[:110]}")
    return probes


def _sweep(probes: dict[str, str], names: list[str], skills: dict[str, str]) -> tuple[dict, list]:
    results = {n: {"hit": 0, "wrong": 0, "none": 0, "unparsed": 0, "error": 0} for n in N_SWEEP}
    trials: list[dict] = []
    for n in N_SWEEP:
        cap = min(n, len(names))
        for seed in SEEDS:
            rng = random.Random(seed)
            for target, request in probes.items():
                outcome, pick, detail = _one_trial(target, request, names, skills, cap, rng)
                results[n][outcome] += 1
                row = {"n": cap, "seed": seed, "target": target, "outcome": outcome}
                if detail:
                    row["detail"] = detail
                else:
                    row.update({"pick": pick, "request": request[:160]})
                trials.append(row)
                if outcome != "error":
                    time.sleep(2.0)  # free tier: stay under the per-minute cap by construction
        d = results[n]
        usable = d["hit"] + d["wrong"] + d["none"] + d["unparsed"]
        acc = f"{100*d['hit']/usable:.1f}%" if usable >= MIN_TRIALS else "insufficient data"
        print(f"  N={cap:4d}  top-1 {acc:>18}  (hit {d['hit']} wrong {d['wrong']} "
              f"none {d['none']} unparsed {d['unparsed']} errors {d['error']})")
    return results, trials


def main() -> int:
    skills = load_skills()
    names = sorted(skills)
    print(f"corpus: {len(names)} distinct readable skills with a description")
    if len(names) < max(N_SWEEP):
        print(f"note: corpus smaller than max N; capping sweep at {len(names)}")

    rng = random.Random(7)
    targets = rng.sample(names, min(12, len(names)))
    print(f"generating {len(targets)} probe requests ...")
    probes = _build_probes(targets, skills)
    print(f"  {len(probes)} probes ready")
    if not probes:
        print("no probes -- refusing to report a number")
        return 1

    results, trials = _sweep(probes, names, skills)

    out = {
        "paper": "arXiv:2608.12610 (Yin et al., 12 Aug 2026)",
        "measures": "trigger reliability as a function of installed-skill count "
                    "(the paper's own named future work)",
        "declared_bias": "probe requests are generated FROM each target's description, so "
                         "target trigger wording leaks into the request; these accuracies are "
                         "an OPTIMISTIC UPPER BOUND on real-world routing",
        "subject_model": SUBJECT_MODEL,
        "generator_model": GENERATOR_MODEL,
        "generator_fallbacks_used": sorted(GENERATOR_USED),
        "corpus_size": len(names),
        "targets": sorted(probes),
        "seeds": SEEDS,
        "min_trials": MIN_TRIALS,
        "by_n": {str(n): results[n] for n in N_SWEEP},
        "trials": trials,
    }
    (HERE / "results.json").write_text(json.dumps(out, indent=2))
    print(f"\nwrote {HERE/'results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
