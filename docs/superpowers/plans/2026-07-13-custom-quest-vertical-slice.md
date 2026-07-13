# Custom Quest Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the `初入凡尘` quest loop from Citizens `old-man`, through spirit-root detection at `鉴灵师`, back to authoritative turn-in with private NPC state, title/particles, and a diff-updated sidebar.

**Architecture:** Game Service owns immutable quest/provider definitions, life-scoped progress, derived readiness, idempotent mutations, and complete interaction projections. Paper owns asynchronous request coordination and transient presentation only, using a 2-second cache, revision/generation stale-response protection, one 10-tick NPC/session coordinator, and main-thread-only Bukkit/Citizens/UI calls. The vanilla client runs no custom code.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, Ruff; Java 21, Paper 1.21.11, Citizens 2.0.43, Jackson, JUnit 5; existing local JDK `/home/adam/.local/jdks/jdk-21` and Gradle `/home/adam/.local/gradle/gradle-9.6.1/bin/gradle`.

**Environment constraint:** Do not download Gradle and do not search for Java. Use the existing JDK and Gradle paths above. The repository wrapper may try to download an incomplete distribution and is not the preferred command for this task.

---

### Task 1: Expose current-life quest facts and player revision

**Files:**
- Modify: `game-service/src/immortal_mmo/player/schemas.py`
- Modify: `game-service/src/immortal_mmo/player/repository.py`
- Modify: `game-service/src/immortal_mmo/player/service.py`
- Test: `game-service/tests/unit/test_player_quest_facts.py`
- Test: `game-service/tests/integration/test_player_api.py`

- [ ] Write failing tests proving `PlayerService.get_current_life_facts(account_id)` returns `account_id`, `life_id`, `generation_no`, spirit-root presence, and a monotonic player revision.
- [ ] Test that first life creation establishes a revision, first spirit-root assignment advances it once, and repeated detection leaves it unchanged.
- [ ] Run `.venv/bin/python -m pytest tests/unit/test_player_quest_facts.py -q` from `game-service/`; expect failure because `CurrentLifeQuestFacts` and the service method do not exist.
- [ ] Add the read-only Pydantic contract:

```python
class CurrentLifeQuestFacts(BaseModel):
    account_id: UUID
    life_id: UUID
    generation_no: int
    spirit_root: SpiritRoot | None
    revision: int
```

- [ ] Add repository-owned per-life revision state and methods that return facts without exposing repository dictionaries. Increment only on canonical fact changes.
- [ ] Add `PlayerService.get_current_life_facts(account_id)` and preserve the existing `player.account_not_found` error.
- [ ] Run the focused unit and existing player integration tests; expect all to pass.

### Task 2: Define and validate quest content

**Files:**
- Create: `game-service/src/immortal_mmo/quest/models.py`
- Create: `game-service/src/immortal_mmo/quest/definitions.py`
- Test: `game-service/tests/unit/test_quest_definitions.py`

- [ ] Write failing tests for the `first-steps` quest, the `old-man` provider, stable definition digest, and startup rejection of unknown quest IDs, duplicate IDs, and main/side overlap.
- [ ] Include a synthetic provider containing ordered main and side quests so multi-quest sorting can be tested without shipping fake runtime content.
- [ ] Run `.venv/bin/python -m pytest tests/unit/test_quest_definitions.py -q`; expect import failure for the missing module.
- [ ] Add immutable domain models for category, repeatability, objective, dialogue keys, presentation hints, quest definition, and provider definition.
- [ ] Add the fixed runtime definitions:

```text
quest: first-steps / 初入凡尘 / main / once_per_life
objective: detect-spirit-root / current_life_spirit_root_present / 1
provider: old-man / main_quest_ids=[first-steps]
active hint: 前往鉴灵师处
ready hint: 返回老村民处
```

- [ ] Normalize validated definitions and compute a deterministic SHA-256 digest for the definition revision.
- [ ] Run the focused tests; expect all to pass.

### Task 3: Add atomic in-memory quest progress and operation ledger

**Files:**
- Create: `game-service/src/immortal_mmo/quest/repository.py`
- Test: `game-service/tests/unit/test_quest_repository.py`

- [ ] Write failing tests for `(life_id, quest_id)` uniqueness, bulk progress reads, per-life quest revision, accept copy-on-write, completed transition, operation replay, and operation-ID conflict.
- [ ] Add concurrent tests using two threads: only one accept returns `changed=true`, and only one ready turn-in returns `changed=true`.
- [ ] Run `.venv/bin/python -m pytest tests/unit/test_quest_repository.py -q`; expect missing repository types.
- [ ] Define a `QuestRepository` protocol and immutable `QuestProgress`/operation result records.
- [ ] Implement `InMemoryQuestRepository` with one short lock around check-and-write operations:

