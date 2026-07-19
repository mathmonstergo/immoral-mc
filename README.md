# ImmortalMC

ImmortalMC 是一个 Minecraft 修仙 MMORPG 项目，由 Paper 适配器和权威的
FastAPI Game Service 组成。Paper、Citizens、MythicMobs 与 BetterHud 负责
Minecraft 侧的交互和展示；使用 PostgreSQL 的 Game Service 负责玩家、任务、
战斗、物品和修炼状态。

## 日常启动

完成首次配置、数据库迁移和插件安装后，在仓库根目录执行：

```bash
./scripts/start-local-server.sh
```

该命令启动 PostgreSQL、Game Service、BetterHud 资源包服务和 Paper。首次准备与
分项排错命令见[快速开始](docs/wiki/getting-started.md)。

## 中文文档

请从 [ImmortalMC 中文 Wiki](docs/wiki/index.md) 开始。Wiki 包含安装、命令、权限、
配置、玩法、内容制作、运维、故障排查和 API 参考。

常用入口：

- [快速开始](docs/wiki/getting-started.md)
- [命令与权限](docs/wiki/commands-and-permissions.md)
- [任务系统与内容制作](docs/wiki/quests.md)
- [修炼系统](docs/wiki/cultivation.md)
- [战斗与 MythicMobs](docs/wiki/combat-and-mythicmobs.md)
- [BetterHud 与材质包](docs/wiki/betterhud-and-resource-pack.md)
- [开发与测试](docs/wiki/development-and-testing.md)

`docs/superpowers/` 下的实现计划和 `.trellis/spec/` 下的工程规范只用于保存开发
历史与内部约束，不能替代公开 Wiki。
