# remove managed entity interaction entity

## Goal

Fix `/immortal spirit-root-detector remove` so removing a detector created by ImmortalMC also removes the corresponding in-world entity. Keep the generic entity interaction foundation safe for future NPC/dialogue workflows.

## What I already know

* User observed that `remove` does not delete the entity.
* Server logs confirm current behavior removes only the interaction binding:
  `spirit_root_detector_removed ... total_detectors=2`, then repeated remove on the same entity reports `target_not_bound`.
* Current `SpiritRootDetectorAdminRunner.removeLookedAtDetector` calls only `registry.removeInteraction(...)`; it has no Paper entity removal hook.
* Current config does not distinguish plugin-created entities from externally bound entities.
* Previous design said `set` should not delete arbitrary existing entities. That remains important for future NPC/dialogue authoring.

## Requirements

* Add a persisted flag that expresses the invariant: whether the interaction owns/manages the underlying entity.
* `/immortal spirit-root-detector create` stores `managed-entity: true`.
* `/immortal spirit-root-detector set` stores `managed-entity: false`.
* Legacy entries and entries missing the field default to `managed-entity: false`.
* `/immortal spirit-root-detector remove` removes the config binding in all successful cases.
* If the removed interaction has `managed-entity: true`, the Paper Adapter also removes the actual entity from the world.
* If the removed interaction has `managed-entity: false`, `remove` only unbinds it.
* Missing entity during managed removal is logged as a warning, not silently ignored.

## Acceptance Criteria

* [x] Unit test proves created/managed detector removal calls an entity remover.
* [x] Unit test proves set/external detector removal does not call entity remover.
* [x] Config mapper tests cover `managed-entity` read/write and default false.
* [x] Full main-plugin Gradle build passes.
* [x] Updated plugin jar is deployed and Paper starts.

## Definition of Done

* Tests added before implementation.
* Code keeps the entity interaction abstraction generic.
* No broad try/catch or silent fallback.
* Work committed, task archived, journal recorded.

## Out of Scope

* Cleaning up detector entities that were already removed from config before this fix.
* Deleting externally authored entities bound with `set`.
* Adding a general entity cleanup command.
