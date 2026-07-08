# Error Handling

> How backend failures are represented, propagated, logged, and returned.

## Principles

* Domain services raise domain errors; API handlers translate them into HTTP responses.
* Validation failures should be explicit and typed. Bad input must not silently become default gameplay state.
* Adapter-facing errors need stable error codes so the Paper plugin can decide whether to retry, show a message, or fail closed.
* Never expose stack traces, SQL details, secrets, or internal configuration in API responses.

## Error Types

Define shared domain error types under `game-service/src/immortal_mmo/core/errors.py`.

Initial shape:

```python
class DomainError(Exception):
    code: str
    message: str
    retryable: bool = False

class NotFoundError(DomainError): ...
class ConflictError(DomainError): ...
class RuleViolationError(DomainError): ...
class ExternalDependencyError(DomainError): ...
```

Use domain-specific codes:

* `player.life_not_found`
* `cultivation.invalid_stage_transition`
* `combat.target_not_attackable`
* `item.not_droppable`
* `zone.unknown_zone`

## API Error Responses

Adapter-facing APIs should return a consistent payload:

```json
{
  "error": {
    "code": "combat.target_not_attackable",
    "message": "Target cannot be attacked in this state.",
    "retryable": false,
    "request_id": "..."
  }
}
```

HTTP status mapping:

* `400`: malformed or invalid request content
* `401`/`403`: authentication or permission failure when introduced
* `404`: entity not found
* `409`: valid request conflicts with current state
* `422`: schema validation failure
* `500`: unexpected server bug
* `503`: downstream dependency unavailable, retry may be possible

## Handling Patterns

* Route handlers should not contain broad `try/except Exception` blocks. Use centralized exception handlers registered with FastAPI.
* Services may catch lower-level exceptions only when they can add domain context or perform rollback/compensation.
* Repositories should let database exceptions propagate to service-level translation unless a known constraint violation maps cleanly to a domain error.
* For gameplay decisions, prefer "fail closed" over applying an uncertain result. Example: if combat calculation cannot load authoritative stats, reject the action instead of using plugin-provided damage.

## Adapter Behavior Expectations

The Adapter should treat Game Service as authoritative:

* If an action request fails with a rule violation, show feedback or cancel the presentation.
* If Game Service is unavailable, do not invent combat, cultivation, reincarnation, or loot results locally.
* For retryable failures, retry only idempotent requests or requests with an idempotency key.

## Common Mistakes To Avoid

* Raising `HTTPException` deep inside domain services.
* Returning `None` for missing domain objects and letting callers guess what happened.
* Logging an error but still returning a successful gameplay result.
* Reusing one generic `bad_request` code for every rule failure.

## Implemented Domain Error Pattern

Domain services raise subclasses of `DomainError` from `game-service/src/immortal_mmo/core/errors.py`.
FastAPI registers `domain_error_handler` in `game-service/src/immortal_mmo/main.py`.

Current implemented player not-found response:

```json
{
  "error": {
    "code": "player.account_not_found",
    "message": "Player account was not found.",
    "retryable": false
  }
}
```

Do not raise `HTTPException` from `player/service.py`. Raise a domain error and let the app-level handler serialize it.
