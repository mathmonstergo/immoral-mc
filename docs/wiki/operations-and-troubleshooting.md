# 运维与故障排查

## 日常启动

完成首次准备后，在仓库根目录执行：

```bash
./scripts/start-local-server.sh
```

该命令启动 PostgreSQL、Game Service、现有 BetterHud 资源包的 HTTP 服务和 Paper。
它不执行数据库迁移或插件/资源包构建；启动前会自动计算当前 ZIP SHA-1，并且只幂等
同步 runtime `server.properties` 中的 `resource-pack` 和 `resource-pack-sha1`。

脚本启动失败时，按以下顺序检查：

1. PostgreSQL 是否健康；
2. Alembic 数据库结构是否已经由独立迁移步骤升级到最新修订；
3. Game Service 是否通过 `/ready`；
4. Paper JAR 和已安装插件是否存在；
5. `immortal-resource-pack` 会话和本机健康检查 URL
   `http://127.0.0.1:8164/build.zip` 是否可用；
6. 脚本输出的客户端 URL 是否能从 Minecraft 所在机器访问，并与
   `server.properties` 中的 `resource-pack` 一致；
7. `resource-pack-sha1` 是否与当前 `build.zip` 的 `sha1sum` 一致。

可通过 `RESOURCE_PACK_PUBLIC_URL` 显式设置客户端地址。若脚本提示资源包属性在 Paper
运行期间发生变化，应正常停止并重启 Paper，再让玩家重新连接；Paper 不会动态重读
这些属性。

相关命令见[快速开始](getting-started.md)。

## 健康检查

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
```

- `/health` 用于确认进程能够响应 HTTP 请求。
- `/ready` 还会检查 PostgreSQL，并要求数据库的 Alembic 修订版本与代码中
  唯一的最新版本一致。数据库不可用或版本过旧时，此接口返回 503。

直接检查迁移状态：

```bash
cd game-service
.venv/bin/alembic current
```

## 日志

Paper 日志：

```bash
tail -n 160 minecraft-nodes/main-server/logs/latest.log
```

排查启动状态时可关注以下事件：

```text
ImmortalMC adapter enabled
quest_provider_catalog_startup_refreshed
mythicmobs_integration_enabled
betterhud_cultivation_enabled
player_login_success
```

搜索故障：

```bash
rg 'SEVERE|ERROR|Exception|_failed|_unavailable' \
  minecraft-nodes/main-server/logs/latest.log
```

Game Service 日志由 Uvicorn 进程输出。测试期间应保留其 tmux 窗格或服务管理器
输出，以便随时查看。

## PostgreSQL 备份

创建自定义格式的本地备份：

```bash
docker compose exec -T postgres \
  pg_dump -U immortal -d immortal -Fc > /tmp/immortal-dev.dump
```

将备份恢复到隔离数据库中，不要覆盖源数据库：

```bash
docker compose exec -T postgres dropdb --if-exists -U immortal immortal_restore
docker compose exec -T postgres createdb -U immortal -O immortal immortal_restore
docker compose exec -T postgres \
  pg_restore --exit-on-error -U immortal -d immortal_restore \
  < /tmp/immortal-dev.dump
```

使用前进行验证：

```bash
DATABASE_URL=postgresql+asyncpg://immortal:immortal_dev_only@127.0.0.1:5432/immortal_restore \
  game-service/.venv/bin/alembic -c game-service/alembic.ini current
```

使用该隔离数据库 URL 启动新的服务进程，并重放已知的幂等键，以验证持久化状态。

## 一次性环境重置

以下操作会永久删除本地 PostgreSQL 中的全部数据：

```bash
docker compose down -v
docker compose up -d --wait postgres
set -a
source game-service/.env
set +a
cd game-service
.venv/bin/alembic upgrade head
cd ..
```

不要把重置数据卷当作生产环境的迁移方案。

## 战斗事件发件箱

查看队列概况：

```bash
sqlite3 minecraft-nodes/main-server/plugins/ImmortalMC/combat-outbox.sqlite3 \
  "select delivery_status, count(*) from kill_outbox group by delivery_status;"
```

如果待处理记录持续增加：

1. 检查 Game Service 的 `/ready`；
2. 核对 Paper 使用的 `game-service.base-url`；
3. 查看重试和错误日志；
4. 修复连接问题时，保持 SQLite 文件完整；
5. 仅在发件箱已安全关闭后重启 Paper。

## 常见故障

### Game Service 无法启动

- `DATABASE_URL must be set`：在当前命令行终端中加载 `game-service/.env`。
- 连接被拒绝：启动 PostgreSQL，并等待其健康检查通过。
- 就绪检查提示修订版本不匹配：运行 `alembic upgrade head`；不要为旧版数据库
  结构添加运行时降级兼容逻辑。

### BetterHud 已被禁用

- `UnsupportedClassVersionError` / class-file version 69：使用 Java 25 运行 Paper。
- 托管资源或重载失败：查看完整异常，并确认使用的是固定版本的 BetterHud。
- HUD 正常但没有资源包下载：按照
  [BetterHud 与资源包](betterhud-and-resource-pack.md)中的步骤排查。

### Citizens 任务命令失败

- 未安装 Citizens：安装并启用固定版本的 Citizens 构建。
- 未选择 NPC：以玩家身份运行 `/npc select <id|name>`。
- 所选 NPC 尚未生成：先生成该 NPC，再执行绑定。
- 任务提供者目录不可用：确认 Game Service 已就绪，然后运行
  `/immortal quest reload`。

### 击杀 MythicMobs 后没有奖励

- `mythicmob_rewards.json` 中缺少完全匹配的怪物 ID；
- 致命伤害来源不是玩家直接攻击或玩家投射物，或者归因信息已经过期；
- 缺少玩家会话或来源人生；
- 事件重复，或最终结果为 `not_rewardable`；
- 储备已满：即使显示已接受的视觉反馈，实际入账仍可能为零。

### 任务进度看起来没有更新

- 确认玩家当前仍是同一人生；
- 触发或重试相关的权威状态变更，或者重新进入任务提供者的交互范围；
- 确认 Game Service 与 Paper 使用相同的任务目录修订版本；
- 查看 Paper 日志中的刷新警告；
- 注意：击杀目标不会计入接取任务之前的当前人生累计击杀记录。

## 本地服务器安全

仓库中提交的本地服务器使用便于离线测试的配置，并非面向公网的生产配置。
不要将其中的 PostgreSQL 凭据、离线模式服务器或资源包托管服务暴露给不受信任的网络。
