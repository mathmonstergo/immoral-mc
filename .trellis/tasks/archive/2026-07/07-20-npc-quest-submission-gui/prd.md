# NPC Quest Submission GUI

## Goal

Replace chat- or double-right-click-based quest turn-in confirmation with an
ImmortalMC-owned NPC quest GUI. The tracked quest scoreboard continues to show
live objective progress, while the GUI provides quest browsing/details and an
explicit confirm-submit action. Item objectives are fulfilled directly from
the player's authoritative inventory without deposit slots or temporary escrow.

## Proximity Speech Compatibility And Extension

The original behavior in which an NPC speaks when a player enters its range is
part of the shipped interaction contract and must remain available alongside
the GUI. Right-clicking a bound quest NPC opens the quest GUI; proximity speech
is a separate presentation path and must not require a second right-click,
offer session, or head-label confirmation.

Only providers that opt in need to speak. Their speech is selected by the Game
Service from ordered, typed rules against authoritative player facts. The first
release supports quest-state conditions and the current-life cultivation realm
level (inclusive minimum/maximum bounds). Multiple conditions on one rule are
ANDed; multiple rules are evaluated by descending priority and stable
declaration order. If no rule matches, the provider returns no bark. Paper
receives only the resolved `key`, `speaker`, `text`, and `cooldown_seconds` and
continues to own range scanning, cache, cooldown, and display behavior.

The condition model is intentionally a typed union so an authoritative
achievement module can add an `AchievementCondition` later without moving
business logic into Paper. Achievement conditions are not enabled until that
module exposes authoritative facts and a monotonic revision. Any fact that can
change a bark must advance the existing interaction-state revision vector so a
new rule result cannot be hidden by an older cached response.

## What I Already Know

* The existing Game Service owns quest state, objective readiness, physical
  item validation, atomic item consumption, completion, and rewards.
* Citizens owns NPC lifecycle and identity; ImmortalMC binds Citizens NPCs to
  authoritative Game Service quest-provider templates.
* Tracked quest progress belongs on the scoreboard. Each material objective is
  rendered on its own row as `<material name> <current>/<required>` without the
  prefix `上交`.
* Right-clicking a bound NPC should open a custom ImmortalMC quest GUI backed
  by a standard six-row chest inventory.
* Both the quest list and quest detail view use the chest GUI. Slots `0..44`
  are the content area and the bottom row, slots `45..53`, is reserved for
  interaction buttons.
* The GUI is for browsing, details, and confirmation only. Players never place
  items into it. Every click/drag into the top inventory is cancelled.
* An item-delivery detail view renders a read-only preview of the exact required
  items and quantities that would be consumed from the current inventory. It
  is not a deposit or escrow view.
* When the player confirms turn-in, Paper scans exact physical item-instance
  IDs and Game Service revalidates and atomically consumes only the required
  quantity. Excess items remain; any shortage causes no consumption.
* If one NPC has multiple quests, the player selects the quest before opening
  its detail/confirmation view.
* Quest-list entries deliberately avoid detail previews. Each entry shows only
  the quest name and the single Lore line `点击查看！`; left-click opens the
  complete detail page. The list page has no right-click shortcut for accept
  or turn-in.
* An unaccepted/available quest is represented by `BOOK`. An accepted/active
  quest is represented by `WRITTEN_BOOK`. State is additionally communicated
  through consistent title/Lore color and emphasis, not by changing business
  behavior based on the display item.
* Material progress uses one terse format everywhere: `<material name>
  <inventory quantity> / <required quantity>`. For example, `玄铁 20 / 15`
  means the inventory currently contains 20 and the objective requires 15.
  Do not add labels such as `背包数量`, `提交消耗`, `提交后剩余`, or `上交`.
* `GRAY_STAINED_GLASS_PANE` is the one shared visual separator and inert filler:
  it forms divider rows/line breaks, fills intentionally unused slots, and
  marks areas that cannot be clicked.

## Assumptions (Temporary)

* The GUI uses one fixed six-row server-created Bukkit inventory shape with a
  custom holder so it can be identified safely and cannot be confused with a
  normal chest. List/detail pagination and bottom-row actions share one
  controller instead of separate GUI mechanisms.
