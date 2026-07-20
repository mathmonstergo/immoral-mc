# Implementation Plan: Selective Cultivation Fix Integration

## Step 1: Establish an Integration Branch

* Confirm `main`, `origin/main`, and `origin/feat/cultivation-progression` still point to the same computer-B baseline.
* Create a dedicated integration branch from current `main`.
* Preserve `fix/cultivation-server-test-fixes`, its linked worktree, and `stash@{0}` unchanged.

## Step 2: Port MythicMobs Normalization

* Add/restore listener tests for binary floating tails, half-up rounding, exact maximum, raw overflow, negative values, NaN/infinity, and contained sink failures.
* Implement one adapter-boundary normalization function in `MythicMobDeathListener`.
* Run targeted Paper adapter tests.

## Step 3: Add Mortal Realm Level 0

* Update the realm catalog to contain levels 0–22 while preserving every level 1–22 value.
* Update catalog validation and cumulative qi thresholds.
* Change fresh state and regression fallbacks to level 0.
* Allow `引气术` at realm level 0 while preserving computer-B technique layer-0 behavior.
* Update ORM checks and the existing baseline migration directly for level 0 current/source values.
* Adapt service progression so normal 10-second settlements append `0 -> 1` at 50 cumulative qi.
* Update Paper DTO validation/HUD projection boundaries to accept level 0.
* Add focused catalog, progression, service, repository, migration, API, and Paper tests.

## Step 4: Integrate Resource-Pack Property Synchronization

* Add reusable shell helpers inside the unified startup script for idempotent property updates.
* Support a client-reachable public resource-pack URL through explicit configuration with a safe local default where appropriate.
* Compute and write the current ZIP SHA-1 before Paper starts.
* Keep one resource-pack HTTP server and one startup command.
* Update current Chinese Wiki documentation; do not restore the old duplicate README workflow.
* Run shell syntax, temporary-fixture property, idempotency, and HTTP smoke checks.

## Step 5: Resolve Specs and Remove Obsolete Integration Surface

* Update database and quality specs with the final MythicMobs and mortal-stage contracts.
* Record role/group speed multiplication as a future extension, not current behavior.
* Verify no development API, command, flag, schedule-shift method, or obsolete test was introduced.

## Step 6: Full Verification

* Run Game Service formatting/lint/type checks.
* Run targeted tests, then the full Game Service test suite.
* Run Paper adapter Gradle tests and build.
* Run migration/schema consistency checks.
* Run `git diff --check` and audit the final diff against `016064c`.
* Verify typed quests, physical items, regional storage, unified startup, Java 25, zero-layer techniques, and 10-second settlement code remain present.

## Step 7: Integrate and Publish

* Review the integration branch history and verification evidence.
* Merge the integration branch into `main` without rewriting computer-B history.
* Push `main` to GitHub.
* Leave the old fix branch/worktree available until the user confirms cleanup.