```text
progress_by_key[(life_id, quest_id)]
quest_revision_by_life[life_id]
operation_result_by_key[(life_id, operation_id)]
```

- [ ] Keep PlayerService calls, projection construction, logging, and all I/O outside repository locks.
- [ ] Implement semantic no-op behavior without increasing quest revision.
- [ ] Run the focused tests repeatedly; expect deterministic passes.

### Task 4: Build quest projections and state transitions

**Files:**
- Create: `game-service/src/immortal_mmo/quest/schemas.py`
- Create: `game-service/src/immortal_mmo/quest/service.py`
- Modify: `game-service/src/immortal_mmo/core/errors.py`
- Test: `game-service/tests/unit/test_quest_service.py`

- [ ] Write failing service tests for `available`, `active`, `ready_to_turn_in`, and `completed`, including acceptance after an already-detected spirit root.
- [ ] Test once-per-life isolation, completed-quest prerequisite evaluation, provider mismatch, premature turn-in, unknown quest/provider errors, and operation conflict.
- [ ] Test actionable ordering: ready, active, available, main before side, then provider order. Verify exactly one actionable quest produces `direct_action_quest_id`.
- [ ] Instrument fakes and assert each aggregate call performs one player-facts read and one bulk progress read, not one read per quest.
- [ ] Run `.venv/bin/python -m pytest tests/unit/test_quest_service.py -q`; expect missing service and schema types.
- [ ] Add Pydantic contracts for revision vector, objective projection, provider quest state, proximity bark, provider projection, tracked quest, aggregate interaction state, and mutation result.
- [ ] Add `ConflictError` and `RuleViolationError` domain bases, then quest-specific stable errors such as `quest.not_found`, `quest.provider_not_found`, `quest.provider_mismatch`, `quest.not_available`, `quest.not_accepted`, `quest.not_ready`, and `quest.idempotency_conflict`.
- [ ] Implement `QuestService` against a `CurrentLifeFactsReader` protocol and `QuestRepository`, deriving spirit-root objective progress from player facts.
- [ ] Return `tracked_quest=null` for available/completed and the correct title, `0/1` or `1/1`, and next-action hint for active/ready.
- [ ] Run the focused service tests; expect all to pass.

### Task 5: Publish aggregate, accept, and turn-in APIs

**Files:**
- Create: `game-service/src/immortal_mmo/quest/api.py`
- Modify: `game-service/src/immortal_mmo/main.py`
- Modify: `game-service/src/immortal_mmo/api/v1/router.py`
- Modify: `game-service/src/immortal_mmo/quest/__init__.py`
- Modify: `game-service/README.md`
- Test: `game-service/tests/integration/test_quest_api.py`

- [ ] Write failing integration tests for exact JSON and error envelopes of:

```http
POST /api/v1/players/{account_id}/current-life/quest-interaction-state
PUT /api/v1/players/{account_id}/current-life/quests/{quest_id}/accept
PUT /api/v1/players/{account_id}/current-life/quests/{quest_id}/turn-in
```

- [ ] Test provider-list de-duplication, the 32-provider cap, required mutation
  body `{"provider_id":"old-man"}`, UUID `Idempotency-Key`, provider mismatch,
  repeated mutation no-ops, and operation conflict.
- [ ] Add the full integration loop: login -> inspect available -> accept -> detect spirit root -> inspect ready -> turn in -> inspect completed/no tracked quest.
- [ ] Run `.venv/bin/python -m pytest tests/integration/test_quest_api.py -q`; expect 404s for missing routes.
- [ ] Add thin FastAPI handlers that resolve `QuestService` from `app.state`, validate the idempotency header, and return typed response models.
- [ ] Assemble one shared `PlayerService`, `InMemoryQuestRepository`, and `QuestService` in `create_app`, preserving explicit test injection.
- [ ] Include the quest router and document the single-process, single-worker, restart-volatile storage limitation in the README.
- [ ] Run `.venv/bin/python -m ruff check .` and `.venv/bin/python -m pytest`; expect a clean backend suite.

### Task 6: Add Java quest HTTP contracts

