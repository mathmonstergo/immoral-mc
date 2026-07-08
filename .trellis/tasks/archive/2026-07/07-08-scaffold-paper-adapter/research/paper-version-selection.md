# Paper Version Selection

## Sources Checked

- Paper API: `https://fill.papermc.io/v3/projects/paper`
- Paper builds: `https://fill.papermc.io/v3/projects/paper/versions/1.21.11/builds`
- Paper builds: `https://fill.papermc.io/v3/projects/paper/versions/1.21.10/builds`
- Paper builds: `https://fill.papermc.io/v3/projects/paper/versions/1.21.8/builds`

## Findings

- Paper publishes `1.21.11` under the `1.21` line.
- `1.21.11` has `STABLE` builds. The latest checked build is `paper-1.21.11-132.jar`, published 2026-05-11.
- `1.21.10` and `1.21.8` also have `STABLE` builds, but they are older patch versions in the same `1.21` line.
- Mojang's current Java release line is `26.x`; the version manifest reports latest release `26.2`.
- Paper `26.1.2` has `STABLE` builds. The latest checked build is `paper-26.1.2-74.jar`, published 2026-07-06.
- Paper `26.2` exists but its checked builds are `ALPHA`, so it is not a good default for a first server development baseline.
- Minecraft Java `26.1` includes visual and technical changes relevant to client presentation: rewritten lightmap behavior, data-driven environment visual attributes, Java 25 requirement, changed world storage, and changed chunk geometry rendering internals.
- Minecraft Java `26.2` adds experimental Vulkan rendering support and a `Graphics API` video setting. Its release notes say Vulkan is experimental, may be less performant or stable, and currently defaults to OpenGL.
- These visual/rendering changes mostly benefit the client presentation layer and future resource-pack/datapack/world-atmosphere work. They do not improve the current Game Service, account/life/spirit-root logic, or the first Paper adapter health-check slice.
- Moving to `26.x` early increases compatibility risk for Paper plugin APIs, Java runtime requirements, world storage migration, and third-party plugins such as WorldGuard, MythicMobs, MMOItems, or MMO-like tooling that may lag behind the newest Minecraft line.

## Recommendation

Use Paper `1.21.11` for the adapter plugin target, pinned explicitly in Gradle and `plugin.yml`. This gives the newest stable `1.21` API without moving onto the newer `26.x` line.

Revisit Paper `26.1.2` after the first adapter slice is working if the project decides to prioritize newest-client visuals over ecosystem stability. Do not use Paper `26.2` until stable Paper builds exist.
