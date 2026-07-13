# custom quest vertical slice

## Goal

Build the first Game Service-authoritative quest vertical slice and connect it
to the existing Citizens `old-man` dialogue interaction. The slice should prove
quest offer, acceptance, objective evaluation, turn-in, completion, conditional
dialogue, and idempotency without introducing a generic editor or third-party
quest engine.

## What I already know

* The user approved developing a custom quest system.
* Citizens owns NPC identity/clicks; ImmortalMC owns dialogue presentation and
  Adapter routing; Game Service owns quest state and rewards.
* MMOCore and third-party quest engines are not part of the runtime plan.
* The current player model has account and current-life IDs plus persisted
  spirit-root state behind the repository boundary.
* `old-man` is a persistent Citizens NPC already bound to the `old-man` dialogue.
* The first quest system should be a small vertical slice, not a general quest
  editor, branching scripting language, or large objective framework.
* Reusing spirit-root detection as the first objective isolates quest-state
  design from the separate MythicMobs combat/death integration.
* The user requires scoreboard-based quest status tracking in the MVP.
* The user selected spirit-root detection as the first quest objective.
* The user wants spirit-root detection results presented with client title,
  subtitle, and particles around the player and detector.
* The user chose a second Citizens NPC as the MVP spirit-root detector and
  deferred enchanting-table/block interaction support.
* The second Citizens NPC's player-facing name is “鉴灵师”.
* The user selected quest completion itself as the MVP reward: completing
  `first-steps` unlocks future quests through prerequisite evaluation, without
  granting items, currency, or cultivation points.
* The user chose a two-step quest acceptance interaction: the first right-click
  plays the offer, and a second right-click after playback accepts the quest.
* Leaving before formal acceptance cancels the pending offer session.
* The user wants a player-specific status label above the quest NPC during the
  offer flow.
* Pending offers cancel beyond 6 blocks or 20 seconds after offer playback.
* The user wants state-aware proximity speech in the normal chat area, delivered
  only to the nearby player rather than broadcast to the server.
* Important NPCs must be able to offer multiple main and side quests.
* The user chose one real MVP quest while requiring the provider/data contracts
  to support multiple quests; no second placeholder quest will be created.
* Proximity speech uses a 60-second cooldown per player/NPC/quest-state; a state
  change may speak immediately.
* The user explicitly requires server performance and interaction latency to be
  part of the design and acceptance criteria.
* The server is intentionally a Wynncraft-style pure plugin server. Players use
  an unmodified vanilla client; no Fabric/NeoForge mod or custom launcher is
  required for the quest MVP.

## Confirmed Product Decisions

* Quest progress belongs to the current life, not permanently to the account.
* Quest definitions are data-driven and identified by stable string IDs.
* The first quest is `first-steps` / “初入凡尘”.
* Initial states are `available`, `active`, `ready_to_turn_in`, and `completed`.
* The first objective is satisfied when the current life has a spirit root.
* Repeated accept/turn-in requests must be idempotent.
* The MVP scoreboard automatically tracks one current quest rather than adding
  player-selectable tracking UI.
* The user chose to hide the quest scoreboard automatically when no quest is active.
* Passive NPC proximity checks use event-driven cached state. They never poll
  Game Service merely because a player remains near an NPC.
* On Game Service failure, Paper preserves the last confirmed cosmetic state,
  reports a retryable failure, and never applies an optimistic accept, objective,
  turn-in, or reward transition.
* High-frequency Minecraft protocol synchronization remains between the vanilla
  client and Paper. Paper-to-Game-Service quest communication is event-driven,
  not tick-driven.

## Open Questions

* None.

## Requirements

* Add a `quest` module with schemas, repository, service, API, and tests.
* Store quest progress against `life_id`.
* Expose inspect/accept/turn-in contracts for one stable quest ID.
* Derive readiness from authoritative current-life spirit-root state.
* Return dialogue/presentation state that the Adapter can map to NPC text.
* Prevent duplicate acceptance, completion, and reward delivery.
* Treat the completed `first-steps` record as the prerequisite/reward that makes
  future quest definitions available; do not store a redundant unlock flag.
* First right-click on an available quest starts a local presentation session
  but does not create authoritative quest progress.
* While offer text is playing, show a player-specific `任务接取中...` TextDisplay
  above `old-man`.
