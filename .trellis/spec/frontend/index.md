# Frontend Development Guidelines

> Initial frontend conventions for the future admin content panel.

## Scope

The current project does not need a player-facing website. Frontend work applies to the future `admin-panel/`, which should edit Game Service data through FastAPI endpoints when content volume justifies a UI.

This repository currently has no frontend implementation. These rules define initial conventions for the first admin-panel scaffold. Update them with real file references once code exists.

## Pre-Development Checklist

Before editing frontend code, read:

1. [Directory Structure](./directory-structure.md)
2. [Component Guidelines](./component-guidelines.md) for UI work
3. [Hook Guidelines](./hook-guidelines.md) for reusable logic or data fetching
4. [State Management](./state-management.md) for local/server/global state decisions
5. [Type Safety](./type-safety.md) for TypeScript and runtime validation
6. [Quality Guidelines](./quality-guidelines.md) before implementation and review
7. Shared guides in `.trellis/spec/guides/`, especially cross-layer thinking when UI edits Game Service data

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Admin panel feature layout | Initial |
| [Component Guidelines](./component-guidelines.md) | Operational UI components and props | Initial |
| [Hook Guidelines](./hook-guidelines.md) | Data-fetching and reusable hooks | Initial |
| [State Management](./state-management.md) | Local, server, URL, and global state rules | Initial |
| [Quality Guidelines](./quality-guidelines.md) | Testing, accessibility, and review checks | Initial |
| [Type Safety](./type-safety.md) | TypeScript and API schema handling | Initial |

## Product Direction

The admin panel is not a marketing site. It is an operational tool for editing and validating structured game content such as items, mobs, quests, zones, and techniques.

Priorities:

* correctness over decoration
* dense but readable data views
* explicit validation before saving
* predictable navigation for repeated editing
* direct use of Game Service APIs so the editor and game read/write the same data