**Files:**
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/QuestRevisionVector.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/QuestObjectiveSnapshot.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/ProviderQuestSnapshot.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/QuestProviderSnapshot.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/TrackedQuestSnapshot.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/QuestInteractionState.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/QuestMutationResult.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/GameServiceClient.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/client/GameServiceClientQuestTest.java`

- [ ] Write local-HTTP-server tests proving snake_case decoding, provider-list
  request JSON, mutation `provider_id` JSON, exact routes, `Idempotency-Key`, and
  complete mutation projections.
- [ ] Test non-200 responses become `GameServiceException`, 4xx is not marked retryable by the caller, and the existing two-second request timeout remains configured.
- [ ] Run the focused test with the existing local toolchain; expect missing records/methods:

```bash
JAVA_HOME=/home/adam/.local/jdks/jdk-21 \
  /home/adam/.local/gradle/gradle-9.6.1/bin/gradle \
  --no-daemon --max-workers=1 test \
  --tests 'com.immortalmc.adapter.client.GameServiceClientQuestTest'
```

- [ ] Add immutable Java records mirroring the Python schema and defensive `List.copyOf` validation where needed.
- [ ] Add `fetchQuestInteractionState`, `acceptQuest`, and `turnInQuest` using `sendAsync`; serialize/parse entirely before any Bukkit callback.
- [ ] Centralize status/error parsing enough to retain useful domain error code and retryability without broad exception swallowing.
- [ ] Run the focused client tests and existing `GameServiceClientTest`; expect all to pass.

### Task 7: Implement session cleanup, cache, and single-flight request coordination

**Files:**
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/session/PlayerSessionCache.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/quest/QuestInteractionCache.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/quest/QuestRequestCoordinator.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/session/PlayerSessionCacheTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/quest/QuestInteractionCacheTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/quest/QuestRequestCoordinatorTest.java`

- [ ] Write failing tests for player-session removal, current-life replacement, 2-second presentation freshness, stale cosmetic retention, and clear-by-player.
- [ ] Test one in-flight refresh per player/provider, duplicate future coalescing, cleanup on success/failure, bounded retry backoff, and generation/revision stale rejection.
- [ ] Test that a successful mutation invalidates older inspect generations and writes through the returned snapshot.
- [ ] Run the focused `adapter.quest.*` tests; expect missing classes.
- [ ] Implement immutable cache entries keyed by player/provider with fetch time, local generation, and authoritative revision vector.
- [ ] Implement coordinator methods for refresh, accept, and turn-in. All network futures run off-thread; only the injected main-thread dispatcher may publish UI/cache effects.
- [ ] Preserve the last confirmed snapshot on transport failure but never return it as mutation authorization.
- [ ] Run the focused tests; expect all to pass.

### Task 8: Make offer dialogue cancellable and player-private

**Files:**
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/dialogue/NpcDialoguePresenter.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/quest/QuestOfferSession.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/quest/QuestOfferSessionStore.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/QuestOfferLabelPresenter.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/BukkitQuestOfferLabelPresenter.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/dialogue/NpcDialoguePresenterTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/quest/QuestOfferSessionStoreTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/presentation/QuestOfferLabelPresenterTest.java`

- [ ] Extend dialogue tests for a completion callback and a session-validity predicate; scheduled lines and completion must be no-ops after token invalidation.
- [ ] Test session transitions `playing_offer -> awaiting_confirmation`, 20-second expiry, replacement, and idempotent cancellation.
- [ ] Test label lifecycle: one display changes text from `任务接取中...` to `右键接取任务`, is visible only to its owning player, and removes exactly once.
- [ ] Run the focused tests; expect failures from missing callback/session APIs.
- [ ] Extend `NpcDialoguePresenter.play` with explicit validity and completion callbacks while preserving the existing simple overload for ordinary dialogue.
- [ ] Implement the pure session store keyed by player UUID with a random token, provider/NPC/quest IDs, world/range anchor, phase, and deadline.
- [ ] Implement the Bukkit presenter on the main thread using a non-persistent, no-gravity, non-interactive `TextDisplay`, `setVisibleByDefault(false)`, and `player.showEntity(plugin, display)`.
- [ ] Run the focused tests and existing dialogue tests; expect all to pass.

### Task 9: Route quest-provider clicks without replaying the legacy dialogue

**Files:**
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/gameplay/QuestProviderInteractionAction.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/citizens/CitizensNpcInteractionHandler.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/content/EntityInteractionDefinition.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/gameplay/QuestProviderInteractionActionTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/citizens/CitizensNpcInteractionHandlerTest.java`