* When offer playback finishes, change that player's TextDisplay to
  `右键接取任务`.
* The second right-click in the awaiting-confirmation state calls the Game
  Service accept endpoint, then removes the temporary TextDisplay and shows the
  active quest scoreboard.
* Do not mutate Citizens' global HologramTrait for per-player state. Spawn an
  ImmortalMC-owned TextDisplay that is hidden by default and shown only to the
  relevant player.
* Cancel and remove the pending TextDisplay when the player leaves the allowed
  range, changes world, disconnects, or exceeds the confirmation timeout.
* Use a 6-block session radius and a 20-second awaiting-confirmation timeout.
* Add edge-triggered NPC proximity detection: entering the configured radius may
  send one state-aware line to that player, such as `最近太不太平了...` when a
  relevant quest is available.
* Proximity speech must use direct player chat delivery, not Bukkit broadcast or
  Citizens global speech.
* Proximity speech must have a per-player/NPC/state cooldown and must not issue an
  HTTP request every server tick; use cached authoritative interaction state.
* Use a 60-second proximity-speech cooldown keyed by player, provider NPC, and
  authoritative interaction state; expire old cache entries.
* Model NPC quest bindings through a stable `quest-provider-id`, not a single
  hardcoded quest ID.
* A quest provider definition may contain ordered main and side quest IDs.
* Game Service interaction state must distinguish quests that are available,
  active, ready to turn in, and completed for the current life.
* If one quest is actionable, right-click enters that quest flow directly. If
  multiple quests are actionable, present a player-specific selection list;
  ready-to-turn-in and active quests sort before newly available quests.
* Ship only `first-steps` content in this MVP; multi-quest selection rendering
  may remain contract-tested until a second real quest is added.
* Paper proximity scanning must run at a bounded low frequency, use squared
  distances in the same world, and never perform blocking HTTP on the server thread.
* Cache one authoritative quest-interaction snapshot per player/provider with a
  server-provided presentation TTL of 2 seconds. Refresh on login, explicit NPC
  interaction, accept, spirit-root detection, turn-in, or explicit refresh.
  Expiry permits one coalesced async refresh but never passive polling while the
  player simply remains in range.
* Mutation responses should include the new interaction/scoreboard snapshot so
  the Adapter does not immediately issue a redundant follow-up request.
* Allow at most one in-flight quest refresh/mutation per player/provider and
  discard stale out-of-order responses using a monotonic state revision.
* Update scoreboard and private NPC labels only when rendered content changes.
* Clean up player caches, proximity state, pending offer sessions, scheduled
  tasks, and TextDisplay entities on quit/plugin disable.
* Keep the existing 2-second HTTP timeout as the failure ceiling. A retryable
  accept or turn-in transport failure may retry at most once with the same
  operation ID; domain 4xx responses are never retried.
* Connect Citizens NPC interaction to the Game Service asynchronously.
* Keep quest definitions reviewable and data-driven.
* Add a Paper sidebar scoreboard that renders the tracked quest title, objective
  progress, and next-action hint from Game Service-authoritative state.
* Refresh the scoreboard on player login, quest acceptance, spirit-root
  detection, quest turn-in, and explicit quest-state refresh.
* Do not let scoreboard text become a second quest-state source.
* Hide the sidebar immediately after successful turn-in and whenever the
  authoritative response reports no active tracked quest.
* Bind `spirit-root-detect` to the “鉴灵师” Citizens NPC using its persistent UUID.
* Keep `old-man` as the quest offer/turn-in NPC and the second NPC as the
  objective interaction target.
* On successful detection, show a client title and subtitle containing the
  localized spirit-root label and element/mutated-element summary.
* Reuse the existing quality/element particle plan, spawning effects around the
  player and the spirit-root detector NPC.
* Preserve existing entity-based spirit-root detector bindings during migration.

## Acceptance Criteria

