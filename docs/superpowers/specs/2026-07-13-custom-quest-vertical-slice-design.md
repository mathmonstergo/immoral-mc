# Custom Quest Vertical Slice Design

## Purpose

Implement the first complete quest loop for the Wynncraft-style pure plugin
server while preserving a clean path toward many main and side quests later.
Players use an unmodified vanilla client. Citizens supplies NPC mechanics,
Paper supplies real-time interaction and presentation, and Game Service remains
the only authority for quest state.

The first quest is `first-steps` / `初入凡尘`:

1. Approach and interact with `old-man`.
2. Play an offer dialogue and require a second right-click to accept.
3. Track `灵根检测 0/1` in the sidebar.
4. Interact with the Citizens NPC `鉴灵师` to detect a spirit root.
5. Show title, subtitle, and bounded particle effects.
6. Update the sidebar to `1/1` and return to `old-man`.
7. Turn in exactly once and hide the sidebar.

## Architecture

### Vanilla client

The client runs no custom quest code. Existing Minecraft protocol traffic
already synchronizes movement, entities, titles, scoreboards, chat, sounds, and
particles between the client and Paper. A resource pack may later improve art,
models, fonts, and sounds, but cannot own quest logic.

### Paper Adapter

Paper is the low-latency interaction layer. It owns:

* Citizens click routing and provider UUID bindings;
* proximity detection and private state-aware chat;
* pending offer sessions and player-private `TextDisplay` entities;
* title, subtitle, particle, and scoreboard rendering;
* short-lived authoritative presentation snapshots;
* asynchronous Game Service request coordination.

Paper does not infer acceptance, readiness, completion, rewards, or unlocks.

### Game Service

Game Service owns:

* immutable quest and provider definitions;
* quest availability and prerequisite evaluation;
* once-per-life progress and completion;
* authoritative objective evaluation;
* idempotent accept and turn-in commands;
* provider interaction and tracked-quest projections.

The quest module obtains current `life_id`, spirit-root presence, and player
revision through an explicit PlayerService facts interface. It never reads the
player repository directly.

### Citizens

Citizens owns NPC identity, spawning, navigation, location, and right-click
events. ImmortalMC maps a Citizens persistent UUID to either a stable
`quest-provider-id` such as `old-man` or an action such as
`spirit-root-detect`. Citizens does not own quest state or player-private task
labels.

## Domain Model

### Quest definition

The MVP loads immutable application definitions through a repository boundary:

```text
QuestDefinition
  id: first-steps
  version: 1
  title: 初入凡尘
  category: main
  repeatability: once_per_life
  prerequisites: []
  objectives:
    - id: detect-spirit-root
      type: current_life_spirit_root_present
      required: 1
  provider_ids: [old-man]
  turn_in_provider_ids: [old-man]
```

Provider definitions contain ordered main and side quest IDs. Startup
validation rejects unknown IDs, duplicates, and a quest listed in both lists.

### Progress

Persist the minimum canonical record:

```text
QuestProgress
  life_id
  quest_id
  definition_version
  status: active | completed
  accepted_at
  completed_at?
  revision
```

The unique key is `(life_id, quest_id)`. `available` is derived from fulfilled
prerequisites plus no progress row. `ready_to_turn_in` is derived from an active
row plus authoritative objective facts. The spirit-root objective does not
duplicate `0/1` in quest storage.

Public state flow:

```text
available -> active -> ready_to_turn_in -> completed
```

If a player already has a spirit root when accepting, the returned state is
immediately `ready_to_turn_in`. A completed `first-steps` row is itself the
future prerequisite fact; no separate unlock flag is stored.

## API Contract

### Aggregate interaction state

```http
POST /api/v1/players/{account_id}/current-life/quest-interaction-state
Content-Type: application/json

{"provider_ids":["old-man"]}
```

The provider list is de-duplicated and capped at 32. An empty list is valid for
refreshing only the tracked quest. The response contains:

