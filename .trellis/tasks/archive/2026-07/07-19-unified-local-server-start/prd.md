# 统一本地服务器启动入口

## Goal

为 ImmortalMC 本地开发环境提供一个从仓库根目录执行的一键启动命令，只集中启动
PostgreSQL、Game Service、现有 BetterHud 资源包 HTTP 服务和 Paper，并管理三个
运行进程的 tmux 会话，减少 Wiki 中分散的手工启动命令。保留现有独立脚本作为
排错和单独重启入口。

## What I Already Know

* 当前只有 `scripts/start-game-service.sh` 和 `scripts/start-paper-server.sh` 两个
  独立脚本；没有统一启动器。
* `compose.yaml` 只定义本地 PostgreSQL，端口为 `127.0.0.1:5432`。
* Game Service 需要 `DATABASE_URL`，监听 `127.0.0.1:8000`；数据库迁移是独立的
  初始化/升级操作，不属于启动器。
* Paper 使用 `minecraft-nodes/main-server/server-port=25549`。
* 快速开始、Paper README、运维 Wiki 和 BetterHud Wiki 分别描述了启动步骤。
* 用户明确要求一键入口负责完整的本地测试运行链路，因此需要启动现有资源包的 HTTP
  服务；仍不执行迁移、构建或配置改写。

## Requirements

* 新增 `scripts/start-local-server.sh`，可从任意当前目录调用，并解析仓库根目录。
* 默认按顺序：启动并等待 PostgreSQL、加载 `game-service/.env` 并启动 Game Service、
  确认其 `/ready`、启动并确认资源包 HTTP 服务，最后启动 Paper。
* 使用固定且可发现的 tmux 会话名：`immortal-game-service`、
  `immortal-resource-pack` 和 `immortal-paper`。
* 已存在的 tmux 会话不得重复启动；命令应明确报告“复用/已存在”，而不是杀掉或
  覆盖用户正在运行的服务。
* 启动失败要返回非零状态并给出可操作的诊断（至少包含对应会话或日志位置）；不得
  把后端未就绪静默当成成功。
* 检查必要命令、`game-service/.env`、Paper JAR 和现有 BetterHud `build.zip`，缺失时
  给出清晰错误。
* 资源包服务从 `minecraft-nodes/main-server/plugins/BetterHud` 提供现有
  `build.zip`，绑定 `0.0.0.0:8164`；启动器确认 URL 可访问后再继续。
* 不执行 Alembic 迁移，不构建或替换插件/资源包，不修改任何
  `server.properties` 或其他运行时配置。
* 项目只支持 Java 25：Paper 启动器必须验证真实 Java 主版本为 25，不回退到 Java
  21；ImmortalMC 插件 Gradle toolchain 也使用 Java 25。
* `scripts/start-game-service.sh` 和 `scripts/start-paper-server.sh` 只启动现成环境；
  缺少 `.venv` 或 `server.properties` 时明确失败，不在启动阶段安装或复制文件。
* 统一入口复用两个独立启动脚本，不复制 Uvicorn 或 Java 启动细节。
* 快速开始、运维排错、Paper README 和根 README 统一以一键入口为首选，保留分步命令
  作为诊断路径；所有公开说明使用简体中文。

## Acceptance Criteria

* [x] 在已经完成初始化和迁移的本地环境执行 `./scripts/start-local-server.sh` 时，
      PostgreSQL 健康、Game Service `/health` 和 `/ready` 成功、资源包 URL 可访问，
      三个 tmux 会话按预期启动。
* [x] 重复执行启动命令不会创建重复会话，也不会终止现有服务。
* [x] 缺少 `.env`、命令、Paper JAR 或 `build.zip` 时，命令以非零状态退出并说明
      修复方式。
* [x] Game Service 未就绪时，Paper 不会被误报为已启动，且输出可定位的日志提示。
* [x] 启动器不会执行迁移、构建或配置改写；资源包服务只托管已有文件。
* [x] Java 25 可以构建和启动；只有 Java 21 时启动器清晰失败，不存在兼容回退。
* [x] `bash -n`、脚本级回归检查和 `python3 scripts/check-wiki-links.py` 通过。

## Definition of Done

* Shell 脚本遵循现有 `set -euo pipefail` 风格，路径引用安全，信号/错误处理清晰。
* 代码评审覆盖重复启动和部分启动失败。
* 公开 Wiki 与 README 同步，明确一键入口启动数据库、Game Service、资源包服务和
  Paper；初始化、迁移、构建仍是独立步骤。
* 不改变生产部署、不引入新的运行时依赖、不推送远端。

## Technical Approach

* 统一启动器只编排已有脚本和 Compose，不承载游戏业务逻辑。
* 统一入口在 Game Service tmux 命令中加载 `game-service/.env`；独立脚本继续要求调用
  方提供 `DATABASE_URL`。
* tmux 命令使用固定会话名和仓库根目录；启动器对 PostgreSQL、Game Service 和资源
  包 URL 做显式健康/readiness 检查，然后启动 Paper。

## Out of Scope

* 自动下载 Java、Paper、BetterHud、Citizens 或 MythicMobs。
* 自动执行 Alembic 迁移、Gradle/BetterHud 构建、复制插件 JAR、修改运行时
  `server.properties` 或计算资源包 SHA-1。
* 新增一键停止命令；现有 Wiki 中的正常停止命令继续使用。
* 面向公网的生产服务管理、systemd、Docker 化 Paper 或跨平台 Windows `.bat` 入口。
* 恢复 Paper 重启后的游戏内自动计时器。

## Technical Notes

* 受影响公开页面：`docs/wiki/getting-started.md`、
  `docs/wiki/operations-and-troubleshooting.md`、
  `docs/wiki/betterhud-and-resource-pack.md`、
  `minecraft-nodes/main-server/README.md` 和 `README.md`。
* 相关规范：`.trellis/spec/backend/quality-guidelines.md`、
  `.trellis/spec/guides/wiki-maintenance-guide.md`。

## Decision (ADR-lite)

**Context**: 日常测试需要四个运行组件，但初始化、内容构建和配置修改属于不同的
操作，混入启动命令会造成不可预期的副作用。

**Decision**: `start-local-server.sh` 只编排现成的 PostgreSQL、Game Service、
BetterHud `build.zip` HTTP 服务和 Paper；固定 tmux 会话并在依赖就绪后按顺序启动。
数据库迁移、Gradle/BetterHud 构建、JAR 复制和 `server.properties` 编辑继续由
操作者显式执行。项目编译与 Paper 运行统一要求 Java 25。

**Consequences**: 首次准备未完成时启动会明确失败，而不是自动修复环境；重复启动
安全复用会话，资源包测试链路可直接使用。Java 25 的测试依赖固定为 Mockito
`5.23.0`（Byte Buddy `1.17.7`）。