* [ ] New life can inspect the quest as available.
* [ ] Accepting creates one active progress record.
* [ ] Repeated acceptance returns the existing state without duplication.
* [ ] Spirit-root detection makes the active quest ready to turn in.
* [ ] Turn-in completes the quest exactly once.
* [ ] Repeated turn-in does not duplicate rewards.
* [ ] `old-man` displays dialogue appropriate to current quest state.
* [ ] First interaction shows `任务接取中...` only to the interacting player.
* [ ] Offer completion changes the private label to `右键接取任务`.
* [ ] Leaving before confirmation cancels the offer without accepting the quest.
* [ ] Entering the old-man proximity radius sends one state-aware private chat line.
* [ ] Remaining in range or re-entering during cooldown does not spam chat.
* [ ] Quest-provider contracts can represent multiple main/side quests even
  though the first content slice may contain only one quest.
* [ ] Sidebar scoreboard shows the active quest title and objective progress.
* [ ] Scoreboard updates after acceptance, spirit-root detection, and turn-in.
* [ ] Right-clicking the configured Citizens detector NPC starts spirit-root detection.
* [ ] Detection success displays title/subtitle and player/NPC particle effects.
* [ ] Adapter HTTP failures do not fake local quest progress.
* [ ] No quest HTTP request executes on the Paper main thread.
* [ ] Proximity scans issue zero HTTP requests on cache hits.
* [ ] Duplicate/in-flight requests are coalesced and stale revisions cannot
  overwrite newer scoreboard or NPC state.
* [ ] At 100 players and 25 configured quest NPCs, the 10-tick coordinator scan
  meets p95 `<0.5 ms` and p99 `<2 ms` without an unbounded player/NPC cross-product.
* [ ] Click handling before HTTP dispatch meets p95 `<0.25 ms`; changed-scoreboard
  apply meets p95 `<0.25 ms` per player.
* [ ] Local click-to-authoritative UI latency meets p95 `<150 ms`, while the
  interaction remains correct through the existing 2-second timeout ceiling.
* [ ] Game Service in-memory handlers meet p95 `<5 ms` and p99 `<10 ms` under
  the MVP load test, with fixed-count repository reads per aggregate request.
* [ ] Performance telemetry records scan latency, request latency, cache
  hit/miss, coalesced requests, timeouts, stale-response drops, scoreboard line
  writes, and live pending TextDisplay counts.
* [ ] Backend and Java automated tests pass.
* [ ] Manual server test completes the full NPC -> spirit root -> NPC loop.

## Definition of Done

* Game Service remains the only quest-state authority.
* Quest transitions and idempotency have direct tests.
* Adapter remains asynchronous and presentation-only.
* API and data contracts are documented in `.trellis/spec/`.
* Work is committed, archived, and journaled.

## Technical Approach

### Architecture and ownership

Game Service is the only quest-state authority. Its quest module owns immutable
quest/provider definitions, once-per-life progress, prerequisite evaluation,
derived readiness, idempotent accept/turn-in transitions, and the tracked-quest
projection. It obtains `life_id`, spirit-root presence, and player revision only
through an explicit PlayerService facts interface.

Citizens owns NPC identity, lifecycle, position, and right-click events. The
ImmortalMC Paper Adapter maps Citizens persistent UUIDs to stable provider/action
IDs and owns only transient presentation: offer sessions, private chat,
player-only `TextDisplay`, title/subtitle, particles, and sidebar rendering.

The vanilla client remains presentation-only through normal Minecraft packets.
Paper may send titles, scoreboard changes, entity metadata, chat, sounds, and
particles, but no custom quest logic is installed or trusted on the client.

### Authoritative state and API

Persist only `active|completed` quest progress under the unique key
`(life_id, quest_id)`. Derive `available` from prerequisites plus absence of a
record, and derive `ready_to_turn_in` from an active record plus current
PlayerService facts. The first spirit-root objective therefore stores no
duplicate `0/1` counter.

One aggregate interaction-state request accepts a bounded, de-duplicated set of
provider IDs and returns provider quest states, ordered actionable quests,
dialogue/action keys, proximity speech, the tracked scoreboard projection, a
contract version, player/quest/definition revision vector, and a 2-second
presentation TTL. Provider input is capped at 32 IDs. One request performs one
PlayerService facts read and one bulk quest-progress read, then computes all
provider views in memory.

Accept and turn-in are idempotent mutations carrying an operation UUID. Their
responses include the updated interaction and tracked-quest projection so Paper
does not issue a redundant follow-up read. Repeating the same semantic command
returns HTTP 200 with `changed=false`; reusing an operation UUID for a different
target returns a conflict. A mutation success invalidates any older inspect
generation still in flight.

