"""The run contract — a reviewable order ticket for one loop (plan 2026-08-12 U1).

Before this module the inputs to a run (target, goal, lane, every budget knob)
existed only as CLI flags: unreviewable, un-diffable, and impossible to attach to
the proof pack a run produces. A contract makes them a file that lives in the
repo next to the thing it converges.

Three rules make it honest rather than decorative:

1. **Compile, don't extend.** A contract is compiled into ``config.Budget`` /
   ``config.Lane`` — primitives the controller already enforces. It adds no
   controller state (KTD1) and cannot introduce a knob the loop does not read.
2. **Fail closed on anything unenforced.** Unknown keys are an error, not a
   silent no-op. A typo'd ``max_iteratons:`` or a hopeful ``safety: {forbidden:
   [...]}`` block MUST NOT read as "configured" when nothing consumes it — a
   declaration the engine ignores is exactly the false-green this repo exists to
   prevent. Notably absent for that reason: ``domain`` (the ``run`` path routes
   by lane and has no forced-domain seam yet) and per-dimension evaluation
   weights (the referee owns its rubric — maker ≠ checker).
3. **The gate is monotonic.** ``require_human_confirm`` may be omitted or set
   ``true``; ``false`` is rejected. A contract is caller-authored, and the
   anti-surrender rule (``config.VerificationGate``) is that a caller can never
   disable its own confirmation. A contract may only ever *tighten*.

``evidence.required`` is checked against a real proof pack by
``missing_evidence`` — so declaring evidence is a claim the run must satisfy,
not a promise in a file.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Budget, Lane
from ..grades import GRADE_RANK

CONTRACT_VERSION = 1

_TOP_KEYS = frozenset({"version", "name", "target", "goal", "lane", "budget", "gate", "evidence"})
_GATE_KEYS = frozenset({"require_human_confirm"})
_EVIDENCE_KEYS = frozenset({"required"})

# Evidence name -> the ``proof.ProofPack`` keys that make it real. Only fields a
# real pack actually carries are nameable; an unlisted name is a parse error, so
# a contract can never require evidence the engine has no way to produce.
EVIDENCE_FIELDS: dict[str, tuple[str, ...]] = {
    "grade_trajectory": ("before_grade", "after_grade"),
    "dimension_diff": ("dim_diff",),
    "iterations": ("iterations",),
    "convergence_status": ("convergence_status",),
    "elapsed": ("elapsed_seconds",),
    "token_cost": ("token_cost",),
    "regression_tests": ("regression_tests",),
}

# Budget knobs, each mapped to how it is validated. ``kind`` is the python type;
# ``minimum`` is an inclusive floor; ``optional`` fields accept an explicit null.
_BUDGET_NUMERIC: dict[str, tuple[type, float, bool]] = {
    # key: (kind, minimum, optional)
    "target_score": (float, 0.0, True),
    "max_iterations": (int, 1, False),
    "plateau_patience": (int, 1, False),
    "plateau_pivots": (int, 0, False),
    "token_budget": (int, 1, True),
    "max_wall_seconds": (float, 1.0, True),
    "max_tool_retries": (int, 0, False),
    "compression_interval": (int, 1, False),
    "min_score_gain": (float, 0.0, False),
}
_BUDGET_KEYS = frozenset({"target_grade", *_BUDGET_NUMERIC})


class ContractError(ValueError):
    """A malformed run contract (unknown key, bad type, or a loosened gate)."""


@dataclass(frozen=True)
class RunContract:
    """A parsed, compiled contract. Every field is something the engine enforces."""

    target: str
    goal: str
    name: str = ""
    lane: Lane | None = None
    budget: Budget = Budget()
    # Always True. Present as a field (rather than implied) so the compiled plan
    # a reviewer reads states the gate explicitly; see rule 3 above.
    require_human_confirm: bool = True
    evidence_required: tuple[str, ...] = ()
    source: str = ""


# ----- primitive validators ------------------------------------------------


def _fail(where: str, msg: str) -> None:
    raise ContractError(f"{where}: {msg}")


def _mapping(value, where: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        _fail(where, f"must be a mapping, got {type(value).__name__}")
    return value


def _reject_unknown(data: dict, allowed: frozenset[str], where: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        _fail(
            where,
            f"unknown key(s) {unknown}; accepted: {sorted(allowed)}. "
            "A contract may only declare what the engine enforces.",
        )


def _string(data: dict, key: str, where: str, *, required: bool = False, default: str = "") -> str:
    if key not in data or data[key] is None:
        if required:
            _fail(where, f"'{key}' is required")
        return default
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        _fail(where, f"'{key}' must be a non-empty string, got {value!r}")
    return value.strip()


def _number(data: dict, key: str, where: str, default):
    """Validate one numeric budget knob against ``_BUDGET_NUMERIC``."""
    if key not in data:
        return default
    kind, minimum, optional = _BUDGET_NUMERIC[key]
    value = data[key]
    if value is None:
        if not optional:
            _fail(where, f"'{key}' may not be null")
        return None
    # bool is an int subclass; a YAML `true` here is a typo, not a number.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(where, f"'{key}' must be a number, got {value!r}")
    if kind is int and not isinstance(value, int):
        _fail(where, f"'{key}' must be a whole number, got {value!r}")
    if value < minimum:
        _fail(where, f"'{key}' must be >= {minimum}, got {value!r}")
    return kind(value)


# ----- section parsers -----------------------------------------------------


def _parse_budget(raw, where: str) -> Budget:
    data = _mapping(raw, where)
    _reject_unknown(data, _BUDGET_KEYS, where)
    defaults = Budget()

    grade = _string(data, "target_grade", where, default=defaults.target_grade).upper()
    if grade not in GRADE_RANK:
        _fail(where, f"'target_grade' must be one of {sorted(GRADE_RANK)}, got {grade!r}")

    knobs = {k: _number(data, k, where, getattr(defaults, k)) for k in _BUDGET_NUMERIC}
    return Budget(target_grade=grade, **knobs)


def _parse_gate(raw, where: str) -> bool:
    data = _mapping(raw, where)
    _reject_unknown(data, _GATE_KEYS, where)
    value = data.get("require_human_confirm", True)
    if value is not True:
        _fail(
            where,
            "'require_human_confirm' may only be true. A contract is caller-authored and "
            "may only tighten the human gate, never disable it (anti-surrender, "
            "config.VerificationGate).",
        )
    return True


def _parse_evidence(raw, where: str) -> tuple[str, ...]:
    data = _mapping(raw, where)
    _reject_unknown(data, _EVIDENCE_KEYS, where)
    required = data.get("required", [])
    if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
        _fail(where, f"'required' must be a list of strings, got {required!r}")
    unknown = sorted({x for x in required} - set(EVIDENCE_FIELDS))
    if unknown:
        _fail(
            where,
            f"unknown evidence {unknown}; a proof pack can carry {sorted(EVIDENCE_FIELDS)}",
        )
    # Order-preserving dedupe so the compiled plan reads as authored.
    seen: list[str] = []
    for name in required:
        if name not in seen:
            seen.append(name)
    return tuple(seen)


def _parse_lane(data: dict, where: str) -> Lane | None:
    raw = _string(data, "lane", where)
    if not raw:
        return None
    try:
        return Lane(raw)
    except ValueError:
        _fail(where, f"'lane' must be one of {[ln.value for ln in Lane]}, got {raw!r}")
    return None  # pragma: no cover - _fail always raises


# ----- entry points --------------------------------------------------------


def parse_contract(data, *, source: str = "contract") -> RunContract:
    """Validate a contract mapping and compile it into a ``RunContract``.

    Raises ``ContractError`` — with the offending key named — on anything the
    engine would not enforce.
    """
    root = _mapping(data, source)
    if not root:
        _fail(source, "contract is empty")
    _reject_unknown(root, _TOP_KEYS, source)

    version = root.get("version")
    if version != CONTRACT_VERSION:
        _fail(source, f"'version' must be {CONTRACT_VERSION}, got {version!r}")

    target = _string(root, "target", source, required=True)
    goal = _string(root, "goal", source, required=True)
    return RunContract(
        target=target,
        goal=goal,
        name=_string(root, "name", source, default=""),
        lane=_parse_lane(root, source),
        budget=_parse_budget(root.get("budget"), f"{source}.budget"),
        require_human_confirm=_parse_gate(root.get("gate"), f"{source}.gate"),
        evidence_required=_parse_evidence(root.get("evidence"), f"{source}.evidence"),
        source=source,
    )


def load_contract(path: str) -> RunContract:
    """Read a ``.yaml``/``.yml``/``.json`` contract from ``path`` and parse it."""
    import json
    import pathlib

    p = pathlib.Path(path)
    suffix = p.suffix.lower()
    if suffix not in {".yaml", ".yml", ".json"}:
        raise ContractError(f"{path}: contract must be a .yaml, .yml, or .json file")
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"{path}: cannot read contract ({exc})") from exc

    try:
        if suffix == ".json":
            data = json.loads(text)
        else:
            import yaml

            data = yaml.safe_load(text)
    except Exception as exc:  # yaml.YAMLError is not a ValueError -- catch broadly, report precisely
        raise ContractError(f"{path}: could not parse ({exc})") from exc

    return parse_contract(data, source=path)


def missing_evidence(contract: RunContract, pack: dict) -> list[str]:
    """Evidence names the contract requires that ``pack`` does not carry.

    A proof pack omits (never fakes) a field it has no source for, so absence
    here is a real, reportable gap between what was promised and what was proved.
    """
    missing = []
    for name in contract.evidence_required:
        keys = EVIDENCE_FIELDS[name]
        if any(pack.get(k) in (None, "", [], {}) for k in keys):
            missing.append(name)
    return missing


def describe(contract: RunContract) -> dict:
    """The compiled plan, as a reviewer (or `--json`) sees it."""
    b = contract.budget
    return {
        "name": contract.name or contract.target,
        "target": contract.target,
        "goal": contract.goal,
        "lane": contract.lane.value if contract.lane else None,
        "budget": {
            "target_grade": b.target_grade,
            "target_score": b.target_score,
            "max_iterations": b.max_iterations,
            "plateau_patience": b.plateau_patience,
            "plateau_pivots": b.plateau_pivots,
            "token_budget": b.token_budget,
            "max_wall_seconds": b.max_wall_seconds,
            "max_tool_retries": b.max_tool_retries,
            "compression_interval": b.compression_interval,
            "min_score_gain": b.min_score_gain,
        },
        "require_human_confirm": contract.require_human_confirm,
        "evidence_required": list(contract.evidence_required),
        "source": contract.source,
    }
