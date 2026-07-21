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
| 物品交付 | `item_code`, `required_quantity` | 玩家实际背包中的权威实体物品数量充足；交付时消耗准确实例 | 立即计入 |
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

Paper 在交付时扫描玩家实际背包中的实体 `item_instance_id`，Game Service 再校验实例属于
当前人生、状态为 `owned`、位置为 `inventory` 且 `item_code` 匹配。Game Service 会在同一
事务中重新验证任务状态和全部物品实例，只消耗目标配置要求的数量，然后完成任务并发放
奖励；超出需求的物品会留在背包中。数量不足、重复实例、身份冲突或提交期间背包状态已经
变化时不会消耗任何物品。仅有同名原版物品、伪造名称/Lore 或存放在地区仓库中的实例都
不能交付。

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
    ProximityBarkRule,
    QuestCategory,
    QuestDefinition,
    QuestDialogueKeys,
    QuestPresentationHints,
    QuestProviderDefinition,
    QuestRepeatability,
    QuestStateCondition,
    RealmLevelCondition,
    RealmLevelObjectiveDefinition,
    TechniqueLayerObjectiveDefinition,
)

TRIAL = QuestDefinition(
    quest_id="foundation-trial",
    version=1,
    title="筑基试炼",
    description="收集材料并完成试炼，证明自己已经具备筑基资格。",
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
    ),
)

