# Minecraft MMORPG 开发架构总览 v2

> 本文档整合了原始架构草案、ADR-001（Game Services 架构选型）以及后续讨论，
> 是当前阶段的权威参考。建议放入 `.trellis/spec/`，让每次 Claude Code
> 会话自动加载，不用每次重新解释项目背景。

## 修订说明

相比 v1，本版本的核心变化：

- Game Services 从"五个独立微服务"改为"一个 Game Service 进程，内部
  按模块划分"（详见 ADR-001）
- 明确了服务间通信方式：Adapter Plugin ↔ Game Service 走本地 HTTP
- 新增战斗服务端权威性原则
- 新增三层测试策略
- 新增编辑器引入时机的判断标准
- 新增成熟插件生态的整合原则和引入时机

---

## 一、项目定位（不变）

目标不是开发一个 Minecraft 插件服，而是开发一个长期运营的 MMORPG 游戏
服务器。

> Minecraft 是客户端表现层，真正的游戏是运行在服务器端的 MMORPG 系统。

---

## 二、整体架构（当前阶段）

    玩家
      |
    Paper Server（单一世界，Multi-Server 是后续方向，不是现在的目标）
      |
    MMORPG Adapter Plugin        <- Java，只做MC事件⇄请求的转换，不含业务逻辑
      |
      | 本地 HTTP（单跳）
      |
    Game Service（单一进程，Python + FastAPI）
      ├── player/         玩家档案、状态、数据同步
      ├── item/           装备、法宝、词缀、掉落
      ├── quest/          任务、剧情、奖励
      ├── combat/         战斗计算、技能、Buff
      └── cultivation/    灵根、修炼、境界突破、功法
      |
    PostgreSQL + Redis

    =========================================
                        MCDR
    =========================================
     Backup / Monitor / Restart / Deploy
     Discord / QQ / 飞书通知
     Log Analysis

Lobby / Cultivation / Dungeon 多节点 + Velocity 代理是 Wynncraft 级终局
形态，**不是当前阶段的目标**，见 ADR-001 第五节。

---

## 三、核心思想（不变）

不要把所有逻辑写进 Paper 插件：

    PlayerJoinEvent → 处理玩家数据 → 计算奖励 → 修改装备 → 保存数据库

这是长期会变成巨型插件的错误模式。推荐链路：

    Minecraft Event → Adapter Plugin → Game Service → Business Logic
    → Database → 返回结果 → Minecraft表现

---

## 四、Monorepo 项目结构

    immortal-mmo/
    ├── proxy/                      （多服阶段才需要）
    ├── minecraft-nodes/
    │   └── main-plugin/            当前单一世界，含Adapter Plugin
    ├── game-service/               单一进程，Python + FastAPI
    │   ├── player/
    │   ├── item/
    │   ├── quest/
    │   ├── combat/
    │   └── cultivation/
    ├── mcdr/
    │   ├── backup-plugin/
    │   ├── monitor-plugin/
    │   ├── discord-plugin/
    │   └── deploy-plugin/
    ├── admin-panel/                内容量涨起来后再建，见第十节
    ├── database/
    ├── tools/
    └── docs/
        ├── architecture-v2.md      本文档
        ├── game-design.md
        ├── coding-style.md
        ├── roadmap.md
        └── decisions/
            └── ADR-001-game-services-modular-monolith.md

---

## 五、各模块职责

### Paper Plugin
负责：玩家事件、NPC交互、UI展示、粒子效果、世界操作。
不负责：战斗公式、经济逻辑、玩家成长规则。

### Adapter Plugin
只做 MC 事件 ⇄ Game Service 请求的转换。物理上是独立进程边界，不是靠
自觉——这样即使 Codex/Claude Code 写代码时想图省事，也没有直接写业务
逻辑的地方可写。

### Game Service
真正的 MMORPG 逻辑所在。语言选 Python + FastAPI，原因见第六节。内部
按 Player / Item / Quest / Combat / Cultivation 划分模块，模块间只能
通过接口调用，不能直接访问彼此的数据表（写进 coding-style.md 的硬规则）。

---

## 六、服务间通信设计

### Adapter ↔ Game Service：本地 HTTP + FastAPI

选择理由（针对你现在的开发方式，不是纯技术最优解）：

- FastAPI 自带网页版接口文档（`/docs`），可以直接在浏览器里手动测试
  每个接口、看请求返回长什么样，不需要写代码就能验证 Claude Code
  写的东西对不对
- 自带请求格式校验，字段类型错了直接报清楚的错误，不会悄悄传坏数据
  进数据库
- Python 语法比 Java/Kotlin 更容易读懂，审查 agent 生成的代码更轻松
- 单跳本地 HTTP 在 Minecraft 20 TPS（50ms/tick）预算内可以忽略不计——
  真正的延迟风险是链式跨服务调用，合并成一个 Game Service 后这条链
  变成单跳，详见 ADR-001

### 两种通信方向要分开设计

