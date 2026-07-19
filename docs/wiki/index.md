# ImmortalMC 中文 Wiki

这里是 ImmortalMC 当前版本的中文使用手册。Wiki 与代码放在同一个仓库中，
保证命令、配置、玩法、内容制作和运维说明可以随代码一起审核、发布。

## 从这里开始

| 读者 | 页面 | 用途 |
|---|---|---|
| 服主 | [快速开始](getting-started.md) | 安装、迁移、构建、启动和连接服务器 |
| 服主 | [命令与权限](commands-and-permissions.md) | 当前全部 `/immortal` 命令 |
| 服主 | [配置说明](configuration.md) | Paper 适配器配置及重载/重启要求 |
| 玩家/内容作者 | [玩家与灵根](players-and-spirit-roots.md) | 登录、人生、鉴灵和鉴灵实体 |
| 内容作者 | [NPC 与对话](npcs-and-dialogues.md) | 对话 YAML、普通实体和 Citizens 绑定 |
| 内容作者 | [任务系统](quests.md) | 四类任务目标、规则、示例和 Citizens 配置 |
| 内容作者 | [战斗与 MythicMobs](combat-and-mythicmobs.md) | 怪物奖励目录、归属和可靠投递 |
| 玩家/内容作者 | [修炼系统](cultivation.md) | 修为、功法、闭关、境界和突破 |
| 玩家/内容作者 | [实体物品与功法秘籍](physical-items-and-technique-manuals.md) | 权威物品身份、任务投递、对账和秘籍学习 |
| 玩家/服主 | [地区仓库](regional-storage.md) | 按地区隔离的分页大箱子与实体物品存取 |
| 服主 | [BetterHud 与材质包](betterhud-and-resource-pack.md) | HUD 资源和客户端材质包分发 |
| 运维 | [运维与故障排查](operations-and-troubleshooting.md) | 健康检查、日志、备份、恢复和常见故障 |
| 接入开发者 | [API 参考](api-reference.md) | OpenAPI、接口分组和幂等规则 |
| 开发者 | [开发与测试](development-and-testing.md) | 架构和质量检查命令 |
| 维护者 | [Wiki 维护规范](wiki-maintenance.md) | 每次功能更新时必须执行的文档同步流程 |

## 兼容版本

| 组件 | 当前目标 |
|---|---|
| Minecraft / Paper | `1.21.11`，本地 Paper 构建号 `132` |
| ImmortalMC 编译与 Paper 运行目标 | Java `25` |
| BetterHud `2.0.0` 本地运行环境 | Java `25` |
| Game Service | Python `3.12`、FastAPI |
| 数据库 | PostgreSQL `17` |
| Citizens | `2.0.43-SNAPSHOT`，构建号 `4211` |
| MythicMobs | 免费版 `5.12.1` |
| BetterHud | `2.0.0` |

## 当前已实现

- 账号与当前人生的持久化登录同步；
- 命令或鉴灵实体触发的鉴灵；
- 通用 NPC 对话和 Citizens 任务 NPC 绑定；
- 物品交付、接取后 MythicMobs 击杀数、指定功法层数、指定境界四类任务目标；
- MythicMobs 击杀修为奖励与 Paper 可靠投递队列；
- 未炼化修为、功法投入、闭关、境界回退和初版突破流程；
- BetterHud 修为双条 HUD 和任务追踪侧边栏；
- 任务固定物品/未炼化修为奖励、实体功法秘籍和按地区分页仓库。

## 当前尚未完整开放

- 随包任务目录目前只有 `first-steps`。四类新目标引擎已经可用，但还没有随包
  配置四个实际生产任务；
- 宗门、原版成就替换和完整轮回体验仍是后续内容。

Wiki 只描述已经交付的行为，不把计划中的功能写成已实现。修改公开功能前请先读
[Wiki 维护规范](wiki-maintenance.md)。
