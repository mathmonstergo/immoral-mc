# 任务

Game Service 负责任务定义、可用条件、目标判定、接受、完成、物品消耗、修订版本和幂等性。
Citizens 提供实体 NPC。Paper 负责显示对话、接近提示、确认信息和任务追踪侧边栏，
但不计算任务进度。

## 已发布内容与引擎支持范围

运行时目录目前只内置一个正式任务：

```text
first-steps / 初入凡尘
objective: detect-spirit-root
provider: old-man / 老村民
```

引擎支持下表列出的五种目标类型，其中四种是新增类型；但尚未内置同时使用四种新类型的
正式任务。合成测试和 PostgreSQL 测试已覆盖这些类型；内容作者必须添加实际任务后，
玩家才能在游戏中接触它们。

## 目标参考

| 类型 | 构造字段 | 完成条件 | 接受任务前的状态 |
|---|---|---|---|
| 灵根存在（`current_life_spirit_root_present`） | 无额外目标字段 | 当前人生已有灵根 | 立即计入 |
| 物品交付 | `item_code`, `required_quantity` | 当前人生的权威物品堆数量充足；交付时消耗准确数量 | 立即计入 |
| MythicMobs 击杀数量 | `mob_internal_name`, `required_count` | 接受任务后产生了足够数量、符合条件的新权威击杀 | 不计入 |
| 功法层数 | `technique_id`, `target_layer` | 指定的有效功法达到或超过目标层数 | 立即计入 |
| 境界等级 | `target_level` | 当前人生达到或超过配置的绝对等级 | 立即计入 |

同一任务中的所有目标使用逻辑与（AND）语义。每个任务支持 1 至 12 个目标。目标 ID 必须唯一，
同一任务内不能重复配置相同的目标类型与目标对象。

### 灵根存在

内置的 `first-steps` 任务使用该目标。目标固定要求当前人生拥有一个权威灵根；如果接受任务前
已经完成鉴灵，现有状态会立即计入。鉴灵入口和实体绑定请参阅[玩家与灵根](players-and-spirit-roots.md)。

### 物品交付

```python
ItemDeliveryObjectiveDefinition(
    objective_id="deliver-pills",
    label="交付筑基丹",
    item_code="foundation_pill",
    required_quantity=3,
)
```

投影只读取 Game Service 的物品堆。交付时会锁定全部所需物品堆，校验所有余额和重放身份，
然后在同一事务中消耗全部物品并完成任务。数量不足或发生冲突时不会消耗任何物品。
这里使用的不是玩家原版 Bukkit 背包。

通用目标模型接受稳定的物品 ID。在完整物品目录加入前，当前 Paper 管理员发放命令/API
只开放 `foundation_pill`。

### MythicMobs 击杀数量

```python
MythicMobKillObjectiveDefinition(
    objective_id="hunt-wolves",
    label="击杀苍狼",
    mob_internal_name="AzureWolf",
    required_count=5,
)
```

该 ID 是 MythicMobs 准确的内部名称/顶层名称，必须与 Game Service 战斗目录一致。
击杀只有在满足以下条件时才会计入：

- 任务已经处于进行中状态；
- 权威事件是新插入的记录，而不是重放；
- `occurred_at >= accepted_at`；
- `source_life_id` 与当前人生一致；
- 生物 ID 完全匹配。

当前人生的累计击杀计数不会作为任务基线。它们保留给未来的成就/统计功能使用。

### 功法层数

```python
TechniqueLayerObjectiveDefinition(
    objective_id="raise-ice-art",
    label="冰冻术达到七层",
    technique_id="Gongfa_68726c",
    target_layer=7,
)
```

`technique_id` 必须与 `game-service/src/immortal_mmo/cultivation/techniques.json`
一致。功法当前层数可以为 0，但 `target_layer` 仍必须为 1 至 13；0 层不满足第 1 层
目标，也不能配置成任务目标。其他功法不能满足该目标，已放弃的功法也不会计入。已有
进度会立即计入；交付前层数回退会使目标重新变为未完成。

### 目标境界

```python
RealmLevelObjectiveDefinition(
    objective_id="reach-foundation",
    label="达到筑基初期",
    target_level=14,
)
```

这是绝对目标，不是“提升一级”。`target_level` 必须为 1 至 22，并与
`realm_catalog.json` 中的等级 ID 一致。已有等级会立即计入；交付前发生境界回退也会反映在目标状态中。

## 编写任务

任务定义目前是 Python 启动内容，不是 YAML 或数据库记录。请编辑：

```text
game-service/src/immortal_mmo/quest/definitions.py
```

混合目标示例：

