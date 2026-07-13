# Quest contract design for `first-steps`

## Decision summary

The MVP should implement one real quest, `first-steps` / “初入凡尘”, while
making the definition and NPC-provider contracts capable of representing more
than one main or side quest.

Ownership remains strict:

| Concern | Owner |
|---|---|
| Citizens NPC identity, entity lifecycle, navigation and click event | Citizens |
| Temporary offer session, private TextDisplay, chat/title/particles and sidebar rendering | Paper Adapter |
| Quest definitions, availability, progress, readiness, completion and prerequisite evaluation | Game Service |
| Current-life identity and spirit-root fact | Game Service player module |

The Adapter may cache an authoritative interaction snapshot for presentation,
but it must never infer or persist quest progress. Accept and turn-in always call
the Game Service. On timeout or an error, the local display stays at the last
confirmed state and no success presentation is shown.

## First quest definition

Definitions should be immutable application data for the MVP, loaded through a
repository boundary. YAML can be added later without changing the service
contract. A representative serialized definition is:

```yaml
id: first-steps
version: 1
title: 初入凡尘
category: main
repeatability: once_per_life
prerequisites: []
objectives:
  - id: detect-spirit-root
    type: current_life_spirit_root_present
    title: 灵根检测
    required: 1
provider_ids:
  - old-man
turn_in_provider_ids:
  - old-man
tracked_by_default: true
dialogue:
  available: first-steps-offer
  active: first-steps-reminder
  ready_to_turn_in: first-steps-turn-in
  completed: first-steps-completed
presentation:
  active_hint: 前往鉴灵师处
  ready_hint: 返回老村民处
```

`provider_ids` and `turn_in_provider_ids` are domain IDs, not Citizens UUIDs.
The Adapter binding maps a Citizens persistent UUID to `quest-provider-id:
old-man`. The detector NPC separately maps its Citizens UUID to the existing
`spirit-root-detect` action.

The completed `first-steps` record is the unlock fact for future definitions.
A future prerequisite should reference `quest_completed:first-steps`; do not
store a second `unlocked=true` flag.

## State model

### Public states

```text
available -> active -> ready_to_turn_in -> completed
```

* `available`: no progress record exists for the current `life_id`, all
  prerequisites pass, and the quest has not been completed for that life.
* `active`: one progress record exists and at least one required objective is
  incomplete.
* `ready_to_turn_in`: the progress record exists and all objectives evaluate as
  complete against current authoritative facts.
* `completed`: completion was committed for this life. It is terminal because
  the MVP repeatability is `once_per_life`.

`available` and `ready_to_turn_in` are derived views. The minimum persisted
record is:

```text
QuestProgress(
  life_id,
  quest_id,
  definition_version,
  status = active | completed,
  accepted_at,
  completed_at?,
  revision
)
```

Use a unique key on `(life_id, quest_id)`. The spirit-root objective does not
need a duplicate counter column: `current=1` is derived from the player
module's current-life fact. This avoids a split-brain state where the player has
a spirit root but the task counter remains zero. Future event-count objectives
may add their own idempotent event ledger behind the quest repository.

The quest module must depend on an explicit player-module interface such as:

```python
class CurrentLifeFactsReader(Protocol):
    def get_current_life_facts(self, account_id: UUID) -> CurrentLifeFacts: ...
```

It must not read player repository dictionaries/tables directly. Each request
resolves the account's current `life_id` first, so reincarnation naturally gets
a fresh once-per-life quest state.

### Transition rules

| Command | Current view | Result |
|---|---|---|
| inspect | no record + prerequisites pass | `available` |
| accept | `available` | create one `active` record |
| accept | `active` | return existing state, `changed=false` |
| accept | `ready_to_turn_in` | return existing state, `changed=false` |
| accept | `completed` | return completed state, `changed=false` |
| accept | prerequisites fail | reject; create nothing |
| objective evaluation | `active`, no spirit root | remains `active`, progress `0/1` |
| objective evaluation | `active`, spirit root present | view becomes `ready_to_turn_in`, progress `1/1` |
| turn-in | `ready_to_turn_in` | atomically mark `completed` |
| turn-in | `completed` | return existing completion, `changed=false` |
| turn-in | `available` or `active` | reject; change nothing |

