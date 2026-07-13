# Citizens quest provider authoring commands

## Goal

Let server administrators bind an existing Game Service quest-provider template
to a Citizens NPC entirely through in-game commands. Normal authoring must never
require copying Bukkit entity UUIDs or Citizens persistent UUIDs into YAML by
hand.

## What I already know

* The quest system already models stable provider templates such as `old-man`.
* Runtime quest state remains authoritative in Game Service.
* Citizens owns NPC creation, identity, location, and lifecycle.
* ImmortalMC already routes Citizens clicks using the NPC's persistent UUID.
* The existing `npc-dialogue set <dialogue-id>` command can bind a looked-at
  Citizens NPC and automatically stores `target-provider: citizens` plus the
  persistent Citizens NPC UUID.
* Citizens itself uses `/npc select <id|name>` for selection-scoped commands,
  while `/template apply <template>` applies named templates to the selected
  NPC.
* Citizens exposes the selection through the public API
  `CitizensAPI.getDefaultNPCSelector().getSelected(CommandSender)`, so
  ImmortalMC can reuse the native selection without internal API access.
* Quest-provider bindings currently have to be written manually in the local
  ImmortalMC `config.yml`; this is unsuitable for normal content authoring.
* The user expects a template-oriented workflow similar to mature plugins:
  create/select an NPC, then attach an existing provider template by command.

## Assumptions

* The command should bind a provider definition that already exists in Game
  Service; it should not create quest definitions in Minecraft.
* The MVP should reuse the existing entity-interaction registry and Citizens
  persistent UUID metadata rather than introduce a second binding store.
* PostgreSQL persistence remains the next separate task after this authoring
  gap is fixed.

## Open Questions

* None.

## Requirements

* Provide an in-game command to bind a stable `quest-provider-id` to a Citizens
  NPC without manual UUID handling.
* Resolve the target exclusively from the invoking player's Citizens selection:
  `/npc select <id|name>` followed by
  `/immortal quest bind <provider-id>`.
* Reject the command when no Citizens NPC is selected; do not silently fall
  back to a looked-at Bukkit entity.
* Persist the Citizens NPC persistent UUID automatically.
* Keep provider definitions and quest state authoritative in Game Service.
* Provide corresponding inspection, listing, removal, and reload operations.
* Reject missing provider templates and non-Citizens targets visibly.
* Add a read-only Game Service quest-provider catalog endpoint. Game Service is
  the only source of provider templates; Paper must not mirror provider IDs in
  configuration.
* Cache the last confirmed provider catalog in the Adapter for command
  validation, template listing, and tab completion.
* Fail closed when the provider catalog is unavailable: do not create an
  unvalidated binding and do not erase previously confirmed bindings/catalog.
* Enforce at most one `quest-provider` binding per Citizens NPC. Rebinding the
  selected NPC replaces its previous provider binding without deleting or
  modifying the Citizens NPC.
* Allow one provider template to be reused by multiple physical Citizens NPCs;
  the template is content, while each binding retains its own persistent NPC
  UUID.

## Acceptance Criteria

* [x] An operator can bind provider `old-man` to a Citizens NPC using only an
      in-game command and a human-readable provider ID.
* [x] The selected Citizens NPC's name, numeric ID, and provider ID are included
      in the success confirmation so stale selections are visible.
* [x] The resulting binding survives Citizens respawn and Paper restart.
* [x] Clicking the bound NPC routes into the existing quest flow.
* [x] No UUID needs to be copied or typed by the administrator.
* [x] Removing the binding does not delete the Citizens NPC.
* [x] Missing provider IDs are rejected before any binding is written.
* [x] Provider IDs and display names can be listed from the Game Service catalog.
* [x] Provider ID tab completion uses the last confirmed catalog.
* [x] Game Service outage during bind leaves existing bindings unchanged.

## Definition of Done

* Backend tests cover the provider catalog response and definition revision.
* Java tests cover command parsing, target resolution, persistence, validation,
  removal, and restart-safe Citizens identity.
* Python lint/tests and Java tests/build pass.
* Gradle tests and build pass.
* The command is manually verified on the local Paper server.
* Relevant command and Citizens integration specs are updated if the contract
  changes.

## Out of Scope (explicit)

* Creating or editing quest definitions from Minecraft chat.
* PostgreSQL persistence for player or quest state.
* A graphical quest editor or inventory GUI.
* Replacing Citizens NPC administration commands.
* Look-at targeting or automatic fallback when no Citizens NPC is selected.
* Implementing the future Citizens-to-MythicMob encounter transition.

## Technical Notes

* Expected command family: `/immortal quest ...`.
* Likely reuse points: `NpcDialogueAdminRunner`, `ImmortalCommandHandler`,
  `ImmortalCommandService`, `CitizensNpcResolver`, `EntityInteractionRegistry`,
  and `QuestProviderInteractionAction`.
* Verified Citizens API contract:
  `NPCSelector#getSelected(CommandSender)`, `select(...)`, and `deselect(...)`.
* Proposed catalog contract:
  `GET /api/v1/quest-providers` returns `contract_version`, definition
  `revision`, and provider entries containing `provider_id`, `display_name`,
  ordered main quest IDs, and ordered side quest IDs.
* Proposed command family:
  * `/immortal quest templates`
  * `/immortal quest bind <provider-id>`
  * `/immortal quest info`
  * `/immortal quest list`
  * `/immortal quest unbind`
  * `/immortal quest reload`

## Research References

