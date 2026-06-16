"""Provider-agnostic LLM refiner with a free-tier fallback chain (Refiner protocol).

The `Refiner` is just a protocol, so the loop does not care *what* drives the
edits. This binding removes the dependency on headless `claude -p` (and its
account quota) by driving any OpenAI-compatible chat endpoint, walking a
fallback chain when a free tier throttles or fails -- the standing policy from
the `free-llm` skill:

    NVIDIA NIM  ->  Groq / Gemini  ->  local Ollama  ->  (paid keys)

Design notes:
  - **stdlib only.** Uses `urllib.request`; no new dependency, matching the
    project's stdlib discipline.
  - **Jailed edits.** The model returns full-file rewrites as JSON; each target
    path is applied ONLY if it resolves inside the tool workspace
    (`within_workspace`). Model output is never executed as a shell command.
  - **Bounded.** A capped set of the tool's text files is shown to the model and
    a capped number of edits is applied, so a refine turn is predictable.
  - **Honest.** Returns a diff_ref (git shortstat) on a real change, or `None`
    when no provider answered or nothing changed -- the loop then rolls back, as
    with any refiner that fails to raise the grade.

Override the chain with env: `LOOPENG_REFINER_CHAIN` = comma-separated provider
keys (e.g. "groq,gemini,ollama"); per-provider `LOOPENG_REFINER_MODEL_<KEY>`
overrides the model id. Probe a wiring before trusting it (free ids churn).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from .base import RefactorBrief
from .safety import run_tool, within_workspace

# Verified free OpenAI-compatible endpoints (free-llm skill, 2026-06-11).
# api_key_env=None marks a keyless local rung (Ollama).
PROVIDERS: dict[str, "Provider"] = {}


@dataclass(frozen=True)
class Provider:
    key: str
    base_url: str
    model: str
    api_key_env: str | None  # None -> local/keyless (Ollama)


def _register(p: Provider) -> Provider:
    PROVIDERS[p.key] = p
    return p


_register(Provider("nim", "https://integrate.api.nvidia.com/v1",
                    "qwen/qwen3-coder-480b-a35b-instruct", "NVIDIA_API_KEY"))
_register(Provider("groq", "https://api.groq.com/openai/v1",
                    "openai/gpt-oss-120b", "GROQ_API_KEY"))
_register(Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
                    "gemini-2.5-flash", "GEMINI_API_KEY"))
_register(Provider("ollama", "http://localhost:11434/v1",
                    "qwen2.5-coder", None))

_DEFAULT_ORDER = ("nim", "groq", "gemini", "ollama")
_TEXT_EXT = (".py", ".go", ".js", ".ts", ".rs", ".rb", ".md", ".toml", ".cfg", ".txt", ".json", ".yaml", ".yml")
_MAX_FILES = 20
_MAX_BYTES_PER_FILE = 6000
_MAX_EDITS = 12


def default_chain() -> list[Provider]:
    """The active fallback chain: env override, else the free-llm default order,
    keeping only rungs whose key is set (Ollama is always kept -- local)."""
    order = os.environ.get("LOOPENG_REFINER_CHAIN")
    keys = [k.strip() for k in order.split(",")] if order else list(_DEFAULT_ORDER)
    chain: list[Provider] = []
    for k in keys:
        p = PROVIDERS.get(k)
        if p is None:
            continue
        if p.api_key_env is None or os.environ.get(p.api_key_env):
            model = os.environ.get(f"LOOPENG_REFINER_MODEL_{k.upper()}", p.model)
            chain.append(Provider(p.key, p.base_url, model, p.api_key_env))
    return chain


def _chat(provider: Provider, messages: list[dict], *, timeout: float) -> str:
    """One OpenAI-compatible chat completion. Raises urllib errors on failure."""
    api_key = os.environ.get(provider.api_key_env, "") if provider.api_key_env else "ollama"
    body = json.dumps({
        "model": provider.model,
        "messages": messages,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(
        f"{provider.base_url}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https endpoints
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def _collect_files(tool_path: str) -> dict[str, str]:
    """Read a bounded set of the tool's text files (path -> truncated content)."""
    out: dict[str, str] = {}
    for root, _dirs, files in os.walk(tool_path):
        if ".git" in root or "/." in root.replace(tool_path, "", 1):
            continue
        for name in sorted(files):
            if not name.endswith(_TEXT_EXT):
                continue
            full = os.path.join(root, name)
            try:
                text = open(full, encoding="utf-8", errors="replace").read(_MAX_BYTES_PER_FILE)
            except OSError:
                continue
            out[os.path.relpath(full, tool_path)] = text
            if len(out) >= _MAX_FILES:
                return out
    return out


