# 快速开始

本页说明如何在 WSL/Linux 中完成首次准备、日常启动本地服务器，并从
Minecraft Java Edition 连接测试。

## 环境要求

- Docker 与 Docker Compose
- tmux
- Python `3.12`
- Java `25`（ImmortalMC 构建和 Paper 运行的唯一支持版本）
- Minecraft Java Edition `1.21.11`
- 至少 2 GB 可供本地 Paper JVM 使用的内存

ImmortalMC 插件以 Java 25 编译，Paper 也只支持使用 Java 25 启动。启动脚本会验证
真实 Java 主版本，不会回退到 Java 21。

## 首次准备

以下步骤只在首次安装、数据库结构变更或插件代码变更时执行，不属于日常启动。

### 1. 配置 PostgreSQL

在仓库根目录执行：

```bash
cp game-service/.env.example game-service/.env
set -a
source game-service/.env
set +a
docker compose up -d --wait postgres
```

开发数据库仅监听 `127.0.0.1:5432`，示例密码只能用于本地测试。

### 2. 安装并迁移 Game Service

```bash
cd game-service
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/alembic current
cd ..
```

迁移必须显式执行。日常启动脚本和 `start-game-service.sh` 都不会修改数据库结构。

### 3. 构建并安装 Paper 插件

```bash
export JAVA_HOME="$HOME/.local/share/jdks/temurin-25"
cd minecraft-nodes/main-plugin
./gradlew --no-daemon --max-workers=1 test
./gradlew --no-daemon --max-workers=1 build
cp build/libs/immortal-main-plugin-0.1.0-SNAPSHOT.jar \
  ../main-server/plugins/
cd ../..
```

首次创建 Paper 运行配置：

```bash
cp minecraft-nodes/main-server/server.properties.example \
  minecraft-nodes/main-server/server.properties
```

本地服务器还需要把当前固定版本的 Citizens、MythicMobs 和 BetterHud jar 放到
`minecraft-nodes/main-server/plugins/`。它们是软依赖：缺失时 ImmortalMC 其他功能
仍可启动，但对应集成功能会关闭并写入日志。

## 日常一键启动

完成首次准备后，在仓库根目录只需执行：

```bash
export RESOURCE_PACK_PUBLIC_URL=http://<wsl-ip>:8164/build.zip
./scripts/start-local-server.sh
```

`RESOURCE_PACK_PUBLIC_URL` 应填写 Minecraft 客户端可访问的地址。未设置时，脚本会从
`hostname -I` 自动选择第一个非回环 IPv4；存在 Docker、VPN、多网卡或端口转发时，
建议始终显式设置。

该命令按顺序完成以下四件事：

1. 启动并等待 PostgreSQL；
2. 在 `immortal-game-service` tmux 会话中启动 Game Service，并等待 `/ready`；
3. 计算现有 BetterHud `build.zip` 的 SHA-1，只同步 `server.properties` 中的
   `resource-pack` 和 `resource-pack-sha1`，并在 `immortal-resource-pack` tmux
   会话中托管该文件；
4. 在 `immortal-paper` tmux 会话中启动 Paper。

重复执行时会复用已经存在的 tmux 会话，不会重复启动或终止服务。它不会执行数据库
迁移，也不会构建或复制插件/资源包。除上述两个资源包属性外，它不会修改其他 Paper
配置。若属性变化时 Paper 已在运行，脚本会提示手动重启 Paper 并重新连接客户端。

启动完成后可检查：

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
curl -fsS http://127.0.0.1:8164/build.zip -o /dev/null
tmux list-sessions
```

接口文档位于 <http://127.0.0.1:8000/docs>。

## 分项启动与诊断

只有需要单独观察或重启某个进程时，才使用以下命令。

单独启动 Game Service：

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

单独启动 Paper：

```bash
tmux new-session -s immortal-paper './scripts/start-paper-server.sh'
```

查看控制台和日志：

```bash
tmux attach -t immortal-game-service
tmux attach -t immortal-resource-pack
tmux attach -t immortal-paper
tail -n 120 minecraft-nodes/main-server/logs/latest.log
```

正常启动应看到类似：

```text
betterhud_cultivation_enabled hud=immortal_cultivation
mythicmobs_integration_enabled
ImmortalMC adapter enabled
quest_provider_catalog_startup_refreshed
```

## 从 Minecraft 连接

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

## 首次检查

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
tmux send-keys -t immortal-resource-pack C-c
docker compose stop postgres
```

除非明确要删除全部本地数据，否则不要执行 `docker compose down -v`。详见
[运维与故障排查](operations-and-troubleshooting.md)。
