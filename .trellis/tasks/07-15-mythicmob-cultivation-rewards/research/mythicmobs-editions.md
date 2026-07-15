# MythicMobs Free vs Premium research

Research date: 2026-07-15

## Sources

* Official Premium Features wiki:
  <https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/Premium-Features>
* Official FAQ:
  <https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/FAQ>
* Official API page:
  <https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/API>
* Official Modrinth project:
  <https://modrinth.com/plugin/mythicmobs>
* Modrinth project API:
  <https://api.modrinth.com/v2/project/NLuc7Jjh>
* Modrinth 5.12.1 release API:
  <https://api.modrinth.com/v2/version/EyAzrRRF>
* Official Maven artifact metadata:
  <https://mvn.lumine.io/repository/maven-public/io/lumine/Mythic-Dist/maven-metadata.xml>

Local runtime artifact inspected:

```text
minecraft-nodes/main-server/plugins/MythicMobsPremium-5.13.0--SHOT.jar
plugin version: 5.13.0-SNAPSHOT-850a23db
```

## The current free build is not verified open source

The official MythicMobs GitLab project and wiki are publicly visible, but
anonymous repository-tree/source requests returned HTTP 403 and no current
license file could be read. The official Modrinth project reports:

```text
license: LicenseRef-All-Rights-Reserved
source_url: null
```

Therefore the current official free build should be described as
**free-to-download/free-of-charge**, not as verified open-source software. Old
source dumps, forks, API examples, public issues, or a public wiki do not grant
an open-source license to the current plugin. This is an engineering finding,
not legal advice; redistribution must follow MythicCraft's actual license.

## Official Premium differences

The official Premium Features and FAQ pages list these Premium benefits:

* earlier access to current releases and access to development builds;
* Premium Discord/support channels and ticket support;
* Premium-only mechanics such as raytracing and chain missile;
* custom damage types and damage modifiers;
* math and placeholders in mob attributes, most skills, item attributes, and
  drop-table amounts;
* skill parameters;
* inline target conditions;
* projectile on-hit conditions and bounce behavior;
* conditional AI goals/targeters;
* `origin=@targeter` support and additional evolving Premium features.

Premium+ additionally advertises priority support and a license usable on
multiple owned servers. Before copying a Premium jar to multiple production or
test servers, the owner should confirm the purchased license terms. Premium
artifacts must not be committed to this repository or redistributed through CI.

## Can the free build support ImmortalMC?

Yes for the foundational integration and a substantial amount of mob content.
The official free project describes custom mobs/bosses, attributes, skills,
equipment/drop tables, spawners, natural spawning, levels, threat tables, AI,
factions, and the developer API. Most importantly for this slice, free 5.12.1
contains the required `MythicMobDeathEvent` API.

The official Modrinth 5.12.1 free jar was downloaded and compared with the
official Maven `io.lumine:Mythic-Dist:5.12.1` artifact. They are byte-identical:

```text
SHA-256 3781927033898c75b0c4e21a8eee1756ca822d80160430c3da9de760c9137cd1
```

The locally installed Premium 5.13.0 snapshot and free 5.12.1 expose the same
methods needed by this integration:

```java
MythicMobDeathEvent#getEntity()
MythicMobDeathEvent#getMobType()
MythicMobDeathEvent#getMobLevel()
MythicMobDeathEvent#getKiller()
MythicMob#getInternalName()
```

Thus the kill-reward boundary does not require a Premium-only mechanic. Free
MythicMobs can run the core mob/death integration. Premium becomes valuable for
richer mob authoring, advanced projectile/AI/damage mechanics, faster releases,
and support—not for deciding authoritative cultivation rewards.

## Selected free-distribution baseline

The product decision is to target the official free-distribution MythicMobs
5.12.1 runtime and API for this slice. Premium-only runtime features are
deferred until a separately licensed Premium environment and a concrete product
requirement exist.

The currently installed Premium artifact identifies itself as:

```text
5.13.0-SNAPSHOT-850a23db
```

The official public Maven repository publishes
`io.lumine:Mythic-Dist:5.13.0-SNAPSHOT`. At research time its resolved artifact
was build `5.13.0-20260714.132533-87`, plugin commit `f04c25f5`. It is not
byte-identical to the locally installed Premium build, but both expose the same
death-event API required by this slice.

The Adapter should compile and test against the stable official
`io.lumine:Mythic-Dist:5.12.1` artifact, which is byte-identical to the official
free 5.12.1 Modrinth jar. Premium snapshot artifacts are intentionally excluded
from CI and release inputs. If a future licensed Premium feature is required,
it should be an additive, separately reviewed integration rather than changing
this baseline.

No Premium binary is committed or shaded into the Adapter. Premium-only content
features may be used by server configuration without making MythicMobs the
authority for cultivation balances or rewards.

## Earlier portable-policy alternative

* Compile the Adapter against the public stable
  `compileOnly("io.lumine:Mythic-Dist:5.12.1")` API.
* Keep the integration limited to the verified common event contract above.
* Run the production/test-server smoke against the official free 5.12.1 build
  selected for this slice. A separately licensed Premium server may be used
  for later manual experiments, but is not part of this release gate.
* Do not bundle or publish either the free runtime jar or Premium jar inside the
  ImmortalMC Adapter artifact.
* Use the stable free 5.12.1 release for the current development/test server.
* Keep all progression, reward values, idempotency, and balances in Game
  Service. Premium-only mechanics may enrich Minecraft presentation and combat
  behavior without becoming persistence authority.

This is the selected policy. Premium is a future optional extension, not a
dependency of the current reward pipeline.
