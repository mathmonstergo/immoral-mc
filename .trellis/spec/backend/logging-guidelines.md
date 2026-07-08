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
