# 命令与权限

ImmortalMC 当前只注册一个根命令：`/immortal`。

## 权限节点

| 权限 | 默认 | 用途 |
|---|---|---|
| `immortalmc.command` | OP | 诊断、内容绑定、测试入口和物品发放 |
| `immortalmc.cultivation` | 所有玩家 | 闭关和突破命令 |

只有 `seclusion` 和 `breakthrough` 使用公开修炼权限，其余当前子命令都使用管理权限。

## 玩家修炼命令

| 命令 | 使用条件 | 作用 |
|---|---|---|
| `/immortal seclusion` | 仅玩家 | 打开权威功法选择界面 |
| `/immortal breakthrough <pill-count>` | 仅玩家，数量 1-10 | 发起突破并安排自动结算 |

## 诊断与测试命令

| 命令 | 使用条件 | 作用 |
|---|---|---|
| `/immortal health` | 玩家或控制台 | 异步调用 Game Service `/health` |
| `/immortal spirit-root` | 仅玩家 | 鉴定或读取当前人生的灵根 |
| `/immortal cultivation grant-item <player> foundation_pill <count>` | 同时拥有管理权限且为 OP；目标在线 | 发放 1-1,000,000 枚权威筑基丹 |

`spirit-root` 是开发/管理快捷入口，当前正式玩法也可通过鉴灵实体触发。

## 鉴灵实体管理

| 命令 | 使用条件 | 作用 |
|---|---|---|
| `/immortal spirit-root-detector create` | 仅玩家 | 在玩家位置创建受保护、由插件管理的鉴灵村民 |
| `/immortal spirit-root-detector set` | 看向 8 格内实体 | 把现有实体绑定为鉴灵实体 |
| `/immortal spirit-root-detector remove` | 看向已绑定实体 | 删除绑定；插件创建的实体也会被删除 |
| `/immortal spirit-root-detector list` | 玩家或控制台 | 列出全部绑定 |
| `/immortal spirit-root-detector reload` | 玩家或控制台 | 从 `config.yml` 重载实体交互 |

## NPC 对话管理

| 命令 | 使用条件 | 作用 |
|---|---|---|
| `/immortal npc-dialogue set <dialogue-id>` | 玩家看向实体 | 绑定已加载的对话 |
| `/immortal npc-dialogue remove` | 玩家看向实体 | 删除对话绑定，不删除实体 |
| `/immortal npc-dialogue list` | 玩家或控制台 | 列出绑定 |
| `/immortal npc-dialogue reload` | 玩家或控制台 | 重载绑定和全部对话 YAML |

目标是 Citizens NPC 时会保存持久 Citizens UUID，而不是只保存临时 Bukkit 实体 UUID。

## 任务 NPC 管理

任务命令使用 Citizens 当前选择。玩家先执行：

```text
/npc select <id|name>
```

| 命令 | 使用条件 | 作用 |
|---|---|---|
| `/immortal quest templates` | 玩家或控制台 | 列出 Game Service 已确认的 NPC 模板 |
| `/immortal quest bind <provider-id>` | 玩家已选择且 NPC 已生成 | 替换该 NPC 的任务模板绑定 |
| `/immortal quest info` | 玩家已选择 NPC | 查看当前绑定 |
| `/immortal quest list` | 玩家或控制台 | 列出所有任务 NPC 绑定 |
| `/immortal quest unbind` | 玩家已选择 NPC | 只删除 ImmortalMC 绑定，不删除 NPC |
| `/immortal quest reload` | 玩家或控制台 | 从 Game Service 刷新模板目录 |

模板目录成功确认后，`provider-id` 支持 Tab 补全。

## 常见提示

- `资料尚未载入`：等待登录同步，或检查 Game Service 是否可用。
- `No Citizens NPC selected`：以玩家身份执行 `/npc select <id|name>`。
- 模板目录不可用：确认 Game Service 已就绪，再执行 `/immortal quest reload`。
- 视线命令找不到实体：站到 8 格内并准确看向实体碰撞箱，不会自动选择最近实体。
- 权限不足：检查上面的两个权限节点及发送者是否还需要 OP 身份。
