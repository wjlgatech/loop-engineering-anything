<!-- Use this template when contributing a demo. See CONTRIBUTING-demos.md. -->

## New demo

- **Demo id:** `<kebab-slug>`
- **Domain:**
- **Target:** `<https:// URL, or repo-relative path for a codebase demo>`
- **Lane:** service | codebase
- **Goal:**
- **Exit criteria:** target grade + max iterations
- **`required_env`:** (env-var names only if the target needs credentials — never paste secret values)
- **Contributor:** `@your-github-handle`

## Result

- [ ] `illustrative` (a representative trajectory — no live run yet)
- [ ] `live_verified` (recorded from a real run via `loop-anything demo record <id> --from <run_id>`)

## Checklist

- [ ] `loop-anything demo validate` passes locally
- [ ] No secret values in the manifest or fixture (`required_env` names only)
- [ ] `loop-anything showcase` renders my card correctly
