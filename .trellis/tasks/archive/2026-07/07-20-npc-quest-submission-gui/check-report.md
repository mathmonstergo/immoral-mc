# Check Report: NPC Quest Submission GUI (incremental)

Status: dimensions 1-5 COMPLETE; final verification GREEN.
Baseline verification before deep review was green (Java 269 tests /
0 failures via cleanTest test; Python 467 passed; ruff clean; wiki check
passed). Later review found and fixed stale-life and asynchronous revision races;
the final counts and commands are recorded below.

## Dimension 1: Spec compliance (COMPLETE)

- Migration `20260719_004` edited in place (adds `life_inventory_states`),
  previously committed in e3f1e25. VERDICT: safe for this repo. The database
  guidelines' "Zero-to-One Schema Replacement" scenario and the explicit
  "Current project decision (development-only schema changes)" sanction
  rewriting development-only revisions to the clean target shape while data is
  disposable; no production data exists. Migration test asserts the new table,
  PK/FK/check constraint names at head. NO FIX NEEDED (working as designed).
- Paper stays non-authoritative: `QuestProviderInteractionAction` reduced to a
  thin router (provider-id metadata -> GUI opener). GUI controller submits only
  identity + scanned physical instance IDs; readiness/consumption decided by
  Game Service (`_consume_delivery_items` validates + consumes atomically,
  shortage -> QuestNotReadyError, no partial debit). OK.
- Monotonic objective revision: `life_inventory_states.revision` incremented in
  `set_instance_location`, `confirm_delivery`, `consume_instance`,
  `consume_inventory_instances` (all physical ownership/location mutations);
  `create_pending_instances` correctly does NOT increment (pending items are
  not inventory input). `revision.objectives = cultivation_revision +
  inventory_revision`, both monotonic; `item_codes` derives from the whole
  catalog so the component is comparable across request shapes. OK.
- Stable-read: `_load_inventory_objective_inputs` bounded 3-attempt retry for
  unlocked projections; locked path re-reads under the revision row lock. Lock
  order (item rows, then revision row) is consistent between mutations and the
  locked projection path. Note: a theoretical 3-txn deadlock window exists via
  the locked-path re-read, but PostgreSQL deadlock detection resolves it and
  per-life concurrency is effectively one player. Not a fix-blocking issue.
- Retry/idempotency: `QuestRequestCoordinator.callMutation` retries once for
  IOException/retryable GameServiceException with the same request closure and
  therefore the same operation UUID; identical mutation identity coalesces;
  different identity while busy fails with QuestRequestBusyException. Matches
  spec.
- No broad exception swallowing found; GUI projection-rejection closes the GUI
  (fail closed) and logs; unknown reward kinds rejected in both Pydantic and
  Java record validators.
- Mutation life fencing is end-to-end: Paper sends required
  `expected_life_id`; Game Service checks it after locking account/current life
  and before operation reservation. `quest.stale_life` is HTTP 409 and
  non-retryable. Frozen operations remain replayable only with their original
  life identity; changing the life under the same operation ID conflicts.
- Proximity rule matching is life-ID agnostic. Rules consume current-life quest
  and realm facts only; `expected_life_id` never enters the condition union.
- Async presentation is fenced at three levels: NPC entry epochs reject a
  leave/re-enter ABA completion, authoritative state invalidates superseded
  provider entries and pre-existing provider generations, and a newer tracked
  publication invalidates older in-flight refresh generations even when the
  definitions hash starts a new revision epoch. Dirty trailing refreshes remain
  scheduled after the fence.
- Provider/rule IDs reject `:` and the resolved key is bounded to 256
  characters. Java objective DTO validation rejects every unknown objective
  type instead of silently rendering it as a generic item.

## Dimension 3: Cross-layer contract v2 (COMPLETE)

- `contract_version` bumped to 2 on both sides; Java record rejects != 2.
- New fields consistent: `description` (str), `objective_type`
  (QuestObjectiveType enum -> string), `item_code` (nullable, item_delivery
  only, enforced by Pydantic model_validator AND Java record compact
  constructor), `reward_previews` (`reward_id`, `kind` in {fixed_item,
  unrefined_cultivation}, `item_code`/`quantity`/`cultivation_amount` shape
  validated identically in `QuestRewardPreview` on both sides).
