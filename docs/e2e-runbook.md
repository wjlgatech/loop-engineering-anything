# E2E reference-loop runbook (U8, R11)

The end-to-end loop is the only path that drives the **live** external tools, so
it is not part of the default `pytest` run (it needs installs, credentials, and
~30–40 min of generation time). Run it deliberately.

## 1. Install the tools (verified commands)

```bash
# referee — CLI-Judge (Python; the package lives in the harness/ subdir)
git clone https://github.com/wjlgatech/cli-judge
pip install -e cli-judge/harness          # installs the `cli-judge` console script
cli-judge selftest                        # sanity: runs the echo adapter, prints a real grade

# codebase lane — CLI-Anything
#   NOTE: generation is a Claude Code SKILL, not a build binary:
#     claude -p "/cli-anything <path-or-repo>"      (driven by ClaudeCodeRefiner-style invocation)
pip install cli-anything-hub              # installs `cli-hub` (browse/install generated CLIs only)
claude plugin marketplace add HKUDS/CLI-Anything && claude plugin install cli-anything

# service lane — CLI-Printing-Press (REQUIRES a Go toolchain)
#   install Go first (e.g. `brew install go`), then:
curl -fsSL https://raw.githubusercontent.com/mvanhorn/cli-printing-press/main/scripts/install.sh | bash
```

`loop-anything preflight` should then show the lane's tools available
(compound-engineering is detected as a Claude Code plugin; set
`LOOPENG_ASSUME_COMPOUND_ENGINEERING=1` if auto-detection can't confirm it).

> **Verified report.json schema** (pin point for the judge adapter): the safety
> signal is the boolean `safety_blocker`; dimensions are `D1..D5` with
> `points`/`max_points`; failing fixtures are `tasks[]` entries that lost points.
> Pass the judge an absolute `cli-judge` path if it is not on the subprocess PATH.

## 2. Resolve the two P0 gates first

1. **Headless refinement.** Confirm `claude -p "/ce-work ..."` applies edits
   unattended in the tool's workspace. `ClaudeCodeRefiner` / `ClaudeCodeCompounder`
   already drive this; verify quality on a throwaway target before trusting an
   overnight run.
2. **Grade stability.** Measure judge variance before trusting single-run deltas:

   ```bash
   loop-anything judge-variance <tool_path> --adapter <adapter.py> -k 7
   ```

   If grades are not stable, set `Budget.min_score_gain` to at least the reported
   `recommended_min_score_gain` so the loop ignores sub-noise jitter.

## 3. Configure and run

```bash
export LOOPENG_E2E_TARGET="https://api.example.com"   # or a local repo path
export LOOPENG_E2E_ADAPTER="/path/to/cli_judge_adapter.py"
export LOOPENG_E2E_LANE="service"                      # or "codebase"
# plus any target API credentials, read from the environment only

pytest tests/e2e/test_reference_loop.py -v             # the gated e2e test
# or drive it directly:
loop-anything run "$LOOPENG_E2E_TARGET" --goal "make this agent-native"
loop-anything report <run_id>
```

The e2e test skips (never fails) when these prerequisites are absent, so a green
default suite does **not** imply the live loop has been exercised.
