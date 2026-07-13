# MMOCore 与 ImmortalMC 集成评估

> 调研日期：2026-07-13  
> 本地候选包：`plugins-new-add/[M]MMOCore-1.13.1-51.jar`  
> 目标运行环境：Paper 1.21.11、Java 21

## 结论

**不建议把 MMOCore 作为 ImmortalMC 的核心 RPG/修仙框架。** 它覆盖职业、等级、属性、技能树、法力/耐力、任务、掉落、队伍、公会、传送点和玩家持久化，几乎全部落在 ImmortalMC 已确定由 Game Service 权威管理的领域内。直接启用会形成两套玩家等级、资源、任务、战斗与存档真相源，尤其与修仙境界、灵根、功法、轮回和自研任务系统冲突。

MMOCore 可以作为**付费、源码可见但非自由开源的可选能力库**进行后续 PoC，但只能挑选不掌握业务真相的外围能力，并且必须通过 ImmortalMC 适配层隔离。当前最稳妥的组合仍是：

- Citizens 管 NPC 实体、皮肤、名称、寻路与生命周期。
- MythicMobs 管怪物模板、生成、AI、技能表现与特效。
- ImmortalMC Adapter 把 Minecraft 事实转换为 Game Service 请求并展示结果。
- Game Service 独占任务、战斗结果、掉落资格、修仙、轮回和玩家成长状态。
- 暂不部署 MMOCore；如未来确有需求，先对单个模块做隔离 PoC，而不是一次性启用整套系统。

## 证据与版本

本地 JAR 的 `plugin.yml` 可确认：

- 插件名 `MMOCore`，版本 `1.13.1-SNAPSHOT`，主类 `net.Indyuce.mmocore.MMOCore`。
- `MythicLib` 是硬依赖：`depend: [ MythicLib ]`。缺少匹配版本的 MythicLib 时插件不能启动。
- `MythicMobs`、`Citizens`、`MMOProfiles`、`PlaceholderAPI`、`Vault`、`ProtocolLib` 等是软依赖。
- `loadbefore` 包含 `MMOItems` 和 `MythicDungeons`。
- 本地 JAR 的 `api-version` 为 `1.14`；这只说明 Bukkit API 下限，不等于已证明兼容 Paper 1.21.11。

本地 JAR 内嵌 Maven 元数据还显示：

- `MMOCore-API` 编译元数据引用 Paper API `1.21.3-R0.1-SNAPSHOT`。
- `MMOCore-Dist` 编译元数据引用 Paper API `1.20.6-R0.1-SNAPSHOT`。
- MythicMobs API 依赖元数据为 `Mythic-Dist 5.7.1`，Citizens 编译依赖元数据为 `2.0.30`。

因此，这个 2026-02-17 构建很可能能运行于较新的 1.21 系列，但**不能由这些元数据推导出 1.21.11 已兼容**。最终必须在当前测试服同时放入匹配的 MythicLib 后做启动、登录、保存/重载、技能、MythicMobs 和 Citizens 联动回归。当前本地目录没有 MythicLib JAR，因此不能直接完成有效启动验证。

官方入口：

