# MythicMobs 5.13.0 与 ImmortalMC 集成调研

> 调研日期：2026-07-13  
> 本地样本：`plugins-new-add/MythicMobsPremium-5.13.0--SHOT.jar`  
> JAR 内版本：`5.13.0-SNAPSHOT-850a23db`  
> 结论：采用 MythicMobs 作为怪物实体、AI、刷新和技能表现引擎；ImmortalMC Adapter 负责桥接；Game Service 继续独占战斗数值、进度与最终掉落裁决。

## 1. 版本、维护状态与许可

### 1.1 本地构建与 1.21.11

本地 JAR 的 `plugin.yml` 声明：

- 主类 `io.lumine.mythic.bukkit.MythicBukkit`
- 版本 `5.13.0-SNAPSHOT-850a23db`
- `folia-supported: true`
- `api-version: 1.13`（这是最低 Bukkit API 声明，不代表只支持 1.13）
- 软依赖包括 WorldGuard、PlaceholderAPI、LibsDisguises、Vault 等
- `loadbefore: [Quests]`

官方当前 changelog 的 5.12.0 明确写有 Minecraft `1.21.11` 支持；5.12.1 继续修复兼容与并发问题。5.13.0 是更新的开发快照，因此**具备 1.21.11 目标支持，但 dev build 仍需在项目实际 Paper 构建上做启动和回归验证，不能把版本号当作稳定性证明**。本地类文件 major version 为 65，即 Java 21，可与项目现有 Java 21 工具链加载。官方 changelog 中“26.1.x requires Java 25”不应误读为 1.21.11 也要求 Java 25。

来源：

- [官方 Changelogs](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/changelogs/Changelogs)
- [官方配置文档](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/Configuration)
- 本地 JAR：`plugin.yml`、`META-INF/MANIFEST.MF`、类文件版本

### 1.2 Premium 许可与分发边界

这是 Premium 构建。JAR 内虽然存在 `META-INF/LICENSE*`，但其中可能包含打包依赖的许可证，**不能据此推断 MythicMobs Premium 产品本身允许再分发**。在没有核对购买账户所接受的当前 MythicCraft 商业条款前，应执行保守规则：

- 不把 Premium JAR 提交到 Git、公开制品仓库、Docker 公共镜像或对外发布包。
- 只在获授权的服务器/开发环境中部署；CI 通过私有制品库或人工安装注入。
- ImmortalMC 代码只以 `compileOnly` 依赖官方 API，不 shade、不解包、不二次分发 MythicMobs 类。
- 项目仓库仅保存自有 Mythic Pack YAML；第三方商店购买的 pack 也须分别核对许可。
- 上线前由购买者在 MythicCraft 账户/资源页面确认服务器数量、开发者共享、备份和团队使用权。

