# Cultivation Progression and Techniques Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement authoritative cultivation realms, common techniques, area-bound seclusion, realm regression, 筑基 breakthrough rules, owner-bound reward feedback, BetterHud projection, and the seclusion selection GUI.

**Architecture:** Game Service owns catalogs, formulas, PostgreSQL state, sessions, random decisions, and API projections. Paper owns asynchronous intent capture and presentation only. PostgreSQL ledgers back lifetime realized cultivation; group-scoped realm-entry records determine the current progress bar.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy async, PostgreSQL 17, Alembic, pytest, Java 21, Paper 1.21.11, BetterHud Bukkit API 2.0.0, JUnit 5, Mockito.

---

## File Map

### Game Service content and pure rules

- Create `game-service/src/immortal_mmo/cultivation/realm_catalog.py`
- Create `game-service/src/immortal_mmo/cultivation/realm_catalog.json`
- Create `game-service/src/immortal_mmo/cultivation/technique_catalog.py`
- Create `game-service/src/immortal_mmo/cultivation/techniques.json`
- Create `game-service/src/immortal_mmo/cultivation/area_catalog.py`
- Create `game-service/src/immortal_mmo/cultivation/areas.json`
- Create `game-service/src/immortal_mmo/cultivation/breakthrough_catalog.py`
- Create `game-service/src/immortal_mmo/cultivation/breakthrough_rules.json`
- Create `game-service/src/immortal_mmo/cultivation/layer_curves.py`
- Create `game-service/src/immortal_mmo/cultivation/allocation.py`
- Create `game-service/src/immortal_mmo/cultivation/progression.py`
- Create `game-service/src/immortal_mmo/cultivation/penalties.py`

### Game Service persistence and APIs

- Modify `game-service/src/immortal_mmo/cultivation/models.py`
- Modify `game-service/src/immortal_mmo/cultivation/db_models.py`
- Modify `game-service/src/immortal_mmo/cultivation/repository.py`
- Modify `game-service/src/immortal_mmo/cultivation/postgres_repository.py`
- Create `game-service/src/immortal_mmo/cultivation/service.py`
- Create `game-service/src/immortal_mmo/cultivation/schemas.py`
- Create `game-service/src/immortal_mmo/cultivation/api.py`
- Create `game-service/src/immortal_mmo/item/models.py`
- Create `game-service/src/immortal_mmo/item/db_models.py`
- Create `game-service/src/immortal_mmo/item/repository.py`
- Create `game-service/src/immortal_mmo/item/postgres_repository.py`
- Create `game-service/migrations/versions/20260716_003_cultivation_progression_techniques.py`
- Modify `game-service/src/immortal_mmo/core/uow.py`
- Modify `game-service/src/immortal_mmo/db/uow.py`
- Modify `game-service/src/immortal_mmo/main.py`
- Modify `game-service/src/immortal_mmo/entrypoint.py`
- Modify `game-service/src/immortal_mmo/api/v1/router.py`
- Modify `game-service/migrations/env.py`

### Existing reward and login contracts

- Modify `game-service/src/immortal_mmo/combat/models.py`
- Modify `game-service/src/immortal_mmo/combat/db_models.py`
- Modify `game-service/src/immortal_mmo/combat/postgres_repository.py`
- Modify `game-service/src/immortal_mmo/combat/service.py`
- Modify `game-service/src/immortal_mmo/combat/schemas.py`
- Modify `game-service/src/immortal_mmo/player/service.py`
- Modify `game-service/src/immortal_mmo/player/schemas.py`
- Modify `game-service/src/immortal_mmo/player/mappers.py`

### Paper Adapter

- Modify `minecraft-nodes/main-plugin/build.gradle.kts`
- Modify `minecraft-nodes/main-plugin/src/main/resources/plugin.yml`
- Modify `minecraft-nodes/main-plugin/src/main/resources/config.yml`
- Modify `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/GameServiceClient.java`
- Modify `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/CombatKillResult.java`
- Modify `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/outbox/OutboxDeliveryWorker.java`
- Modify `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/ImmortalMainPlugin.java`
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/CultivationSnapshot.java`
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/TechniqueSnapshot.java`
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/SeclusionRequest.java`
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/SeclusionSnapshot.java`
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/BreakthroughRequest.java`
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/BreakthroughSnapshot.java`
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/CultivationProjectionStore.java`
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/CultivationRewardPresenter.java`
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/BukkitCultivationRewardPresenter.java`
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/BetterHudCultivationIntegration.java`
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/SeclusionInventoryController.java`
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/gameplay/CultivationAreaResolver.java`
- Create BetterHud YAML/assets under `minecraft-nodes/main-plugin/src/main/resources/betterhud/`

