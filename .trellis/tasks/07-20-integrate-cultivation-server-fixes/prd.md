# Integrate Cultivation Server Test Fixes into Main

## Goal

Preserve all development completed on computer B and safely integrate the still-relevant behavior from the local `fix/cultivation-server-test-fixes` branch into the current `main`, using the computer-B branch architecture and schemas as the authoritative baseline.

## What I Already Know

* `main`, `origin/main`, and `origin/feat/cultivation-progression` currently point to `016064c`.
* The computer-B branch fully contained the former local `main`; that integration was a conflict-free fast-forward.
* `fix/cultivation-server-test-fixes` diverged at `d40a922` and has 6 unique commits, while the computer-B line has 19 unique commits after the same base.
* The local fix branch contains four functional themes: MythicMobs level normalization, development-only seclusion controls, BetterHud resource-pack test tooling, and a mortal level-0 cultivation entry stage.
* The fix branch was previously verified with 374 Game Service tests, the Paper Gradle build, resource-pack smoke checks, and production-route exposure checks.
* A synthetic merge reports 10 textual conflicts; most non-conflicting files merge mechanically, but mechanical success is not sufficient proof that the resulting schema and behavior are coherent.
* Local uncommitted Trellis updates are preserved in `stash@{0}` and are outside this integration scope.

## Assumptions (Temporary)

* The current computer-B `main` is the authoritative architecture and schema baseline.
* We should migrate behavior, tests, and contracts from the local fix branch rather than preserve obsolete implementation shapes merely to retain commit history.
* Existing computer-B features—typed quests, physical item rewards, regional storage, unified startup, Java 25, zero-layer techniques, and ten-second seclusion—must not regress.

## Open Questions

* None.

## Requirements (Evolving)

* Do not lose any commit or behavior currently present on the computer-B branch.
* Analyze every local-only commit and every merge conflict semantically before integration.
* Use the current `main` schemas and module boundaries as the baseline.
* Retain local fixes only where they are not already superseded and remain compatible with the current product rules.
* Preserve a recoverable branch/reference until integration and verification are complete.
* Retain MythicMobs decimal normalization and contained failure behavior.
* Retain the `凡人` level-0 entry stage, adapted to computer B's zero-layer technique and 10-second settlement model.
* Extend the unified local startup workflow with automatic resource-pack URL/SHA synchronization instead of adding a competing launcher.
* Do not add development-only seclusion completion/cancellation APIs, Paper commands, configuration flags, or alternate settlement state transitions.
* Keep future acceleration compatible with the normal settlement engine by allowing a role/group-derived speed multiplier, such as an `admin` group, rather than a separate development module.

## Acceptance Criteria (Evolving)

* [ ] Current `main` remains recoverable and all computer-B commits remain reachable.
* [ ] Each of the 6 local-only commits is classified as required, already superseded, partially reusable, or obsolete.
* [ ] Each of the 10 textual conflicts has an explicit semantic resolution rationale.
* [ ] MythicMobs floating-point tails are normalized at the Paper boundary without relaxing downstream schemas.
* [ ] New lives start as `凡人` and advance `0 -> 1` through the current authoritative settlement model.
* [ ] Unified local startup advertises the configured resource-pack URL and matching SHA-1.
* [ ] Production and development both use the same 10-second settlement path; no development seclusion route or command is introduced.
* [ ] Integrated behavior passes relevant Game Service and Paper tests.
* [ ] Database migrations and cultivation schemas form one clean zero-to-one baseline without compatibility shims.
* [ ] Git history and final diff demonstrate that no computer-B feature was removed accidentally.

## Definition of Done

* Relevant unit and integration tests pass.
* Paper adapter tests/build pass.
* Migration and schema consistency checks pass.
* Conflict decisions and retained behavior are documented.
* Final `main` is pushed only after review and verification.

## Out of Scope (Explicit)

* Reapplying the stashed Trellis framework update.
* Deleting the linked local fix worktree or its branch.
* Preserving obsolete compatibility behavior solely because it existed on the older branch.
* Implementing role/group-based cultivation speed multipliers in this task; this is a documented future extension.

## Technical Notes

* Common ancestor: `d40a922`.
* Current computer-B tip: `016064c`.
* Local fix tip: `6f7c971`.
* Previous task artifacts: `.worktrees/cultivation-server-test-fixes/.trellis/tasks/07-17-cultivation-server-test-fixes/`.
* Synthetic conflict files are being analyzed against both sides and their common ancestor.
* Detailed analysis: `research/conflict-analysis.md`.

## Decision (ADR-lite, evolving)

**Context**: A textual branch merge would combine an older repair implementation with a newer computer-B architecture and could silently reintroduce obsolete session semantics.

**Decision**: Use current `main` as the authoritative baseline and selectively migrate required behavior from the local fix branch. Do not resolve conflicts by taking complete old files. Drop the old development seclusion module entirely; future testing acceleration will be modeled as a role/group multiplier inside the normal settlement calculation.

**Consequences**: Git commit identity from the old branch may not be preserved for redesigned pieces, but all intended behavior will be traceable and testable without sacrificing computer-B features or carrying compatibility patches. There is one settlement engine and one lifecycle model. A later `admin` multiplier can accelerate generated cultivation without exposing a bypass route or manufacturing state.

## Technical Approach

Create an integration branch from the current computer-B-based `main`. Port the independent MythicMobs normalization fix, reimplement the mortal level-0 schema and progression behavior against the current zero-layer/10-second model, and fold resource-pack URL/SHA synchronization into the unified local startup workflow. Resolve documentation and tests from the current branch outward; never replace current files wholesale with their older branch versions.