- [ ] Write failing tests for provider metadata `quest-provider-id=old-man` and state behavior: available starts offer, awaiting-confirmation accepts, active reminds, ready turns in, completed talks/no-ops.
- [ ] Test that a quest-provider binding consumes the click once and does not also route the old unconditional `npc-dialogue` action.
- [ ] Test accept/turn-in failures leave authoritative UI unchanged and return a retry message.
- [ ] Run focused tests; expect the quest action and single-consumer behavior to be missing.
- [ ] Implement a dedicated provider action; do not reuse the unconditional `NpcDialogueInteractionAction` state machine.
- [ ] Make Citizens binding resolution select the authoritative quest-provider action once while retaining legacy entity/detector compatibility.
- [ ] Keep the 500 ms physical-click debouncer separate from offer-session state.
- [ ] Run focused Citizens/gameplay tests; expect all to pass.

### Task 10: Add indexed proximity and shared session validation coordinator

**Files:**
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/quest/QuestNpcPosition.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/quest/QuestNpcChunkIndex.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/quest/QuestNpcCoordinator.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/citizens/BukkitQuestNpcSource.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/quest/QuestNpcChunkIndexTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/quest/QuestNpcCoordinatorTest.java`

- [ ] Write failing pure-Java tests for world/chunk indexing, adjacent-chunk candidate lookup, squared six-block range, and outside-to-inside edges.
- [ ] Test 60-second cooldown keyed by player/NPC/state, immediate speech after state change, cache-hit zero HTTP, cache-miss one coalesced refresh, and no speech while remaining inside.
- [ ] Test pending sessions cancel on range, world, timeout, NPC disappearance, and player disappearance.
- [ ] For 100 players and 25 NPCs, assert bounded candidate/HTTP counts rather than flaky wall-clock p95 assertions. Test scan carryover when a configured work limit is reached.
- [ ] Run focused tests; expect missing coordinator/index types.
- [ ] Implement a Citizens adapter that snapshots only configured spawned providers by persistent UUID; keep Citizens API types outside the pure coordinator.
- [ ] Implement the chunk index and one coordinator `tick()` intended to run every 10 ticks. It reads cache only on the proximity hot path and sends private chat to one player.
- [ ] Add counters/timers for scan duration, candidate checks, cache hit/miss, refresh coalescing, and stale-response drops.
- [ ] Run focused tests; expect all to pass.

### Task 11: Render the authoritative sidebar by diff

**Files:**
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/QuestScoreboardModel.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/QuestScoreboardView.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/QuestScoreboardRenderer.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/BukkitQuestScoreboardView.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/presentation/QuestScoreboardRendererTest.java`

- [ ] Write failing tests for initial `修仙纪事` rendering, `0/1` to `1/1` line-only updates, hint change, equal-model no-op, and `tracked_quest=null` hide/release.
- [ ] Test per-player isolation and cleanup without retaining Player objects in long-lived maps.
- [ ] Run the focused test; expect missing renderer/view types.
- [ ] Implement a pure diff renderer against a small `QuestScoreboardView` interface.
- [ ] Implement the Bukkit view with stable entries/teams and main-thread-only mutations. Do not recreate or reassign an unchanged scoreboard.
- [ ] Add render-attempt and changed-line-write counters.
- [ ] Run focused tests; expect all to pass.

### Task 12: Integrate spirit-root title, particles, and quest refresh

**Files:**
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/gameplay/SpiritRootDetectionUseCase.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/gameplay/SpiritRootDetectionInteractionAction.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/SpiritRootTitlePresenter.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/BukkitSpiritRootTitlePresenter.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/gameplay/SpiritRootDetectionInteractionActionTest.java`

- [ ] Add failing Java tests that successful detector interaction displays title `灵根觉醒`, a localized subtitle, existing player/NPC particles, and schedules exactly one authoritative quest refresh.
- [ ] Test repeated detection remains idempotent and a failed detection cannot advance the sidebar.
- [ ] Run focused Java tests; expect missing title and quest-refresh callbacks.
- [ ] Implement title/subtitle presentation and reuse `SpiritRootParticlePlanner`/`BukkitSpiritRootParticlePresenter` with their existing bounded plan.
- [ ] After successful detection, issue one explicit `QuestRequestCoordinator` refresh for `old-man`; apply its authoritative snapshot and scoreboard on the main thread. Do not poll and do not infer `1/1` from the animation result.
- [ ] Run focused tests; expect all to pass.

### Task 13: Lifecycle cleanup, configuration, and plugin assembly

**Files:**
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/ImmortalMainPlugin.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/event/ImmortalPlayerLifecycleListener.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/event/PlayerJoinLoginService.java`
- Modify: `minecraft-nodes/main-plugin/src/main/resources/config.yml`
- Modify: `minecraft-nodes/main-plugin/src/main/resources/dialogues/old-man.yml`
- Modify: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/PluginResourceTest.java`
- Modify: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/config/PluginSettingsTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/event/ImmortalPlayerLifecycleListenerTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/quest/QuestLifecycleCleanupTest.java`

