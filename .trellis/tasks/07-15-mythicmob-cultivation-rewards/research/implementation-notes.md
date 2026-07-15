# Implementation smoke notes

Date: 2026-07-15

## Runtime setup

- Supplied free-distribution `MythicMobs-5.12.1.jar` was installed locally as
  `plugins/MythicMobs.jar`; its verified SHA-256 is
  `3781927033898c75b0c4e21a8eee1756ca822d80160430c3da9de760c9137cd1`.
- The stale local Premium 5.13.0 jar and Paper remap cache entry were removed.
- Paper 1.21.11 started with Citizens 2.0.43, MythicMobs 5.12.1, and the
  freshly built ImmortalMC plugin. MythicMobs reported `5.12.1-46bae256` and
  loaded the native `AzureWolf`/`AzureDragon` definitions.
- ImmortalMC logged `mythicmobs_integration_enabled` and created the durable
  `plugins/ImmortalMC/combat-outbox.sqlite3` outbox. The first boot exposed a
  stale ignored runtime config missing the new strict combat settings; adding
  the current config contract fixed startup without adding a compatibility
  fallback.

## Game Service smoke

- A disposable PostgreSQL 17 instance was migrated to Alembic head
  `20260715_002` (host port `55432` was used because an unrelated local
  PostgreSQL process already owns `127.0.0.1:5432`).
- Player login created one account/life. An `AzureWolf` event at level `2.000`
  returned `accepted` with reward `12` and unrefined balance `12`.
- Replaying the identical event returned `duplicate` with the same stored
  result. PostgreSQL contained exactly one row each in
  `combat_kill_events`, `life_mob_kill_counters`,
  `cultivation_resource_entries`, and `life_cultivation_states`.
- An unknown mob returned explicit `not_rewardable`; an `AzureWolf` event with
  a mismatched source-life UUID returned `current_life_unavailable`. Neither
  outcome added a cultivation reward.
- The SQLite outbox was empty after the successful direct API smoke, which is
  consistent with the delivery worker acknowledging rows after Game Service
  success. An in-game player kill is still required for a complete end-to-end
  MythicMob attribution smoke because no Minecraft client/player was available
  in this session.

## Verification

- Python backend checks: Ruff, 170 tests, compileall, pip check, and Alembic
  head checks passed before this runtime smoke.
- Java adapter: `JAVA_HOME=/home/adam/.local/jdks/jdk-21 ./gradlew test build`
  passed and produced `immortal-main-plugin-0.1.0-SNAPSHOT.jar`.
