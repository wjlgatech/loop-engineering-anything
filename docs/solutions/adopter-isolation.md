# Adopter isolation: jail the install, not just the files (KTD7)

**Decision.** The catalog adopter (`src/loopeng/adopt.py`) installs a third-party
CLI into a dedicated `--target`/venv dir inside the workspace, spawns every
install subprocess with a **credential-pruned `env=`** (ambient secrets like
`ANTHROPIC_API_KEY` are stripped by name; only manifest-declared `required_env`
plus minimal `PATH`/`HOME`/`TMPDIR` survive), pins by a **full 40-char commit
SHA** (tags/branches rejected), only adopts from an allowlisted host, and
requires human review of the pinned source.

**Why.** `pip install git+…` and `npx` run arbitrary `setup.py`/build/postinstall
code **at install time, before any filesystem jail applies**, with the full
inherited environment. So `within_workspace` alone is a false sense of safety —
a compromised or malicious package could read ambient credentials or write
outside the workspace during install. Stripping credentials from the subprocess
environment and isolating the install location closes that window. A full commit
SHA is the only immutable git pin: a moved tag or a force-push past the host
allowlist would otherwise silently install different code.

**Enforced by.** `adopt.validate_spec` (rejects non-SHA refs, non-allowlisted
hosts, unsafe names); `adopt.pruned_env`; `run_tool(env=...)`. Tests in
`tests/test_adopt.py` assert the install targets the workspace and the subprocess
env omits credential-pattern keys.

See `docs/plans/2026-06-15-003-...-plan.md` (KTD7).