- **Paper → Game Service（请求驱动）**：玩家发起的动作（攻击、用道具、
  对话选择），用 HTTP 请求-响应，现在就该这么做。
- **Game Service → Paper（事件驱动）**：服务端主动触发的表现（buff到期、
  定时事件、后台任务完成通知），请求-响应模型处理不了"服务端主动通知"
  这件事。Demo 阶段可以先用 Paper 定时轮询 Game Service 的"待处理事件"
  接口顶替，但接口设计时要预留这个口子——Redis 已经在技术栈里，未来
  升级成 Redis Pub/Sub 作为轻量消息总线成本较低，前提是现在别把
  Adapter 写死成只会发请求。

---

## 七、战斗服务端权威性原则

一条原则，不需要复杂的反作弊系统：

> **Adapter 只能上报"玩家做了什么"（用了哪个技能、打了哪个目标），
> 伤害数值必须由 Combat 模块根据存档里的属性 + 装备 + 技能公式自己算
> 出来，绝不接受客户端/插件传来的伤害数字直接写库。**

这条原则从一开始就这么写代码，成本几乎是零；先图省事让数字直接从
客户端/插件传上来，以后想改成服务端权威就是重写。现阶段不需要额外
做复杂的反作弊检测（移动速度异常检测那一套），那是有真实玩家、有
真实作弊动机之后才值得投入的东西。

这条原则在引入 MythicMobs 等插件后依然成立，见第九节。

---

## 八、测试策略（三层）

1. **数据文件校验**：item.json / mob.json 这些配置文件加 schema
   校验，格式错了直接报错，不会悄悄产生一个字段拼错的装备。
2. **公式对照测试**："给定输入-期望输出"，比如"100攻击力打50防御力
   的怪，应该出150点伤害"。这种测试不需要看实现代码就能看懂在验证
   什么。
3. **端到端测试**：把完整玩家循环（进灵根检测→加入宗门→学功法→
   打怪→突破→存档）跑一遍。每次 Claude Code 改了什么，跑一下这条
   测试就知道有没有破坏原有流程。

习惯性让 Claude Code "顺便写测试"，验收标准是测试跑通，而不是
"看起来对了"。

---

## 九、和成熟插件的整合原则

MythicMobs / MMOItems / MMOCore / BetonQuest 这些插件运行在 Paper
进程里，是"Minecraft 表现层"的一部分。核心原则：

> **插件解决"机制怎么实现"（生成什么样的怪、装备长什么样、技能特效
> 怎么放），Game Service 决定"数字应该是多少"（这次攻击造成多少
> 伤害、这件装备该有什么属性、这次突破成不成功）。**

具体来说：

- MythicMobs 负责生成怪物的外观、AI 行为、技能演出，但一次攻击
  最终扣多少血，走第七节的服务端权威流程，不直接用 MythicMobs
  配置文件里写的数字。
- MMOItems 负责装备的图标、Lore 展示、GUI 编辑，但装备最终提供
  多少属性加成、是否与灵根/境界挂钩，这类跟你自己的修仙体系强相关
  的规则由 Item 模块决定，MMOItems 更多是"展示层容器"。
- MMOCore 的类/技能树系统是通用西方 RPG 风格（class、mana、
  profession），不直接套用在灵根/境界/功法这套东西上。它更适合当作
  底层技能施法引擎（把粒子技能绑定到右键、做冷却UI）来用，具体的
  境界突破规则仍然是 Cultivation 模块自己的逻辑。
- 这些插件自带的存档（YAML/内置SQL）不作为跨系统数据的唯一来源。
  凡是要跟修仙数值挂钩的数据，最终都要能在 PostgreSQL 里查到，
  插件自己的存档只管插件自己范围内的东西（比如 MythicMobs 的怪物
  刷新计时器）。

什么时候引入哪个插件，见第十一节的路线图。

---

## 十、数据驱动 + 编辑器引入时机

避免 `if quest == xxx`，采用 `quest.json` / `item.json` / `mob.json` /
`skill.json`，程序解释数据。

**现在不需要专门做编辑器，先用 Claude Code 本身当编辑器。** 内容量小
的时候，直接让 Claude Code 按 schema 生成并校验 JSON（"帮我加一把
武器，攻击力80，冰系词缀"），比设计和写图形界面编辑器快得多。

什么时候该做真正的编辑器（对应 Monorepo 里已经留好的 `admin-panel/`
目录）：

- item/mob/quest 的字段结构跑过一轮验证、基本稳定下来之后
- 内容量涨到手动维护容易出错的时候（几百件装备要保证掉落表不重复、
  ID不冲突）

优先级：装备、怪物（结构化程度高、适合做表单）> 剧情/任务（数量通常
不多，更依赖叙事直觉，继续跟 Claude Code 对话生成）> GUI（偏代码，
不算数据资产）> VFX（先手写模板，参数体系稳定后再考虑做预览工具）。

编辑器不需要单独维护一套数据，直接调用 Game Service 的 FastAPI
接口读写，保证编辑器改的东西和游戏里读的东西永远是同一份数据。

