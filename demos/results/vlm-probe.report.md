# Research report — run #5

- Target: vlm-probe (FM-os failure-probe wrap) (service lane)
- Goal: make the FM-os VLM failure-probe wrap agent-native: `version --json` exits 0; `probe run --model mock --json` prints one JSON envelope with a 'modes' map and exits 0 (report-only: exit 0 even when the gate would fail); `probe gate --model X --json` prints a JSON verdict with 'gate_pass' and exits 1 when the gate fails (mock) / 0 when it passes (patched) — never prompt, never log on stdout, keep the real probe engine (probe_runner) wired, never hardcode verdicts. Engine API (do NOT invent attributes): run_probes(model, spec) returns a plain dict {mode_id: {'measured': bool, 'score': float|None, 'threshold': float, 'probes': list}}; gate(results, spec) returns (ok: bool, reasons: list[str]); load_spec() returns the spec.
- Status: **converged**  |  Final grade: **A**
- Iterations: 3
- Grade trajectory: F -> F -> A

## Learnings compounded
- iteration 3: grade F - A by targeting [D2] (regression: 1 file changed, 68 insertions(+), 8 deletions(-))