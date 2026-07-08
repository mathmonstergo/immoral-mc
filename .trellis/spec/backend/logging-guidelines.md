# Logging Guidelines

> Operational logging for Game Service and Adapter-facing flows.

## Current Status

No logging library is implemented yet. Initial convention: use Python's standard `logging` with structured `extra` fields or JSON formatting. Introduce a third-party structured logging library only with a task-level reason.

## Required Fields

Every request log should make these fields available where possible:

* `request_id`
* `account_id`
* `life_id`
* `player_uuid` or Minecraft identity when provided by the Adapter
* `module`
* `action`
* `outcome`
* `duration_ms`

Do not block logging if some identity fields are not available during early login or account creation.

## Log Levels

* `debug`: local development details, deterministic calculation inputs, cache behavior
* `info`: successful player lifecycle events and important gameplay state transitions
* `warning`: recoverable problems, rejected player actions, missing optional data, retryable dependency issues
* `error`: failed requests, database failures, unexpected exceptions, lost authoritative state transitions
* `critical`: data corruption risk, migration failure, service cannot safely continue

## What To Log

Log important domain transitions:

* account created or linked
* life created, reincarnated, or restored
* spirit root detected
* cultivation stage breakthrough attempt and outcome
* combat action accepted/rejected and final authoritative outcome
* item instance created, durability changed, migrated to loot pool, or transferred
* zone snapshot synchronization
* Adapter request failures and retryable downstream failures

For formula logs, log inputs and final result at `debug` only unless diagnosing production issues.

## What Not To Log

Never log:

* secrets, tokens, database URLs, API keys, or `.env` values
* raw request bodies that may contain sensitive data
* full inventory/provenance dumps at `info` level
* stack traces in normal domain rejections
* personally identifying chat content unless a moderation/audit feature explicitly requires it

## Example Pattern

Target pattern for initial implementation:

```python
logger.info(
    "spirit_root_detected",
    extra={
        "request_id": request_id,
        "account_id": str(account_id),
        "life_id": str(life_id),
        "module": "cultivation",
        "action": "detect_spirit_root",
        "outcome": result.spirit_root,
    },
)
```

## Common Mistakes To Avoid

* Logging only English prose messages without machine-readable context.
* Using `print()` in service code.
* Logging expected rule rejections as stack-trace errors.
* Omitting the account/life identity from player state transitions.
* Sending Adapter debug/status messages such as profile sync start/success to
  player chat instead of Paper logs.

## Scenario: Paper Adapter Operational Logging

### 1. Scope / Trigger

Trigger: Paper Adapter actions call Game Service and need to be observable
during Windows-client manual testing without exposing implementation status in
player chat.

### 2. Signatures

* Runtime logger source: `JavaPlugin#getLogger()`
* Adapter logging interface:
  `AdapterLogger.debug/info/warn/error(...)`
* Paper log file:
  `minecraft-nodes/main-server/logs/latest.log`

### 3. Contracts

Log level usage:

* `debug`: development-only start/rejection details, e.g. command started.
* `info`: successful operational transitions, e.g. `player_login_success`,
  `health_check_success`, `spirit_root_test_success`.
* `warn`: recoverable failures or missing player state, e.g.
  `player_login_failure`, `spirit_root_test_rejected`.
* `error`/`severe`: plugin bugs or unexpected exceptions that need developer
  action.

Player chat contract:

* Do not send profile sync/debug messages such as "profile loaded".
* Diagnostics commands may return concise command output to the sender.
* Gameplay flows may send intentional feedback such as a spirit-root result,
  but the detailed operational trace still goes to Paper logs.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Player joins and profile sync succeeds | `info` log includes player, UUID, account ID, life ID; no debug chat |
| Player joins and Game Service fails | `warn` log includes player, UUID, reason; no technical chat spam |
| `/immortal health` succeeds | Sender receives concise result; `info` log includes service/status/version |
| Temporary spirit-root test succeeds | Player receives result; `info` log includes account, life, quality, elements |
| Temporary spirit-root test lacks session | Player receives an actionable message; `warn` log records missing profile |

### 5. Good/Base/Bad Cases

* Good: logs use stable event names and key-value fields.
* Base: command output is concise and meant for the command sender.
* Bad: join lifecycle sends "Loading profile" or "profile loaded" to player
  chat.
* Bad: debugging requires screenshots/OCR of chat instead of Paper logs.

### 6. Tests Required

Java tests should assert:

* profile sync success/failure writes `info`/`warn` logs and sends no debug chat
* diagnostics command success/failure writes server logs
* temporary gameplay-test command writes server logs while preserving intended
  player-facing feedback

### 7. Wrong vs Correct

#### Wrong

```java
sendMessage.accept("ImmortalMC profile loaded.");
```

This exposes adapter lifecycle noise to players and gives developers no durable
server-side trace.

#### Correct

```java
logger.info("player_login_success player_name=Sensen minecraft_uuid=... account_id=...");
```

The operational event is visible in Paper logs while player chat stays reserved
for intentional gameplay UX.