---

### Task 1: Realm Catalog, Layer Curves, and Pure Allocation Rules

**Files:**
- Create: `game-service/src/immortal_mmo/cultivation/realm_catalog.py`
- Create: `game-service/src/immortal_mmo/cultivation/realm_catalog.json`
- Create: `game-service/src/immortal_mmo/cultivation/layer_curves.py`
- Create: `game-service/src/immortal_mmo/cultivation/allocation.py`
- Test: `game-service/tests/unit/test_realm_catalog.py`
- Test: `game-service/tests/unit/test_technique_layer_curves.py`
- Test: `game-service/tests/unit/test_seclusion_allocation.py`

- [ ] **Step 1: Write failing realm-catalog tests**

```python
def test_realm_catalog_has_approved_twenty_two_levels(catalog):
    assert catalog.level(10).max_exp == 3_829
    assert catalog.level(11).max_exp == 5_169
    assert catalog.level(12).max_exp == 6_978
    assert catalog.level(13).max_exp == 9_420
    assert catalog.level(22).max_exp == 116_145_360
    assert catalog.level(22).next_level_id is None


def test_qi_cumulative_capacity_uses_three_five_seven_nine_techniques(catalog):
    totals = catalog.qi_cumulative_totals()
    assert [totals[level] for level in (10, 11, 12, 13)] == [
        11_293, 16_462, 23_440, 32_860
    ]
    assert [ceil(totals[level] / 3_765) for level in (10, 11, 12, 13)] == [3, 5, 7, 9]
```

- [ ] **Step 2: Run the tests and confirm RED**

Run:

```bash
/home/adam/projects/immortal_mc/game-service/.venv/bin/python -m pytest \
  tests/unit/test_realm_catalog.py -q
```

Expected: import failure for missing `cultivation.realm_catalog`.

- [ ] **Step 3: Implement the strict realm catalog**

Use frozen records and reject duplicate IDs, gaps, non-positive `max_exp`, a
non-terminal level without a successor, or a level above 22. Keep level 14 as
an explicit anchor rather than deriving it from level 13.

```python
@dataclass(frozen=True, slots=True)
class RealmLevel:
    level_id: int
    name: str
    major_realm: str
    max_exp: int
    next_level_id: int | None
```

- [ ] **Step 4: Write failing largest-remainder curve tests**

```python
@pytest.mark.parametrize("capacity,ratio", [(3_765, (3, 2)), (14_644, (17, 10))])
def test_layer_costs_are_positive_exact_and_reproducible(capacity, ratio):
    first = build_transition_costs(capacity, *ratio)
    second = build_transition_costs(capacity, *ratio)
    assert first == second
    assert len(first) == 12
    assert all(cost > 0 for cost in first)
    assert sum(first) == capacity
```

- [ ] **Step 5: Verify RED, implement exact integer normalization, and verify GREEN**

Implement `weight_i = p**i * q**(11-i)`, floor quotas, and largest fractional
remainders with transition index tie-breaking. Run the three task test files.

- [ ] **Step 6: Write failing water-filling tests and implement allocation**

```python
def test_equal_allocation_redistributes_full_technique_overflow():
    result = allocate_equal(
        amount=11,
        remaining={UUID(int=1): 2, UUID(int=2): 100, UUID(int=3): 100},
    )
    assert result == {UUID(int=1): 2, UUID(int=2): 5, UUID(int=3): 4}
```

Remainders use sorted stable technique UUID only for equal-allocation ties.

- [ ] **Step 7: Commit**

```bash
git add game-service/src/immortal_mmo/cultivation/realm_catalog.py \
  game-service/src/immortal_mmo/cultivation/realm_catalog.json \
  game-service/src/immortal_mmo/cultivation/layer_curves.py \
  game-service/src/immortal_mmo/cultivation/allocation.py \
  game-service/tests/unit/test_realm_catalog.py \
  game-service/tests/unit/test_technique_layer_curves.py \
  game-service/tests/unit/test_seclusion_allocation.py
git commit -m "feat: add cultivation realm and layer rules"
```

### Task 2: Technique, Area, and Breakthrough Catalogs

