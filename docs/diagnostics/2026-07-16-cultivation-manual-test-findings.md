# Cultivation Progression Manual Test Findings

Date: 2026-07-16  
Branch: `feat/cultivation-progression`  
Server: Paper `1.21.11-132`, Java 21  
Client: PCL, Fabric `1.21.11`, connecting through `localhost:25549`

## Summary

The end-to-end manual test confirmed that the core Game Service, Paper adapter,
PostgreSQL persistence, quest flow, spirit-root flow, combat reward delivery,
reserve cap, seclusion creation, and item adjustment paths are operational.

Two real defects were found:

1. The BetterHud resource pack was offered but never downloaded by the client,
   so BetterHud private-use glyphs rendered as square boxes.
2. Some MythicMobs spawned from eggs produced a mob level that caused an
   uncaught `IllegalArgumentException` in the Paper event listener.

There is also a manual-testability gap: an ordinary qi seclusion currently
waits the full ten-hour mastery duration, leaving the session active and
blocking breakthrough testing.

## Verified Working Flows

The following behavior was verified from Paper logs, Game Service access logs,
and PostgreSQL state:

- Paper, BetterHud, Citizens, MythicMobs, and ImmortalMC enabled successfully.
- Game Service health returned `200 OK`.
- Player login and reconnect reused the same account and current life.
- `/immortal health` succeeded.
- `/immortal spirit-root` created a variant wood root.
- Repeating spirit-root detection returned the existing result.
- The Citizens spirit-root detector interaction succeeded.
- The `first-steps` quest was accepted and turned in; PostgreSQL records it as
  `completed`.
- Explicitly spawned level-1 AzureWolf kills were delivered to Game Service.
- AzureDragon was resolved through the flat reward profile.
- The unrefined reserve cap worked: nine wolves raised the reserve to `90`, and
  AzureDragon credited only the remaining `10`, producing a final balance of
  `100`.
- The SQLite combat outbox was empty after delivery.
- `/immortal seclusion` created an authoritative ordinary session.
- `/immortal cultivation grant-item Telluria foundation_pill 1` succeeded and
  persisted a pill balance of `1`.
- Breakthrough attempts returned `409 Conflict` without partial writes while an
  ordinary seclusion was active.

Final relevant PostgreSQL state:

```text
player: Telluria
current_level: 1
unrefined_cultivation: 100
realized_cultivation: 0
active_session: ordinary / active
foundation_pill: 1
quest first-steps: completed
combat events: 10 rewarded
```

## P0: BetterHud Resource Pack Download Timeout

### Symptom

After joining, Minecraft displayed the server resource-pack prompt. The player
accepted it, but the HUD at the top of the screen consisted of square boxes
instead of the intended bars and realm text.

### Evidence

The client log records two failed attempts:

```text
[22:01:57] Existing file .../downloads/.../4e3af... not found or had mismatched hash
[22:02:18] Pack 1 failed to download
[22:02:18] Failed to download http://192.168.31.202:8163/4E3AF...zip
Caused by: java.net.ConnectException: Connection timed out: connect

[22:05:28] Existing file .../downloads/.../4e3af... not found or had mismatched hash
[22:05:49] Pack 1 failed to download
[22:05:49] Failed to download http://192.168.31.202:8163/4E3AF...zip
Caused by: java.net.ConnectException: Connection timed out: connect
```

Client log location:

```text
E:\mc\.minecraft\versions\1.21.11-Fabric_0.18.4\logs\latest.log
```

The temporary resource-pack HTTP server received no client `GET` request. Its
only request was the local diagnostic `HEAD` probe.

The generated `plugins/BetterHud/build.zip` is not missing the ImmortalMC
assets. It contains:

```text
assets/betterhud/font/hud_immortal_cultivation_image.json
assets/betterhud/font/hud_immortal_cultivation_text_1_2_1.json
assets/betterhud/textures/image_image_immortal_main-fill_*.png
assets/betterhud/textures/image_image_immortal_reserve-fill_*.png
pack.mcmeta
```

### Root Cause

The Minecraft client connected to Paper through `localhost:25549`, while
BetterHud advertised the resource pack through the WSL/LAN address
`192.168.31.202:8163`. Windows could not connect to that HTTP endpoint and
timed out.

BetterHud still sent its private-use font glyphs through the HUD. Without the
resource pack, Minecraft displayed those glyphs as square boxes.

This is a local WSL resource-pack delivery configuration problem, not evidence
that the generated HUD ZIP lacks ImmortalMC textures.

### Recommended Fix

For the computer-B local test environment:

1. Disable BetterHud self-hosting.
2. Serve `plugins/BetterHud/build.zip` from a separate HTTP server bound to
   `0.0.0.0` on an unused port such as `8164`.
3. Configure Paper to send a URL reachable in the same way as the server:

   ```text
   http://localhost:8164/build.zip
   ```

4. Set `resource-pack-sha1` to the current ZIP SHA-1.
5. Restart Paper.
6. Remove the failed cached server-pack download for this instance, reconnect,
   accept the pack, and confirm the HTTP server receives a real `GET`.
7. Confirm the client log includes the server pack in the resource-manager
   reload list.

The current client is heavily modded and has several enabled resource packs:
Fabric, Iris, Sodium, Voxy, EMF/ETF, and FreshAnimations. These did not cause
the observed failure because the server pack never downloaded. After delivery
is fixed, repeat one check using a clean 1.21.11 client if rendering remains
incorrect.

