# Paper quest interaction performance design

## Scope and existing constraints

This note covers the Paper 1.21.11 Adapter side of the first quest vertical
slice. Game Service remains authoritative; Paper only caches interaction views
and renders Citizens interaction, private chat, private `TextDisplay`, title,
particles, and scoreboard state.

Relevant existing behavior:

* `GameServiceClient` already uses `HttpClient.sendAsync` with a two-second
  request timeout.
* `PlayerJoinLoginService` already demonstrates the required completion model:
  network completion off-thread, followed by Bukkit work through
  `runTask(plugin, task)`.
* Citizens clicks arrive through `NPCRightClickEvent` and are keyed by the
  Citizens persistent UUID. The existing 500 ms click debouncer is useful for
  duplicate physical clicks but is not a quest-session lock.
* `PlayerSessionCache` is a `ConcurrentHashMap`, but currently has no removal
  method or quit listener. Quest caches and pending offers must not repeat that
  leak.
* Dialogue playback schedules one Bukkit task per line. Offer-session
  cancellation must make delayed lines/transition callbacks harmless after the
  player leaves, changes world, disconnects, or starts a newer session.

## Recommended runtime model

Use one plugin-owned `QuestInteractionCoordinator` with these bounded stores:

```text
player UUID -> authoritative quest interaction snapshot
(player UUID, provider UUID) -> proximity edge/cooldown state
player UUID -> pending offer session
player UUID -> tracked scoreboard render state
provider UUID -> spawned Citizens NPC location/index entry
```

All Bukkit/Citizens/entity/scoreboard access stays on the server thread. HTTP
and JSON parsing stay on `HttpClient` completion threads. Cache values should be
immutable records so network callbacks can safely construct them off-thread and
publish them on the server thread.

## Citizens NPC proximity detection

Do not issue a Game Service request from a movement event or every scheduler
tick. Do not compute every online-player/all-Citizens-NPC pair every tick.

For the MVP, only quest-provider NPCs need proximity tracking, not the entire
Citizens registry. Maintain a provider index from configured persistent
Citizens UUIDs. Resolve only spawned providers and index them by:

```text
world UUID + chunk X + chunk Z -> provider runtime entries
```

Recommended scheduler:

* Run every 10 ticks (500 ms). A 6-block trigger does not require tick-level
  precision.
* For each online player, inspect the player's chunk and adjacent chunks only.
* Reject different worlds first, then compare squared distance (`<= 36.0`);
  never calculate square roots.
* Track the previous inside/outside bit per `(player, provider)`. Speak only on
  an outside-to-inside edge.
* Use a 60-second cooldown keyed by `(player, provider, interaction-state-key)`.
  A state change produces a different key and may speak immediately.
* Prune entries when the player quits and when a provider despawns/removes.

Fixed MVP NPCs can be indexed when Citizens integration enables and refreshed
on Citizens spawn/despawn events. If providers later patrol, update their chunk
entry on a low-frequency task (10 ticks is sufficient) or navigation/location
events. Avoid rebuilding the entire index every tick.

At the current scale, iterating a small configured provider list would also be
acceptable, but the chunk index establishes a stable cost as non-quest Citizens
and player counts grow.

## Cached interaction state

Proximity speech must be a cache-only read on its hot path. Define an immutable
snapshot containing at least:

* account/life identity and a monotonically increasing local generation;
* provider ID and ordered actionable quest summaries;
* state (`available`, `active`, `ready_to_turn_in`, `completed`);
* tracked quest title, objective progress, and next-action hint;
* fetch time/version.

Populate or refresh it on login, explicit NPC interaction, accept, spirit-root
detection, turn-in, and explicit refresh. Successful mutation responses should
write through the cache immediately; do not follow every mutation with another
GET unless the API contract cannot return the new projection.

For passive proximity reads:

* Fresh cache: render immediately.
* Missing/stale cache: start at most one in-flight refresh per
  `(player, provider)` and skip speech for that scan. Render after the response
  only if the player is still online and still in range.
* A short 2-5 second freshness window is enough for passive hints. Explicit
  clicks always request authoritative state unless a mutation response already
  established the current state.
* Coalesce concurrent identical reads by storing the in-flight future. Remove it
  on completion, including failure.
* Apply bounded backoff after failures so a down Game Service cannot cause a
  request storm from every 500 ms scan.

Never infer completion locally from the spirit-root animation. The detection
response (or the quest projection included with it) must be the source used to
update the scoreboard and provider state.

## Asynchronous HTTP and stale-response safety

Calling `sendAsync` is necessary but not sufficient. Every completion must
return to the server thread before it calls Bukkit, Paper, Adventure, Citizens,
scoreboard, or entity APIs.

Recommended flow:

```text
server thread: validate click/session, show immediate pending UI
    -> async HTTP and JSON parse
    -> server thread: validate player/session generation
    -> update cache and render
```

Each pending interaction gets a generation/token. The callback applies only if:

* the plugin is still enabled;
* the player is online;
* the cached current-life ID still matches the request;
* the pending session token still matches;
* the player is in the required world/range when range still matters.

This prevents late accept/inspect responses from resurrecting a cancelled UI or
overwriting a newer quest state. Do not block with `join()`, `get()`, synchronous
HTTP, sleeps, or database access on the Paper thread.

Keep the existing two-second HTTP deadline, but give the player immediate local
feedback (pending label/sound) within the click tick. On failure, clear pending
UI and show a retryable message without fabricating progress.

## Player-private chat and TextDisplay

State-aware proximity speech should use direct Adventure/Paper player delivery,
for example `player.sendMessage(Component)`. It is private because it is sent to
one `Player`; do not use Bukkit broadcast or Citizens global speech traits.