**Files:**
- Create: `game-service/src/immortal_mmo/cultivation/technique_catalog.py`
- Create: `game-service/src/immortal_mmo/cultivation/techniques.json`
- Create: `game-service/src/immortal_mmo/cultivation/area_catalog.py`
- Create: `game-service/src/immortal_mmo/cultivation/areas.json`
- Create: `game-service/src/immortal_mmo/cultivation/breakthrough_catalog.py`
- Create: `game-service/src/immortal_mmo/cultivation/breakthrough_rules.json`
- Test: `game-service/tests/unit/test_technique_catalog.py`
- Test: `game-service/tests/unit/test_area_catalog.py`
- Test: `game-service/tests/unit/test_breakthrough_catalog.py`

- [ ] **Step 1: Write failing strict-schema tests**

Assert the common model only: group, elements, minimum level, major realm,
weight, layer cap 13, prerequisites, and typed effect projection. Reject
authored progression, fusion, and branch fields.

```python
def test_unknown_independent_progression_field_is_rejected(tmp_path):
    payload = valid_technique_payload()
    payload["techniques"][0]["realm_layer_caps"] = {"foundation": 6}
    with pytest.raises(TechniqueCatalogError, match="realm_layer_caps"):
        load_technique_catalog(write_json(tmp_path, payload))
```

- [ ] **Step 2: Verify RED and implement catalog loaders based on `combat/catalog.py`**

Seed the agreed fixtures: 引气术, 冰冻术, 缠绕术, 地刺术, 火弹术, 燃血斩,
灵力针刺, and 风裂遁刃诀. Validate qi max nine, later group max five, and
canonical weights `1/2/5/10`.

- [ ] **Step 3: Add area tests and content**

Create `neutral_training_ground` with `speed_basis_points=10000` and
`yield_basis_points=10000`, plus accelerated/high-yield fixtures. Reject zero,
negative, or overflowing basis points.

- [ ] **Step 4: Add breakthrough table tests and content**

```python
def test_breakthrough_profiles_match_approved_tables(catalog):
    assert catalog.profile("four_root").basis_points == (
        500, 1000, 1600, 2400, 3200, 4200, 5300, 6700, 8200, 10000
    )
    assert catalog.profile("five_root").basis_points[-1] == 5000
```

Freeze a 10-minute initial duration and allow catalog validation up to 15
minutes. One-to-three roots require exactly one pill.

- [ ] **Step 5: Run focused tests and commit**

```bash
/home/adam/projects/immortal_mc/game-service/.venv/bin/python -m pytest \
  tests/unit/test_technique_catalog.py tests/unit/test_area_catalog.py \
  tests/unit/test_breakthrough_catalog.py -q
git add game-service/src/immortal_mmo/cultivation game-service/tests/unit
git commit -m "feat: add cultivation content catalogs"
```

### Task 3: PostgreSQL Schema and ORM Models

**Files:**
- Create: `game-service/migrations/versions/20260716_003_cultivation_progression_techniques.py`
- Modify: `game-service/src/immortal_mmo/cultivation/db_models.py`
- Create: `game-service/src/immortal_mmo/item/db_models.py`
- Modify: `game-service/migrations/env.py`
- Modify: `game-service/tests/conftest.py`
- Modify: `game-service/tests/integration/test_migrations.py`
- Create: `game-service/tests/integration/test_cultivation_migrations.py`

- [ ] **Step 1: Write failing migration assertions**

Assert Alembic head `20260716_003`, exact tables, named constraints, indexes,
downgrade, and clean re-upgrade. Required tables:

```text
life_cultivation_states
cultivation_resource_entries
life_techniques
technique_investment_entries
life_realm_entries
cultivation_sessions
cultivation_session_techniques
breakthrough_technique_debits
life_item_stacks
item_resource_entries
```

- [ ] **Step 2: Verify RED against the old migration head**

Run:

```bash
/home/adam/projects/immortal_mc/game-service/.venv/bin/python -m pytest \
  tests/integration/test_cultivation_migrations.py -q
```

Expected: missing revision/tables.

- [ ] **Step 3: Implement migration and matching ORM**

`life_cultivation_states` gains `current_level` and active-session identity.
`life_realm_entries` stores generation, parent, active status, source floor,
target baseline, and transition metadata. Sessions store frozen JSON snapshots,
cumulative elapsed/generated/consumed/retained totals, status, and idempotency
identity. Use explicit `RESTRICT` FKs and named check constraints.

- [ ] **Step 4: Run migration tests and metadata drift check**