* Existing quest APIs and schemas should be reused unless repository inspection
  finds a missing authoritative projection needed by the GUI.
* The current tracked-quest scoreboard remains the only continuous progress
  display; NPC interaction is not required to view progress.

## Open Questions

* None. The MVP interaction and presentation decisions are confirmed.

## Requirements (Evolving)

* Right-clicking a bound quest-provider NPC opens a six-row ImmortalMC quest GUI.
* Quest list and quest detail pages use slots `0..44` for content and reserve
  slots `45..53` for back/previous/next/refresh/confirm/close actions.
* GUI text uses Adventure components with an explicit restrained style system:
  important titles/actions may be bold; available, active, ready, completed,
  disabled, and error states use consistent colors; default item-text italics
  are disabled. Slot routing never trusts material, color, name, or Lore.
* Every intentionally empty or non-interactive slot is filled with an unnamed
  `GRAY_STAINED_GLASS_PANE`. Whole rows of the same pane are used as visual
  separators/line breaks between detail-page sections. Pane clicks do nothing.
* Quest list entries and detail state come from authoritative Game Service data.
* Quest-list icons contain exactly the styled quest name plus one Lore line,
  `点击查看！`, for quests whose detail page can be opened. Description,
  objectives, rewards, and current state are not exposed in list-item Hover
  and are rendered only on the detail page.
* Unavailable/locked quests remain visible as `BOOK` entries with their quest
  name, but replace the click prompt with red `暂未解锁`. They are inert and do
  not open a detail page.
* The list order is ready to submit, active, available, unavailable/locked, then
  completed. Completed quests are gray and always placed at the bottom.
* The complete detail page contains the quest description, one entry per
  objective, reward preview, current state, and the accept/submit action.
* Item objective progress is derived from the player's current inventory and is
  shown as one independent scoreboard/GUI row per material.
* Scoreboard rows and detail objective text use the same uncapped
  inventory/current format: `<title> <current> / <required>`.
* The detail page provides a confirm-submit button only when the quest is ready.
* The same detail-page action slot performs `确认接取` for an available quest
  and `确认提交` for an active ready quest. An active incomplete quest renders a
  disabled action item instead of sending a mutation request.
* Item objective icons preview the exact quantities to be consumed from the
  player's current inventory; they cannot accept cursor or shift-clicked items.
  Their Lore stays terse and shows only `<material> <current> / <required>`;
  readiness is communicated by color/state rather than explanatory sentences.
* Confirming submits the exact current inventory item-instance IDs through the
  existing idempotent turn-in transaction.
* GUI close/back actions never mutate quest or item state.
* Stale account, life, NPC binding, quest revision, or asynchronous responses
  must be dropped or revalidated before rendering/submitting.
* Replace the current count-derived objective revision with a true monotonic
  per-life inventory/objective-input revision. Inventory decrease and same-count
  item replacement must publish newer projections instead of being discarded
  by Paper as stale.
* Preserve the existing outside-to-inside NPC proximity bark path independently
  of the quest GUI. Provider definitions may omit bark rules (silent provider)
  or declare ordered typed rules for important quest/NPC moments.
* Evaluate proximity rules only in Game Service using authoritative quest state
  and current-life realm level. Paper must never infer quest, level, or future
  achievement conditions from local state.

## Acceptance Criteria (Evolving)

* [x] Right-clicking a bound Citizens NPC opens the correct quest-provider GUI.
* [x] Quest list and detail views use the same six-row chest layout, with no
      content item placed in the bottom interaction row.
* [x] Every unused/non-clickable slot and each full-row visual divider uses an
      unnamed `GRAY_STAINED_GLASS_PANE`; clicking or dragging over it has no
      effect.
* [x] Available quests render as `BOOK`, accepted quests render as
      `WRITTEN_BOOK`, and state colors/bold text remain consistent across list,
      detail, and action buttons.
* [x] Each quest-list icon Hover contains only the task name and the exact Lore
      prompt `点击查看！` when it is viewable; no description, objective, reward,
      or state detail is duplicated there.