---

## 十一、成熟插件引入路线图

核心判断标准：**跟着垂直切片走，插件在对应步骤第一次被需要时引入，
但只用它解决机制问题，不用它替代 Game Service 的数值权威。**

参考垂直切片：进入游戏 → 检测灵根 → 加入宗门 → 学功法 → 击杀妖兽 →
获得资源 → 突破境界 → 保存数据

| 系统 | 推荐插件 | 现状（2026年） | 引入时机 |
|---|---|---|---|
| 怪物/技能演出 | MythicMobs | 持续更新（5.9.x），事实标准 | 从"击杀妖兽"这一步开始就用，哪怕只配一只怪 |
| 装备/词缀/套装 | MMOItems（+ MythicLib） | 持续更新（6.10.x） | 和 MythicMobs 同期，"获得资源"这一步需要第一件真实装备时 |
| 职业/技能施法引擎 | MMOCore（+ MythicLib） | 持续更新（1.13.x） | 缓一缓：先在 Cultivation 模块把灵根/境界/功法规则定清楚，再决定用 MMOCore 的哪部分做施法引擎，不要直接套它的 class/mana 系统 |
| 剧情/任务链 | BetonQuest | 长期活跃，Spigot 历史评分前十 | 单条垂直切片跑通之后，开始做第一条真正的多任务连线剧情时 |
| 公会/宗门 | SimpleClans | 持续维护，社区活跃 | "加入宗门"这一步：demo 阶段可以先硬编码一个宗门；等多玩家真实测试、需要建/邀/退功能时再接入 |
| 经济系统 | Vault + EssentialsX（免费）或 CMI（付费，二选一，不能共存） | 均持续维护 | 出现第一个"东西能被买卖"的需求时再装，Vault 本身随时可以先装着 |
| 副本/RAID | MythicDungeons（成熟，生态最完整）或 SinceDungeon（更新，自带跨服路由，值得关注） | 均持续更新 | 最后再做：核心战斗/掉落/修炼循环稳定之后，作为可重复的终局内容 |
| 大世界/多世界/地形 | WorldEdit + WorldGuard + Multiverse-Core + Terra/TerraformGenerator | 均为长期标准工具 | WorldEdit 现在就能用（搭建测试场景）；Multiverse/Terra 等需要多个区域或大世界探索需求出现后再投入 |

---

## 十二、MCDR 定位与职责（不变）

MCDR 不参与 MMORPG 游戏逻辑，是 Minecraft 服务器运维自动化层：进程
生命周期管理、自动备份、日志监控、管理机器人、部署自动化。

不要用 MCDR 实现战斗系统、装备系统、修炼系统——这些属于 Game
Service。

---

## 十三、Codex / Claude Code 角色

工作方式：需求 → 设计文档 → 架构讨论 → 代码生成 → 测试 → 重构。

负责：编码、重构、测试生成、Debug、文档维护、MCDR插件开发。

开发者负责：世界观、游戏设计、架构决策、产品方向。

**新增纪律**（模块化单体阶段容易被破坏的地方）：

- 模块之间只能通过接口调用，不能直接访问彼此的数据表
- 生成涉及多模块的代码时，先检查是否在抄近道绕过接口
- 每次改动"顺便写测试"，对照第八节的三层策略

---

## 十四、开发方式：垂直切片（不变）

不要先做完装备系统再做任务系统再做技能系统。应该先跑通完整玩家循环：

    进入游戏 → 检测灵根 → 加入宗门 → 学功法 → 击杀妖兽 → 获得资源
    → 突破境界 → 保存数据

插件引入的节奏也跟着这条线走，见第十一节。

---

## 十五、文档驱动

维护 `docs/`：architecture-v2.md（本文档）、game-design.md、
coding-style.md、roadmap.md、decisions/。

每次 Codex 开发前先读取 docs。建议把本文档放进 `.trellis/spec/`，
让 Trellis 在每次 Claude Code 会话自动注入，不用每次重新解释背景。

---

## 十六、待明确 / 后续 ADR

- [ ] Game Service → Paper 的推送机制：轮询顶替到什么时候切到 Redis
      Pub/Sub
- [ ] Adapter 的短暂状态和 Game Service 权威状态之间的一致性/崩溃恢复
      策略
- [ ] Cultivation 模块的灵根/境界/功法规则设计文档（game-design.md）
- [ ] Multi-Server 阶段的玩家状态同步方案（不紧急）

---

## 十七、最终定位（不变）

开发者：游戏制作人 + 架构设计者
Codex / Claude Code：AI研发团队
Paper：Minecraft游戏运行环境
Adapter Plugin：Minecraft适配层
Game Service：真正的MMORPG逻辑
MCDR：服务器运维管家
成熟插件（MythicMobs等）：机制层工具，不是数值权威

最终目标：不是制作一个 Minecraft 插件，而是制作一个运行在 Minecraft
上的完整 MMORPG 服务器。