```bash
/home/adam/projects/immortal_mc/game-service/.venv/bin/python -m pytest \
  tests/integration/test_migrations.py \
  tests/integration/test_cultivation_migrations.py -q
/home/adam/projects/immortal_mc/game-service/.venv/bin/alembic check
```

- [ ] **Step 5: Commit**

```bash
git add game-service/migrations game-service/src/immortal_mmo/cultivation/db_models.py \
  game-service/src/immortal_mmo/item/db_models.py game-service/tests
git commit -m "feat: add cultivation progression schema"
```

### Task 4: Repository, Item Slice, and Unit of Work

**Files:**
- Modify: `game-service/src/immortal_mmo/cultivation/models.py`
- Modify: `game-service/src/immortal_mmo/cultivation/repository.py`
- Modify: `game-service/src/immortal_mmo/cultivation/postgres_repository.py`
- Create: `game-service/src/immortal_mmo/item/models.py`
- Create: `game-service/src/immortal_mmo/item/repository.py`
- Create: `game-service/src/immortal_mmo/item/postgres_repository.py`
- Modify: `game-service/src/immortal_mmo/core/uow.py`
- Modify: `game-service/src/immortal_mmo/db/uow.py`
- Modify: `game-service/src/immortal_mmo/entrypoint.py`
- Modify: `game-service/tests/support/fakes.py`
- Modify: `game-service/tests/unit/test_database_factory.py`
- Create: `game-service/tests/integration/test_cultivation_postgres_repository.py`
- Create: `game-service/tests/integration/test_item_postgres_repository.py`

- [ ] **Step 1: Write failing repository contract tests**

Test default state creation, sorted technique locks, entry-chain reads,
session exclusivity, ledger/aggregate atomicity, and item stack consume.

```python
async def test_consume_item_stack_rejects_insufficient_quantity(repository):
    await repository.grant_for_test(life_id, "foundation_pill", 2)
    with pytest.raises(InsufficientItemQuantity):
        await repository.consume(life_id, "foundation_pill", 3, operation_id)
```

- [ ] **Step 2: Verify RED and implement Protocols/fakes first**

Define focused repository methods; do not expose raw SQLAlchemy rows to the
service. Extend the shared UoW with `items` using the same AsyncSession.

- [ ] **Step 3: Implement PostgreSQL repositories with lock order**

Use the lock order `account -> life -> cultivation state -> techniques sorted
by ID -> item stack -> session`. Resource and investment ledger rows and
materialized balances are written in the same transaction.

- [ ] **Step 4: Run focused unit/integration tests and commit**

```bash
/home/adam/projects/immortal_mc/game-service/.venv/bin/python -m pytest \
  tests/unit/test_database_factory.py \
  tests/integration/test_cultivation_postgres_repository.py \
  tests/integration/test_item_postgres_repository.py -q
git add game-service/src/immortal_mmo game-service/tests
git commit -m "feat: add cultivation and item repositories"
```

### Task 5: Progression Projection and Capped Combat Rewards

**Files:**
- Create: `game-service/src/immortal_mmo/cultivation/progression.py`
- Create: `game-service/src/immortal_mmo/cultivation/schemas.py`
- Create: `game-service/src/immortal_mmo/cultivation/service.py`
- Create: `game-service/src/immortal_mmo/cultivation/api.py`
- Modify: `game-service/src/immortal_mmo/combat/models.py`
- Modify: `game-service/src/immortal_mmo/combat/db_models.py`
- Modify: `game-service/src/immortal_mmo/combat/postgres_repository.py`
- Modify: `game-service/src/immortal_mmo/combat/service.py`
- Modify: `game-service/src/immortal_mmo/combat/schemas.py`
- Modify: `game-service/src/immortal_mmo/main.py`
- Modify: `game-service/src/immortal_mmo/api/v1/router.py`
- Test: `game-service/tests/unit/test_cultivation_progression.py`
- Test: `game-service/tests/unit/test_combat_service.py`
- Test: `game-service/tests/integration/test_cultivation_api.py`
- Test: `game-service/tests/integration/test_combat_api.py`

- [ ] **Step 1: Write failing group-scoped progress tests**

```python
def test_training_old_group_changes_lifetime_not_current_bar():
    snapshot = project_progress(
        current_level=14,
        group_investments={"qi": 20_000, "level:14": 1_000},
        active_entry=entry(target_group="level:14", target_baseline=0),
    )
    assert snapshot.realized_total == 21_000
    assert snapshot.current_progress == 1_000
```

Test first entry empty, qi optional entry empty, re-entry restoring retained
target progress, active-chain invalidation, and level-22 fill without level 23.

