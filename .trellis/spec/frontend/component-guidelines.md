# Component Guidelines

> Component conventions for the future admin panel.

## UI Character

The admin panel should feel like a quiet operational tool:

* compact information density
* restrained visual styling
* predictable layout and navigation
* tables, filters, forms, tabs, and dialogs where appropriate
* no landing-page hero sections or decorative marketing composition

Use cards only for repeated entities, modals, or genuinely framed tools. Do not nest cards inside cards.

## Component Structure

Component files should be small and explicit:

```tsx
type ItemStatusBadgeProps = {
  status: ItemStatus;
};

export function ItemStatusBadge({ status }: ItemStatusBadgeProps) {
  return <Badge tone={statusTone[status]}>{statusLabel[status]}</Badge>;
}
```

Rules:

* Define props with `type`, not inline object annotations.
* Keep data fetching in route/page hooks, not in low-level visual components.
* Keep domain decisions out of visual-only components.
* Split components when a file mixes loading, mutation, form validation, and rendering in a way that is hard to review.

## Props Conventions

* Prefer explicit prop names over generic names like `data`.
* Use discriminated unions for mode-specific props.
* Pass IDs and domain objects intentionally. Do not pass entire API responses through many layers if only two fields are needed.
* Callback props should be named by event, e.g. `onSave`, `onCancel`, `onTemplateSelect`.

## Styling Patterns

No styling library exists yet. First admin-panel scaffold must document the chosen approach here.

Initial UI rules regardless of library:

* use stable dimensions for tables, toolbars, icon buttons, forms, and editor panels
* keep text within its container on mobile and desktop
* avoid one-note palettes; admin UI should prioritize legibility
* use icons for common tool actions when the chosen icon library provides them
* avoid in-app explanatory text about how the UI works unless the text is part of validation or domain content

## Accessibility

* Use real buttons, inputs, labels, and semantic table/list structures.
* Every form input needs a visible label or accessible name.
* Validation messages must be associated with the relevant field.
* Keyboard navigation must work for save/cancel, dialogs, tabs, menus, and table row actions.
* Do not use color alone to indicate risk tier, status, or validation outcome.

## Common Mistakes To Avoid

* Building a marketing-style dashboard instead of a content operations tool.
* Hiding validation errors behind generic toast messages.
* Fetching inside deeply nested components, making data flow hard to trace.
* Letting admin UI maintain a separate data model from Game Service.
