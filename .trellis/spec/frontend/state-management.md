# State Management

> State ownership rules for the future admin panel.

## State Categories

Use the smallest state scope that matches the problem:

* Local state: component-only UI state such as open dialogs, focused rows, temporary field state.
* URL state: filters, search text, pagination, selected content IDs, and editor routes that should survive refresh/share.
* Server state: data loaded from Game Service APIs.
* Global client state: rare app-wide UI or session state.

## Server State

Initial convention: use TanStack Query or an equivalent server-state library once `admin-panel/` is scaffolded.

Rules:

* Game Service is the source of truth.
* Save actions must call Game Service APIs; do not persist admin edits only in browser storage.
* Cache invalidation must be explicit after mutations.
* Optimistic updates are allowed only when rollback is straightforward and the Game Service contract is stable.

## Local Form State

Forms may maintain draft state while editing. Draft state should be transformed into a typed API payload at submit time.

For content definitions, prefer explicit save/cancel over auto-save until validation, conflict handling, and revision behavior are designed.

## When To Use Global State

Use global state only for:

* authenticated admin identity/session metadata
* app-wide notifications
* persisted UI preferences such as table density
* feature flags or environment-level configuration

Do not put item templates, quest definitions, mob lists, or zone snapshots in global client state.

## Derived State

Compute derived values from source state during render or memoized selectors. Do not store both the source and derived value unless there is a measured performance reason.

## Common Mistakes To Avoid

* Mirroring server state into global stores.
* Keeping filters only in component state when they define the page view.
* Implementing client-side authority for rules that belong in Game Service.
* Auto-saving complex content before validation and conflict handling are defined.