- [ ] **Step 2: Verify RED and implement projection/rollback pure functions**

Realm entries form one active parent chain. Invalidated generations are ignored
forever. Clamp local progress and return an explicit snapshot containing realm
name, current/max, reserve/cap, revision, and full flags.

- [ ] **Step 3: Write failing accepted-zero combat tests**

```python
async def test_full_reserve_kill_is_accepted_with_zero_credit(service):
    result = await service.process_batch(full_reserve_batch())
    assert result.results[0].outcome == "accepted"
    assert result.results[0].configured_reward_amount > 0
    assert result.results[0].credited_cultivation_amount == 0
```

- [ ] **Step 4: Persist the frozen credited amount and balance on combat events**

Duplicate replay reads the combat event's stored result even when no nonzero
resource ledger row exists. Preserve old event fingerprint semantics and reject
changed immutable requests.

- [ ] **Step 5: Add snapshot endpoint and composition tests**

Expose `GET /api/v1/players/{account_id}/current-life/cultivation`. Initialize
default level-1 state even before the first kill.

- [ ] **Step 6: Run tests and commit**

```bash
/home/adam/projects/immortal_mc/game-service/.venv/bin/python -m pytest \
  tests/unit/test_cultivation_progression.py tests/unit/test_combat_service.py \
  tests/integration/test_cultivation_api.py tests/integration/test_combat_api.py -q
git add game-service
git commit -m "feat: project realm progress and cap combat rewards"
```

### Task 6: Ordinary Seclusion Service and API

**Files:**
- Create: `game-service/src/immortal_mmo/cultivation/area_catalog.py`
- Extend: `game-service/src/immortal_mmo/cultivation/service.py`
- Extend: `game-service/src/immortal_mmo/cultivation/schemas.py`
- Extend: `game-service/src/immortal_mmo/cultivation/api.py`
- Test: `game-service/tests/unit/test_seclusion_time.py`
- Test: `game-service/tests/unit/test_cultivation_service.py`
- Test: `game-service/tests/integration/test_cultivation_api.py`

- [ ] **Step 1: Write failing cumulative-time and inverse-yield tests**

```python
def test_partial_settlements_equal_one_combined_settlement():
    one = cumulative_time_budget(7200, 10_000, [3_765], 36_000)
    split = cumulative_time_budget(3600, 10_000, [3_765], 36_000)
    assert one - split == incremental_time_budget(7200, split, 10_000, [3_765], 36_000)


def test_inverse_yield_never_exceeds_effective_cap():
    consumed = maximum_convertible_reserve(100, 15_000)
    assert consumed == 67
    assert consumed * 15_000 // 10_000 <= 100
```

- [ ] **Step 2: Verify RED and implement pure time/yield functions**

Use only integer arithmetic and cumulative totals. Reject zero/negative elapsed,
stale versions, mixed major realms, duplicate IDs, mastered selections, and
more than five selections.

- [ ] **Step 3: Write failing service tests for start/settle/replay**

Cover selection freezing, active-session exclusivity, reserve over-cap use,
equal allocation, mastery redistribution, auto-end, and unused reserve.

- [ ] **Step 4: Implement idempotent start/status/settle endpoints**

Use `Idempotency-Key` UUIDs. Start stores frozen snapshots. Settle uses the
injected clock, cumulative time, capacity-aware conversion, atomic ledger
updates, and active-chain progression. Exact-level full stops the session;
shared qi can cross deterministic levels only up to the explicit barrier.

- [ ] **Step 5: Run tests and commit**

```bash
/home/adam/projects/immortal_mc/game-service/.venv/bin/python -m pytest \
  tests/unit/test_seclusion_time.py tests/unit/test_cultivation_service.py \
  tests/integration/test_cultivation_api.py -q
git add game-service
git commit -m "feat: add authoritative cultivation seclusion"
```

### Task 7: Technique Abandonment, Transfer, and Realm Regression

**Files:**
- Extend: `game-service/src/immortal_mmo/cultivation/service.py`
- Extend: `game-service/src/immortal_mmo/cultivation/repository.py`
- Extend: `game-service/src/immortal_mmo/cultivation/postgres_repository.py`
- Extend: `game-service/src/immortal_mmo/cultivation/schemas.py`
- Extend: `game-service/src/immortal_mmo/cultivation/api.py`
- Test: `game-service/tests/unit/test_cultivation_regression.py`
- Test: `game-service/tests/integration/test_cultivation_api.py`

