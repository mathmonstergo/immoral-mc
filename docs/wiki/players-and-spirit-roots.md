# 玩家与灵根

## 账号与当前人生

玩家加入服务器时，Paper 会异步调用：

```http
POST /api/v1/players/login
```

Game Service 会创建或重新加载：

- 一个以 Minecraft UUID 为键的永久账号；
- 一个当前人生，拥有独立的 `life_id`、轮回代数、状态、灵根、任务、物品和修炼状态。

Paper 只缓存返回的会话投影，PostgreSQL 始终是权威数据源。登录成功或失败会写入
Paper 日志，不会反复刷出到玩家聊天栏。

## 鉴灵

目前有两个入口：

1. 管理员/开发命令：

   ```text
   /immortal spirit-root
   ```

2. 与已绑定的鉴灵实体进行游戏内交互。

鉴灵结果对当前人生具有权威性并会持久保存。重复鉴灵只会返回已有结果，
不会重新随机生成灵根。

鉴灵交互成功后，会向玩家显示聊天、标题和粒子反馈，并刷新正在追踪的任务。
运行细节只记录在 Paper 日志中。

## 创建鉴灵实体

在当前位置创建一个由插件管理并受保护的鉴灵村民：

```text
/immortal spirit-root-detector create
```

也可以看向 8 格范围内的现有实体并进行绑定：

```text
/immortal spirit-root-detector set
```

查看和维护绑定：

```text
/immortal spirit-root-detector list
/immortal spirit-root-detector remove
/immortal spirit-root-detector reload
```

插件创建的鉴灵实体会标记为 `managed-entity: true`；移除该绑定时，如果实体仍然存在，
实体也会一并移除。绑定现有实体不会将该实体的所有权交给 ImmortalMC。

绑定保存在 `plugins/ImmortalMC/config.yml` 的
`content.entity-interactions.entries` 下。请使用命令完成绑定，不要手动复制实体 UUID。

## 任务集成

内置的 `first-steps` 任务使用 `current_life_spirit_root_present` 目标。当前人生拥有灵根后，
无论鉴灵由命令还是鉴灵实体触发，任务都会进入可交付状态。

## 当前限制

- 该命令仍是管理员/开发快捷入口；鉴灵实体交互才是当前预期的游戏流程。
- 面向玩家的完整轮回流程尚未发布。
- Paper 目前尚未提供账号/当前人生管理命令。

目标语义请参阅[任务](quests.md)，通用实体绑定请参阅 [NPC 与对话](npcs-and-dialogues.md)。
