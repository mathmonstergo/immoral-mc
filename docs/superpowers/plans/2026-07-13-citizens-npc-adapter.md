# Citizens NPC Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route persistent Citizens NPC interactions into the existing ImmortalMC dialogue/action system without introducing a second quest engine.

**Architecture:** Citizens remains an optional Paper runtime integration. Core command and interaction code sees a Citizens-free resolver interface; the Citizens package converts Bukkit entities and `NPCRightClickEvent` instances into persistent Citizens UUIDs. Existing entity bindings remain readable, while Citizens metadata becomes authoritative for Citizens-backed dialogue lookup.

**Tech Stack:** Java 21, Paper 1.21.11, Citizens 2.0.43 build 4211 API, Gradle 9.6.1, JUnit 5.

---

### Task 1: Dependency and persistent identity metadata

**Files:**
- Modify: `minecraft-nodes/main-plugin/build.gradle.kts`
- Modify: `minecraft-nodes/main-plugin/src/main/resources/plugin.yml`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/content/EntityInteractionRegistry.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/content/EntityInteractionRegistryTest.java`

- [ ] Write failing registry tests for finding and removing an interaction by `target-provider=citizens` and `citizens-npc-uuid` regardless of its Bukkit `EntityBinding`.
- [ ] Run the focused test with local Gradle and verify the new methods are missing.
- [ ] Add `findAllByMetadata` and `removeInteractionsByMetadata`, preserving existing action/binding behavior.
- [ ] Add the Citizens Maven repository, non-transitive `compileOnly` dependency, and `softdepend: [Citizens]`.
- [ ] Run the focused test and existing content tests.

### Task 2: Optional resolver boundary and command source

**Files:**
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/citizens/CitizensNpcResolver.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/citizens/BukkitCitizensNpcResolver.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/command/ImmortalCommandSource.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/command/ImmortalBukkitCommandExecutor.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/command/ImmortalCommandSourceTest.java`

- [ ] Write failing tests proving command sources can carry an optional persistent Citizens UUID and default to unavailable.
- [ ] Run the focused test and verify failure from the missing field/factory.
- [ ] Add the resolver interface with `Optional<UUID> persistentNpcUuid(Entity)` and an unavailable implementation.
- [ ] Add the Citizens API implementation using `CitizensAPI.getNPCRegistry().getNPC(entity)` and `NPC#getUniqueId()`.
- [ ] Populate the optional UUID for the selected Bukkit entity in the command executor.
- [ ] Run command-source and command-handler tests.

### Task 3: Citizens-aware dialogue binding commands

**Files:**
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/command/NpcDialogueAdminRunner.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/command/NpcDialogueAdminMessages.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/command/NpcDialogueAdminRunnerTest.java`

- [ ] Write failing tests proving `set` stores `target-provider=citizens` plus the persistent UUID, rebinding removes the old Citizens record, and `remove` works after the Bukkit binding changes.
- [ ] Run the focused test and confirm the persisted metadata assertions fail.
- [ ] Add stable metadata constants and make set/remove prefer the persistent Citizens UUID while retaining legacy entity behavior.
- [ ] Update admin list/bound messages to show the Citizens UUID when present.
- [ ] Run all command tests.

### Task 4: Exactly-once Citizens click routing

**Files:**
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/citizens/CitizensNpcInteractionHandler.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/citizens/CitizensNpcInteractionListener.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/interaction/InteractionDebouncer.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/citizens/CitizensNpcInteractionHandlerTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/interaction/InteractionDebouncerTest.java`

- [ ] Write failing tests proving persistent UUID lookup routes configured actions, unknown UUID is a no-op, unhandled actions log, and the same player/UUID click inside 500 ms is rejected.
- [ ] Run focused tests and verify missing production types cause failure.
- [ ] Implement a monotonic-time debouncer keyed by player UUID plus Citizens NPC UUID.
- [ ] Implement a Citizens-free handler that finds metadata bindings and routes the existing `BukkitEntityInteractionContext`.
- [ ] Implement the thin `NPCRightClickEvent` listener and set delayed cancellation only when handled.
- [ ] Run Citizens handler/debouncer tests.

### Task 5: Generic listener exclusion and plugin assembly

**Files:**
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/event/ImmortalEntityInteractionListener.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/ImmortalMainPlugin.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/event/ImmortalEntityInteractionListenerTest.java`

- [ ] Write a failing test proving the generic listener exits before registry lookup/routing when the resolver identifies a Citizens NPC.
- [ ] Run the focused test and verify current listener routes the entity path.
- [ ] Inject a Citizens-entity predicate/resolver into the generic listener while retaining an unavailable default.
- [ ] In plugin assembly, enable the Citizens resolver/listener only when Citizens is enabled; otherwise use the unavailable resolver and log one capability line.
- [ ] Reorder assembly only as needed so both command and event paths share the same resolver and action router.
- [ ] Run listener and plugin resource tests.

### Task 6: Full verification and server migration

**Files:**
- Modify runtime config only: `minecraft-nodes/main-server/plugins/ImmortalMC/config.yml`
- No committed commercial or third-party JAR changes.

- [ ] Run `.venv/bin/pytest -q` in `game-service/` and expect 8 passing tests.
- [ ] Run local Gradle `test build` with Java 21 and verify success.
- [ ] Stop Paper cleanly, deploy the rebuilt ImmortalMC JAR, and restart.
- [ ] Create or select a Citizens NPC, bind `old-man`, right-click once, and confirm one dialogue sequence.
- [ ] Restart Paper and confirm the same Citizens NPC still resolves through its persistent UUID.
- [ ] Scan startup/runtime logs for severe errors, duplicate dialogue starts, or stale binding warnings.