```python
from immortal_mmo.quest.models import (
    ItemDeliveryObjectiveDefinition,
    MythicMobKillObjectiveDefinition,
    QuestCategory,
    QuestDefinition,
    QuestDialogueKeys,
    QuestPresentationHints,
    QuestProviderDefinition,
    QuestRepeatability,
    RealmLevelObjectiveDefinition,
    TechniqueLayerObjectiveDefinition,
)

TRIAL = QuestDefinition(
    quest_id="foundation-trial",
    version=1,
    title="筑基试炼",
    category=QuestCategory.SIDE,
    repeatability=QuestRepeatability.ONCE_PER_LIFE,
    prerequisites=("first-steps",),
    objectives=(
        ItemDeliveryObjectiveDefinition(
            "deliver", "交付筑基丹", "foundation_pill", 3
        ),
        MythicMobKillObjectiveDefinition(
            "hunt", "击杀苍狼", "AzureWolf", 5
        ),
        TechniqueLayerObjectiveDefinition(
            "technique", "冰冻术达到七层", "Gongfa_68726c", 7
        ),
        RealmLevelObjectiveDefinition(
            "realm", "达到筑基初期", 14
        ),
    ),
    provider_ids=("trial-master",),
    turn_in_provider_ids=("trial-master",),
    dialogue_keys=QuestDialogueKeys(
        available="foundation-trial.available",
        active="foundation-trial.active",
        ready_to_turn_in="foundation-trial.ready_to_turn_in",
        completed="foundation-trial.completed",
    ),
    presentation=QuestPresentationHints(
        active_next_action="完成筑基试炼",
        ready_next_action="返回试炼执事处",
        available_proximity_text="想参加筑基试炼吗？",
        active_proximity_text="试炼尚未完成。",
        ready_proximity_text="你已通过试炼。",
    ),
)

TRIAL_MASTER = QuestProviderDefinition(
    provider_id="trial-master",
    display_name="试炼执事",
    main_quest_ids=(),
    side_quest_ids=("foundation-trial",),
)
```

将两个定义与现有任务/提供者一起加入 `QUEST_CATALOG`。除非有意移除对应内容，
否则不要删除 `FIRST_STEPS` 或 `OLD_MAN`。

校验规则：

- 稳定 ID 必须匹配 `[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}`；
- 任务版本必须为正数；当已存储语义变得不兼容时，必须修改版本；
- 所有前置任务和提供者 ID 都必须存在于同一目录中；接取和交付提供者列表均不能为空、
  不能重复，并且任务与提供者必须双向声明同一关系；
- 数量/计数必须为正数，层数为 1 至 13，等级为 1 至 22；
- MythicMobs 目标必须存在于战斗奖励目录，功法目标必须存在于功法目录且目标层数不超过
  该功法上限，境界目标必须存在于境界目录；拼错引用会使 Game Service 启动失败；
- 物品目标目前只校验稳定物品 ID；完整权威物品目录尚未加入。

## 添加任务对话

创建四个与所配置对话键匹配的运行时 YAML 文件：

```text
plugins/ImmortalMC/dialogues/foundation-trial.available.yml
plugins/ImmortalMC/dialogues/foundation-trial.active.yml
plugins/ImmortalMC/dialogues/foundation-trial.ready_to_turn_in.yml
plugins/ImmortalMC/dialogues/foundation-trial.completed.yml
```

请使用 [NPC 与对话](npcs-and-dialogues.md)中的结构。打包的默认对话既需要资源文件，
也需要显式的启动复制条目；服务器自行编写的运行时文件可以直接添加并重新加载。

## 绑定 Citizens 任务 NPC

使用新目录重启 Game Service 后：

```text
/immortal quest reload
/immortal quest templates
/npc select <id|name>
/immortal quest bind trial-master
/immortal quest info
```

选中的 Citizens NPC 必须已生成。重新绑定只会替换该 NPC 原有的任务提供者绑定。
同一个提供者模板可以由多个 NPC 复用。解除绑定绝不会删除 Citizens NPC。

## 玩家交互

- 进入配置半径后，可以显示一条根据状态变化的私有接近提示。
- 右键点击会开始对话。任务邀约对话结束时会显示私有确认提示；在邀约有效时间内再次右键即可接受。
- 已接受的任务会显示在 `修仙纪事` 侧边栏中，最多包含 12 行目标和一条下一步行动提示。
- 相关的战斗、物品、修炼、功法和境界变更会异步刷新权威投影。
- 已完成任务的投影会保持完成状态，即使之后相关状态发生回退。

## 验证清单

1. 重启 Game Service，并确认 `/api/v1/quest-providers` 包含新的提供者和修订版本。
2. 运行 `/immortal quest reload`，然后运行 `templates`。
3. 绑定一个真实的 Citizens NPC，并在 Paper 重启后通过 `info` 验证绑定。
4. 接受任务并检查侧边栏中的每一行。
5. 验证接受任务前的击杀不会计入，重复事件也不会被计算两次。
6. 验证物品不足时不会消耗任何物品，成功交付会消耗准确的配置数量。
7. 验证只有指定功法/境界能够完成状态目标，无关功法或境界不能完成目标。

当前功能范围尚未实现任务奖励。在奖励模型完成前，不要在对话中承诺奖励。