- [ ] **Step 1: Write failing active-generation regression tests**

Test `A(valid) -> B(invalidated)` followed by new `C` from A; C must become the
active branch and B must never block it. Test cross-major drop and retained
higher-group progress restoration on re-entry.

- [ ] **Step 2: Verify RED and implement active-chain rebuilding**

Abandon atomically debits the technique investment ledger and realized
aggregate, invalidates the active suffix, and returns a new snapshot. Transfer
preserves only the configured fraction that fits the target; the destroyed
remainder drives the same rebuild.

- [ ] **Step 3: Add API idempotency and conflict tests**

Reject mutation while a breakthrough is pending. Replay returns the frozen
response and never double-debits.

- [ ] **Step 4: Run tests and commit**

```bash
/home/adam/projects/immortal_mc/game-service/.venv/bin/python -m pytest \
  tests/unit/test_cultivation_regression.py \
  tests/integration/test_cultivation_api.py -q
git add game-service
git commit -m "feat: add technique-backed realm regression"
```

### Task 8: 筑基 Breakthrough and Deterministic Random Penalties

**Files:**
- Create: `game-service/src/immortal_mmo/cultivation/penalties.py`
- Extend: `game-service/src/immortal_mmo/cultivation/service.py`
- Extend: `game-service/src/immortal_mmo/cultivation/schemas.py`
- Extend: `game-service/src/immortal_mmo/cultivation/api.py`
- Test: `game-service/tests/unit/test_breakthrough_penalties.py`
- Test: `game-service/tests/unit/test_breakthrough_service.py`
- Test: `game-service/tests/integration/test_cultivation_api.py`

- [ ] **Step 1: Write failing HMAC allocator golden tests**

Use fixed entropy and exact technique UUIDs. Assert the full debit vector,
order invariance, total equality, no negative balance, and capacity-aware
multi-round redistribution.

```python
def test_penalty_total_uses_floor():
    assert breakthrough_penalty(3_829) == 1_276
    assert breakthrough_penalty(5_169) == 1_723
    assert breakthrough_penalty(6_978) == 2_326
    assert breakthrough_penalty(9_420) == 3_140
```

- [ ] **Step 2: Verify RED and implement HMAC-SHA256 round allocation**

Use exact rational largest remainders and full-digest tie-breaking. Do not use
Python's process-randomized `hash()` or floating point.

- [ ] **Step 3: Write failing breakthrough lifecycle tests**

Cover full-progress eligibility, root-count profile selection, pills 1–10,
atomic pill consume, 10-minute frozen duration, success to level14, qi 10–12
50/50 advancement/loss, qi13 forced loss, session exclusivity, replay, and
restart settlement.

Add a narrowly scoped administrative item-adjustment operation used by server
operators/tests to place `foundation_pill` into the authoritative life stack.
It requires its own idempotency key and audited `administrative_adjustment`
ledger row; ordinary clients cannot choose trusted balances.

- [ ] **Step 4: Implement start/status/settle**

Generate and persist primary/secondary rolls and penalty entropy once. A qi
advance keeps investment/reserve and appends the new entry baseline. Loss
debits the fixed total and rebuilds the active realm chain. Release session
exclusivity only on terminal settlement.

- [ ] **Step 5: Run tests and commit**

```bash
/home/adam/projects/immortal_mc/game-service/.venv/bin/python -m pytest \
  tests/unit/test_breakthrough_penalties.py \
  tests/unit/test_breakthrough_service.py \
  tests/integration/test_cultivation_api.py -q
git add game-service
git commit -m "feat: add foundation breakthrough settlement"
```

### Task 9: Adapter Reward Presentation and Cultivation Client Contracts