* [x] An unavailable quest remains visible as a `BOOK` with its quest name and
      red `暂未解锁` Lore, and clicking it cannot open details or mutate state.
* [x] Quest entries are ordered ready, active, available, unavailable, and
      completed; completed entries are gray and remain at the bottom.
* [x] Opening a quest shows a complete detail page containing description,
      independent objective rows, reward preview, current state, and the
      state-appropriate primary action.
* [x] Multiple material objectives render on separate lines without `上交`.
* [x] Scoreboard and detail views render material progress in the exact shared
      format `<material> <current> / <required>` without verbose quantity
      labels or clamping current inventory to the requirement.
* [x] The scoreboard continues to refresh independently of NPC interaction.
* [x] An incomplete quest cannot invoke turn-in from the GUI.
* [x] Available quests can be accepted from their detail page, and the same
      action position becomes submit/disabled according to authoritative state.
* [x] Confirming a ready quest consumes only required physical items and awards
      the quest exactly once.
* [x] Excess items remain, and shortage/stale inventory causes no partial debit.
* [x] Multiple available/active quests can be selected deterministically.
* [x] Player inventory clicks, shift-clicks, hotbar swaps, and drags cannot move
      items into or out of the read-only quest GUI.
* [x] Quit, life replacement, provider rebind, stale response, double-click, and
      GUI close do not duplicate or misroute a submission.
* [x] Material removal and same-count item replacement advance a monotonic
      objective-input revision, and the scoreboard/GUI accept the lower or
      changed progress as the newest state.
* [x] A provider with no matching proximity rule returns no bark without
      affecting GUI opening; a matching rule returns the configured text and
      stable rule key.
* [x] Proximity rules select the highest-priority matching rule in declaration
      order, support ANDed quest-state/realm-level conditions, and a realm
      change advances the interaction revision so the next bark is authoritative.
* [x] Existing Paper proximity behavior remains intact: outside-to-inside
      entry, cache TTL, cooldown, state-key changes, bounded scanning, and stale
      async completion guards continue to pass while right-click still opens
      the GUI.

## Definition of Done

* Python and Java unit/integration tests cover the authoritative turn-in and GUI
  interaction lifecycle.
* Ruff, Game Service tests, Java 25 Gradle test/build, Wiki checks, and diff
  checks pass.
* Public Wiki and backend quality/database contracts describe the shipped flow.
* Public Wiki documents optional proximity speech rules and the supported
  condition types, including the current limitation that achievement facts are
  not yet available.

## Out of Scope (Explicit)

* Item deposit slots, Merchant GUI recipes, and temporary Paper-side escrow.
* Rewriting regional warehouse interaction behavior.
* Implementing the system shop GUI in this task.
* Making Paper authoritative for quest readiness, item identity, or rewards.

## Technical Notes

* The implementation should extend the existing Citizens quest-provider
  binding, quest interaction-state projection, tracked-quest refresh, physical
  item reconciliation, and idempotent turn-in paths instead of creating a
  second quest engine.
* Research reference:
  `research/current-quest-gui-contract.md` records the existing Paper flow,
  reusable holder/controller pattern, backend transaction guarantees, and the
  required objective-revision repair.

## Decision (ADR-lite, Evolving)

**Context**: Accepting and submitting quests through separate chat/dialogue and
inventory mechanisms would duplicate navigation, stale-response handling, and
NPC identity checks.

**Decision**: Use one six-row chest GUI for provider quest lists and quest
details. The detail-page primary action changes between accept, disabled, and
submit according to authoritative quest state.

**Consequences**: One GUI lifecycle/controller owns navigation and mutation
coordination, while Game Service remains authoritative for every state change.
List ItemStack hover stays intentionally minimal. Viewable entries use
`点击查看！`; locked entries stay visible but use red `暂未解锁` and remain inert.
Left-click provides the full detail page only when the quest is viewable, and
all material progress surfaces share one concise quantity formatter. Gray
stained-glass panes provide the shared visual grammar for section breaks,
unused space, and inert regions. Completed quests are gray and sort last.
