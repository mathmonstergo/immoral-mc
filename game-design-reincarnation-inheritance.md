# 轮回与传承系统设计 + 开发路线图

> 关联文档：architecture-v2.md（整体架构）、ADR-001（Game Services 架构选型）
> 本文档覆盖三个互相联动的系统：死亡分区与轮回触发、装备溯源与掉落池、
> 功法道痕传承。三者共用同一个技术前提——Player 模块需要拆成
> "账号（Account）"和"世代（Life）"两层，这是本文档最先要定下来的事。

---

## 一、系统总览

    Account（永久，跟登录绑定）
      ├── account_technique_marks   功法道痕，永久挂账，跨世累加
      └── Lives（世代，每轮回一次新增一条）
            ├── 灵根（每世重新检测）
            ├── 境界 / 修炼进度（每世归零）
            ├── 当前持有装备（可能在死亡时进入掉落池）
            └── 状态：存活 / 已轮回

死亡时具体发生什么，取决于死亡地点的分区等级。注意耐久损耗是完全
独立的常驻系统（装备使用即消耗，任意区域都会发生），不参与下面的
死亡判定：

    绿区 → 无惩罚，正常复活
    黄区 → 复活，但有一次"掠夺判定"（几率被夺走一件指定类型装备）
    红区 → 检查保命道具
            ├─ 有 → 消耗道具，取消轮回，濒死复活，
            │       但仍跑一次和黄区一样的"掠夺判定"（死里逃生有代价）
            └─ 无 → 触发轮回：结算道痕、全部可掉落装备进池、开启新一世

---

## 二、数据模型设计

    accounts
    - account_id
    - created_at

    lives                              # 每一世一条记录
    - life_id
    - account_id
    - generation_no                    # 第几世，从1开始
    - spirit_root                      # 本世检测出的灵根，重开必重roll
    - cultivation_stage
    - status                           # alive / reincarnated
    - died_at, death_cause, death_zone_id   # 为空表示仍存活

    zones                              # Game Service 自己的权威副本，
    - zone_id                          # 从 WorldGuard 区域配置同步而来，
    - risk_tier                        # 不是每次判定都反查 WorldGuard
    - (green / yellow / red)

    item_instances
    - item_id
    - template_id
    - rolled_stats                     # 掉落/生成时定死的具体属性
    - tier                             # 境界匹配用，练气期法宝不进筑基期池子
    - droppable_on_death: bool         # 由 item 模板定义，不是所有装备都参与掉落池
    - provenance[]                     # 只追加，不覆盖：
                                        # {account_id, 角色名, 世代, 事件类型, 时间}

    region_loot_pools
    - zone_id
    - tier
    - item_instance_ids[]              # 等待被同tier怪物刷出的历史装备

    technique_definitions
    - technique_id
    - max_level                        # "满层"的判定基准
    - tier
    - mark_value_per_layer             # 每层道痕加成值，随tier不同而不同

    account_technique_marks            # 永久挂账，按层数累加
    - account_id
    - technique_id
    - layer_count                      # 0~100，每次某一世练满该功法+1层
    - last_earned_at_life_id           # 记录最近一次达成是第几世

---

## 三、死亡与轮回处理流程

    on_player_death(account_id, life_id, zone_id, cause):

        zone = 查zones表(zone_id)

        if zone.risk_tier == 绿:
            正常复活，无惩罚

        elif zone.risk_tier == 黄:
            执行掠夺判定(account_id, life_id)   # 定义见下方
            正常复活

        elif zone.risk_tier == 红:
            if Item模块查到保命类道具:
                消耗该道具
                取消死亡判定，HP设为极低值，短暂无敌，正常存活
                执行掠夺判定(account_id, life_id)   # 和黄区共用同一判定，
                                                     # 死里逃生仍有代价
            else:
                # 触发轮回
                1. 结算该life：status=reincarnated, died_at, death_cause, death_zone_id
                2. 遍历该life所有 droppable_on_death=true 的装备：
                   append provenance，移入对应 region_loot_pools
                3. 创建新 life：generation_no+1，spirit_root重新roll，
                   cultivation_stage归零
                4. 通知Adapter：玩家进入新一世，触发灵根检测流程


    执行掠夺判定(account_id, life_id):
        roll 概率:
            命中 -> 从该life当前持有的 droppable_on_death=true 装备中
                    随机选一件，append provenance记录"被掠夺"，
                    放入对应 region_loot_pools（和轮回迁出的目标位置
                    完全一样，见第四节——两种触发方式，同一份装备
                    集合、同一个去处）
            未命中 -> 无事发生

耐久不参与这条流程：耐久是装备使用即消耗的常驻系统，任意区域、
任意时刻都在发生，和死亡、分区无关，单独在 Item 模块里维护，详见
第四节。

Adapter 只上报"玩家在哪死的、怎么死的"，红区道具够不够、要不要触发
轮回，这个判断完全在 Game Service 里做——延续第七节战斗服务端权威
原则，不能让 Paper 插件自己判断轮回逻辑。

---

## 四、装备耐久、掉落与溯源机制

这一节包含三个独立但共享同一份"装备集合"的机制：耐久消耗、死亡
掠夺判定、轮回装备迁出。三者触发条件完全不同，但除耐久外都只作用于
被标记 `droppable_on_death=true` 的装备。

### 4.1 耐久（常驻，与死亡无关）

装备每次被使用（攻击、格挡、施法等，具体触发点由你在 Item 模块定义）
就消耗一点耐久，不区分绿黄红区，不因为死亡触发。这是一个独立的、
一直在跑的系统，跟本文档其他机制没有耦合关系。