**Files:**
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/CombatKillResult.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/GameServiceClient.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/outbox/OutboxDeliveryWorker.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/CultivationSnapshot.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/TechniqueSnapshot.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/SeclusionRequest.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/SeclusionSnapshot.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/BreakthroughRequest.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/BreakthroughSnapshot.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/CultivationRewardPresenter.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/BukkitCultivationRewardPresenter.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/outbox/OutboxDeliveryWorkerTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/presentation/BukkitCultivationRewardPresenterTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/client/GameServiceClientCultivationTest.java`

- [ ] **Step 1: Write failing accepted-only presentation tests**

Assert `accepted` maps by event ID to the original player/world/position and
dispatches presentation before/independently of acknowledgement. `duplicate`
and terminal outcomes never present again.

- [ ] **Step 2: Verify RED and add a response-consumer boundary**

`OutboxDeliveryWorker` receives a `CultivationRewardPresenter`. HTTP completion
maps response results to rows, schedules Paper presentation on the main thread,
and still acknowledges terminal rows even if presentation throws.

- [ ] **Step 3: Implement owner-bound orb presenter**

Spawn visual `ExperienceOrb` entities at the death location with zero XP value,
owner UUID metadata, bounded mob-level-derived count, and a pickup listener that
updates only the owner's HUD animation. Reconnect snaps to authoritative state.

- [ ] **Step 4: Add cultivation/seclusion HTTP DTO tests**

Decode snake-case snapshots and mutation errors. Every mutation sends a UUID
`Idempotency-Key` and remains asynchronous. Include breakthrough start/status/
settle and operator item-adjustment DTOs.

- [ ] **Step 5: Run Java tests and commit**

```bash
JAVA_HOME=/home/adam/.cache/codex/jdks/temurin-21 \
LD_LIBRARY_PATH=/home/adam/.cache/codex/jdks/temurin-21/lib:/home/adam/.cache/codex/jdks/temurin-21/lib/server \
./gradlew test
git add minecraft-nodes/main-plugin
git commit -m "feat: present accepted cultivation rewards"
```

### Task 10: BetterHud Projection and Resource Assets

**Files:**
- Modify: `minecraft-nodes/main-plugin/build.gradle.kts`
- Modify: `minecraft-nodes/main-plugin/src/main/resources/plugin.yml`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/CultivationProjectionStore.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/BetterHudCultivationIntegration.java`
- Create: `minecraft-nodes/main-plugin/src/main/resources/betterhud/images/immortal-cultivation.yml`
- Create: `minecraft-nodes/main-plugin/src/main/resources/betterhud/layouts/immortal-cultivation.yml`
- Create: `minecraft-nodes/main-plugin/src/main/resources/betterhud/huds/immortal-cultivation.yml`
- Create: `minecraft-nodes/main-plugin/src/main/resources/betterhud/assets/immortal/main-empty.png`
- Create: `minecraft-nodes/main-plugin/src/main/resources/betterhud/assets/immortal/main-fill.png`
- Create: `minecraft-nodes/main-plugin/src/main/resources/betterhud/assets/immortal/reserve-empty.png`
- Create: `minecraft-nodes/main-plugin/src/main/resources/betterhud/assets/immortal/reserve-fill.png`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/presentation/CultivationProjectionStoreTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/presentation/BetterHudCultivationIntegrationTest.java`
- Modify: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/PluginResourceTest.java`

- [ ] **Step 1: Write failing projection-store tests**

```java
assertEquals("元婴后期", store.snapshot(playerId).realmName());
assertEquals(0.0, store.snapshot(playerId).currentRatio());
assertEquals(116145360L, store.snapshot(playerId).maxExp());
```

- [ ] **Step 2: Verify RED and implement last-confirmed authoritative cache**

Store only Game Service projections. Revisions must not move backward. Remove
on quit. Missing state returns display-disabled values, not invented gameplay.

- [ ] **Step 3: Add BetterHud API 2.0.0 and soft dependency**

Register string/number placeholders for realm name, current, max, current ratio,
reserve, cap, and reserve ratio. Install packaged managed YAML/assets into the
BetterHud data folder, reload BetterHud, add `immortal_cultivation` HUD to the
HudPlayer, and call `update()` after projection changes. If BetterHud is absent,
log a visible warning and preserve gameplay.

- [ ] **Step 4: Generate the four minimal PNG bar textures using the imagegen skill**

Create pixel-clean transparent assets: colored main empty/fill and thin gray
reserve empty/fill. Keep dimensions encoded in the YAML tests and inspect them
with `view_image` before committing.

- [ ] **Step 5: Test resources and commit**

```bash
JAVA_HOME=/home/adam/.cache/codex/jdks/temurin-21 \
LD_LIBRARY_PATH=/home/adam/.cache/codex/jdks/temurin-21/lib:/home/adam/.cache/codex/jdks/temurin-21/lib/server \
./gradlew test
git add minecraft-nodes/main-plugin
git commit -m "feat: add BetterHud cultivation projection"
```

### Task 11: Seclusion Selection GUI and Plugin Wiring

**Files:**
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/SeclusionInventoryController.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/presentation/SeclusionInventoryHolder.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/gameplay/CultivationAreaResolver.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/ImmortalMainPlugin.java`
- Modify: `minecraft-nodes/main-plugin/src/main/resources/config.yml`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/command/ImmortalCommandHandler.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/command/ImmortalCommandService.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/presentation/SeclusionInventoryControllerTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/command/ImmortalCommandHandlerTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/PluginResourceTest.java`

