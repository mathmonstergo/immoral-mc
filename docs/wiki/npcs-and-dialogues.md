# NPC 与对话

ImmortalMC 支持通用实体交互和持久化的 Citizens NPC 身份。Citizens 负责 NPC 创建、
皮肤、名称、导航和实体生命周期；Game Service 负责权威的任务与玩家状态。

## 对话文件

运行时对话文件位于：

```text
plugins/ImmortalMC/dialogues/<dialogue-id>.yml
```

不含 `.yml` 的文件名必须与声明的 `id` 完全一致。

```yaml
id: village-guide
title: "村中指引"
speaker: "老村民"
line-delay-ticks: 30
sound: "entity.villager.ambient"
pitch: 1.0
opening-lines:
  - "§6§l村中指引"
lines:
  - "沿着石路向北，就能看到修炼场。"
  - "遇到苍狼时不要离开安全区域太远。"
```

必填字段：

- `id`, `title`, `speaker`
- 非空的 `opening-lines`
- 非空的 `lines`

可选字段及默认值：

| 字段 | 默认值 | 约束 |
|---|---:|---|
| `line-delay-ticks` | `30` | 正整数 |
| `sound` | `entity.villager.ambient` | 有效且非空的 Bukkit 音效键 |
| `pitch` | `1.0` | 正数 |

只有缺失时，内置默认对话文件才会被复制。插件启动时不会覆盖已有的运行时文件。

## 绑定对话

创建文件后，重新加载内容：

```text
/immortal npc-dialogue reload
```

看向 8 格范围内的实体并进行绑定：

```text
/immortal npc-dialogue set village-guide
```

列出或移除绑定：

```text
/immortal npc-dialogue list
/immortal npc-dialogue remove
```

对于普通 Bukkit 实体，绑定使用世界与实体 UUID。对于 Citizens NPC，ImmortalMC 会记录
稳定的 Citizens UUID，因此 NPC 重生或服务器重启不会使内容身份失效。

## Citizens 操作流程

使用 Citizens 命令创建和管理 NPC，然后选中它：

```text
/npc select <id|name>
```

任务提供者使用[任务](quests.md)中记录的选中式操作流程。不要把临时的 Bukkit 实体 UUID
粘贴到任务绑定中。

同一个 Citizens NPC 可以同时拥有任务提供者元数据和独立对话元数据。两者同时适用时，
任务交互优先：玩家右键后会打开该提供者的六行箱子任务列表，而不是先进入通用对话。
任务列表、详情、接取和确认提交的完整规则参见[任务](quests.md)。该任务界面不承担商店
或地区仓库功能。

靠近任务 NPC 时的单句私有话语不使用本页的对话 YAML。它由 Game Service 中可选的
`QuestProviderDefinition.proximity_bark_rules` 根据权威任务状态和境界等级选择；未命中规则
时 NPC 保持安静。靠近说话不会启动右键对话会话，也不会改变右键打开任务界面的优先级。
配置方法参见[配置靠近 NPC 说话](quests.md#配置靠近-npc-说话)。

## 绑定持久化与保护

绑定是以下位置中的普通条目：

```yaml
content:
  entity-interactions:
    entries: []
```

命令流程会记录操作专用元数据，并将完整列表写回 `plugins/ImmortalMC/config.yml`。
受保护实体无法通过普通的受保护交互流程修改。

## 故障排查

- `dialogue ... is not loaded`：检查文件名与 `id`，然后重新加载。
- 找不到看向的目标：移动到 8 格范围内，并将准星对准实体碰撞箱。
- Citizens 绑定未能正确保留：确认 Citizens 先于 ImmortalMC 启用，并通过已选中的
  Citizens NPC 完成绑定。
- 启动或重新加载时 YAML 加载失败：检查必填列表、正数时间值、`sound` 和 `pitch` 字段。
