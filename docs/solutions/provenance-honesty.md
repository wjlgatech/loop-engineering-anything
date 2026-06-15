# Provenance honesty: live_verified is record-only

**Decision.** A demo/proof card flips to `source: live_verified` **only** via
`loop-anything demo record` / `demo proof` against a real run in the memory
store. Hand-editing a fixture to `live_verified` is forbidden; a `blocked_safety`
run is recorded honestly and never as a passing proof; a no-gain run is recorded
as-is; a proof target with no run stays in **draft** (no fixture) — never a
fabricated `illustrative` trajectory.

**Why.** This is the failure mode the "honesty pass" (commit `0c90d7d`)
corrected: a fabricated `blocked_safety` status was being shown decoratively to
light up a badge. The `source` axis (`illustrative` | `live_verified`) plus the
record-only write path makes verified status **unfakeable at a glance**. The
proof pipeline reuses this primitive rather than inventing a second write path:
`demo proof` extends `demo record`'s payload, it does not bypass it.

**Enforced by.** `ProofPack.is_improvement` returns False for `blocked_safety`;
`tests/test_starter_demos.py` asserts proof targets are draft-or-illustrative,
never unearned-`live_verified`; badge/state coverage is exercised by synthetic
generator tests, never by planting real-world status.

See `docs/plans/2026-06-15-003-...-plan.md` (KTD2) and plan-002 KTD2.