- GameServiceClientQuestTest exercises exact snake_case JSON for the new
  fields including `"item_code":null` and reward preview decoding.
- Turn-in still sends `inventory_item_instance_ids`; backend consumes only the
  required quantity per sorted item_code, excess untouched (existing paths
  unchanged).
- Uncapped `current` on both sides: Python `evaluate_objective` no longer
  min()s item quantity; Java `QuestObjectiveSnapshot` allows current >= 0 and
  `progressText` renders uncapped.
- Provider sort order updated identically: Python `_actionable_sort_key`
  (ready 0, active 1, available 2, unavailable 3, completed 4) == Java
  `QuestProviderMenuModel.STATE_RANK`; Java sort is stable (Stream.sorted)
  preserving server order within rank.

## Dimension 4: Dead code / duplicate formatters (COMPLETE)

- Deleted classes (QuestOfferLabel, QuestOfferLabelPresenter,
  QuestOfferSession, QuestOfferSessionStore, BukkitQuestOfferLabelPresenter)
  have zero remaining references in src/main and src/test.
- Deleted `first-steps.*.yml` dialogue resources: no remaining resource or
  saveDialogueIfMissing references; `first-steps.` appears only as a
  dialogue_key JSON literal in GameServiceClientQuestTest (wire-contract
  fixture, fine). `old-man.yml` dialogue kept for NpcDialogueInteractionAction.
- One shared quantity formatter: `QuestProviderMenuModel.progressText`
  (`<title> <current> / <required>`); QuestScoreboardModel now delegates to it
  (old private double-space formatter removed).
- QuestNpcCoordinator: Map/HashMap/distanceSquared still used after
  validateSessions removal; no orphaned imports.

## Dimension 2: PRD acceptance sweep (COMPLETE)

Every PRD acceptance checkbox has matching code + test coverage:
- Six-row GUI, content 0..44, buttons 45..53 (slot constants; controller test
  asserts 54 slots, divider row 9..17 panes, primary at 53).
- BOOK vs WRITTEN_BOOK mapping incl. unavailable=BOOK; state colors + bold via
  one styled() helper with italics explicitly disabled; slot routing uses the
  holder slot map, never material/name/Lore.
- List entry: exactly styled name + single lore `点击查看！` when viewable; red
  `暂未解锁` and inert when locked (controller test lockedQuestIsVisibleRed...);
  detail opens only via left click; right click on list entries does nothing.
- Order ready/active/available/unavailable/completed-gray-last identical and
  tested on both sides (test_provider_list_order_places_unavailable_before_
  completed + QuestProviderMenuModelTest); Java Stream.sorted is stable so
  within-rank server order is deterministic (deterministic selection).
- All clicks/drags on the GUI view cancelled first (covers shift-click and
  number-key hotbar swap because every InventoryClickEvent whose top holder is
  the quest holder is cancelled; rawSlot 60 player-inventory click asserted);
  pane slots inert; back/close never mutate state.
- Detail page renders description (multi-line lore), one row per objective
  (max 12 fits slots 18..29), reward preview, state line, and the
  state-appropriate primary action; same slot 53 is 确认接取 / 确认提交 /
  disabled variants; busy renders a yellow pane and DISABLED_* sends no
  mutation (incomplete quest cannot invoke turn-in).
- Shared uncapped progress format `<material> <current> / <required>` via the
  single `QuestProviderMenuModel.progressText`; scoreboard renderer test
  asserts `玄铁 20 / 15` (20 > 15 uncapped) and per-material rows; no
  `上交`/`背包数量`/`提交消耗`/`提交后剩余` labels anywhere in src.
- Python `evaluate_objective` no longer clamps item current; completed uses
  current >= required.
- Turn-in submits exact current physical inventory instance IDs; Game Service
  consumes only required quantities per sorted item_code; excess untouched;
  shortage/stale rolls back everything (new PostgreSQL test
  test_turn_in_finalize_failure_rolls_back_items_rewards_progress_and_revision
  plus existing shortage/ownership tests); rewards awarded exactly once
  (idempotent operation replay tests updated to contract v2).