* `contract_version`;
* account and current-life IDs;
* player, quest, and definition revisions;
* ordered provider quest states and actions;
* direct-action quest ID or ordered multi-quest choices;
* proximity speech text, state key, and cooldown;
* the tracked quest projection or `null`;
* a presentation cache TTL of 2 seconds.

Each aggregate request performs one PlayerService facts read and one bulk
quest-progress read. Provider and prerequisite evaluation then occurs in memory.

Actionable ordering is:

1. ready to turn in;
2. active;
3. available;
4. main before side;
5. provider definition order.

The MVP contains one real quest. Multi-quest selection is contract-tested but
does not render a fake second quest.

### Accept and turn-in

```http
PUT /api/v1/players/{account_id}/current-life/quests/{quest_id}/accept
Idempotency-Key: <operation UUID>
Content-Type: application/json

{"provider_id":"old-man"}

PUT /api/v1/players/{account_id}/current-life/quests/{quest_id}/turn-in
Idempotency-Key: <operation UUID>
Content-Type: application/json

{"provider_id":"old-man"}
```

Both commands re-evaluate current authoritative state. A successful response
contains `changed`, the canonical quest state, revisions, and the updated
interaction/tracked-quest projection. Paper therefore does not issue an
immediate follow-up scoreboard request.

Game Service validates that `provider_id` is bound to the quest and is allowed
for the requested accept or turn-in action. A click at an unrelated NPC cannot
mutate the quest merely by knowing its ID.

Repeating accept or turn-in is a successful no-op with `changed=false`.
Replaying the same operation ID returns the stored result. Reusing an operation
ID for a different command or target is a conflict.

Transport failure may retry once with the same operation ID. Domain 4xx
responses are not retried. The existing 2-second HTTP timeout remains the hard
failure ceiling.

## NPC Interaction

### Proximity speech

The coordinator scans every 10 ticks. It indexes only configured, spawned quest
NPCs by world and chunk. For each player it considers the current and adjacent
chunks, rejects different worlds, and compares squared distance against `36.0`.

Speech occurs only on an outside-to-inside edge. It is sent directly to the
player and uses a 60-second cooldown keyed by player, NPC, and authoritative
state key. A state change can speak immediately.

The scan hot path reads cache only. A cache miss schedules at most one
coalesced asynchronous refresh for that player/provider and skips speech for
that scan. Remaining in range never causes polling.

### Offer session

The first right-click in `available` state creates only a local offer session:

```text
playing_offer -> awaiting_confirmation -> accepted | cancelled
```

One non-persistent TextDisplay is hidden by default and shown only to the
interacting player. It displays `任务接取中...` during playback and changes to
`右键接取任务` afterward.

The session cancels without calling Game Service when the player:

* moves beyond 6 blocks;
* changes world;
* disconnects or is kicked;
* waits 20 seconds after playback completes;
* starts a replacement session;
* loses the NPC because it despawns or is removed.

The shared 10-tick coordinator validates all sessions. It does not create one
repeating task per player. Delayed dialogue callbacks carry a session token and
become no-ops after cancellation or replacement.

The second right-click during `awaiting_confirmation` sends accept. Only the
authoritative success response removes the label and displays active progress.

### Spirit-root detector

The Citizens NPC named `鉴灵师` is bound through its persistent UUID to
`spirit-root-detect`. A successful authoritative detection:

* shows title `灵根觉醒`;
* shows a localized subtitle such as `异灵根 · 金雷`;
* reuses the existing quality/element particle planner;
* emits bounded particles around the player and detector NPC;
* refreshes or applies the returned quest projection once.

No enchanting-table or generic block binding is included in this slice.

## Scoreboard

Paper renders the authoritative `tracked_quest` model:

```text
修仙纪事

初入凡尘
灵根检测  0/1
前往鉴灵师处
```

After detection, the progress is `1/1` and the hint is `返回老村民处`.
Successful turn-in returns `tracked_quest=null`, which hides and releases the
plugin sidebar immediately.

The renderer keeps stable entries/teams and a last-rendered immutable model. It
updates changed lines only and performs no work when the model is equal. It is
event-driven by login, accept, detection, turn-in, and explicit refresh, never
by polling or proximity scans.

