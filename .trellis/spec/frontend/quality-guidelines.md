# Frontend Quality Guidelines

> Quality standards for the future admin panel.

## Project-Specific Quality Bar

The admin panel edits game data that the Game Service will use in production. A polished UI is useful, but correctness, validation, and traceable data flow are more important.

## Forbidden Patterns

* Building a player-facing landing page when the task is an admin/content tool.
* Creating a separate frontend-only data model that diverges from Game Service.
* Saving invalid content definitions and relying on later manual cleanup.
* Using `any` for API data.
* Hiding failed saves behind generic success UI.
* Introducing a UI component library or state framework without recording the decision in the task/spec.

## Required Patterns

* TypeScript for all frontend code.
* API schemas/types aligned with Game Service.
* Explicit loading, empty, error, dirty, saving, and saved states for editor flows.
* Accessible form controls and keyboard-friendly dialogs/menus.
* Tests for validation-heavy forms and critical save flows.
* Consistent operational UI patterns: lists, filters, detail editors, validation panels.

## Testing Requirements

When `admin-panel/` exists, add:

* unit tests for schema adapters and validation helpers
* component tests for forms with validation and save states
* integration tests for list/edit/save flows with mocked API responses
* end-to-end tests only for critical admin workflows once the UI stabilizes

## Review Checklist

Before marking frontend work complete, verify:

* Does the UI call Game Service for authoritative reads/writes?
* Are API payloads typed and validated?
* Are errors shown at the right level, not only as generic toasts?
* Can a user recover from failed saves without losing edits?
* Are loading/empty/error states implemented?
* Does keyboard navigation work for primary workflows?
* Does text fit in compact UI surfaces on desktop and mobile widths?
* Were new frontend stack decisions captured in this spec?

## Initial Verification Commands

No frontend project exists yet. The first admin-panel scaffold task must add concrete commands here, such as:

```bash
cd admin-panel
npm run typecheck
npm run lint
npm run test
```

Until those tools exist, verification for spec-only changes is documentation review plus consistency checks.
