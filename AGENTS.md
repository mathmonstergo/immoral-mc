<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->

## Public Wiki Documentation Contract

`docs/wiki/` is the authoritative public usage manual. Any change to a
player-, server-owner-, content-author-, operator-, or integrator-visible
feature must update the relevant Wiki page in the same change. This includes
commands, permissions, configuration, dependencies, API contracts, gameplay
rules, content schemas, installation, upgrades, and troubleshooting.

New feature modules require a discoverable page linked from
`docs/wiki/index.md`. Internal `.trellis/spec/` files, task PRDs, tests, and
dated documents under `docs/superpowers/` do not replace the public Wiki.

Public Wiki prose must be written in Simplified Chinese. Keep commands,
permissions, configuration keys, API paths, identifiers, and code examples in
their exact technical form instead of translating them.

Before completing work, run:

```bash
python3 scripts/check-wiki-links.py
```

Report either `Docs impact: required - <updated pages>` or a concrete reason
for `Docs impact: none`.
