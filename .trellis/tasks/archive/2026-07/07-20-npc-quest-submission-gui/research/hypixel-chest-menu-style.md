# Hypixel-Inspired Chest Menu Style

## Useful conventions

Public Hypixel-style chest menus consistently use a read-only inventory,
strongly differentiated action/status colors, concise bold headings, short
click prompts, deliberate blank spacing, and a fixed bottom action area. Glass
panes are commonly used to make the grid read as a designed interface rather
than as a storage container.

## ImmortalMC adaptation

ImmortalMC should borrow the visual hierarchy without copying server-specific
wording or decorative clutter:

* Use one restrained color vocabulary for available, active, ready, completed,
  disabled, and error states.
* Disable Minecraft's default italic styling on GUI names and Lore.
* Keep list entries scannable: styled quest name plus `点击查看！` only for
  viewable quests; locked quests use red `暂未解锁` and remain inert.
* Move description, objectives, rewards, and state into the detail page.
* Use unnamed `GRAY_STAINED_GLASS_PANE` items for every unused/inert slot and
  for whole-row separators that act like visual line breaks.
* Reserve the last row for navigation and actions; do not mix quest content
  into it.
* Keep completed quests gray and sorted at the bottom. Keep locked quests
  visible so progression is discoverable without exposing their details.
* Cancel every top-inventory click/drag and route behavior exclusively through
  holder-owned slot metadata, never through visible item text.

## Deliberate non-goals

Do not reproduce dense Hover summaries, animated decorative items, excessive
color variation, or multiple pane colors. The visual system should remain
clean, stable, and easy to parse in Chinese.