- Double-submit/stale protection layers: holder busy CAS
  (serializesOneOperationAtATime), coordinator mutation-identity coalescing +
  busy rejection, operationId match check on completion, generation map +
  openMenus identity, sameSession account/life check, QuestProviderBindingGuard
  revalidation (rebind/unbind/foreign action invalidates - guard tests),
  holder.update rejects component-wise older revision vectors and throws on
  identity mismatch (GUI closes, fail closed).
- Quit/kick/life replacement: lifecycle listener + cleanupPlayer call
  questProviderMenus.clearPlayer; onDisable closes the GUI controller first;
  statePublisher goes through TrackedQuestRefreshCoordinator.publish which
  performs its own join-token/account/life staleness validation.
- Scoreboard refreshes independently (TrackedQuestRefreshCoordinator wiring
  unchanged); GUI turn-in additionally reconciles items and refreshes
  cultivation.
- Monotonic objective revision: same-count swap and decrease covered at three
  levels (fake-repo service test, SimpleNamespace stable-read unit test, real
  PostgreSQL test test_item_objective_revision_advances_for_same_count_
  inventory_replacement + test_physical_inventory_changes_advance_one_
  monotonic_life_revision), migration metadata test extended.

Minor observations (not defects, no action):
- Filler panes set displayName to an empty non-italic Component rather than
  leaving Bukkit's default item name; this is the standard way to render an
  "unnamed" pane with no visible text.
- `direct_action_quest_id`/`actionable_quest_ids` remain in the contract and
  are still produced/asserted, but Paper main code no longer consumes them
  after the GUI replacement (only proximity bark + quests are consumed). They
  are legitimate projection summary fields; removal would be a contract change
  outside check scope.

## Dimension 5: Wiki accuracy (COMPLETE)

- `docs/wiki/quests.md`: new 任务列表 / 任务详情与确认 sections describe the
  shipped behavior exactly: six-row chest, content vs bottom action row,
  BOOK/WRITTEN_BOOK, single `点击查看！` lore, red `暂未解锁` inert entries,
  ready/active/available/locked/completed-gray-last order, unnamed gray panes
  as divider/filler, read-only item preview (explicitly "不是上交槽"), exact
  `玄铁 20 / 15` uncapped example with a note that no verbose labels are added,
  atomic revalidated consumption with excess preserved and single reward, and
  explicit scope limits (no shop/Merchant/escrow/regional storage). The
  `<材料> <背包数量> / <需求>` line is a placeholder-format schema immediately
  grounded by the exact example, consistent with the PRD format.
- Player-interaction bullet updated from the old double-right-click offer flow
  to the GUI flow; verification checklist updated to exercise the GUI.
- `docs/wiki/npcs-and-dialogues.md`: quest-provider precedence now states the
  right click opens the six-row quest list instead of generic dialogue, links
  to quests.md. No stale references to 邀约/再次右键/offer labels remain
  anywhere in docs/wiki. `python3 scripts/check-wiki-links.py` passes.

## Files modified by the checker

The final checker added/finalized mutation life fencing, proximity entry and
revision-generation guards, strict cross-language validation, regression tests,
public Wiki clarification, backend quality contracts, and this report.

## Verification (final)

- `minecraft-nodes/main-plugin`: `./gradlew --no-daemon --max-workers=1 clean test build`
  -> BUILD SUCCESSFUL; 294 tests, 0 failures, 0 errors, 0 skipped.
- `game-service`: `.venv/bin/python -m pytest`
  -> 497 passed in 47.31s.
- `game-service`: `.venv/bin/python -m ruff check .`
  -> All checks passed.
- `python3 scripts/check-wiki-links.py`
  -> 16 pages, Chinese headings, index coverage, and local links verified.
- `python3 ./.trellis/scripts/task.py validate .trellis/tasks/07-20-npc-quest-submission-gui`
  -> implement/check context files valid.
- Python AST audit of `game-service/src` and `game-service/tests`
  -> 79 quest `accept`/`turn_in` call sites, 0 missing `expected_life_id`.
- `git diff --check` -> passed.

Automated acceptance is complete. A real Paper/Citizens client smoke remains
the operator acceptance step: bind a live NPC, approach from outside the range,
change quest/realm state, leave/re-enter, open the six-row GUI, and exercise
accept/turn-in while observing server logs.