- [ ] Write failing tests for validated quest settings, join refresh after login succeeds, quit/kick/world-change cleanup/cancellation, and plugin disable clearing all player-scoped maps/displays/tasks.
- [ ] Add configuration for a 10-tick scan, 6-block range, 20-second offer timeout, 60-second bark cooldown, 2-second presentation TTL, and persistent Citizens UUID bindings.
- [ ] Run focused resource/settings/lifecycle tests; expect missing configuration and listeners.
- [ ] Assemble one coordinator, request layer, label presenter, scoreboard renderer, title presenter, and provider action in `ImmortalMainPlugin`.
- [ ] Start one shared repeating task at 10 ticks, retain its handle, and implement `onDisable` cancellation and cleanup.
- [ ] Register join/quit/kick/world-change lifecycle handling. Refresh quest state only after login has produced account/life identity.
- [ ] Migrate `old-man` from unconditional `npc-dialogue` routing to the single `quest-provider-id: old-man` path. Preserve legacy entity-based spirit-root detector bindings.
- [ ] Run all focused lifecycle/configuration tests; expect all to pass.

### Task 14: Full automated verification

**Files:**
- Update tests only if failures reveal an actual contract gap; do not weaken assertions to obtain green output.

- [ ] Run backend lint and tests from `game-service/`:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
```

- [ ] Run plugin tests and build from `minecraft-nodes/main-plugin/` using the already-installed toolchain:

```bash
JAVA_HOME=/home/adam/.local/jdks/jdk-21 \
  /home/adam/.local/gradle/gradle-9.6.1/bin/gradle \
  --no-daemon --max-workers=1 test build
```

- [ ] Confirm no test or build step downloads Gradle or searches for Java.
- [ ] Review cross-layer field names and route paths against the design spec and exact HTTP contract tests.
- [ ] Run `git diff --check` and inspect all player-scoped cleanup paths.

### Task 15: Runtime migration and end-to-end performance acceptance

**Files:**
- Modify runtime-only: `minecraft-nodes/main-server/plugins/ImmortalMC/config.yml`
- Deploy runtime-only: `minecraft-nodes/main-server/plugins/immortal-main-plugin-0.1.0-SNAPSHOT.jar`
- Do not commit third-party plugin JARs or generated server data.

- [ ] Confirm Game Service health with `curl -fsS http://127.0.0.1:8000/health`.
- [ ] Stop Paper cleanly through the existing `immortal-paper` tmux session before replacing the plugin JAR; do not hot-replace a running JAR.
- [ ] Create the Citizens NPC `鉴灵师`, record its persistent Citizens UUID, and bind it to `spirit-root-detect`. Preserve the existing `old-man` persistent UUID/provider binding.
- [ ] Deploy the built plugin, restart through the existing project script, and scan `minecraft-nodes/main-server/logs/latest.log` for `SEVERE`, `ERROR`, `Exception`, Citizens binding failures, or duplicate dialogue starts.
- [ ] Manually verify: proximity private speech -> first click offer -> private label -> leave cancels -> repeat -> second click accepts -> sidebar `0/1` -> 鉴灵师 title/subtitle/particles -> sidebar `1/1` -> old-man turn-in -> sidebar hidden.
- [ ] Verify two players see independent labels, proximity speech, quest state, and scoreboards.
- [ ] Exercise 100 synthetic players and 25 indexed quest NPC positions with counters, then record scan p50/p95/p99, cache hit ratio, request count, coalesced count, stale drops, scoreboard writes, and live session/display counts.
- [ ] Confirm target budgets: scan p95 `<0.5 ms`, p99 `<2 ms`; click pre-dispatch p95 `<0.25 ms`; changed-scoreboard apply p95 `<0.25 ms`; local click-to-authoritative UI p95 `<150 ms`.
- [ ] After disconnecting all test players, confirm quest caches, in-flight entries, cooldown/edge state, sessions, displays, and scoreboard render state return to zero.