## P1: MythicMobs Mob Level Escapes Event Listener Validation

### Symptom

Four AzureWolf deaths produced a Paper event error and no combat reward event:

```text
Could not pass event MythicMobDeathEvent to ImmortalMC v0.1.0-SNAPSHOT
java.lang.IllegalArgumentException: mobLevel is outside supported bounds
```

Occurrences:

```text
22:04:20
22:05:09
22:05:20
22:05:20
```

These wolves came from eggs obtained with:

```text
/mm egg get AzureWolf 20
```

Later wolves created explicitly with:

```text
/mm mobs spawn AzureWolf:1 20
```

were processed successfully at level `1.000`.

### Code Path

The failure occurs while constructing:

```text
minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/mythicmobs/
MythicMobDeathSnapshot.java
```

`MythicMobDeathListener` converts the MythicMobs `double` with
`BigDecimal.valueOf(value)`. `MythicMobDeathSnapshot` then rejects values with
more than three decimal places. The snapshot is constructed before the
listener's existing `try/catch`, so the exception escapes to Paper's event
manager and produces a full stack trace.

### Impact

- The death is not written to the SQLite outbox.
- Game Service never receives the kill fact.
- The player receives no reward or presentation.
- One unexpected third-party value generates a noisy server-thread exception.

### Recommended Fix

1. Capture and log the raw MythicMobs level when normalization fails.
2. Normalize finite MythicMobs levels to the API contract's three-decimal
   representation at the adapter boundary.
3. Move snapshot construction inside the listener's guarded error path.
4. Fail closed with one structured warning/error instead of escaping the event.
5. Add tests for:
   - spawn-egg MythicMobs;
   - floating-point tails beyond three decimal places;
   - NaN/infinity;
   - negative and over-limit levels;
   - a valid explicitly spawned `1.000` mob.

## P1: Ten-Hour Seclusion Blocks Manual Breakthrough Testing

### Evidence

The seclusion started successfully at approximately `22:09` local time. The
database stored:

```text
session_kind: ordinary
status: active
source_level: 1
started_at: 2026-07-16 22:09 local
completes_at: 2026-07-17 08:09 local
cumulative_generated: 0
cumulative_reserve_consumed: 0
cumulative_retained: 0
```

Both breakthrough attempts correctly returned `409 Conflict`. The second
attempt happened after granting a foundation pill, but the ordinary cultivation
session was still active.

### Assessment

The ten-hour qi mastery baseline matches the current design. The transaction
and conflict behavior are correct. The gap is testability: the manual tester
cannot complete seclusion, observe settlement, progress through levels, or
reach breakthrough in a normal test session.

### Recommended Test Support

Provide one explicit local-development mechanism without changing production
rules, for example:

- a development-only accelerated area;
- an administrator command to advance the clock and settle a session;
- an administrator command to cancel an active development session;
- a documented breakthrough-ready database preset.

The mechanism must still call the authoritative Game Service settlement path;
Paper must not calculate cultivation locally.

## P2: AzureWolf Level-1 Reward Documentation Correction

The level curve uses level 1 as its baseline. Observed and tested values are:

```text
level 1.000 -> 10
level 2.000 -> 12
level 3.900 -> 14
```

The earlier manual instruction that level 1 should award `12` was incorrect.
No reward calculation defect was observed here.

Observed combat totals:

```text
9 x AzureWolf level 1: configured 10, credited 10 each
1 x AzureDragon level 1: configured 500, credited 10 due to reserve cap
final unrefined reserve: 100
```

## Expected or Non-Blocking Log Noise

The following should not be treated as cultivation defects:

- `combat_kill_attribution_missing` for a SkeletalKnight that suffocated in a
  wall: there was no player-owned lethal source, so no reward should be created.
- MythicMobs example-dialog warnings for missing
  `ExampleQuestAccepted`, `ExampleQuestDeclined`, and
  `ExampleCharacterConfirmed`: these are unused example-content warnings, but
  removing the sample definitions would make the test log cleaner.
- Offline-mode Mojang/Realms `401` errors in the client.
- Iris update-check timeouts.
- EMF/Voxy optional compatibility warnings from the modded client.
- Paper's warning that 1.21.11 is behind the newest Minecraft release; the
  project intentionally targets Paper 1.21.11.

## Suggested Fix Order for Computer A

1. Fix local resource-pack delivery and verify a client `GET` plus successful
   resource-manager reload.
2. Fix MythicMobs level normalization and event error containment; add
   regression tests.
3. Add a development-only seclusion settlement/acceleration workflow.
4. Clean unused MythicMobs example-dialog warnings.
5. Update manual test instructions to state the correct AzureWolf reward
   baseline.

## Retest Checklist

- [ ] Client downloads the BetterHud ZIP successfully.
- [ ] No square private-use glyphs appear.
- [ ] Both HUD bars and Chinese realm text render.
- [ ] Spawn-egg AzureWolf death creates no Paper stack trace.
- [ ] Explicit AzureWolf and AzureDragon rewards still reach Game Service.
- [ ] SQLite outbox drains to zero.
- [ ] Reserve cap remains correct.
- [ ] A development seclusion can settle during the test session.
- [ ] Breakthrough conflict remains stable while a session is open.
- [ ] Breakthrough can start from a documented ready state after the session is
      closed.
