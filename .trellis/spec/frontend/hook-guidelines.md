# Hook Guidelines

> Reusable hook patterns for the future admin panel.

## Current Status

No frontend stack exists yet. Initial convention: use React hooks and a dedicated server-state library such as TanStack Query when the admin panel is scaffolded.

## Hook Categories

Use custom hooks for:

* server state access, e.g. `useItemTemplate`, `useUpdateItemTemplate`
* URL/query parameter parsing, e.g. `useItemFilters`
* local form helpers when they are reused across editors
* feature-level orchestration that would make pages too large

Do not create hooks just to wrap one `useState` call with no shared behavior.

## Data Fetching

Server data belongs in server-state hooks:

```ts
export function useItemTemplate(templateId: string | undefined) {
  return useQuery({
    queryKey: ["item-template", templateId],
    queryFn: () => api.items.getTemplate(templateId!),
    enabled: Boolean(templateId),
  });
}
```

Rules:

* Query keys must include every input that changes the result.
* Mutations must invalidate or update affected query caches.
* Hooks should expose domain names, not raw endpoint names where a domain concept is clearer.
* Do not duplicate Game Service validation logic in hooks. Hooks may run client-side preflight validation, but Game Service remains authoritative.

## Naming Conventions

* Hooks must start with `use`.
* Read hooks: `use<Item|Quest|Mob>...`
* Mutation hooks: `useCreate...`, `useUpdate...`, `useDelete...`
* URL hooks: `use...Params` or `use...Filters`

## Error Handling

Hooks should preserve structured API error data so components can show field-level or action-level messages. Avoid converting all errors into plain strings too early.

## Common Mistakes To Avoid

* Storing fetched server data in `useState` after loading it.
* Using a hook to hide cross-feature coupling.
* Letting hooks silently swallow failed saves.
* Running mutations from render paths instead of event handlers.