TRIAL_MASTER = QuestProviderDefinition(
    provider_id="trial-master",
    display_name="试炼执事",
    main_quest_ids=(),
    side_quest_ids=("foundation-trial",),
    proximity_bark_rules=(
        ProximityBarkRule(
            rule_id="foundation-trial-ready",
            text="你已通过试炼。",
            conditions=(
                QuestStateCondition(
                    "foundation-trial", ("ready_to_turn_in",)
                ),
                RealmLevelCondition(minimum_level=14),
            ),
            priority=100,
            cooldown_seconds=60,
        ),
        ProximityBarkRule(
            rule_id="foundation-trial-active",
            text="试炼尚未完成。",
            conditions=(
                QuestStateCondition("foundation-trial", ("active",)),
            ),
        ),
        ProximityBarkRule(
            rule_id="foundation-trial-available",
            text="想参加筑基试炼吗？",
            conditions=(
                QuestStateCondition("foundation-trial", ("available",)),
            ),
        ),
    ),
)
```

将两个定义与现有任务/提供者一起加入 `QUEST_CATALOG`。除非有意移除对应内容，
否则不要删除 `FIRST_STEPS` 或 `OLD_MAN`。

校验规则：

- 稳定 ID 必须匹配 `[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}`；其中提供者的
  `provider_id` 和靠近话语规则的 `rule_id` 不得包含 `:`；
- 任务版本必须为正数；当已存储语义变得不兼容时，必须修改版本；
- 所有前置任务和提供者 ID 都必须存在于同一目录中；接取和交付提供者列表均不能为空、
  不能重复，并且任务与提供者必须双向声明同一关系；
- 数量/计数必须为正数，层数为 1 至 13，等级为 1 至 22；
- MythicMobs 目标必须存在于战斗奖励目录，功法目标必须存在于功法目录且目标层数不超过
  该功法上限，境界目标必须存在于境界目录；拼错引用会使 Game Service 启动失败；
- 物品目标目前只校验稳定物品 ID；完整权威物品目录尚未加入。

## 配置靠近 NPC 说话

靠近说话和右键任务界面是两条独立流程。玩家从范围外进入范围内时，Paper 请求或读取
Game Service 的权威任务投影；如果提供者规则命中，NPC 会向该玩家显示一条私有话语。
右键同一个 NPC 仍然直接打开六行任务界面，不需要再次右键确认，也不使用旧的任务邀约
会话或头顶标签。

`QuestProviderDefinition.proximity_bark_rules` 是可选配置。未配置规则、或没有规则命中时，
该提供者保持安静，因此只需要为重要任务或重要 NPC 配置。规则属于提供者模板；多个
Citizens NPC 绑定同一个提供者时会共享这些规则。需要不同话语时，应创建不同的提供者
模板。

当前支持的条件：

| 条件 | 字段 | 含义 |
|---|---|---|
| `QuestStateCondition` | `quest_id`, `states` | 引用任意已知任务；`states` 可使用 `unavailable`、`available`、`active`、`ready_to_turn_in`、`completed` |
| `RealmLevelCondition` | `minimum_level`, `maximum_level` | 当前人生的权威境界等级范围，边界均包含；至少填写一项，范围为 0 至 22 |

靠近规则没有 `life_id` 或 `expected_life_id` 条件。Game Service 每次都使用玩家“当前人生”
的权威事实进行匹配，因此换成任意新人生后，只要任务状态、境界等条件相同，就能触发同一
规则。API 中的 `expected_life_id` 仅用于保护接取/提交写操作，防止旧界面请求误改新人生。

一条规则内的多个条件使用逻辑与（AND）；需要逻辑或（OR）时，创建多条规则。同一规则的
同一个任务不能重复配置任务状态条件，境界范围条件也不能重复。规则按 `priority` 从高到低
选择第一条命中的规则；优先级相同时保持声明顺序。空 `conditions` 是显式的无条件兜底规则。

`rule_id` 在同一提供者内必须唯一，并用于稳定的冷却键。靠近话语使用
`<provider-id>:<rule-id>` 作为稳定键，因此两个 ID 都不能包含 `:`，组合键长度最多 256 个
字符；`text` 必须是去除首尾空白后的非空文本；`cooldown_seconds` 范围为 1 至 86400，
默认 60。规则引用不存在的任务、重复
规则 ID 或非法等级会使 Game Service 启动失败。修改规则后需要重启 Game Service；Paper
仍只接收已经解析好的 `key`、`speaker`、`text` 和 `cooldown_seconds`，不会自行判断任务
或境界条件。

成就条件尚未开放：当前项目没有权威成就状态与单调修订来源。后续加入成就模块后会扩展
同一个 typed condition union；在此之前不要在 Paper 配置或推断成就状态。

## 任务对话键

`QuestDefinition.dialogue_keys` 仍是任务定义中的稳定状态标识，但当前 Citizens 任务流程
不会按这些键读取 `plugins/ImmortalMC/dialogues/*.yml`。任务名称、描述、目标、奖励和操作均由
六行任务界面显示，因此新增任务不需要创建四份状态对话 YAML。

需要独立的通用 NPC 对话时，按 [NPC 与对话](npcs-and-dialogues.md)创建并绑定
`npc-dialogue` 内容。若同一个 Citizens NPC 同时绑定任务提供者与通用对话，任务界面优先。

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

## 配置任务奖励

任务可以配置固定实体物品和固定未炼化修为奖励：

```python
from immortal_mmo.quest.models import (
    FixedItemRewardDefinition,
    UnrefinedCultivationRewardDefinition,
)

rewards=(
    FixedItemRewardDefinition(
        reward_id="starter-technique-manual",
        item_code="technique_manual:GF_YinqiShu_01",
        quantity=1,
        technique_id="GF_YinqiShu_01",
    ),
    UnrefinedCultivationRewardDefinition(
        reward_id="starter-cultivation",
        amount=50,
    ),
)
```

`reward_id` 在任务内必须唯一。固定物品奖励会创建独立 `item_instance_id` 并进入待投递状态；
功法秘籍的 `item_code` 与 `technique_id` 必须准确对应。固定未炼化修为直接写入权威储备，
不受地区、境界、闭关速度或产出倍率影响；达到储备上限的剩余部分会保持待领取状态，可通过
权威领取 API 在容量释放后继续领取。VIP 奖励倍率尚未实现。

当前 `first-steps` 已配置 1 本引气术秘籍和 50 点未炼化修为。实体物品的投递、对账和使用
参见[实体物品与功法秘籍](physical-items-and-technique-manuals.md)。

## 玩家交互

- 进入配置半径后，只有命中提供者靠近规则时才显示对应的私有话语；未配置规则的 NPC
  不会说话。
- 右键点击已绑定的 Citizens 任务 NPC，会打开 ImmortalMC 管理的六行箱子任务界面。
- 已接受的任务会显示在 `修仙纪事` 侧边栏中，最多包含 12 行目标和一条下一步行动提示。
- 相关的战斗、物品、修炼、功法和境界变更会异步刷新权威投影。任务奖励实体物品完成
  投递确认、物品存入地区仓库或从地区仓库取回后，也会主动刷新任务侧边栏。
- 已完成任务的投影会保持完成状态，即使之后相关状态发生回退。

### 任务列表

任务列表和任务详情都使用六行箱子界面。前 45 格显示内容，最下面一行保留给返回、翻页、
刷新、确认和关闭等操作。玩家不能把背包物品放入任务界面，也不能从界面中取出展示物品。

- 尚未接取且可以接取的任务使用 `BOOK`；已经接取的任务使用 `WRITTEN_BOOK`。
- 可以查看的条目只显示任务名称和 `点击查看！`，左键后进入完整详情。
- 尚未满足前置条件的任务仍会显示为 `BOOK`，Lore 使用红色 `暂未解锁`；该条目不可点击，
  也不会发送接取或提交请求。
- 排序依次为可提交、进行中、可接取、暂未解锁、已完成。已完成任务使用灰色并始终置底。
- 所有有意留空、不可交互或用于分隔章节的格子统一使用无名称
  `GRAY_STAINED_GLASS_PANE`。整行灰色玻璃板可作为详情章节之间的分隔线；点击或拖动物品
  到这些格子都不会产生效果。

任务列表不展示任务描述、目标进度或奖励，也不能通过右键列表条目快捷接取或提交。

### 任务详情与确认

左键可查看的任务后会打开完整详情页，其中包含任务描述、每个目标的独立进度、奖励预览、
当前状态以及与状态对应的主操作：

- 可接取任务显示 `确认接取`；
- 已接取但尚未完成的任务显示不可用的操作项，不会发送提交请求；
- 已满足全部目标的任务显示 `确认提交`；
- 当接取 NPC 与交付 NPC 不同时，在错误的提供者处查看详情会显示
  `请前往任务发布者接取` 或 `请前往交付 NPC`，不会误报为前置条件未解锁或目标未完成；
- 返回、关闭或直接关闭箱子不会修改任务或物品状态。

物品目标只是当前背包和预计消耗量的只读预览，不是上交槽、临时托管区或仓库。每种材料
独占一行，并在任务详情和 `修仙纪事` 中统一使用以下格式：

```text
<材料> <背包数量> / <需求>
```

例如 `玄铁 20 / 15` 表示背包当前有 20 个，任务需要 15 个；界面不会把 20 截断为 15，
也不会添加“上交”“提交消耗”或“提交后剩余”等标签。

玩家点击 `确认提交` 后，Paper 只提交当前背包扫描到的实体物品实例 ID。Game Service 会
原子重新验证任务仍可提交、实例仍属于当前人生和背包，并且数量仍然充足，然后只扣除每个
目标要求的数量。任何一项不足或状态过期都会使整个提交失败，不会部分扣除；多余材料保持
不变，奖励也只会成功发放一次。

该界面只负责 Citizens 任务 NPC 的任务浏览、接取和提交，不包含系统商店、Merchant 交易、
物品押金槽或地区仓库操作。地区仓库仍使用[地区仓库](regional-storage.md)中记录的独立入口。

## 验证清单

1. 重启 Game Service，并确认 `/api/v1/quest-providers` 包含新的提供者和修订版本。
2. 运行 `/immortal quest reload`，然后运行 `templates`。
3. 绑定一个真实的 Citizens NPC，并在 Paper 重启后通过 `info` 验证绑定。
4. 右键 NPC，验证六行任务列表、锁定条目、完成任务置底、详情页和灰色玻璃分隔。
5. 从详情页接取任务，并检查详情与侧边栏中每一行目标的格式和进度。
6. 验证接受任务前的击杀不会计入，重复事件也不会被计算两次。
7. 验证物品不足时不会消耗任何物品；数量充足时只消耗需求量，多余物品保持不变。
8. 验证只有指定功法/境界能够完成状态目标，无关功法或境界不能完成目标。
9. 从范围外靠近 NPC，验证任务状态或境界变化会选择新的 `rule_id` 和话语；没有命中规则
   时保持安静，右键仍然打开任务界面。
