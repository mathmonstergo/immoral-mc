# ImmortalMC Main Plugin

Thin Paper adapter plugin for the ImmortalMC Game Service.

## Target

- Minecraft / Paper: `1.21.11`
- Java: `21`
- Build tool: Gradle Kotlin DSL, wrapper pinned to `9.6.1`
- Plugin descriptor: `src/main/resources/plugin.yml`

The plugin is an adapter only. It reports Minecraft-side facts to the FastAPI
Game Service and displays the response in Minecraft. Cultivation, combat,
loot, economy, player progression, and persistence rules belong in
`game-service/`.

## Current Slices

Connectivity command:

```bash
/immortal health
```

It reads `game-service.base-url` from `config.yml`, calls `GET /health`
asynchronously, and sends the result back to the command sender on the Paper
main thread.

Default config:

```yaml
game-service:
  base-url: "http://127.0.0.1:8000"
```

Player login sync:

- listens for Paper `PlayerJoinEvent`
- calls `POST /api/v1/players/login` asynchronously
- caches the returned account/current-life snapshot in memory
- sends player-facing success/failure feedback on the Paper main thread

Spirit-root command:

```bash
/immortal spirit-root
```

This command uses the cached Game Service `account_id`, calls
`POST /api/v1/players/{account_id}/current-life/spirit-root`, and displays the
returned spirit-root payload. The Java plugin does not roll spirit roots or
persist player progression state.

## MythicMobs cultivation rewards

The plugin compiles against the official free-distribution MythicMobs `5.12.1`
API and listens to typed `MythicMobDeathEvent` events. A reward event is
captured only when ImmortalMC already recorded a lethal player-owned combat
source; MythicMobs `getKiller()` is not used as a fallback.

Operator flow:

1. Define the mob with a stable top-level key in native MythicMobs YAML, for
   example `AzureWolf`.
2. Add the exact same `internal_name` to
   `game-service/src/immortal_mmo/combat/mythicmob_rewards.json` with a Game
   Service-owned reward profile and telemetry mode.
3. Restart Game Service after catalog changes and restart/reload Paper content.
4. Kill the mob with a tracked player source. Unknown IDs are acknowledged as
   `not_rewardable`; no default reward exists.

Every death fact is committed first to
`plugins/ImmortalMC/combat-outbox.sqlite3` using SQLite WAL and
`synchronous=FULL`. A separate load-aware worker sends bounded HTTP batches;
SQLite is not a cultivation database and acknowledged rows are deleted.

Useful outbox inspection:

```bash
sqlite3 plugins/ImmortalMC/combat-outbox.sqlite3 \
  "select delivery_status, count(*) from kill_outbox group by delivery_status;"
```

Accepted Game Service rewards spawn owner-tagged zero-XP orbs at the recorded
death position. Their count is a bounded mob-level visual only; it does not
encode or calculate the credited cultivation amount. Duplicate and terminal
no-reward results never present again.

## Cultivation HUD and controls

The plugin packages BetterHud resources for a two-bar bottom display:

- main colored bar and Chinese realm name: realized current-realm progress
- thin gray bar: unrefined reserve

Install BetterHud on the Paper server and require its generated resource pack
for the intended layout. BetterHud is a soft dependency: if it is missing or
reload fails, ImmortalMC logs a warning and keeps authoritative gameplay
running. HUD snapshots are scoped to the current life so a late response from
an old life cannot overwrite a reincarnated player.

Cultivation requests remain asynchronous and carry only account/life IDs,
selected technique IDs, semantic area IDs, pill counts, and idempotency keys.
Paper never calculates area speed/yield, retained cultivation, breakthrough
chance, or failure loss.

Player commands:

```text
/immortal seclusion
/immortal breakthrough <pill-count>
```

These commands use the public `immortalmc.cultivation` permission. Existing
operator commands retain `immortalmc.command`; administrators can grant test
pills with `/immortal cultivation grant-item <player> foundation_pill <count>`.
Configured `cultivation.areas[].area-id` values must match Game Service area
catalog IDs. The default local cuboid uses `neutral_training_ground`.

The seclusion GUI loads authoritative learned techniques asynchronously and
shows their group, major realm, attribute codes, layer, investment progress,
and active/full state. If a timed settlement remains `active` because capacity
or reserve is still available, Paper keeps the session open and schedules the
next authoritative settlement instead of reporting false completion.

## Development Flow

1. Write or update automated tests for the adapter behavior.
2. Implement the Java adapter code.
3. Run checks:

   ```bash
   ./gradlew --no-daemon --max-workers=1 test
   ./gradlew --no-daemon --max-workers=1 build
   ```

   The first `./gradlew` run downloads Gradle. If WSL networking times out
   while downloading, install/use a local Gradle `9.6.1` and run the same
   tasks with `gradle --no-daemon --max-workers=1 test build`.

4. Start the FastAPI Game Service.
5. Put `build/libs/immortal-main-plugin-0.1.0-SNAPSHOT.jar` in a Paper
   `1.21.11` server's `plugins/` directory.
6. Start the Paper server and run `/immortal health` as an operator.

Server verification comes after automated checks. For most feature slices,
the expected loop is: implement a small task, run tests/build, then verify the
visible Minecraft behavior in the server.

## Low-Memory Notes

Gradle is configured in `gradle.properties` with `org.gradle.daemon=false`,
`org.gradle.workers.max=1`, and a small JVM heap. Avoid starting a full Paper
server during routine unit-test work; run the server only when verifying a
Minecraft-facing behavior.
