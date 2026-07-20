# Verification: Selective Cultivation Fix Integration

## History and Scope

- Authoritative computer-B baseline `016064c` remains an ancestor of the
  integration branch.
- No application file present at `016064c` is deleted by the integration diff.
- Typed quests, physical items, regional storage, the unified launcher, Java
  25, zero-layer techniques, and ten-second settlement sentinels remain.
- `development_api.py`, development seclusion flags/commands, and alternate
  settlement state transitions were not introduced.

## Automated Checks

- Game Service: `.venv/bin/pytest -q` -> `459 passed`.
- Changed Python files: Ruff -> passed.
- Paper Adapter: Java 25 `./gradlew --no-daemon --max-workers=1 test build` ->
  `BUILD SUCCESSFUL`.
- Shell: `bash -n` and ShellCheck for all startup scripts -> passed.
- Resource pack: temporary-property URL/SHA synchronization, Java Properties
  duplicate cleanup, permission preservation, byte-identical second run,
  invalid URL rejection, dedicated-directory isolation, and HTTP 404 for
  non-`build.zip` paths -> passed.
- Resource-pack tmux contract: generated single-pane session accepted; old or
  prefix-similar public roots and additional session panes/windows rejected.
- Wiki: `python3 scripts/check-wiki-links.py` -> passed.
- Whitespace: `git diff --check` -> passed.

## PostgreSQL Coverage

- Fresh migration and ORM constraints accept realm level 0.
- `life_realm_entries` enforces a native `0 -> 1` root shape; active-chain
  validation rejects missing roots, discontinuous levels, invalid parents, and
  group-inconsistent entries rather than inferring compatibility history.
- Same-group re-entry projects from its cumulative `target_baseline`, while
  cross-group re-entry projects retained target-group investment from zero.
- A real FastAPI + SQLAlchemy UoW + PostgreSQL test settles a mortal ordinary
  seclusion and atomically verifies state, technique balance, resource ledgers,
  session totals, and the adjacent `0 -> 1` realm entry.
- Computer-B reward tests exposed parent/child flush-order defects. Quest grant
  parents now flush before physical item and cultivation-ledger children; the
  full PostgreSQL suite passes without foreign-key failures or cleanup deadlocks.

## Documentation Impact

Docs impact: required and completed in `docs/wiki/cultivation.md`,
`docs/wiki/betterhud-and-resource-pack.md`, `docs/wiki/getting-started.md`,
`docs/wiki/operations-and-troubleshooting.md`, and the local Paper README.
