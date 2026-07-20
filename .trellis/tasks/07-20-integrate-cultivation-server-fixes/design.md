# Design: Selective Cultivation Fix Integration

## Baseline and Safety

The current `main` at `016064c` is the authoritative computer-B baseline. Implementation occurs on a new integration branch created from that commit. The remote `origin/feat/cultivation-progression`, local `fix/cultivation-server-test-fixes`, and `stash@{0}` remain untouched until the integration is verified and merged.

The old fix branch is a source of behavior and tests, not a source-tree baseline. Files are not resolved with blanket `ours`/`theirs`; each retained behavior is implemented against current module boundaries.

## 1. MythicMobs Numeric Boundary

Keep `MythicMobDeathSnapshot` and downstream API/database decimal contracts strict.

At `MythicMobDeathListener`:

1. Read the raw third-party `double` inside the guarded capture path.
2. Reject non-finite, negative, and raw values above `999999999.999` before rounding.
3. Normalize accepted values with `BigDecimal.valueOf(raw).setScale(3, HALF_UP)`.
4. Construct and submit the snapshot inside the same failure boundary.
5. On failure, emit one structured diagnostic and no outbox fact.

This can follow the local commit closely because computer B did not modify these files after the common ancestor.

## 2. Mortal Realm Entry on the Current Progression Model

Add level 0 `凡人` with `max_exp=50` and successor level 1. Existing levels 1–22 retain their IDs, names, realm groupings, thresholds, and successors.

Realm level and technique layer remain independent:

* a new life starts at realm level 0;
* `引气术` is learnable at realm level 0;
* newly learned techniques still begin at technique layer 0 under the computer-B curve;
* ordinary seclusion continues to settle in 10-second cycles;
* when cumulative `qi` investment reaches 50, the normal settlement transaction appends the adjacent `0 -> 1` realm entry;
* level-1 progress begins at zero because the first 50 points form the mortal-stage baseline.

The baseline migration is rewritten directly because this is a zero-to-one project. Database constraints accept current/source level 0 while preserving the maximum of 22. No compatibility migration or fallback shim is added.

Regression fallback becomes level 0 when no valid active realm-entry chain remains. Breakthrough policies remain unchanged because they start at later levels.

## 3. Unified Resource-Pack Startup

Keep `scripts/start-local-server.sh` as the single local orchestration entrypoint.

Before starting the resource-pack HTTP server, the script will:

1. resolve the existing BetterHud `build.zip`;
2. derive or accept an explicit client-reachable public URL;
3. compute the ZIP SHA-1;
4. update only `resource-pack` and `resource-pack-sha1` in the ignored runtime `server.properties`, idempotently;
5. then start the existing tmux-managed HTTP server and verify the local endpoint.

Configuration should reuse the unified script's environment boundary rather than introduce `serve-betterhud-resource-pack.sh`. Wiki documentation will explain localhost/WSL/LAN reachability and hash refresh behavior.

## 4. No Development Seclusion Module

Do not port:

* `development_api.py`;
* `DEVELOPMENT_API_ENABLED`;
* Paper `development-tools` configuration;
* `dev-seclusion complete/cancel` commands;
* schedule-shift repository methods;
* tests or specs for an alternate development lifecycle.

All users use the same 10-second authoritative settlement path. A future role/group speed multiplier may adjust cultivation generation before the existing cumulative settlement calculation. That extension must not create a second API or session state machine and is outside this task.

## 5. Conflict Resolution Policy

* Application composition, plugin composition, launcher structure, typed quests, items, storage, Java 25, and current tests come from computer B.
* Mortal realm semantics are added to current cultivation code and fixtures.
* MythicMobs normalization is ported from the local branch.
* Resource-pack property synchronization is folded into the current unified launcher.
* Specs are updated with durable final contracts only; old task artifacts are not merged into the active task tree.

## Verification and Rollback

Verification includes targeted tests first, then the full Game Service suite, Paper Gradle tests/build, shell syntax and resource-pack property smoke tests, migration checks, and a history/diff audit proving computer-B features remain present.

Rollback before merge is deleting the integration branch. After merge, rollback is reverting the integration commit(s); the old fix branch and computer-B remote branch remain available as independent references.