If the player already has a spirit root when accepting, the accept response is
immediately `ready_to_turn_in`. The definition describes the desired fact, not
the order in which the player happened to produce it.

## Quest provider contract

A provider definition supports ordered main and side quest IDs even though the
MVP ships only one quest:

```json
{
  "provider_id": "old-man",
  "display_name": "老村民",
  "main_quest_ids": ["first-steps"],
  "side_quest_ids": []
}
```

Validation at startup should reject duplicate provider IDs, duplicate quest IDs
within one provider, unknown quest IDs, or a quest listed in both main and side
collections. Array order is the content author's tie-breaker.

An actionable quest is `ready_to_turn_in`, `active`, or `available`.
`completed` entries may be returned for state-aware dialogue but do not enter a
selection menu. Selection ordering is:

1. `ready_to_turn_in`
2. `active`
3. `available`
4. main before side within the same state
5. provider definition order as the final tie-breaker

If exactly one quest is actionable, right-click enters it directly. If more
than one is actionable, the Adapter renders the returned ordered choices. The
MVP only contract-tests this branch; it does not add fake second-quest content.

## NPC interaction snapshot

One provider inspection endpoint should return all presentation data needed for
one player/NPC interaction without follow-up requests:

```http
GET /api/v1/players/{account_id}/quest-providers/{provider_id}/interaction
```

```json
{
  "account_id": "uuid",
  "life_id": "uuid",
  "provider_id": "old-man",
  "snapshot_revision": 7,
  "generated_at": "2026-07-13T12:00:00Z",
  "cache_ttl_ms": 2000,
  "quests": [
    {
      "quest_id": "first-steps",
      "title": "初入凡尘",
      "category": "main",
      "state": "available",
      "action": "offer",
      "dialogue_id": "first-steps-offer",
      "objectives": [
        {
          "objective_id": "detect-spirit-root",
          "title": "灵根检测",
          "current": 0,
          "required": 1,
          "completed": false
        }
      ]
    }
  ],
  "actionable_quest_ids": ["first-steps"],
  "direct_action_quest_id": "first-steps",
  "proximity_bark": {
    "key": "first-steps:available",
    "text": "最近太不太平了...",
    "cooldown_seconds": 60
  },
  "tracked_quest": null
}
```

`snapshot_revision` is a monotonic life quest revision used for stale-response
protection, not an authorization token. Every mutation re-evaluates the command
from current server state. The Adapter discards an async response older than the
latest revision it has already applied for that player.

Suggested state presentation for `old-man`:

| State | Action | Dialogue | Proximity bark |
|---|---|---|---|
| available | `offer` | offer text, then wait for second right-click | `最近太不太平了...` |
| active | `remind` | direct player toward `鉴灵师` | `去找鉴灵师看看吧。` |
| ready_to_turn_in | `turn_in` | completion/turn-in text | `看来你已经有所收获。` |
| completed | `talk` | normal dialogue or no quest action | absent by default |

The pending-offer session is deliberately absent from this contract because it
is transient presentation state, not quest progress. The Adapter owns:

```text
(player UUID, Citizens NPC UUID, quest ID,
 phase = playing_offer | awaiting_confirmation,
 started_at, playback_finished_at, expires_at)
```

It displays `任务接取中...` while playback runs, then `右键接取任务`.
The private TextDisplay is removed when the player accepts, moves beyond 6
blocks, changes world, disconnects, or waits more than 20 seconds after playback
finishes. Cancellation never calls the accept API.

## Proximity bark and performance

Proximity speech is edge-triggered and private to the player. The Adapter sends
the returned `text` with direct player messaging, never Bukkit broadcast or
Citizens global speech.

Recommended runtime behavior:

* Run proximity scans every 10 ticks (500 ms), not every tick.
* Only scan online players in worlds that contain configured quest-provider
  NPCs. Compare squared distance; do not allocate `Location` objects in inner
  loops where avoidable.
* Track inside/outside state by `(player UUID, Citizens NPC UUID)` and only
  consider a bark on the outside -> inside edge at the configured 6-block
  radius.
* Read `proximity_bark` from the cached interaction snapshot. Never issue HTTP
  from the scan loop.