For the label above `old-man`, do not mutate Citizens' global name or
`HologramTrait`. Create one ImmortalMC-owned `TextDisplay` per pending player
session:

1. Spawn on the server thread near the NPC head.
2. Call `setVisibleByDefault(false)` before exposing it.
3. Call `player.showEntity(plugin, display)` only for the owning player.
4. Mark it non-persistent, non-interactive, no gravity, and use billboard/aligned
   presentation settings suitable for a short label.
5. Store its entity UUID/reference in the pending session and remove it on every
   terminal path.

The same entity must change from `任务接取中...` to `右键接取任务`; do not spawn a
second display. If the NPC can move, relocate the display at the same 10-tick
session validation cadence. For fixed MVP NPCs, only range/world validation is
needed.

One display per pending session is bounded by online player count and lasts at
most dialogue duration plus 20 seconds. It must be removed on acceptance,
timeout, distance over 6 blocks, world change, quit, NPC despawn/removal, plugin
disable, and session replacement. Delayed callbacks must tolerate an already
removed entity.

## Pending-offer session scheduling

Avoid one repeating task per player. Use the same 10-tick coordinator scan to
validate all pending offers:

* compare world and squared distance;
* expire awaiting-confirmation sessions after 20 seconds;
* update a moving NPC's private display position if needed;
* remove invalid sessions in one pass.

Dialogue line tasks may remain individually scheduled for this MVP, but each
line and the final `awaiting confirmation` transition must check the session
token. A future dialogue engine can replace these with one timeline scheduler if
large concurrent cinematic conversations make task counts material.

## Sidebar scoreboard updates

The scoreboard is a projection, never a quest-state store. Render from the
authoritative snapshot after login, accept, spirit-root detection, turn-in, and
explicit refresh. Do not poll it every tick or recreate it on every proximity
scan.

Recommended implementation:

* Create one plugin-managed scoreboard/objective per player when an active
  tracked quest first appears.
* Keep stable entries/teams for title, objective, and hint lines; update only
  lines whose text changed.
* Keep a small last-rendered immutable model and return immediately when the
  model is equal.
* All scoreboard creation and mutation runs on the server thread.
* On no active tracked quest, clear the plugin sidebar immediately and release
  the render state.
* On quit, discard the render model and scoreboard references.

Assigning an entire private scoreboard can conflict with other plugins that also
own player scoreboards. The MVP may own the sidebar because MMOCore is excluded,
but the renderer should be isolated behind an interface so it can later adopt a
shared HUD/scoreboard manager. Do not repeatedly call `setScoreboard` for an
unchanged model.

## Player exit and plugin shutdown cleanup

Add one explicit cleanup entry point invoked by `PlayerQuitEvent` (and ideally
`PlayerKickEvent`) that removes:

* `PlayerSessionCache` entry;
* quest/provider snapshots and in-flight request registrations;
* proximity inside/cooldown state;
* pending offer and its `TextDisplay`;
* scoreboard render state;
* dialogue/session generations.

On plugin disable, cancel the coordinator task, invalidate all generations,
remove every owned display, and clear maps. Network futures do not need forceful
cancellation if callbacks first test plugin/session validity, though cancelling
known futures is useful for prompt resource release.

Use bounded maps keyed by online player UUID. Cooldown timestamps should be
pruned on quit and may also be pruned during the low-frequency scan. Do not retain
`Player`, `NPC`, `Entity`, `World`, or scoreboard objects in long-lived static
maps; prefer UUIDs and resolve on the server thread.

## Main-thread budget and failure containment

Paper has roughly 50 ms per tick at 20 TPS. This feature should consume only a
small fraction of that budget:

* Proximity/pending scan target: p95 below 0.5 ms and p99 below 2 ms per run at
  the expected concurrency.
* Individual click handler before HTTP dispatch: below 0.25 ms p95.
* Scoreboard diff/apply: below 0.25 ms p95 per changed player.
* No network wait, JSON parse, filesystem read, YAML reload, or Game Service
  database work on the Paper thread.
* Cap particle counts and animation task duration; the existing one-shot
  particle presenter is preferable to per-tick unbounded particle loops.

If a scan exceeds budget, carry remaining players into the next run rather than
processing an unlimited backlog in one tick. Logging should summarize/rate-limit
repeated Game Service failures instead of logging one stack trace per player per
scan.

## Verification and performance metrics

Automated tests should cover:

* proximity is edge-triggered and 60-second cooldown is state-specific;
* a stale cache produces one coalesced refresh, not one request per scan;
* range/world/timeout/quit removes a private display exactly once;
* a late HTTP response cannot restore a cancelled or superseded session;
* scoreboard writes occur only when the render model changes and clear on no
  active quest;
* all player-scoped maps are empty after quit/disable;
* repeated accept/turn-in responses remain idempotent at the Adapter boundary.

Manual/load verification should record:

* Paper TPS/MSPT before and during 100 simulated/real players near 25 configured
  quest NPCs;
* coordinator scan p50/p95/p99 and maximum duration;
* Game Service request rate, cache hit ratio, coalesced request count, timeouts,
  and failure-backoff count;
* click-to-pending-label latency (target: same tick) and click-to-authoritative
  UI latency (local Game Service p95 target: below 150 ms, while remaining
  correct up to the two-second timeout);
* live private `TextDisplay` count versus pending session count;
* cache/map sizes before players join and after all players leave;
* scoreboard render attempts versus actual changed-line writes;
* particle/entity packet spikes during simultaneous spirit-root detection.

Use Paper's built-in timings/spark-style profiling available on the server plus
plugin counters/timers around the coordinator. The success condition is not
only 20 TPS: there should be no synchronous HTTP frames, no unbounded player/NPC
cross-product, no repeated passive-state HTTP polling, and no retained
player-owned state after disconnect.