### 4.2 死亡掠夺判定（黄区死亡 / 红区保命道具触发后）

两种情况共用同一个判定（见第三节"执行掠夺判定"）：命中则从当前
持有的 `droppable_on_death=true` 装备中随机选一件，标记"被掠夺"，
放入 region_loot_pools。

### 4.3 轮回装备迁出（红区无保命道具，真正触发轮回时）

不是概率判定，而是把该 life 所有 `droppable_on_death=true` 的装备
全部迁出，append provenance，放入 region_loot_pools——这是"真正
死亡、失去一切"和"死里逃生、小概率损失一件"的核心区别。

### 4.4 掉落池检索（其他玩家如何捡到这些装备）

装备本身要么在 Item 模块里被标记 `droppable_on_death=true`（比如捡来的
杂鱔法宝），要么标记为 false（比如任务专属、非卖品）——这个标记由你
在设计具体装备模板时逐件决定，不是引擎强制的规则。

进池子时按 `tier` 分桶，怪物掉落检索只从匹配自己 tier 的桶里抽，避免
"练气期小怪掉出筑基期传家宝"这种破坏感。

    on_mob_kill(mob_tier, zone_id):
        照常执行原有掉落表判定
        额外 roll 一次"传承装备"判定：
            命中 -> 从 region_loot_pools[zone_id][mob_tier] 里
                    随机抽一件，append provenance记录"新主人"，
                    给玩家；从池子里移除
            未命中 -> 无事发生

`provenance` 是只追加的历史链，不是覆盖式的"当前拥有者"字段——这样
以后想做"历任持有者"的完整展示（类似传奇装备的flavor text），直接
查这个 list 就行，不用改数据结构。

---

## 五、功法道痕机制（永久挂账，已确认）

**触发时机的一处理解，需要你确认**：我把触发点定在"功法练到满级的
那一刻"，而不是"角色轮回死亡的那一刻"。理由是：这样玩家在同一世
存活期间练满一门功法，账号立刻就能感受到永久回馈，不用等到死了才
知道生效没生效，体验上更即时。如果你想要的是"死亡结算时才统一
检查"，告诉我改，逻辑不复杂。

    on_technique_reach_max_level(account_id, technique_id, current_life_id):
        if account_technique_marks 中已存在该 technique_id:
            无操作（同一功法只挂账一次，不会因为下一世重复练满而叠加，
                    见下方"待确认"）
        else:
            插入 account_technique_marks:
                mark_value = 该功法定义的固定加成值
                first_earned_at_life_id = current_life_id

    on_new_life_technique_selected(account_id, technique_id):
        if account_technique_marks 中存在该 technique_id:
            对该功法的修炼属性叠加 mark_value

---

## 六、我做的假设 / 需要你确认的参数

以下几处目前没有明确设定具体数值或规则，我按"倾向保守、避免破坏
轮回意义"的原则给了默认方案，都是配置层面的东西，不影响现在动手
搭数据结构：

1. **红区保命道具触发后是否仍有惩罚**：目前设定为"完全免罚，纯粹
   保命"。另一种做法是"免轮回，但仍按黄区规则跑一次掉落/耐久判定"，
   作为"死里逃生的代价"。哪种手感更符合你想要的，后面调整
   `on_player_death` 里红区分支即可。
2. **同一功法在不同世重复练满是否叠加**：目前设定为"只挂账一次，
   不叠加"，避免道痕系统变成"反复刷同一功法无限堆属性"，削弱
   轮回"重新开始"的意义。如果你想要的是有上限的多次叠加（比如
   最多叠3次），也是配置层面的调整。
3. **黄区"掉落 vs 耐久损耗"的判定概率**：目前只搭了判定框架，具体
   数值属于后期数值调优的范畴，不建议现在就定死，先用一个明显宽松
   的默认值（比如10%掉落，其余走耐久）跑通流程即可。

---

## 七、开发路线图

延续架构文档里"垂直切片"的方法，不要一次性把整套轮回系统焊死再测试。
建议顺序：

**阶段一：单世角色闭环（暂不含轮回）**
在 Player/Cultivation 模块里先按"一个账号=一个life"跑通原有的垂直
切片（进灵根检测→加入宗门→学功法→打怪→突破→存档），配合 MythicMobs
+ MMOItems 完成最基础的打怪掉落。这一步的目的是先把地基打稳，轮回
系统的复杂度先不引入。

**阶段二：账号/世代拆分**
把 `accounts` / `lives` 表结构落地，即使还没有真正的轮回触发条件，
先证明"一个账号下可以有多条life记录、新life不继承旧life任何数据"这
条链路走得通。这一步趁现在改动成本低的时候做，晚做代价会高很多
（前面已经讨论过原因）。

**阶段三：死亡分区与轮回触发**
先只做2个测试区域（一个黄、一个红），把 `zones` 表、保命道具判定、
轮回触发流程跑通。不用一开始就覆盖游戏里所有区域，先验证机制本身
对不对。

**阶段四：装备溯源与掉落池**
在阶段三跑通之后再做，因为它依赖阶段三的死亡事件作为触发源。先做
一件测试装备标记 `droppable_on_death=true`，验证"死亡进池子→怪物
掉落里抽出来→provenance链正确"这条完整路径。

**阶段五：功法道痕**
最后做，因为它依赖 Cultivation 模块的功法等级系统已经稳定。先验证
单条链路：练满一门测试功法→账号层出现道痕→开新一世选同功法→加成
生效。

每个阶段结束都对照第八节（测试策略）写一条端到端测试，改动了就跑，
不要靠"感觉对了"验收。