### Paper interaction coordinator

Use one plugin-owned coordinator. It indexes configured, spawned quest NPCs by
world and chunk and scans online players every 10 ticks. The hot path checks only
the player's current and adjacent chunks, rejects other worlds, compares squared
distance, tracks outside-to-inside transitions, and reads proximity text only
from cache. A cache miss schedules at most one async refresh for that
player/provider and skips speech for that scan.

HTTP and JSON parsing remain fully asynchronous. Every Bukkit, Citizens, entity,
Adventure, particle, and scoreboard change is marshalled to the main thread.
Each request/session has a local generation token; callbacks verify plugin,
player, life, session, world/range, and generation before applying results.
Older responses are discarded using both the local generation and authoritative
revision vector.

### Presentation lifecycle

The first available-state click starts only a local offer session. One
non-persistent TextDisplay is hidden by default and shown solely to the player;
it changes from `任务接取中...` to `右键接取任务`. The shared 10-tick coordinator
validates range/world/timeout rather than creating one repeating task per player.
Leaving 6 blocks, changing world, disconnecting, NPC removal, replacement, or a
20-second confirmation timeout removes the display and cancels the session
without calling accept.

The sidebar renders only the authoritative tracked-quest projection. It keeps
stable entries/teams and updates changed lines only. Login, successful mutation,
spirit-root detection, and explicit refresh can update it; proximity scanning
cannot. `tracked_quest=null` hides and releases the plugin sidebar immediately.

### Performance and failure containment

The Paper main thread performs no HTTP wait, JSON parsing, filesystem/config
reload, or Game Service work. The coordinator uses bounded maps keyed by online
player/provider UUIDs, prunes them on quit/despawn, and clears sessions, displays,
scoreboards, futures, and tasks on disable. If one scan exceeds its budget, it
carries remaining players to the next run instead of processing an unlimited
backlog in one tick.

On timeout or server error, pending mutation UI is cleared and the player gets a
short retry message. The last confirmed cosmetic snapshot may remain visible,
but it cannot authorize a mutation or fabricate progress. Repeated failure logs
are rate-limited and refresh attempts use bounded backoff to prevent a request
storm while Game Service is unavailable.

The MVP Game Service repository remains explicitly single-process,
single-worker, and restart-volatile. Its write critical sections contain only
short in-memory checks/copy-on-write updates; they do not call PlayerService or
perform I/O while locked. PostgreSQL persistence, unique constraints, operation
ledger, and transactions are required before this is treated as operational
player storage.

## Decision (ADR-lite)

**Context**: NPC proximity, private status, scoreboard updates, and multi-quest
providers need fresh authoritative state without placing HTTP or heavy rendering
on Paper's 50 ms tick budget.

**Decision**: Use an event-driven aggregate snapshot architecture. Game Service
returns complete provider/scoreboard projections and monotonic revision data;
Paper keeps a short presentation cache, coalesces refreshes, scans indexed NPCs
every 10 ticks, and applies only changed UI on the main thread.

**Consequences**: Normal movement near NPCs performs zero HTTP on cache hits and
bounded spatial work. Player-visible authoritative changes require an explicit
event refresh, and during an outage the UI may temporarily show the last
confirmed cosmetic state, but no quest mutation is guessed locally. The
coordinator and revision checks add implementation complexity, justified by
predictable server cost and resistance to stale async responses.

## Out of Scope

* MythicMobs kill objectives unless explicitly selected for this slice.
* Branching choices, timers, escort, collection, party-shared progress.
* Quest editor/admin panel.
* Multiple tracked quests, pin/unpin controls, scrolling, paging, or HUD editor.
* Enchanting-table or generic block-interaction bindings.
* Full item, currency, economy, or mail reward systems.
* Cross-server event delivery.
* Client mods, a custom launcher, or client-authoritative quest prediction.

## Technical Notes

* Backend package: `game-service/src/immortal_mmo/quest/`.
* Player source of current-life truth: `game-service/src/immortal_mmo/player/`.
* Adapter action: existing Citizens-backed `npc-dialogue` route.
* The quest module must call the player module through an explicit service
  interface rather than reading player repository tables directly.
* Research references:
  * `research/quest-contract-design.md`
  * `research/quest-backend-performance.md`
  * `research/paper-quest-performance.md`