- [Spigot 资源页](https://www.spigotmc.org/resources/%E2%AD%90-mmocore-%E2%AD%90-classes-skills-levels-skill-trees-professions-mana-waypoints.70575/)
- [官方 Phoenix 文档](https://docs.phoenixdevt.fr/mmocore/)
- [官方 GitLab 源码仓库](https://gitlab.com/phoenix-dvpmt/mmocore)
- [官方仓库 README/API 依赖说明](https://gitlab.com/phoenix-dvpmt/mmocore/-/blob/master/README.md)
- [官方许可证](https://gitlab.com/phoenix-dvpmt/mmocore/-/blob/master/LICENSE)

本次访问 Spigot 页面遇到 Cloudflare challenge，无法直接核对资源页当前价格、下载权限、最新稳定版声明、购买者说明和 1.21.11 兼容标签；这些项目不得视为已核实。

## 许可与源码可用性

MMOCore 的官方 GitLab 仓库公开可读，但其 LICENSE 明确为 **All Rights Reserved**，不是 MIT、Apache、GPL 等自由/开源许可证。官方条款要点包括：

- 未购买许可不得下载、编译、反编译或在服务器使用。
- 购买后可下载、反编译、fork 和修改以满足自己的生产服务器需要。
- 许可范围描述为一个生产服务器或同一代理网络，加一个私有测试服。
- 不得重新分发、销售或赠送官方或修改版本。
- 开发者可为已经购买许可的客户做一次性定制，但不能公开销售衍生版本。

因此应将其描述为“**源码公开可见的商业插件**”，而不是“开源插件”。在部署前必须确认项目账户已经合法购买，并保存购买主体、允许的生产网络与测试服范围。即使能自行 fork，也不能把其源码合并进 ImmortalMC 仓库或重新发布构建物。

## 功能范围

官方文档导航、本地默认配置和 JAR 类结构共同确认了以下模块：

| 模块 | 本地/官方证据 | 对 ImmortalMC 的价值 | 冲突程度 |
|---|---|---|---|
| Classes / subclasses | 默认 `classes/`、职业选择 GUI、`PlayerChangeClassEvent` | 可快速构建传统 RPG 职业 | 高：与灵根、境界、功法路线并存会形成第二套身份体系 |
| Main levels / EXP | 经验曲线、经验表、经验来源、升级事件、原版经验重定向 | 通用等级和经验 UI | 极高：与修仙境界和轮回成长权威冲突 |
| Attributes / player stats | 自定义属性、属性点、重置点、MythicLib stats | 可复用数值面板和加点 GUI | 高：Game Service 已要求权威计算战斗/成长 |
| Skills / skill trees | 大量内建技能、绑定、快捷施法、冷却、技能树 GUI | 成熟的技能展示、绑定和施法体验 | 中到高：功法/技能解锁与伤害结果必须留在 Game Service |
| Mana / stamina / stellium | 默认玩家数据、资源恢复 tick、资源更新事件 | 可提供成熟资源条和技能消耗体验 | 极高：会出现与灵力/真气等修仙资源并行的第二账本 |
| Professions | mining、farming、fishing、alchemy、enchanting、smithing、smelting、woodcutting | 生活职业模板较完整 | 中到高：经验、掉落、采集与炼丹/炼器成长需统一权威 |
| Custom mining / restrictions | 自定义方块采集、再生、工具限制、WorldGuard 条件 | 可减少矿区机制开发量 | 中：可仅复用机制，但掉落和成长不能由它直接裁决 |
| Waypoints | 传送点、路径计算、费用与等待时间 | 独立且相对外围，可快速提供传送网络 | 低到中：最适合单模块 PoC，但 stellium 费用需禁用或桥接 |
| Parties / friends / guilds | 内建队伍、好友、公会及多个外部插件适配 | 社交功能完整 | 中：与未来宗门、队伍收益、跨服数据设计可能冲突 |
| Quests | 内建任务、目标、触发器、任务 GUI | 可快速做传统任务 | 极高：用户已决定任务插件自研，Game Service 是唯一任务真相源 |
| Economy / drops / loot chests | Vault、金币袋、掉落表、战利品箱 | 通用掉落表现 | 高：奖励幂等、掉落资格和修仙资源必须由 Game Service 决定 |
| Combat / PvP mode | combat log、PVP 等级限制、死亡经验损失 | 通用 RPG 规则较全 | 极高：与权威战斗计算、境界压制等设计直接重叠 |
| Party/guild chat and GUI | 内建交互与可配置 GUI | 可节省普通社交 UI 开发 | 低到中：仅当不承担核心状态时可考虑 |

官方文档首页也明确提醒 MMOCore 附带的是示例 classes、attributes、quests 等，服务器仍需大量自行配置。它不是“安装后自动获得完整 MMO 内容”的低成本方案。

## 持久化与数据所有权

本地 `config.yml` 可确认 MMOCore 会保存职业、等级等玩家数据和公会数据，并提供自动保存；支持 MySQL，默认表名为 `mmocore_playerdata`，也存在 YAML 公会数据管理实现。默认玩家数据至少包括：

- level、class points
- skill points / reallocation points
- attribute points / reallocation points
- health、mana、stellium、stamina

这与 ImmortalMC 的 `accounts -> lives -> cultivation/quest/...` 架构不兼容。轮回要求永久账户与每一世角色分离，而 MMOCore 默认围绕 Minecraft 玩家/可选 MMOProfiles 档案保存传统 RPG 数据。若让 MMOCore成为成长主库，将产生以下问题：

- 轮回时哪些字段清空、继承或封存难以用 MMOCore 原生模型准确表达。
- Game Service 与 `mmocore_playerdata` 之间需要双向同步，失败后无法确定哪个系统是真相源。
- 离线写入、崩溃恢复、自动保存和 Game Service 事务可能相互覆盖。
- 卸载 MMOCore 时，玩家技能绑定、属性点、职业等级、资源和任务进度都需迁移。

正确边界是：MMOCore 若被采用，只能保存其自身非权威 UI/机制状态；所有可影响任务完成、修仙成长、轮回、战斗结果和奖励的状态必须在 Game Service 中有独立、权威记录。禁止用定时“双写同步”维持两套主库。

## API、事件与占位符

官方 README 给出了作为依赖的 Maven 仓库和 `MMOCore-API`/`MythicLib-dist` 依赖方式。当前 README 示例仍展示 `MMOCore-API 1.12.1-SNAPSHOT` 与 `MythicLib 1.6.2-SNAPSHOT`，而本地 JAR 是 1.13.1 snapshot，集成时必须锁定实际可解析且与服务器 JAR 匹配的构建，不能照抄示例版本。

本地 JAR 可确认存在公开 API 和 Bukkit 事件，包括但不限于：

- 玩家数据加载：`PlayerDataLoadEvent`
- 等级/经验：`PlayerLevelChangeEvent`、`PlayerLevelUpEvent`、`PlayerExperienceGainEvent`
- 职业：`PlayerChangeClassEvent`
- 资源：`PlayerResourceUpdateEvent`
- 战斗：`PlayerCombatEvent`
- 技能施法模式、按键、属性使用事件
- 队伍/公会聊天事件
- 物品解锁/锁定事件、采矿/钓鱼/战利品箱事件

JAR 中包含 PlaceholderAPI expansion 和大量占位符枚举；官方文档也提供 [Placeholders](https://docs.phoenixdevt.fr/mmocore/general/placeholders) 与 [Plugin API](https://docs.phoenixdevt.fr/mmocore/api/api) 页面。占位符适合作为计分板/菜单只读展示接口，但不应被 ImmortalMC 解析为权威业务输入。事件同样只适合观测或触发适配流程，不能把 MMOCore 事件携带的等级、经验或资源值直接当作 Game Service 真相。

## 与 Citizens、MythicMobs、MMOItems 的关系

### Citizens

Citizens 是软依赖。本地 JAR 包含 Citizens 兼容层、交互事件，以及 `TalktoCitizenObjective`、`GetItemObjective`。这说明 MMOCore 可以把 Citizens NPC 交互用作其任务目标。

ImmortalMC 不应使用这条内建任务链，因为任务系统已决定自研。应由 Citizens 提供稳定 NPC ID，ImmortalMC 捕获 Citizens 交互并调用 Game Service 的对话/任务命令。不要让 `TalktoCitizenObjective` 成为任务完成记录。

### MythicMobs

MythicMobs 是软依赖。本地 JAR 包含：

- 击杀指定 MythicMob / Mythic faction 的任务目标
- 击杀 MythicMob / faction 的经验来源
- Mythic skill trigger
- MythicMobs 掉落表、金币袋和货币掉落桥接

这些功能整合度很高，但也会让 MythicMobs 击杀直接推进 MMOCore 任务、经验和掉落。ImmortalMC 应关闭/不配置这些权威路径，只监听 MythicMobs 生成、伤害、死亡等事实，再交给 Game Service 判断任务推进、经验、掉落和修仙奖励。

### MMOItems / MythicLib

MMOCore 与 MMOItems 设计为同一生态：`loadbefore: MMOItems`，共同依赖 MythicLib 的 stats、damage、skills、mana/stamina 等基础设施。两者组合能提供传统 MMO 的职业、装备属性和技能闭环，但采用越深，ImmortalMC 就越难维持自己的战斗和成长权威。

MythicLib 是不可选的硬依赖，不只是一个轻量工具包。引入 MMOCore 等于同时引入 MythicLib 的数值、伤害、玩家资源和技能抽象，并新增版本矩阵：Paper + Java + MythicLib + MMOCore + MythicMobs/Citizens。即便暂不使用 MMOItems，也会承担 MythicLib 升级与 API 变更风险。

## 可复用边界建议

### 推荐直接采用

无。当前项目尚处于 NPC/任务/修仙垂直切片早期，引入 MMOCore 的依赖和数据模型成本大于收益。

### 可以做隔离 PoC

1. **Waypoints GUI 与传送表现**：不启用 MMOCore 等级/任务/职业权威；传送资格与费用由 Game Service 判断，MMOCore 仅展示/执行传送。若无法无侵入替换 stellium 与资格检查，则放弃。
2. **技能栏/按键绑定/施法 UI**：Game Service 返回技能是否可用、消耗和结果；MMOCore 只处理绑定与视觉。需要验证能否阻止本地技能直接造成权威伤害。
3. **只读 Placeholder 输出**：仅用于展示非权威信息；核心境界、灵根、功法数据仍由 ImmortalMC 自己提供 PlaceholderAPI expansion。
4. **部分社交 GUI**：仅在宗门/队伍模型稳定后评估，且 Game Service 必须是成员关系与收益规则的主库。

### 明确禁止复用为权威系统

- MMOCore quests
- class/main level/EXP 作为修仙成长
- mana/stamina/stellium 作为灵力或真气主账本
- MMOCore combat damage、PvP 等级规则、死亡经验损失
- 直接由 MMOCore/MythicMobs 发放修仙、任务或轮回奖励
- MMOCore playerdata 作为 `life` 或轮回存档
- MMOCore profession 等级作为炼丹、炼器或采集的唯一真相

## 锁定与卸载风险

| 风险 | 影响 | 缓解方式 |
|---|---|---|
| 商业许可证与再分发限制 | CI、镜像、成员协作和备份不能随意携带 JAR/源码 | 私有制品库、记录购买主体，不提交商业 JAR，不分发修改构建 |
| MythicLib 硬依赖 | 多一层核心运行时和升级矩阵 | 固定版本，测试服先行，ImmortalMC 使用 softdepend/反射隔离可选桥接 |
| Snapshot 构建 | 行为/API 可能变化，稳定性声明不清 | 不直接上生产；优先取得对应稳定发布版和 changelog |
| 双成长系统 | 等级、资源、技能点、任务进度不一致 | 不让 MMOCore 持有权威成长；禁止双写 |
| 配置和 GUI 深度定制 | 大量 YAML 内容形成迁移成本 | 所有业务 ID 与规则保留在 ImmortalMC 内容模型，MMOCore 配置仅做投影 |
| 事件/API 版本变化 | 适配器在升级时编译或运行失败 | 单独 `MMOCoreBridge` 模块、版本探测、契约测试、可关闭 feature flag |
| 卸载后玩家数据丢失 | 职业、技能绑定、等级、资源、任务等难迁移 | 只采用可丢弃/可重建的外围状态；采用前先写导出和回滚方案 |

MMOCore 的公开源码降低了排查和定制难度，但 All Rights Reserved 许可证、商业发布节奏、MythicLib 硬依赖以及庞大的玩家数据模型仍然造成明显锁定。源码可见不等于可以随意 fork 后永久自维护或再发布。

## Paper 1.21.11 验证门槛

在任何采用决定前，至少完成以下测试：

1. 获取与 MMOCore 1.13.1-51 明确匹配的合法 MythicLib 构建。
2. 在当前 Paper 1.21.11 / Java 21 测试服同时安装 MythicLib、MMOCore、Citizens、MythicMobs、ImmortalMC。
3. 验证所有插件 enable，无 `NoSuchMethodError`、`ClassNotFoundException`、反射/NMS 错误和严重事件异常。
4. 玩家登录、退出、重启后数据能保存和恢复；验证 MySQL/YAML 实际使用模式。
5. 验证 Citizens NPC 交互不会被 MMOCore quest listener 抢占或重复推进。
6. 验证 MythicMobs 击杀不会绕过 Game Service 直接授予经验、掉落或任务进度。
7. 验证技能栏、action bar、原版经验条、伤害监听与 ImmortalMC 展示/战斗监听没有冲突。
8. 停用 MMOCore 后，Citizens、MythicMobs、ImmortalMC 核心流程仍可启动和运行。

在这些测试通过前，兼容状态应标记为“**未验证**”，而不是“支持 Paper 1.21.11”。

## 最终建议

维持当前架构决策：Citizens 与 MythicMobs 作为成熟基础设施，自研任务插件和 Game Service 权威业务。MMOCore 暂不加入默认运行栈。

只有当项目出现一个清晰、独立且开发成本显著的缺口，例如成熟技能绑定 UI 或传送点网络，并且该能力能够在不采用 MMOCore 职业、等级、资源、任务、战斗和持久化权威的情况下独立运行，才创建单独 PoC。PoC 的通过条件必须包含可关闭、可卸载、可重建数据以及 Game Service 权威不被绕过。
