# 开发与测试

## 架构

```text
Minecraft/Paper 事件与命令
  -> ImmortalMC Adapter（异步 HTTP 与表现层）
  -> FastAPI Game Service（权威领域规则）
  -> PostgreSQL（持久化状态）
```

Citizens、MythicMobs 和 BetterHud 只是机制或表现层集成，不是任务、奖励、修炼或
玩家状态的替代数据源。

Game Service 是模块化单体：

- `player`：账号、生命和灵根；
- `quest`：任务目录、目标、生命周期和投影；
- `combat`：击杀事实、计数器和奖励解析；
- `cultivation`：境界、功法、闭关和突破；
- `item`：当前人生的物品栈与审计记录；
- `storage`：按当前人生和 `area_id` 隔离的分页容器、槽位和幂等移动；
- `core` / `db`：设置、错误、工作单元（Unit of Work）和 SQLAlchemy 装配。

跨模块写入共享同一个工作单元（Unit of Work）；模块不得直接访问其他模块的表。

## 后端检查

```bash
cd game-service
.venv/bin/python -m ruff check .
TESTCONTAINERS_RYUK_DISABLED=true .venv/bin/python -m pytest
```

PostgreSQL 集成测试使用 Docker/Testcontainers。禁用 Ryuk 是本地约定的工作流；
测试容器仍使用一次性数据库。

迁移检查：

```bash
.venv/bin/alembic current
.venv/bin/alembic check
```

## Paper 检查

```bash
export JAVA_HOME="$HOME/.local/share/jdks/temurin-25"
cd minecraft-nodes/main-plugin
./gradlew --no-daemon --max-workers=1 test
./gradlew --no-daemon --max-workers=1 build
```

在可行的情况下，自动化检查不要求 BetterHud/Citizens 作为正常运行时插件存在。
最后仍应使用真实 Paper 环境对面向 Minecraft 的行为执行冒烟测试。

## Wiki 检查

```bash
python3 scripts/check-wiki-links.py
```

每次公开行为变更都必须在同一变更中更新对应页面。开始实现前请阅读
[Wiki 维护](wiki-maintenance.md)。

## 内容来源

| 内容 | 权威来源 | 重载行为 |
|---|---|---|
| 任务/提供者目录 | `quest/definitions.py` | 重启 Game Service |
| MythicMobs 奖励 | `combat/mythicmob_rewards.json` | 重启 Game Service |
| 境界 | `cultivation/realm_catalog.json` | 重启 Game Service |
| 功法 | `cultivation/techniques.json` | 重启 Game Service |
| 区域 | `cultivation/areas.json` 与 Paper 长方体区域 | 重启受影响的两端 |
| 突破 | `cultivation/breakthrough_rules.json` | 重启 Game Service |
| 对话 | `plugins/ImmortalMC/dialogues/*.yml` | 重载对话 |
| 实体/NPC 绑定 | Paper `config.yml` | 使用命令或功能重载 |
| BetterHud 资源 | 插件资源 | 重新构建 jar，重启 Paper |

## 完成标准

- 业务行为在 Game Service 中实现，不在 Paper 中重复；
- 使用有类型的边界和稳定的错误契约；
- 在合适的层级添加回归测试；
- 迁移与元数据保持同步；
- Paper 主线程不会被 HTTP 请求阻塞；
- 更新相关 Wiki 页面，并从索引页链接到该页面；
- 对玩家可见的变更执行本地服务/Paper 冒烟测试。

`docs/superpowers/` 下的历史计划用于解释过去的决策，可能已经过时。Wiki 才描述
当前构建的使用方式。
