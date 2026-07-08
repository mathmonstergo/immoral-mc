# Type Safety

> TypeScript and runtime validation conventions for the future admin panel.

## Current Status

No frontend code exists yet. Initial convention: TypeScript is required for `admin-panel/`. Runtime validation should be generated from or aligned with Game Service schemas whenever practical.

## API Types

Prefer generated or shared API types from the FastAPI OpenAPI schema once the Game Service exists. Do not manually redefine large response shapes in multiple frontend files.

Expected flow:

```text
Game Service Pydantic schema -> OpenAPI -> generated admin-panel API types
```

If generation is not available yet, define temporary types in the relevant feature folder and mark them as temporary in the code comment.

## Type Organization

* API-generated types: `src/api/generated/`
* API client schemas/adapters: `src/api/schemas/`
* Feature-specific view types: `src/features/<feature>/types.ts`
* Shared UI-only types: colocate with the component or place under `src/components/`

## Validation

Game Service performs authoritative validation. The frontend performs user-friendly preflight validation:

* required fields
* enum selections
* numeric ranges
* malformed JSON-like content
* obvious cross-field conflicts that are already part of the API contract

Initial convention: use Zod or generated validators if the scaffold chooses a compatible generation path.

## Forbidden Patterns

* `any` for API responses, content definitions, or form payloads.
* Type assertions to silence real uncertainty, e.g. `value as ItemTemplate` without validation.
* Duplicating backend enum strings in multiple files.
* Treating all API errors as `unknown` strings after they cross the API client.

## Common Patterns

Use discriminated unions for editor modes:

```ts
type EditorMode =
  | { kind: "create" }
  | { kind: "edit"; templateId: string };
```

Use narrow types for risk tiers and gameplay enums:

```ts
type ZoneRiskTier = "green" | "yellow" | "red";
```

Keep these aligned with Game Service schemas as soon as schemas exist.
