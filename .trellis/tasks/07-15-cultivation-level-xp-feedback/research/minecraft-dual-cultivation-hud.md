# Minecraft dual cultivation HUD research

## Question

Can a Paper server replace the vanilla numeric XP level with a Chinese realm
name and add a thinner gray reserve bar directly below the XP bar?

## Findings

### Vanilla protocol and Paper API

The clientbound experience packet contains exactly three values:

* one floating-point `experienceBar` progress value;
* one integer `level`;
* one integer `totalExperience`.

Paper exposes the same shape through `Player.sendExperienceChange(float, int)`
and the normal integer XP/level setters. There is no text field for the level
label and no second XP-bar channel. A pure Paper plugin can therefore control
one vanilla bar and one numeric label, but cannot implement the requested
Chinese label plus a second precisely positioned bar.

### Feasible approaches

#### BetterHud plus an automatically delivered resource pack (recommended)

BetterHud describes itself as a server-side HUD implementation. It supports
auto-generating a resource pack, images, text, animation, Bukkit/Paper 1.21+
and a Bukkit API. It has no required Bukkit-side dependency beyond its own
plugin installation.

Use a custom bottom HUD that visually replaces the vanilla XP presentation:

* main colored bar: realized cultivation progress within the current realm;
* centered Chinese realm name: replaces the visible numeric level;
* thin gray lower bar: unrefined cultivation reserve;
* values supplied by the ImmortalMC adapter from authoritative Game Service
  state.

Players do not install a mod, but must accept the server resource pack. The
pack should be marked required if consistent presentation is mandatory.

#### Project-owned custom resource-pack renderer

Build the font/image/shader HUD and packet/action-bar positioning in this
project. This avoids a runtime BetterHud dependency but creates substantial
version-specific UI, font-spacing, screen-scaling and pack-distribution work.

#### No resource pack

Keep one vanilla XP bar and show the Chinese realm and unrefined reserve via
ActionBar, BossBar or scoreboard. This does not meet the requested layout and
is only a fallback.

## Recommendation

Use BetterHud with a required, automatically delivered server resource pack.
Treat the entire two-bar display as a projection: it must never become the
authoritative cultivation store. Suppress or visually replace the vanilla XP
level presentation so unrelated vanilla XP cannot misrepresent realm state.

## Sources inspected

* Local Paper API 1.21.11: `org.bukkit.entity.Player` experience methods.
* PrismarineJS protocol schema for the clientbound set-experience packet.
* BetterHud upstream README: server-side HUD, generated resource packs,
  image/text/animation support, Bukkit 1.21+ and Bukkit API support.