- [ ] **Step 1: Write failing GUI state-machine tests**

Test one-to-five selection, same-major enforcement, mastered/locked rejection,
click-order independence, confirm/cancel, stale authoritative rejection, and
cleanup on quit/disable.

Add resolver tests for configured world/cuboid area bindings, overlap rejection,
outside-area failure, and stable semantic area IDs.

- [ ] **Step 2: Verify RED and implement inventory holder/controller**

The GUI displays authoritative technique name, group, attribute, layer,
progress, and eligibility. Confirmation sends selected stable IDs plus area ID
to Game Service. Paper does not calculate rates or settlement.

`CultivationAreaResolver` reads server-mechanism coordinates from `config.yml`
and returns only the semantic area ID. Game Service remains the owner of speed/
yield values and rejects unknown IDs.

- [ ] **Step 3: Wire `/immortal seclusion` and plugin lifecycle**

Open asynchronously after fetching techniques/snapshot, publish inventory only
on the main thread, register listeners, refresh BetterHud after success, and
clean sessions on quit/disable.

Also wire `/immortal breakthrough <pill-count>` to start the authoritative
session and schedule status/settle calls after the returned completion time.
Wire an operator-only `/immortal cultivation grant-item <player>
foundation_pill <count>` command to the audited Game Service adjustment API so
the current zero-to-one server can provision test/administrative pills without
local item authority.

- [ ] **Step 4: Run adapter tests/build and commit**

```bash
JAVA_HOME=/home/adam/.cache/codex/jdks/temurin-21 \
LD_LIBRARY_PATH=/home/adam/.cache/codex/jdks/temurin-21/lib:/home/adam/.cache/codex/jdks/temurin-21/lib/server \
./gradlew test build
git add minecraft-nodes/main-plugin
git commit -m "feat: add seclusion selection interface"
```

### Task 12: Cross-Layer Verification, Specs, and Operational Handoff

**Files:**
- Modify: `.trellis/spec/backend/quality-guidelines.md`
- Modify: `.trellis/spec/backend/database-guidelines.md`
- Modify: `game-service/README.md`
- Modify: `minecraft-nodes/main-plugin/README.md`
- Modify: `.trellis/tasks/07-15-cultivation-level-xp-feedback/task.json`

- [ ] **Step 1: Run Game Service quality gates**

```bash
cd game-service
/home/adam/projects/immortal_mc/game-service/.venv/bin/python -m ruff check .
/home/adam/projects/immortal_mc/game-service/.venv/bin/python -m pytest -q
/home/adam/projects/immortal_mc/game-service/.venv/bin/alembic check
```

Expected: all green, no warnings introduced by this task.

- [ ] **Step 2: Run Paper quality gates**

```bash
cd minecraft-nodes/main-plugin
JAVA_HOME=/home/adam/.cache/codex/jdks/temurin-21 \
LD_LIBRARY_PATH=/home/adam/.cache/codex/jdks/temurin-21/lib:/home/adam/.cache/codex/jdks/temurin-21/lib/server \
./gradlew --no-daemon --max-workers=1 test build
```

Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 3: Run focused cross-layer contract checks**

Verify JSON field names between Pydantic and Jackson, accepted-zero reward
replay, login/reconnect HUD snapshot, seclusion idempotency, breakthrough
restart settlement, and BetterHud-absent safe startup.

- [ ] **Step 4: Update executable project specs**

Record the common technique catalog contract, group-scoped realm-entry chain,
reserve mutation boundary, session lock order, and Adapter presentation-only
boundary. Do not document deferred authored techniques as implemented.

- [ ] **Step 5: Final review and commit**

```bash
git add .trellis/spec game-service/README.md minecraft-nodes/main-plugin/README.md
git commit -m "docs: record cultivation progression contracts"
```

---

## Plan Self-Review

- Every deterministic formula has a direct unit-test task before implementation.
- PostgreSQL and API behavior have integration coverage.
- Game Service remains authoritative at every Adapter boundary.
- Accepted kills with zero credited reserve remain accepted and replayable.
- First entry and regression re-entry semantics are both covered.
- Repeated seclusion settlement and random penalties have golden deterministic tests.
- BetterHud failure cannot mutate gameplay.
- Authored techniques and live combat effects remain excluded.
