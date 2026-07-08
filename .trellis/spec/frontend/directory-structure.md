# Frontend Directory Structure

> Target organization for the future admin panel.

## Current Status

No frontend code exists yet. The architecture says `admin-panel/` should be created after item/mob/quest field structures stabilize and content volume makes manual maintenance risky.

## Target Layout

Initial convention: React + TypeScript + Vite for `admin-panel/`, unless a later ADR chooses a different stack.

```text
admin-panel/
├── package.json
├── src/
│   ├── app/
│   │   ├── App.tsx
│   │   ├── router.tsx
│   │   └── providers.tsx
│   ├── api/
│   │   ├── client.ts
│   │   ├── generated/
│   │   └── schemas/
│   ├── features/
│   │   ├── items/
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   ├── pages/
│   │   │   └── types.ts
│   │   ├── mobs/
│   │   ├── quests/
│   │   ├── zones/
│   │   └── techniques/
│   ├── components/
│   │   ├── ui/
│   │   └── layout/
│   ├── lib/
│   ├── styles/
│   └── test/
└── tests/
```

## Feature Organization

Use feature folders for domain-heavy screens:

* `items`: item templates, item instances, affixes, durability rules
* `mobs`: mob templates, tier, drop links
* `quests`: quest definitions, dialogue, rewards
* `zones`: risk tier snapshots and sync review
* `techniques`: technique definitions and mark values

Shared components belong in `components/` only when they are genuinely reusable across features. Avoid promoting one-off feature UI too early.

## Naming Conventions

* React components: `PascalCase.tsx`
* Hooks: `useThing.ts`
* Feature utilities: `camelCase.ts`
* Route pages: `ThingListPage.tsx`, `ThingEditPage.tsx`
* Domain types: colocate in feature `types.ts` unless generated from API schemas

## Routing

Admin routes should map to work areas rather than marketing pages:

```text
/items
/items/:templateId
/mobs
/quests
/zones
/techniques
```

Prefer list/detail/editor flows over wizard-only interfaces. Editors need clear validation and save states.

## Examples

This is a target pattern for the first admin-panel implementation, not existing code:

```tsx
export function ItemEditPage() {
  const { templateId } = useParams();
  const item = useItemTemplate(templateId);

  return <ItemTemplateForm item={item.data} />;
}
```

The page coordinates route state and loading state; the form owns editing and validation UI.