* [`research/citizens-authoring-command-ux.md`](research/citizens-authoring-command-ux.md)
  — compares Citizens selection/templates with the existing ImmortalMC look-at
  authoring flow and recommends explicit target semantics.
* [`research/dialogue-to-mythic-encounter.md`](research/dialogue-to-mythic-encounter.md)
  — evaluates signal-driven disguised Mythic actors versus swapping a Citizens
  NPC for a MythicMob after dialogue; retained for the future combat slice.

## Feasible Approaches

### Approach A: look-at target only

`/immortal quest-provider bind <provider-id>` binds the Citizens NPC in the
crosshair. This is the smallest MVP and matches existing dialogue authoring.

### Approach B: Citizens selection only

Administrators run `/npc select <id|name>` first; the ImmortalMC bind command
uses that selection. This matches Citizens templates but carries stale-selection
risk.

### Approach C: explicit support for both

The normal command targets the looked-at NPC; an explicit `--selected` form
targets the Citizens selection. This avoids ambiguous fallback behavior while
supporting both workflows.

## Decision (ADR-lite)

**Context**: Quest providers need a normal in-game authoring workflow without
manual UUID handling. Citizens already owns NPC selection and exposes the
selection through a public API.

**Decision**: Use the Citizens-selected NPC exclusively. Administrators select
with `/npc select <id|name>`, then run
`/immortal quest bind <provider-id>`. ImmortalMC stores the persistent
Citizens UUID automatically and reports the selected NPC identity in the
confirmation.

**Consequences**: The workflow matches Citizens templates and avoids duplicate
targeting concepts. Administrators must keep the selected NPC visible in command
feedback to avoid stale-selection mistakes. Look-at fallback is intentionally
out of scope.

### Provider catalog authority

**Context**: The Adapter must validate human-readable provider IDs and offer tab
completion, but duplicating the provider list in Paper config would create a
second content source.

**Decision**: Add a read-only Game Service provider catalog endpoint. The
Adapter caches only the last confirmed catalog and uses it for `templates`,
`bind`, and tab completion. Binding fails closed when no confirmed catalog is
available or the ID is unknown.

**Consequences**: Provider definitions remain authoritative in one place. The
authoring command now spans Game Service and Paper, and must handle asynchronous
catalog refresh without touching Bukkit/Citizens APIs off the main thread.

## Technical Approach

Game Service exposes a typed, read-only provider catalog projection from the
existing `QuestDefinitionCatalog`. The endpoint returns stable provider IDs,
display names, ordered quest IDs, and the same definition revision already used
by interaction snapshots.

Paper adds provider catalog DTOs/client decoding plus a small last-confirmed
cache. Startup/reload asynchronously refreshes the catalog. Commands and tab
completion read only the cache; a failed refresh records a retryable error while
preserving the previous confirmed catalog.

A new `QuestProviderAdminRunner` obtains the selected NPC through a thin
Citizens selection port backed by
`CitizensAPI.getDefaultNPCSelector().getSelected(sender)`. It writes a normal
`quest-provider` `EntityInteractionDefinition` with:

```yaml
target-provider: citizens
citizens-npc-uuid: <resolved automatically>
quest-provider-id: <validated provider id>
```

The stored Bukkit binding is only a current presentation fallback; routing,
removal, and restart safety use the persistent Citizens UUID. Rebinding removes
the previous quest-provider binding for that NPC before writing the replacement.
Unbinding removes only ImmortalMC metadata/config and never deletes/despawns the
Citizens NPC.

All Citizens, Bukkit, config, and message operations stay on the Paper main
thread. HTTP/catalog refresh stays asynchronous. Confirmations include selected
NPC ID/name and provider ID/display name.

## Implementation Plan

1. Add provider catalog schemas/API/tests in Game Service.
2. Add Adapter catalog DTO/client/cache/tests and refresh lifecycle.
3. Add Citizens selection port and `quest-provider` command parser/messages/
   runner/tab completion.
4. Wire plugin lifecycle, persistence, failure handling, and regression tests.
5. Run backend and Java checks, deploy the rebuilt JAR, and manually verify
   select/bind/info/unbind/restart behavior.

## Future Follow-up

### Generic non-quest NPC proximity profiles

NPCs with fixed proximity chat but no quests must not be represented as empty
quest providers. Introduce a future Adapter-local `npc-profile` presentation
template containing speaker identity, fixed proximity text, cooldown, and
optional ordinary dialogue. A Citizens NPC may compose a local `npc-profile`
binding with a Game Service `quest-provider` binding; a non-quest NPC binds only
the profile. Generalize the current quest proximity scanner into a shared NPC
proximity coordinator so static profiles and cached authoritative quest barks
reuse spatial indexing/cooldown/cleanup without forcing static presentation
through quest HTTP APIs. When both exist, an authoritative state-specific quest
bark takes priority and the static profile is only a configured fallback.

This profile system is recorded for a separate task and is not part of the
current quest authoring command implementation.

### Citizens-to-MythicMob encounter reveal

The user wants some dialogue actors to reveal a monster form and start combat.
This is recorded as a future independent combat task. The selected design is a
Citizens-to-MythicMob swap: after authoritative dialogue/eligibility completes,
Game Service authorizes an encounter, Adapter captures the Citizens persistent
identity and location, hides/despawns (never deletes) the NPC, plays
transformation particles/sound, and spawns the configured MythicMob at the same
location. Death, timeout, spawn failure, plugin disable, or reconciliation must
restore the Citizens NPC according to policy. A later encounter template will
hold the dialogue ID, Mythic internal mob ID, VFX, and restore policy.
