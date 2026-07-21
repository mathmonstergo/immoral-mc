# Proximity Speech Rules

## Existing boundary

The GUI replacement did not remove proximity speech. Paper still performs the
outside-to-inside scan through `QuestNpcCoordinator`, reads the short-lived
`QuestInteractionCache`, refreshes the authoritative interaction projection on
a miss, applies per-player/NPC/bark-key cooldown, and formats the resolved
speaker line. Right-click independently routes through
`QuestProviderInteractionAction` to `QuestProviderGuiOpener`.

The deleted `QuestOfferSession`, offer label, and second-right-click classes
belonged only to the old accept-confirmation interaction and must not be
restored.

## Chosen model

`QuestProviderDefinition` owns an optional ordered tuple of
`ProximityBarkRule`. Each rule has a stable provider-local ID, text, priority,
cooldown, and typed conditions. Initial condition types are:

* `QuestStateCondition`: one known quest and one or more projected states.
* `RealmLevelCondition`: inclusive current-life minimum/maximum level.

Conditions within one rule use AND. Rules use descending priority and stable
declaration order. An empty condition tuple is an explicit unconditional
fallback. No match means no bark. A rule may reference a known quest outside
the provider's own quest list so an important NPC can react to broader story
progress.

The Game Service resolves a single rule and keeps the wire shape unchanged:
`key`, `speaker`, `text`, `cooldown_seconds`. Paper never receives or evaluates
conditions. The stable key is `<provider-id>:<rule-id>`, so a newly selected
rule bypasses the previous rule's cooldown while repeated entry for the same
rule remains rate-limited.

## Revision requirement

Realm-only speech rules must load the authoritative cultivation state even
when no quest has a realm objective. Its monotonic revision remains part of
`QuestRevisionVector.objectives`, alongside the monotonic physical-inventory
revision. This lets Paper reject a late pre-level-change projection. The
authoritative new-life realm is level 0; no default level may be treated as a
player fact.

Quest-state rules reuse the same global projected quest-state calculation as
the GUI. Quest references are validated against the complete catalog at
startup. Missing rules and unmatched rules are intentionally silent.

## Deferred achievement condition

There is currently no authoritative achievement module, stored achievement
facts, or achievement revision. Adding a condition that Paper or quest code
guesses would violate server authority and make cache invalidation incorrect.
The typed condition union and centralized selector are the extension point;
an achievement condition should be added only with its authoritative facts and
monotonic revision in the same change.