## Concurrency and Stale Responses

HTTP and JSON parsing run off the Paper thread. Bukkit, Adventure, Citizens,
entity, particle, and scoreboard APIs run only on the main thread.

At most one identical refresh is in flight per player/provider. Each request
has a local generation, and each authoritative response has a player/quest/
definition revision vector. Before applying a callback, Paper verifies:

* the plugin is enabled;
* the player remains online and on the same life;
* the session token is current;
* required world/range conditions still hold;
* no newer generation or revision has already been applied.

A mutation response invalidates older inspect generations. Late responses
cannot resurrect cancelled labels or overwrite a newer scoreboard.

## Failure Handling

On timeout or Game Service failure, Paper clears pending mutation UI and sends
a short retry message. It may continue rendering the last confirmed cosmetic
snapshot, but cannot use it to accept, complete, reward, or advance progress.

Refresh failures use bounded backoff. Repeated failures are rate-limited in logs
instead of producing one stack trace per player per scan. Unknown quest/provider
bindings are treated as configuration errors and do not produce local fallback
state.

Quit, kick, NPC removal, and plugin disable clean up caches, in-flight request
registrations, edge/cooldown state, sessions, displays, scoreboard state, and
scheduled tasks. Long-lived maps use UUIDs rather than retaining Player, NPC,
World, or Entity objects.

## Performance Budgets

Paper has a 50 ms tick budget. This feature targets:

| Operation | Target |
|---|---:|
| 10-tick proximity/session scan | p95 `<0.5 ms`, p99 `<2 ms` |
| Click handler before HTTP dispatch | p95 `<0.25 ms` |
| Changed-scoreboard apply | p95 `<0.25 ms` per player |
| Local click to authoritative UI | p95 `<150 ms` |
| Game Service in-memory handler | p95 `<5 ms`, p99 `<10 ms` |
| HTTP failure ceiling | `2 seconds` |

If a scan exceeds budget, the coordinator carries remaining players into the
next run. It never processes an unbounded backlog in one tick. Particle count
and animation duration are capped.

Verification uses 100 players and 25 configured quest NPCs. Metrics include
scan latency, request latency, cache hit/miss, coalesced requests, request
timeouts, stale-response drops, scoreboard changed-line writes, and live
TextDisplay/session counts. After all players leave, player-scoped map and
display counts must return to zero.

## Storage Limitation and Migration

The MVP repository is explicitly single-process, single-worker, and
restart-volatile. Short write critical sections protect check-and-create/update
operations. PlayerService calls and I/O occur outside repository locks.

Before operational player storage, migrate to PostgreSQL with:

* primary key `(life_id, quest_id)` on quest progress;
* indexed life/status reads;
* an idempotency operation ledger;
* transactional accept and turn-in;
* an outbox for any future reward that cannot share the local transaction.

Redis is unnecessary for this slice and would add avoidable invalidation and
dual-write complexity.

## Testing

Game Service tests cover state derivation, life isolation, prerequisites,
provider ordering, concurrent/idempotent accept, premature turn-in, concurrent/
idempotent completion, operation conflicts, and fixed-count aggregate reads.

Paper tests cover cache-only proximity scans, edge/cooldown behavior, request
coalescing, stale response rejection, all offer cancellation paths, main-thread
application, scoreboard diffing/hiding, and complete cleanup.

The manual acceptance test runs the complete loop on the server:

```text
old-man -> offer -> accept -> 鉴灵师 -> title/particles -> scoreboard 1/1
-> old-man -> turn-in -> scoreboard hidden
```

## Out of Scope

* client mods and custom launchers;
* MythicMobs kill objectives;
* multiple simultaneously tracked quests or tracking controls;
* a rendered multi-quest selection UI before a second real quest exists;
* enchanting-table and generic block interactions;
* item, currency, economy, mail, or cultivation rewards;
* quest editor, branching, party sharing, escort, collection, or timers;
* cross-server state distribution.
