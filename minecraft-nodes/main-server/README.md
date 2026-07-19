# ImmortalMC 本地 Paper 服务器

此目录是供 Windows Minecraft 客户端联调使用的本地 Paper `1.21.11` 服务器。
完整安装和排错说明见 [ImmortalMC 中文 Wiki](../../docs/wiki/index.md)，尤其是
[快速开始](../../docs/wiki/getting-started.md)、
[BetterHud 与资源包](../../docs/wiki/betterhud-and-resource-pack.md)和
[运维与故障排查](../../docs/wiki/operations-and-troubleshooting.md)。

ImmortalMC 适配器和当前固定的 BetterHud `2.0.0` 都以 Java 25 为基线。本地启动
脚本只接受 Java 25，并会校验真实 Java 主版本；不会回退到 Java 21。

## 日常启动

首次配置、数据库迁移和插件安装完成后，从仓库根目录执行：

```bash
./scripts/start-local-server.sh
```

该命令启动 PostgreSQL、Game Service、现有 BetterHud 资源包的 HTTP 服务和 Paper。
三个进程分别运行在 `immortal-game-service`、`immortal-resource-pack`、
`immortal-paper` tmux 会话中。它不会执行迁移、构建插件/资源包或修改服务器配置。

重新进入控制台：

```bash
tmux attach -t immortal-game-service
tmux attach -t immortal-resource-pack
tmux attach -t immortal-paper
```

## 分项诊断

只有需要单独观察某个进程时，才直接运行已有脚本：

```bash
set -a
source game-service/.env
set +a
./scripts/start-game-service.sh
```

```bash
tmux new-session -s immortal-paper './scripts/start-paper-server.sh'
```

从会话外正常停止 Paper：

```bash
tmux send-keys -t immortal-paper 'stop' Enter
```

## 从 Minecraft 连接

在 Windows Minecraft Java Edition `1.21.11` 中查询并连接当前 WSL 地址：

```bash
hostname -I
```

使用客户端可访问的第一个地址和本地 Paper 端口：

```text
<wsl-ip>:25549
```

WSL 重启后 IP 可能变化。启用了 WSL localhost 转发时也可尝试
`localhost:25549`，不要把某次查询得到的 IP 写死到长期文档中。

## 基本检查

```text
/immortal health
/immortal spirit-root
```

`/immortal health` 是管理员诊断命令。`/immortal spirit-root` 是开发测试入口；正式
玩法通过绑定的鉴灵实体触发。

观察 Paper 日志：

```bash
tail -n 120 minecraft-nodes/main-server/logs/latest.log
```

调试和状态信息应写入 Paper 日志，玩家聊天中只显示有意设计的玩法反馈。

## MythicMobs 联调

将官方免费版 MythicMobs `5.12.1` jar 安装为：

```text
minecraft-nodes/main-server/plugins/MythicMobs.jar
```

启动 Paper 后确认 `MythicMobs` 和 `ImmortalMC` 均已启用，日志中没有
`SEVERE` 或链接错误。怪物使用原生 MythicMobs YAML 配置；顶层怪物键必须与
Game Service 奖励目录中的 `internal_name` 完全一致。

本目录的 `online-mode=false`、`enforce-secure-profile=false` 和
`prevent-proxy-connections=false` 仅用于本地测试，不能直接用于公网服务器。
