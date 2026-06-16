# P0 feasibility gates: status (asymmetric — do not treat both as closed)

**P0 #2 — grade stability: RESOLVED empirically.** The variance probe over the
live CLI-Judge returned identical grades across runs (spread 0.0) — the judge is
deterministic, so single-run grades are a safe control signal and
`Budget.min_score_gain` can stay 0. Re-check any target with
`loop-anything judge-variance <tool> --adapter <a.py> -k 7`.

**P0 #1 — refine quality: OPEN (mechanism settled, quality unmeasured).**
`/ce-work` + `/ce-compound` run headlessly via `claude -p` (mechanism resolved),
but whether headless `/ce-work` *substantively* raises the grade on a real tool
— vs. cosmetic edits to the graded fixtures — is unmeasured. Two compounding
risks: (a) `/ce-work` has no tool-specific context (only D1–D5 + fixture IDs),
so refinement may be shallow; (b) the same author picks the captured payloads and
writes the adapter, so a grade can be an artifact of fixture choice. The
mitigation is a **first-light experiment with a pre-registered substantive-vs-
cosmetic bar + held-out fixtures**, run the moment the `claude -p` quota opens
(2026-07-01). Build everything against scripted verdicts first; gate the
multi-target buildout on a positive first-light signal.

See `docs/plans/2026-06-15-003-...-plan.md` (KTD6) and `docs/e2e-runbook.md`.
