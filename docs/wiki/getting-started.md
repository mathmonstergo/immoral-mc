# 快速开始

本页说明如何在 WSL/Linux 中启动 PostgreSQL、Game Service 和本地 Paper，
再从 Minecraft Java Edition 连接测试。

## 环境要求

- Docker 与 Docker Compose
- Python `3.12`
- Java `25`（当前 BetterHud `2.0.0` 运行所需）
- Minecraft Java Edition `1.21.11`
- 至少 2 GB 可供本地 Paper JVM 使用的内存

ImmortalMC 插件本身以 Java 21 编译。必须使用 Java 25 是因为当前 BetterHud
`2.0.0` 使用 class-file version 69。

## 1. 配置 PostgreSQL

在仓库根目录执行：

```bash
cp game-service/.env.example game-service/.env
set -a
source game-service/.env
set +a
docker compose up -d --wait postgres
```

开发数据库仅监听 `127.0.0.1:5432`，示例密码只能用于本地测试。

## 2. 安装并迁移 Game Service

```bash
cd game-service
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/alembic current
cd ..
```

迁移必须显式执行。`start-game-service.sh` 不会自动修改数据库结构。

## 3. 启动 Game Service

当前 shell 中必须已经加载 `DATABASE_URL`：

```bash
set -a
source game-service/.env
set +a
./scripts/start-game-service.sh
```

需要后台运行时：

```bash
tmux new-session -d -s immortal-game-service \
  "set -a; source '$PWD/game-service/.env'; set +a; exec '$PWD/scripts/start-game-service.sh'"
```

检查服务：

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
```

接口文档位于 <http://127.0.0.1:8000/docs>。

## 4. 构建并安装 Paper 插件

```bash
cd minecraft-nodes/main-plugin
./gradlew --no-daemon --max-workers=1 test
./gradlew --no-daemon --max-workers=1 build
cp build/libs/immortal-main-plugin-0.1.0-SNAPSHOT.jar \
  ../main-server/plugins/
cd ../..
```

本地服务器还需要把当前固定版本的 Citizens、MythicMobs 和 BetterHud jar 放到
`minecraft-nodes/main-server/plugins/`。它们是软依赖：缺失时 ImmortalMC 其他功能
仍可启动，但对应集成功能会关闭并写入日志。

## 5. 启动 Paper

```bash
tmux new-session -s immortal-paper './scripts/start-paper-server.sh'
```

启动脚本会优先寻找 Java 25，再回退到 Java 21 路径。用日志确认 JVM 和插件状态：

```bash
tail -n 120 minecraft-nodes/main-server/logs/latest.log
```

正常启动应看到类似：

```text
betterhud_cultivation_enabled hud=immortal_cultivation
mythicmobs_integration_enabled
ImmortalMC adapter enabled
quest_provider_catalog_startup_refreshed
```

## 6. 从 Minecraft 连接

本地 Paper 端口是 `25549`。查询本次 WSL IP：

```bash
hostname -I
```

使用第一个客户端可访问的地址：

```text
<wsl-ip>:25549
```

开启 WSL 端口转发时，`localhost:25549` 也可能可用。WSL 重启后 IP 可能变化，
不要长期复制旧 IP。

## 7. 首次检查

管理员执行：

```text
/immortal health
/immortal quest templates
```

拥有默认修炼权限的玩家可执行：

```text
/immortal seclusion
/immortal breakthrough 1
```

修炼命令需要玩家资料已加载且有对应权威状态。功法获取流程尚未完成，闭关界面为空
不一定是故障。

## 正常停止

```bash
tmux send-keys -t immortal-paper 'stop' Enter
tmux send-keys -t immortal-game-service C-c
docker compose stop postgres
```

除非明确要删除全部本地数据，否则不要执行 `docker compose down -v`。详见
[运维与故障排查](operations-and-troubleshooting.md)。

