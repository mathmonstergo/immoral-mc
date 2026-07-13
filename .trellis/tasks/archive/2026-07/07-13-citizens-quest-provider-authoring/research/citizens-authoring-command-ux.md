# Citizens quest-provider authoring command UX

## Comparable patterns

### Citizens selected-NPC commands

Citizens build 4211 exposes:

```text
/npc select|sel [id|name] (--range range) (--registry [name])
```

Most Citizens commands then operate on the sender's selected NPC. This is
useful when the target is not directly in the crosshair and is familiar to
experienced Citizens administrators. A stale selection is also easy to forget,
so commands should make the selected identity visible in their confirmation.

Citizens exposes this through its public API:

```java
CitizensAPI.getDefaultNPCSelector().getSelected(commandSender)
```

The returned `NPC` supplies the persistent UUID, current entity, name, numeric
ID, and spawned state needed for validation and confirmation messages.

### Citizens templates

Citizens build 4211 exposes:

```text
/template apply <namespace:template-name>
/template generate <namespace:name>
/template list
```

Applying a named template to a selected NPC is the closest match to the user's
expected workflow. The important separation is that a human-readable template
ID is supplied while the plugin resolves the selected NPC identity internally.

### Existing ImmortalMC dialogue authoring

ImmortalMC already exposes:

```text
/immortal npc-dialogue set <dialogue-id>
```

It ray-traces the entity the player is looking at, resolves whether it is a
Citizens NPC, stores the Citizens persistent UUID automatically, replaces an
older binding for the same Citizens NPC, and never requires UUID input. This is
the cheapest proven implementation pattern in the current repository.

## Constraints from this project

* `quest-provider-id` names a Game Service provider definition such as
  `old-man`; it is not an NPC identity.
* Citizens persistent UUID is the restart-safe NPC identity.
* Bukkit entity UUID is only the current spawned entity identity and may change.
* Binding state belongs to the Adapter entity-interaction registry; quest
  definitions and player progress remain in Game Service.
* Removing a binding must not remove a Citizens-owned NPC.
* The current Game Service has no provider-catalog administration endpoint, so
  validating provider existence may require a small read-only catalog contract
  or a bounded inspect-style validation call.

## Feasible approaches

### A. Look-at target only

```text
/immortal quest-provider bind <provider-id>
```

The command targets the Citizens NPC in the player's crosshair, matching the
existing ImmortalMC dialogue command.

Pros: smallest implementation, direct visual feedback, no stale selection.
Cons: target must be spawned, visible, and within the ray-trace distance.

### B. Citizens selected NPC only

```text
/npc select <id|name>
/immortal quest-provider bind <provider-id>
```

The command reads the player's Citizens selection, matching Citizens templates.

Pros: native Citizens administrator workflow and works without aiming.
Cons: hidden stale selection can bind the wrong NPC unless confirmations are
very explicit; requires a new selection resolver boundary.

### C. Explicit support for both

```text
/immortal quest-provider bind <provider-id>
/immortal quest-provider bind <provider-id> --selected
```

Default targets the looked-at NPC; `--selected` explicitly targets the Citizens
selection.

Pros: supports both novice visual authoring and Citizens-native administration
without ambiguous fallback behavior.
Cons: slightly larger command/parser/test surface.

## Recommendation

Use approach C if selected-NPC administration is expected soon; otherwise ship
approach A as the MVP and reserve `--selected`. Never silently prefer a stale
Citizens selection over the NPC currently being looked at.

## Local evidence

* `Citizens-2.0.43-b4211.jar` command annotations for `NPCCommands#select`
* `Citizens-2.0.43-b4211.jar` command annotations for
  `TemplateCommands#apply`
* `ImmortalBukkitCommandExecutor#sourceFor`
* `NpcDialogueAdminRunner#setLookedAtEntityAsDialogue`
