# Wiki 维护

Wiki 是发布物的一部分。当代码可以运行，但运维人员、内容作者和玩家无法发现或
使用该功能时，功能仍未完成。

## 必须更新的规则

只要公开或运维可见的行为发生变化，就必须在同一变更中更新相关的 `docs/wiki/`
页面，包括：

- 命令、参数、权限节点以及发送者/上下文限制；
- 配置键、默认值、校验规则以及重启/重载行为；
- 支持的依赖、版本、启动顺序以及可选依赖行为；
- 游戏规则、目标语义、限制和当前未实现内容；
- 内容目录字段或创作流程；
- API 路由、载荷、幂等性和错误码；
- 安装、迁移、备份、资源包或故障排查步骤。

内部 `.trellis/spec/` 更新、带日期的设计文档、源代码注释或测试，都不能替代
公开 Wiki 文档。

## 新功能页面模板

每个重要功能页面都应回答以下问题：

1. 当前已经发布了什么，明确未发布什么？
2. 谁会使用它：玩家、服务器所有者、内容作者、运维人员还是开发者？
3. 需要哪些依赖和兼容版本？
4. 如何启用或配置？
5. 涉及哪些命令和权限？
6. 权威状态来源是什么？
7. 玩家或运维人员的正常操作流程是什么？
8. 哪些变更需要重载，哪些需要重启？
9. 如何验证？
10. 常见故障和恢复步骤是什么？

在同一变更中将页面加入 [Wiki 索引](index.md)。

## 权威来源对照表

| 主题 | 主要来源 | Wiki 目标页面 |
|---|---|---|
| 命令和权限注册 | `plugin.yml`、命令解析器/运行器 | [命令与权限](commands-and-permissions.md) |
| Paper 默认值 | Adapter `config.yml` 和有类型的设置 | [配置](configuration.md) |
| HTTP 契约 | FastAPI 路由/Pydantic/OpenAPI | [API 参考](api-reference.md) 及实时 OpenAPI |
| 任务行为/目录 | `quest/models.py`、`definitions.py`、服务 | [任务](quests.md) |
| 战斗奖励/发件箱 | 战斗目录/服务、Paper 发件箱 | [战斗与 MythicMobs](combat-and-mythicmobs.md) |
| 修炼目录/服务 | 修炼 JSON 和服务 | [修炼](cultivation.md) |
| HUD/资源交付 | 已打包的 BetterHud 资源、服务器属性 | [BetterHud 与资源包](betterhud-and-resource-pack.md) |
| 运行时/启动/迁移 | 脚本、Compose、Alembic、就绪检查 | [快速开始](getting-started.md)、[运维与故障排查](operations-and-troubleshooting.md) |

避免在多个 Wiki 页面中重复复制生成的值。详细行为应集中放在一个功能页面中，
再从命令、配置和参考页面链接过去。

## 语言规则

公开 Wiki 的说明文字统一使用简体中文。命令、配置键、API 路径、标识符和代码示例
保留英文，以便可以直接复制使用；JSON/YAML 示例中的技术字面量也必须保持英文。

## 审查清单

- [ ] 已将 Wiki 影响分类为“必须更新”或“无需更新”，并说明原因。
- [ ] 已根据源码/测试而非记忆核对当前行为。
- [ ] 命令、权限、配置、依赖和限制均准确无误。
- [ ] 新增或重命名的页面已从 `index.md` 链接。
- [ ] `python3 scripts/check-wiki-links.py` 已确认标题包含中文、页面可从索引发现且
  相对链接有效。
- [ ] 现有 README 链接仍然有效。
- [ ] 未将带日期的计划/规范写成当前使用文档。
- [ ] 仅在截图能实质性澄清 UI 流程时添加，并随 UI 一起更新截图。

## 审查中的文档影响

在 PR/任务摘要中使用以下两种固定结果之一：

```text
Docs impact: required - updated docs/wiki/quests.md and commands-and-permissions.md
Docs impact: none - internal refactor; no command/config/API/gameplay behavior changed
```

只写 `none` 而不提供具体原因是不充分的。

## 发布纪律

仓库中的副本是权威版本。不要独立编辑远程 Wiki 并使其与仓库发生偏离。如果以后
引入托管 Wiki/文档站点，应从本目录单向发布或镜像。