官方入口：[MythicCraft](https://mythiccraft.io/)；API 依赖仓库见[官方 API 文档](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/API)。

## 2. 推荐职责边界

| 能力 | MythicMobs | ImmortalMC Adapter | Game Service |
|---|---|---|---|
| 怪物实体、外观、AI、寻路、仇恨 | 主责 | 识别与桥接 | 不直接操作 Bukkit 实体 |
| 刷新点、随机刷新、BossBar、粒子、声音 | 主责 | 触发/观测 | 可下发内容或状态指令 |
| 玩家属性、境界、灵根、功法、任务状态 | 不作为权威源 | 展示/转发 | 唯一权威 |
| 玩家对怪物最终伤害 | 只负责表现和应用批准结果 | 拦截、请求、应用 | 计算和裁决 |
| 怪物对玩家最终伤害 | 只负责攻击行为/技能表现 | 拦截、请求、应用 | 计算和裁决 |
| 掉落资格、掉落池、数量、归属 | 禁用默认裁决 | 收集死亡上下文、发放结果 | 计算、幂等入账 |
| 任务击杀计数 | 提供 mob 身份/死亡事件 | 上报事实 | 校验并推进任务 |

该边界与 `architecture-v2.md` 一致：MythicMobs 决定“怎么表现”，Game Service 决定“数字是多少”。不要在 Mythic YAML、Adapter Java 和 Game Service 三处同时维护一套伤害/掉落规则。

## 3. 身份模型：内部名、UUID 与 Bukkit Entity ID

### 3.1 三种标识不要混用

1. **Mythic mob internal name**：配置顶层 key，例如 `immortal_spirit_wolf_t1`。官方要求唯一且无空格。它是内容模板 ID，稳定、可版本控制，适合映射到 Game Service 的 `mob_template_id`。
2. **ActiveMob UUID**：本地 5.13 API 的 `ActiveMob#getUniqueId()`；通过 `ActiveMob#getEntity()` 可取得抽象实体，再取得 Bukkit entity。它表示某次具体出生的实体实例。
3. **Bukkit `Entity#getEntityId()`**：整数型运行时网络/进程 ID，只适合当前服务器进程的短暂查找，重启、卸载或实体重建后不可作为业务主键。

建议跨边界事件使用：

```json
{
  "event_id": "uuid",
  "mob_template_id": "immortal_spirit_wolf_t1",
  "mob_instance_uuid": "bukkit-entity-uuid",
  "world": "world",
  "spawn_epoch": 42,
  "player_uuid": "..."
}
```

`spawn_epoch` 或由 Adapter 生成的 encounter UUID 用于防止同一实体 UUID/重试上下文混淆；`event_id` 用于 Game Service 幂等处理。不要把 Bukkit numeric entity ID 写入 PostgreSQL 作为外键。

### 3.2 API 解析方式

官方示例与本地 JAR 均支持：

```java
MythicMob type = MythicBukkit.inst().getMobManager()
        .getMythicMob("immortal_spirit_wolf_t1")
        .orElseThrow();
ActiveMob active = type.spawn(BukkitAdapter.adapt(location), 1.0);
Entity entity = active.getEntity().getBukkitEntity();
String templateId = active.getMobType();
UUID instanceId = active.getUniqueId();
```

官方 API 页面还展示按 Bukkit entity UUID 获取 ActiveMob。5.13 本地公开接口 `MobManager` 本身较窄，而 `MythicBukkit.inst().getMobManager()` 的具体返回类型是 `MobExecutor`；实现时应尽量封装在单一 `MythicMobGateway` 内，避免业务代码依赖 core 实现类型。最稳妥的事件路径是直接使用事件携带的 `ActiveMob`。

来源：

- [官方 API](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/API)
- [官方 Mobs/Internal Name](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/Mobs/Mobs)
- [Mythic JavaDocs](https://www.mythiccraft.io/javadocs/mythic/)
- 本地 JAR：`MythicMob`、`ActiveMob`、`MobManager`、`MythicBukkit` 公共签名

## 4. 事件与 API 集成面

### 4.1 生成

- `MythicMobPreSpawnEvent`：可取消；提供 mob type、level、location、spawn reason。适合维护模式、区域限流或尚未开放内容的前置拒绝。
- `MythicMobSpawnEvent`：可取消；提供 `ActiveMob`、type、entity、living entity、level、spawn reason、spawner。适合登记 encounter、写 PDC/内存索引和观测。
- 主动生成：`getMythicMob(internalName)` 后 `spawn(...)`；必须在正确的 Bukkit/区域线程调用。

### 4.2 伤害与技能

- `MythicDamageEvent`：可取消并可 `setDamage`，只覆盖 Mythic damage mechanic 的伤害准备阶段。
- `MythicSkillEvent`：可取消，提供 `SkillMetadata` 与 `Skill`，适合审计或阻止某些技能执行；不应每次技能都同步 HTTP。
- `MythicTriggerEvent`：本地 JAR 实际实现 `Cancellable`，官方表格未标记可取消，文档与二进制存在差异；以目标版本 JAR 回归测试为准。
- `SkillEventBus#processTrigger(...)`：可从 ImmortalMC 自定义任务/境界事件触发 Mythic 表现技能。
- `ActiveMob#signalMob(...)` / signal trigger：适合 Game Service 裁决完成后让怪物播放受击、阶段切换或任务演出。

仅监听 `MythicDamageEvent` 不足以实现全局权威伤害，因为普通近战、箭、药水、其他插件和 Bukkit 原生伤害可能不经过该事件。必须把 `EntityDamageByEntityEvent` 等 Bukkit 伤害事件作为统一入口，并用 Mythic 事件补充技能元数据/防止双处理。

推荐伤害状态机：

1. Bukkit/Mythic 事件在服务器线程提取只读快照：攻击者 UUID、目标 UUID、mob internal name、技能 ID、世界/距离、当前 tick。
2. 取消原始伤害，生成幂等 `combat_action_id`，异步请求 Game Service；绝不在 tick/region 线程阻塞等待 HTTP。
3. Game Service 仅接收“谁对谁做了什么”，自行读取属性并返回批准伤害、效果和版本号，不信任插件上报的最终 damage。
4. 回到目标实体所属线程，重新确认实体仍存活且 encounter/action 未过期，再应用一次批准伤害。
5. 应用时设置短生命周期 re-entry token，避免 Adapter 应用伤害再次进入同一路由。

异步响应会改变即时打击手感。MVP 可使用短超时和每玩家有界队列；失败策略应是 **fail closed（不造成权威伤害）并记录/提示**，不能回退到 Mythic/YAML 数值，否则会产生可利用的不一致。

### 4.3 死亡与掉落

- `MythicMobDeathEvent`：提供 ActiveMob、killer、mob type、level 以及可替换的 Bukkit `List<ItemStack>`。
- `MythicMobLootDropEvent`：提供 Mythic `LootBag`、physical/intangible drops、exp、money；exp/money 可修改。
- Bukkit `EntityDeathEvent` 仍用于清除 vanilla drops/exp，并覆盖未走 Mythic droptable 的路径。

为了保持 Game Service 权威：

- Mythic mob 配置默认 `PreventOtherDrops: true`，不配置业务掉落表，或使用一个只负责表现的空 droptable。
- 在 `MythicMobDeathEvent` 清空 drops；在 `MythicMobLootDropEvent` 清除物理/无形掉落并把 exp/money 设为 0；在 `EntityDeathEvent` 再做兜底清空。
- 只向 Game Service 上报 `mob_template_id`、instance UUID、killer/participants、伤害贡献、位置和 encounter ID。
- Game Service 以 `death_event_id` 幂等计算并持久化奖励。Adapter 收到结果后再发物品/资源或展示掉落表现。
- 不用 Mythic `CommandDrop` 调用业务命令，不让 Mythic Vault money/exp 成为修仙经济权威。

死亡事件本身不可取消，因此“先让 Mythic 掉、再异步问服务”会产生复制窗口。应先同步清空所有本地掉落，再异步发放已经持久化的服务端结果。玩家离线时奖励进入 Game Service 待领取队列，而不是依赖地面 Item 实体。

来源：[官方 API 事件表](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/API)、[官方 Drops](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/drops/Drops)、本地 5.13 事件类公共签名。

## 5. 配置与 Packs

使用一个项目自有 pack，而不是直接修改 MythicMobs 根目录生成文件：

```text
plugins/MythicMobs/Packs/ImmortalMC/
  packinfo.yml
  files/
    mobs/spirit-wolf.mob.yml
    skills/spirit-wolf.skill.yml
    drops/empty.droptable.yml
```

5.12+ 官方 pack 支持 `files/` 目录按后缀解析：`.mob.yml`、`.skill.yml`、`.droptable.yml`、`.randomspawn.yml`、`.spawner.yml` 等。也支持传统 `Packs/<Pack>/Mobs|Skills|Items/...` 结构。建议选 `files/` 新结构并把整个 `ImmortalMC` pack 作为版本化内容部署单元。

命名规则：

- internal name 使用稳定命名空间，例如 `immortal_<region>_<species>_<tier>`，发布后不随显示名变化。
- Game Service `mob_template_id` 与 internal name 一一对应；schema 校验确保不重复。
- YAML 中 `Health`/`Damage` 只设为承载实体所需的技术值，不作为业务平衡来源；文档注明“非权威”。
- `PreventOtherDrops: true`；禁用/避免 Mythic money、exp、业务 item drops。
- 开发 reload 后监听 `MythicReloadCompleteEvent`，重新校验所有 Game Service mob ID 在 Mythic 中可解析；缺失则阻止相应刷新，不静默生成 vanilla mob。

来源：

- [官方 Packs](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/Packs)
- [官方 Files and Directories](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/Guides/(Step-2)-Files-And-Directories)

## 6. Citizens 协作

MythicMobs 本地配置和官方文档明确支持 Citizens 目标过滤：`TargetCitizensNPCs` 默认 `false`；目标器也有 `npc`/`targetnpcs` 过滤选项。这正符合项目分工：

- Citizens 只负责持久 NPC、皮肤、名称、站位、寻路和交互实体。
- ImmortalMC 自研任务/会话监听 Citizens NPC 的点击并推进 Game Service 任务。
- MythicMobs 负责敌对怪、Boss、技能演出，不把 Citizens NPC 转成任务权威源。
- 保持 `TargetCitizensNPCs: false`，防止怪物 AoE/自动目标误伤任务 NPC；只有明确的剧情战斗才在单个技能 targeter 中局部放开。
- 不建议为基础集成引入 Denizen/Depenizen；官方兼容页说明 Depenizen 能桥接 Citizens/Denizen 与 MythicMobs，但项目已经决定自研任务系统，引入脚本层会形成第二套业务编排。

来源：

- [官方 Configuration](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/Configuration)
- [官方 Targeters](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/Skills/Targeters)
- [官方 Compatible Plugins](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/Compatible-Plugins)

## 7. 线程与性能

### 7.1 线程规则

- Mythic/Bukkit 实体、世界、inventory API 默认视为线程受限；不要从 `HttpClient` completion thread 直接调用。
- Paper 主线程上用 scheduler 回切；若未来启用 Folia，必须改为 entity/region scheduler，而不是全局 `BukkitScheduler#runTask`。
- 本地 JAR 声明 `folia-supported: true`，官方 changelog 也持续修复 Folia race；这不等于调用方可以忽略 region ownership。
- 不在 spawn、damage、death、skill 事件内同步调用 FastAPI。事件内只复制 primitive/immutable snapshot，随后异步 I/O。
- reload 时 API 对象可能失效；缓存 internal name 字符串，不长期缓存 `MythicMob`/`Skill` 实例，收到 reload-complete 后重建索引。

### 7.2 性能预算

- 不在每 tick、`~onTimer` 或每粒子 mechanic 上请求 Game Service。
- 服务调用按“玩家动作/伤害裁决/死亡结算”粒度；纯粒子、声音、AI 和仇恨留在 Mythic 本地。
- 限制每玩家、每 mob 并发请求；对同 tick 多段命中批量化或使用服务端定义的 skill execution token。
- HTTP 设置连接复用、严格超时、队列上限和指标：延迟 p50/p95/p99、超时率、取消伤害数、重复 event ID、待发奖励数。
- 怪物数量、spawner interval、timer skills、threat table、bossbar 更新都应压测。官方 5.12.1 已优化 particles、bossbar、spawner clock、drop hot paths，但内容配置仍可制造过载。

来源：[官方 Changelogs](https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/changelogs/Changelogs)、本地 `plugin.yml`。

## 8. 依赖方式、软依赖与降级

推荐在 Adapter 中增加一个很薄的端口：

```java
interface MythicMobGateway {
    Optional<MythicMobIdentity> identify(Entity entity);
    boolean hasTemplate(String internalName);
    void signal(UUID entityUuid, String signal);
}
```

实现类可以直接依赖 Mythic API；任务、战斗和会话用例只依赖该端口。Gradle 使用官方仓库和 `compileOnly("io.lumine:Mythic-Dist:<已验证版本>")`。官方 API 页面当前示例仍是 5.12.1；在 5.13 正式 artifact 可用前，不能凭空声明 `5.13.0-SNAPSHOT` 坐标稳定存在。可在本地/私有仓库提供与服务器 JAR 完全匹配的 compile-only API，但不得公开分发 Premium binary。

`plugin.yml` 选择取决于运行目标：

- 生产服的怪物垂直切片离不开 MythicMobs：使用 `depend: [MythicMobs]`，缺失即明确拒绝启动，最易诊断。
- 若同一 Adapter 还必须支持无 Mythic 的基础开发服：使用 `softdepend: [MythicMobs]`，启动时检测 `PluginManager#getPlugin("MythicMobs")`，只注册 Mythic listener/gateway；其余登录、灵根和 NPC 对话继续可用。

建议当前阶段采用 `softdepend`，但对“刷怪/战斗”功能 fail closed：

- Mythic 缺失或版本不兼容：禁用 Mythic mob spawn、战斗与掉落桥接，输出一次结构化错误。
- Game Service 不可用：已有怪物可以保留 AI/表现，但所有权威伤害和奖励停止，不退回 YAML 数值。
- internal name 映射缺失：取消生成或不计入任务/掉落，绝不能按显示名猜测。
- API linkage error：启动阶段 capability probe 后禁用整个 gateway，避免战斗中反复抛错。

## 9. 分阶段实施方案

### Phase 1：只集成身份与一只怪

1. 私有部署 MythicMobs JAR，首次启动生成配置。
2. 添加 `Packs/ImmortalMC`，定义 `immortal_test_spirit_wolf_t1`，禁止所有本地掉落。
3. Adapter 增加 `softdepend`、`MythicMobGateway` 和启动 capability check。
4. 监听 spawn/death，记录 internal name、instance UUID、spawn reason；暂不改变伤害。
5. Game Service 增加 mob template 与幂等 death endpoint，返回固定测试奖励。

### Phase 2：权威掉落

1. 三层清空 Mythic/vanilla drops 与 exp/money。
2. 死亡快照异步提交，Game Service 事务内判定并存储奖励。
3. Adapter 发放/展示已提交结果；离线与失败进入可重试队列。
4. 接入自研任务系统，以 internal name 作为击杀目标 ID。

### Phase 3：权威伤害

1. 先覆盖玩家普通攻击一条链，加入 action ID、重入标记、超时和实体存活检查。
2. 再覆盖怪物普通攻击、投射物、Mythic damage mechanic。
3. 多段技能改为一次 skill action 由 Game Service 返回命中/伤害计划，Mythic 只播放表现。
4. 最后才开放复杂 boss phases、aura 和定时技能。

### Phase 4：任务与 Citizens 联动

Citizens NPC 点击由 ImmortalMC 任务插件处理；任务状态改变后，通过 signal/custom trigger 让 Mythic 播放刷怪、阶段切换或场景技能。不要让 Mythic command drops 或 Denizen 脚本直接修改任务数据库。

## 10. 测试清单

### 单元/契约测试

- internal name 与 Game Service `mob_template_id` 映射、未知 ID 拒绝。
- 同一个 `combat_action_id`/`death_event_id` 重放不会重复伤害或发奖。
- HTTP 超时、503、无效 JSON 时 fail closed。
- 批准伤害回调时实体已死亡、卸载、换世界、UUID 不匹配均不应用。
- re-entry token 防止批准伤害递归触发。
- reload 后 gateway 缓存重建。

### MockBukkit/集成测试

- 无 MythicMobs 时 Adapter 基础功能仍启动，Mythic 功能明确禁用。
- 不兼容 Mythic API 时 capability probe 报单一明确错误。
- spawn event 提取 internal name/UUID/spawn reason 正确。
- MythicMobDeathEvent、MythicMobLootDropEvent、EntityDeathEvent 后 drops/exp/money 均为零。
- Citizens NPC 在默认 target filters 下不被 Mythic 技能选中。

### 实服端到端

- Paper 1.21.11 + Java 21 冷启动、`/mm reload`、完整重启。
- 生成 1/100/500 只测试怪，观察 TPS、tick time、内存、HTTP 队列和日志。
- 普攻、暴击、多段、箭、环境伤害、宠物/召唤物、非玩家击杀。
- 玩家击杀瞬间退出、服务重启、Game Service 重启、响应乱序、重复响应。
- 怪物死亡只发一次 Game Service 奖励，地面无 Mythic/vanilla 漏掉落。
- NPC 周围 AoE 不误伤 Citizens；任务接受后能触发 Mythic 刷怪与演出。

## 11. 主要风险与决策

| 风险 | 影响 | 控制 |
|---|---|---|
| 5.13 dev build API/行为变化 | 启动或事件回归 | 锁定构建 hash；gateway 隔离；升级先跑集成测试 |
| Premium 误分发 | 许可风险 | JAR 不入库；私有注入；核对购买条款 |
| Mythic 与 Game Service 双重伤害 | 数值翻倍/递归 | 统一入口、取消原伤害、re-entry token |
| Mythic/vanilla 掉落漏清 | 复制与经济破坏 | Mythic death + loot + Bukkit death 三层兜底 |
| 同步 HTTP 阻塞 tick | 卡服 | 全异步、超时、有界队列、回所属线程 |
| 异步响应实体已变化 | 错目标/幽灵伤害 | UUID + encounter + alive/world 检查 |
| display name 当业务 ID | 改名即坏档 | 只用 internal name + instance UUID |
| Citizens 被怪物锁定 | 任务 NPC 死亡/演出破坏 | `TargetCitizensNPCs: false`，局部显式开放 |
| reload 后缓存陈旧 | 调用旧对象 | 缓存字符串，reload-complete 后重建 |
| Game Service 故障时本地回退 | 可作弊、状态分叉 | fail closed；待处理队列；不采用 YAML 数值兜底 |

最终建议：**立即引入 MythicMobs，但第一步只做一只怪的身份、生成、死亡和权威掉落闭环；权威实时伤害是更高风险的第二阶段。Citizens 与 MythicMobs 各守 NPC/怪物职责，自研任务系统通过 Adapter 事件和 signal/custom trigger 连接两者。**
