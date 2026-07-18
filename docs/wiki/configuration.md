# 配置说明

Paper 适配器运行配置位于：

```text
plugins/ImmortalMC/config.yml
```

默认模板位于 `minecraft-nodes/main-plugin/src/main/resources/config.yml`。

## Game Service 地址

```yaml
game-service:
  base-url: "http://127.0.0.1:8000"
```

这是 Paper 可访问的权威服务地址，修改后需要重启 Paper。

## 服务器标识

```yaml
server-id: "main-1"
```

这个稳定 ID 会写入战斗事实。线上服务器不要随意改名，修改后需重启 Paper。

## 战斗归属与可靠投递

```yaml
combat:
  attribution:
    max-source-age-seconds: 900
    max-active-targets: 20000
  outbox:
    file: "combat-outbox.sqlite3"
    writer-queue-capacity: 4096
    busy-timeout-ms: 5000
  delivery:
    normal-interval-ms: 1000
    high-load-interval-ms: 5000
    tps-threshold: 17.0
    batch-size: 100
    high-load-batch-size: 200
    max-pending-age-seconds: 30
    lease-seconds: 30
    max-attempts: 20
```

SQLite 文件只是可靠投递队列，不是权威游戏数据库。以上设置都在插件启动时读取，
修改后需重启 Paper。不要在 Paper 运行时手工编辑发件箱。

## 任务接近扫描

```yaml
quest:
  scan-interval-ticks: 10
  proximity-radius: 6.0
  max-players-per-scan: 100
```

- `scan-interval-ticks`：任务 NPC 扫描间隔；
- `proximity-radius`：玩家私有提示的触发距离；
- `max-players-per-scan`：每轮处理上限，超出部分顺延到下一轮。

修改后需重启 Paper。

## 修炼区域

```yaml
cultivation:
  areas:
    - area-id: neutral_training_ground
      world: world
      min: {x: -32, y: -64, z: -32}
      max: {x: 32, y: 320, z: 32}
```

每个长方体把 Minecraft 坐标映射到一个 Game Service 语义 `area_id`。该 ID 必须
存在于 `game-service/src/immortal_mmo/cultivation/areas.json`。Paper 不提交速度或
收益数值。同一世界的区域不能重叠或倒置，修改后需重启 Paper。

## 实体交互绑定

```yaml
content:
  entity-interactions:
    entries: []
```

鉴灵、对话和任务 NPC 管理命令会在这里保存普通条目。优先使用命令，不要手工复制
实体 UUID，因为命令还会校验目标、保存 Citizens 持久 UUID、处理重复绑定并安全写回。

停服时手工修改后，需要执行对应重载命令或重启 Paper。

## Game Service 环境变量

本地文件 `game-service/.env`：

```dotenv
DATABASE_URL=postgresql+asyncpg://immortal:immortal_dev_only@127.0.0.1:5432/immortal
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT_SECONDS=5
DATABASE_ECHO=false
```

`DATABASE_URL` 必填且必须使用 `postgresql+asyncpg://`。示例凭据禁止用于线上。

## 重载/重启对照表

| 修改内容 | 必须执行 |
|---|---|
| Paper `config.yml` 运行设置 | 重启 Paper |
| 对话 YAML | `/immortal npc-dialogue reload` |
| 实体交互绑定 | 对应重载命令或重启 Paper |
| Python 任务/提供者定义 | 重启 Game Service，再 `/immortal quest reload` |
| 战斗、境界、功法、区域、突破 JSON 目录 | 重启 Game Service |
| ImmortalMC 内置 BetterHud 资源 | 重建并复制 jar，再重启 Paper |
| Alembic 迁移 | 按需要停止写入，执行 `alembic upgrade head`，重启 Game Service |

修改内容目录前还应阅读对应功能页，其中包含各自的校验规则。