* Use a per `(player UUID, Citizens NPC UUID, bark.key)` 60-second cooldown.
  Because the key includes quest state, a state change may speak immediately
  without waiting for the old state's cooldown.
* On a cache miss, schedule one deduplicated async refresh and skip that scan's
  bark. Do not queue one request per tick or per click.
* Expire interaction snapshots after the server-provided `cache_ttl_ms`
  (recommended MVP value: 2 seconds). Keep stale data available only for quiet
  cosmetic rendering; never use it to approve accept or turn-in.
* Invalidate/update the player's cache immediately from successful accept and
  turn-in responses. After spirit-root detection, perform one async tracked
  quest/provider refresh. This yields prompt scoreboard updates without polling.
* Coalesce concurrent refreshes per `(account_id, provider_id)` with a shared
  `CompletableFuture`. Bound HTTP calls with the existing 2-second timeout and
  never block the Paper main/entity thread.

This creates bounded background work: spatial checks occur twice per second,
normal movement causes zero HTTP traffic while the cache is warm, and quest
state changes get push-like local refreshes from command responses.

## Scoreboard model

The authoritative response should provide a presentation-neutral tracked quest
model. The Adapter owns Bukkit scoreboard formatting:

```json
{
  "tracked_quest": {
    "quest_id": "first-steps",
    "title": "初入凡尘",
    "state": "active",
    "objectives": [
      {
        "objective_id": "detect-spirit-root",
        "title": "灵根检测",
        "current": 0,
        "required": 1,
        "completed": false
      }
    ],
    "next_action_hint": "前往鉴灵师处"
  }
}
```

For `ready_to_turn_in`, progress becomes `1/1` and the hint becomes `返回老村民处`.
For `available` and `completed`, `tracked_quest` is `null`. A successful turn-in
therefore immediately hides the sidebar. The Adapter must also hide it on login
or refresh whenever the authoritative value is null.

MVP sidebar rendering:

```text
修仙纪事

初入凡尘
灵根检测  0/1
前往鉴灵师处
```

Use stable scoreboard entries/team prefixes so only changed lines are updated;
do not recreate the scoreboard every proximity scan. Refresh on login, accept,
successful spirit-root detection, turn-in and explicit admin refresh. The model
is single-tracked-quest by design; multi-track selection is out of scope.

## Idempotent mutation APIs

### Accept

```http
POST /api/v1/players/{account_id}/quests/{quest_id}/accept
Content-Type: application/json

{"operation_id":"uuid"}
```

```json
{
  "operation_id": "uuid",
  "changed": true,
  "quest": {"quest_id":"first-steps","state":"active"},
  "tracked_quest": {},
  "snapshot_revision": 8
}
```

Acceptance must run in one repository transaction/critical section:

1. resolve current life;
2. load and validate definition/prerequisites;
3. insert `(life_id, quest_id)` under a unique constraint;
4. if the row already exists, return its current derived state;
5. store/replay the operation result for the same `operation_id`.

Semantic idempotency is required even with a new operation ID: accepting an
already active, ready or completed quest returns HTTP 200 with `changed=false`.

### Turn-in

```http
POST /api/v1/players/{account_id}/quests/{quest_id}/turn-in
Content-Type: application/json

{"operation_id":"uuid"}
```

Turn-in atomically re-reads current-life facts, verifies all objectives, changes
`active` to `completed`, records `completed_at`, and advances the life quest
revision. The only MVP reward is that committed completion record. There is no
separate reward delivery or unlock write.

Repeated turn-in after completion returns HTTP 200, `changed=false`, the same
completed state, `tracked_quest=null`, and no additional side effect.

For both APIs, an `operation_id` replay with the same route/account/life/quest
returns the stored response. Reuse of an operation ID for a different command
or target is a conflict. Repository implementations should use either a
transactional operation ledger or equivalent unique constraints; a process-local
debouncer alone is insufficient.

## Error matrix

All domain failures use the existing envelope:

```json
{"error":{"code":"quest.not_ready","message":"...","retryable":false}}
```

