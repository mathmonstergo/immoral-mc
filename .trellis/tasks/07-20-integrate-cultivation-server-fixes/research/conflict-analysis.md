# Conflict and Semantic Delta Analysis

## Baseline

* Authoritative computer-B line: `origin/feat/cultivation-progression` / current `main` at `016064c`.
* Local fix line: `fix/cultivation-server-test-fixes` at `6f7c971`.
* Common ancestor: `d40a922`.
* The computer-B line has 19 unique commits after the common ancestor; the local fix line has 6.
* The computer-B commits remain reachable from both `origin/feat/cultivation-progression` and `origin/main`, so selective integration cannot erase them.

## Local-Only Commit Classification

### `294a63c` — MythicMobs level normalization

**Classification: required and cleanly reusable.**

The current computer-B listener still constructs the strict snapshot directly from `BigDecimal.valueOf(event.getMobLevel())`. It contains sink/snapshot failures, but does not normalize floating-point tails or reject invalid raw values before rounding. The local commit adds the missing adapter-boundary normalization and tests. Computer B did not touch these files after the common ancestor.

### `972f50e` — development seclusion controls

**Classification: obsolete implementation; do not migrate.**

The local implementation assumes `completes_at` represents a long authoritative completion horizon. Computer B changed ordinary seclusion into 10-second discrete settlement cycles; `completes_at` now represents the first settlement boundary, not full mastery. Porting the old `complete` operation unchanged would only make one cycle due and could then terminalize a partially processed session. That is semantically wrong under the new model.

The user selected the clean result: omit the development API, commands, flags, repository schedule-shift method, and related tests. A future `admin` or other role/group may supply a speed multiplier to the normal settlement engine. That future model preserves one authoritative calculation path and does not require a development-only session lifecycle.

### `06c84b7` — BetterHud resource-pack test workflow

**Classification: partially superseded; retain missing behavior in the unified workflow.**

Computer B added `scripts/start-local-server.sh`, a tmux-managed resource-pack server, Java 25 startup, and Chinese Wiki documentation. This supersedes the separate startup instructions and much of the old README change. However, the unified script does not automatically synchronize `resource-pack` and `resource-pack-sha1` in `server.properties`, while the local helper does. The clean integration is to add configurable public URL plus automatic SHA-1/property synchronization to the unified startup path, not introduce a second overlapping launcher.

### `05fbd3e` / `d3dee85` — task/spec records

**Classification: do not merge task history wholesale; selectively preserve durable contracts.**

The old active task artifacts describe an earlier architecture. Relevant contracts—third-party numeric normalization, authoritative ownership, and mortal entry invariants—should be incorporated into current specs/task notes. Development-seclusion contracts should not be preserved unless that capability is redesigned and selected.

### `6f7c971` — mortal cultivation entry stage

**Classification: required behavior, but reimplement on the computer-B baseline.**

The current main still starts at realm level 1. The local commit adds level 0 `凡人`, a 50-point reserve/progression threshold, level-0 database constraints, realm-entry history, Paper boundary support, and tests. This product behavior is absent from computer B and should be retained if the local branch is a source of intended functionality.

Computer B meanwhile added zero-layer techniques and 10-second settlement cycles. Realm level 0 and technique layer 0 are separate concepts and can coexist, but old test fixtures and service patches must be adapted to the new technique curve and cycle model rather than copied wholesale.

## Ten Textual Conflicts

### 1. `.trellis/spec/backend/database-guidelines.md`

Computer B documents typed quests, physical items, regional storage, and the new cultivation cycle contracts. The local branch adds level-0 realm/schema constraints. Resolution: use computer-B document as base and append only the current mortal-entry invariants.

### 2. `.trellis/spec/backend/quality-guidelines.md`

Computer B adds zero-layer technique, Java 25, unified startup, quest/item/storage quality contracts. The local branch adds MythicMobs numeric-boundary rules, development-control rules, HUD notes, and mortal-stage checks. Resolution: keep computer-B content; add MythicMobs and mortal rules; retain only resource-pack details missing from the unified workflow; omit obsolete development-control rules unless redesigned.

### 3. `game-service/src/immortal_mmo/main.py`

Computer B wires item and storage services into the application. The local branch conditionally mounts a development cultivation router. Resolution: computer-B application composition wins. Add no development router unless the capability is explicitly retained and redesigned.

### 4. `game-service/tests/integration/test_cultivation_api.py`

Computer B tests the current UoW composition, typed quest/item dependencies, zero-layer techniques, and 10-second cycles. The local branch adds mortal snapshots/transitions and development-completion integration. Resolution: retain the current fixture/composition and add adapted mortal integration coverage; old development-completion tests are invalid under the new timing model.

### 5. `game-service/tests/unit/test_cultivation_regression.py`

Computer B updates regression behavior for the current zero-layer/cycle model. The local branch changes the fallback realm from level 1 to level 0. Resolution: keep current cases and change/add only the mortal fallback expectations and data.

### 6. `game-service/tests/unit/test_cultivation_service.py`

Computer B substantially expands settlement tests for the 10-second cumulative-cycle model. The local branch adds mortal transition cases using the old fixture shape. Resolution: retain computer-B settlement behavior and add targeted level `0 -> 1` assertions adapted to current fixtures.

### 7. `game-service/tests/unit/test_realm_catalog.py`

Computer B validates levels 1–22 plus zero-layer technique behavior elsewhere. The local branch changes the realm catalog to 0–22. Resolution: update current catalog invariants to 0–22 while preserving all existing level 1–22 values.

### 8. `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/ImmortalMainPlugin.java`

Computer B wires physical items, regional storage, and quest-refresh behavior. The local branch only passes a development-tools flag into the cultivation command runner. Resolution: computer-B composition wins; no flag is added unless redesigned development commands are retained.

### 9. `minecraft-nodes/main-server/README.md`

Computer B moved operational guidance into a unified startup model and Chinese Wiki. The local branch adds separate resource-pack serving, development commands, and HUD tuning notes. Resolution: keep the computer-B structure; place missing resource-pack URL/SHA behavior in the unified script and Wiki, avoiding duplicate startup paths.

### 10. `scripts/start-paper-server.sh`

Computer B has stricter Java 25 discovery and is called by the unified launcher. The local branch contains an older Java 25 fallback list. Resolution: take the computer-B file unchanged.

## Recommended Integration Shape

1. Create a new integration branch from current `main`; never merge directly on `main` during development.
2. Port `294a63c` cleanly.
3. Reimplement the mortal level-0 behavior against the current zero-layer/cycle architecture, using tests first.
4. Fold automatic resource-pack URL/SHA synchronization into `start-local-server.sh` and current Wiki documentation.
5. Do not merge the old development seclusion implementation. Record role/group-based speed multiplication as a future extension, outside this task.
6. Update specs with final invariants, run full Game Service and Paper verification, then merge the integration branch into `main` only after review.
