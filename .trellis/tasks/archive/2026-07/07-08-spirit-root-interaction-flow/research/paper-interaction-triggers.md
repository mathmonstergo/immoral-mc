# Paper Interaction Triggers For Spirit-Root Detection

## Sources Checked

* Paper docs: `https://docs.papermc.io/paper/dev/event-listeners`
* Paper `1.21.11` Javadocs:
  * `PlayerInteractEvent`
  * `PlayerInteractEntityEvent`
* Local adapter code under `minecraft-nodes/main-plugin/`

## Relevant Paper API Facts

* Paper listeners implement `org.bukkit.event.Listener` and are registered with
  `PluginManager#registerEvents(listener, plugin)`.
* `PlayerInteractEvent` is cancellable and exposes:
  * `getAction()`
  * `getClickedBlock()`
  * `getHand()`
* `PlayerInteractEvent` may fire once per hand. A listener should normally
  process only `EquipmentSlot.HAND` to avoid duplicate detections.
* `PlayerInteractEntityEvent` is cancellable and exposes:
  * `getRightClicked()`
  * `getHand()`
* Paper's listener docs warn that other plugins may cancel or modify events.
  MVP should use `ignoreCancelled = true` unless it needs to override vanilla
  behavior.

## Current Repo Constraints

* `SpiritRootCommandRunner` already contains the authoritative flow:
  cached session lookup -> Game Service detection call -> main-thread
  feedback/logging.
* Reusing a lower-level service behind both the temporary command and a new
  listener will avoid duplicate async/error/logging logic.
* `ImmortalMainPlugin` already wires listeners and command runners manually.
* The Adapter must not roll spirit-root values locally.
* Server-side operational logs should be emitted through `AdapterLogger`.

## Feasible MVP Approaches

### Approach A: Configured Detection Block (Recommended)

Player right-clicks a configured block location/material, e.g. an altar block
in the starter area.

Pros:
* Closest to "set a place for the player to interact with".
* Uses one native Paper event: `PlayerInteractEvent`.
* No extra plugin dependency.
* Easy to smoke test in the local Paper server by placing one block.
* Gives a stable world anchor for particles/sounds.

Cons:
* Needs config for world/location/material or a simple local-test default.
* The block must exist in the test world.

### Approach B: Detection Item

Player right-clicks with a special item, identified by material/display name or
future `PersistentDataContainer` metadata.

Pros:
* Portable and easy to test without a fixed world location.
* Fits future quest reward/tutorial flows.

Cons:
* Requires a way to grant the item.
* Less like a fixed cultivation altar.
* Custom item identity needs a small convention before it is robust.

### Approach C: NPC/Entity Interaction

Player right-clicks a named entity/NPC to start detection.

Pros:
* Strong RPG presentation and close to Wynncraft-style UX.
* Future dialogue/quest integration is natural.

Cons:
* Requires entity spawn/persistence/identity handling or an external NPC
  plugin later.
* More moving parts for the current adapter scaffold.
* Higher risk before the project has a world/NPC management convention.

## Recommendation

Start with Approach A: a configured detection block. Implement it as a
listener-driven vertical slice, while extracting the current command runner's
shared detection orchestration into a reusable service. Keep `/immortal
spirit-root` as a dev fallback until the interaction flow is stable.