| Situation | HTTP | Code | Retryable | Adapter behavior |
|---|---:|---|---|---|
| Account does not exist | 404 | `player.account_not_found` | false | clear pending UI, ask player to relog |
| No current live life can be resolved | 409 | `player.current_life_unavailable` | false | clear pending UI; log IDs |
| Quest ID is unknown | 404 | `quest.not_found` | false | clear pending UI; log content/config error |
| Provider ID is unknown | 404 | `quest.provider_not_found` | false | no bark/action; log config error |
| Quest is not bound to clicked provider | 409 | `quest.provider_mismatch` | false | reject action and refresh provider snapshot |
| Prerequisite is not met / quest unavailable | 409 | `quest.not_available` | false | do not create progress; refresh snapshot |
| Turn-in attempted before acceptance | 409 | `quest.not_accepted` | false | refresh snapshot; no success text |
| Active objective is incomplete | 409 | `quest.not_ready` | false | keep scoreboard; show reminder, not success |
| Same operation ID used for different payload/target | 409 | `quest.idempotency_conflict` | false | generate a new ID only for a genuinely new player action |
| Concurrent accept loses unique-row race | 200 | normal response, `changed=false` | n/a | apply returned authoritative state |
| Concurrent/repeated turn-in after completion | 200 | normal response, `changed=false` | n/a | hide scoreboard; no duplicate reward |
| Malformed UUID/body | 422 | FastAPI validation error | false | log programming/config error |
| Game Service timeout/unreachable | local client error | n/a | true | preserve last confirmed display, clear pending mutation UI, allow manual retry |
| Unexpected server error | 500 | `domain.error` or specific code | true only if explicitly marked | do not advance local state; structured log with operation ID |

Completed is not an error for accept or turn-in because treating repeats as
successful no-ops makes retries safe and simplifies recovery after a lost HTTP
response.

## End-to-end MVP flow

1. On login, the Adapter fetches the tracked quest and relevant provider
   snapshots asynchronously. No active quest means no sidebar.
2. Entering `old-man`'s 6-block radius may display the cached available-state
   bark. The same player/NPC/state key is quiet for 60 seconds.
3. First right-click inspects/uses the authoritative provider snapshot, plays
   the offer and creates only a local pending-offer session.
4. During playback, only that player sees `任务接取中...`; afterward they see
   `右键接取任务`.
5. Leaving 6 blocks, changing world, disconnecting, or waiting 20 seconds after
   playback cancels the local session without a Game Service mutation.
6. A second right-click sends accept with a fresh operation ID. Only a success
   response removes the label and shows the authoritative `0/1` sidebar.
7. Right-clicking the Citizens `鉴灵师` triggers the existing authoritative
   spirit-root detection. The Adapter shows title/subtitle and particles from
   that successful result, then refreshes the tracked quest once.
8. The refreshed sidebar shows `1/1` and `返回老村民处`.
9. Right-clicking `old-man` in `ready_to_turn_in` enters turn-in presentation
   and calls the idempotent turn-in API.
10. The completion response has `tracked_quest=null`; the Adapter hides the
    sidebar. Future quest definitions may now pass a
    `quest_completed:first-steps` prerequisite.

## Required contract tests

Game Service tests should cover:

* available inspection for a new life;
* one provider containing ordered main and side quest IDs;
* accept creates exactly one record;
* repeated and concurrent accept are 200 no-ops;
* accept after prior spirit-root detection returns ready immediately;
* active quest changes from `0/1` to `1/1` from player-module facts;
* premature turn-in is rejected without mutation;
* turn-in commits completion exactly once;
* repeated/concurrent turn-in cannot duplicate completion/reward;
* a new life does not inherit once-per-life progress;
* provider mismatch and operation-ID conflict errors;
* completed `first-steps` satisfies a future prerequisite in a synthetic unit
  test without shipping a second content definition.

Adapter tests should cover:

* no HTTP call from the periodic proximity scan;
* outside -> inside edge and 60-second state-keyed cooldown;
* cache refresh request coalescing and stale revision rejection;
* pending offer cancellation at distance/world/disconnect/timeout;
* accept/turn-in failures never update the sidebar optimistically;
* sidebar line diffing and hiding on `tracked_quest=null`;
* async completion is marshalled back to the correct Bukkit/entity thread.