def _build_messages(tool_path: str, brief: RefactorBrief) -> list[dict]:
    files = _collect_files(tool_path)
    listing = "\n\n".join(f"### {p}\n```\n{c}\n```" for p, c in files.items()) or "(no readable source files)"
    dims = ", ".join(brief.target_dimensions) or "the lowest-scoring dimensions"
    fixtures = ", ".join(brief.failing_fixtures) or "none reported"
    system = (
        "You are a senior engineer improving an agent-native CLI so an independent "
        "grader (CLI-Judge) raises its score. Make focused, correct edits. "
        "Respond ONLY with JSON of the form "
        '{"summary": "...", "edits": [{"path": "<relative path>", "content": "<full new file contents>"}]}. '
        "Each edit replaces the entire file. Do not include files you are not changing. "
        "Never add destructive shell commands, network exfiltration, or secrets."
    )
    user = (
        f"Goal: {brief.goal}\n"
        f"Prioritize these dimensions: {dims}.\n"
        f"Failing fixtures to address: {fixtures}.\n\n"
        f"Current files:\n{listing}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_edits(content: str) -> tuple[str, list[dict]]:
    """Extract (summary, edits) from a model response. Tolerates ```json fences."""
    text = content.strip()
    if "```" in text:
        # take the largest fenced block
        parts = text.split("```")
        text = max((p[4:] if p.lower().startswith("json") else p for p in parts), key=len).strip()
    try:
        data = json.loads(text)
    except ValueError:
        return ("", [])
    edits = data.get("edits") if isinstance(data, dict) else None
    if not isinstance(edits, list):
        return ("", [])
    clean = [e for e in edits if isinstance(e, dict) and isinstance(e.get("path"), str)
             and isinstance(e.get("content"), str)]
    return (str(data.get("summary", "")), clean[:_MAX_EDITS])


@dataclass
class FallbackLLMRefiner:
    """Drives refactoring via an OpenAI-compatible chat endpoint with a fallback
    chain (Refiner protocol). A claude-free, quota-free alternative refiner."""

    chain: list[Provider] | None = None
    timeout: float = 5 * 60
    last_provider: str | None = None
    # This refiner does not surface token cost; the controller falls back to the
    # wall-clock budget (U4). Declared to satisfy the Refiner protocol.
    last_token_cost: int | None = None

    def refactor(self, tool_path: str, brief: RefactorBrief) -> str | None:
        chain = self.chain if self.chain is not None else default_chain()
        messages = _build_messages(tool_path, brief)
        content = None
        for provider in chain:
            try:
                content = _chat(provider, messages, timeout=self.timeout)
                self.last_provider = provider.key
                break
            except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, OSError):
                continue  # free tier throttled / unreachable -> next rung
        if content is None:
            return None  # whole chain failed -> no change, loop will not advance

        _summary, edits = _parse_edits(content)
        applied = 0
        for edit in edits:
            dest = os.path.normpath(os.path.join(tool_path, edit["path"]))
            if not within_workspace(dest, tool_path):
                continue  # jail: never write outside the tool workspace
            os.makedirs(os.path.dirname(dest) or tool_path, exist_ok=True)
            try:
                with open(dest, "w", encoding="utf-8") as fh:
                    fh.write(edit["content"])
                applied += 1
            except OSError:
                continue
        if applied == 0:
            return None

        diff = run_tool(["git", "-C", tool_path, "diff", "--shortstat"], timeout=60)
        return diff.stdout.strip() or f"applied {applied} edit(s) via {self.last_provider}"
