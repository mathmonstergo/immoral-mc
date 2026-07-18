# Wiki Maintenance Guide

Use this checklist for every implementation or review that can change how a
player, server owner, content author, operator, or integrator uses ImmortalMC.

## Before Development

- [ ] Identify the affected `docs/wiki/` page before editing behavior.
- [ ] Write public explanatory prose in Simplified Chinese; preserve commands,
      permissions, configuration keys, API paths, identifiers, and code
      examples in their exact technical form.
- [ ] Check the authoritative command/config/API/catalog source instead of
      relying on an older README or dated design plan.
- [ ] Decide whether the change affects install, upgrade, reload/restart, or
      troubleshooting steps.
- [ ] For a new feature, plan one discoverable Wiki page with status,
      dependencies, usage, configuration, permissions, verification, and
      limitations.

## Before Completion

- [ ] Update public Wiki pages in the same change as public behavior.
- [ ] Link new pages directly from `docs/wiki/index.md`.
- [ ] Keep current limitations explicit; do not document planned behavior as
      shipped.
- [ ] Run `python3 scripts/check-wiki-links.py`; it rejects headings without
      Chinese text, pages missing from the Wiki index, and broken local links.
- [ ] State `Docs impact: required - <pages>` or give a concrete reason for
      `Docs impact: none`.

Internal `.trellis/spec/` contracts, task PRDs, tests, and
`docs/superpowers/` history do not satisfy the public documentation requirement.
