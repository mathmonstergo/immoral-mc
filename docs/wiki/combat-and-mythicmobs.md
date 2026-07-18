# 战斗与 MythicMobs 奖励

MythicMobs 负责怪物定义、生成、AI、技能和表现。Game Service 负责判定击杀是否
有效，并管理击杀对应的修为奖励、当前人生累计击杀计数、任务进度和持久化结果。

## 依赖项

- MythicMobs 免费版 `5.12.1`
- ImmortalMC Paper 适配器
- 正在运行的 Game Service 和 PostgreSQL

MythicMobs 是软依赖。缺少它时，ImmortalMC 的其他功能仍可运行，但无法记录
MythicMob 奖励，也无法使用击杀目标。

## 添加可奖励怪物

1. 使用常规的 MythicMobs 顶层键定义怪物：

   ```yaml
   AzureWolf:
     Type: WOLF
     Display: '&bAzure Wolf'
     Health: 20
     Damage: 4
   ```

2. 将完全相同的 ID 添加到：

   ```text
   game-service/src/immortal_mmo/combat/mythicmob_rewards.json
   ```

   ```json
   {
     "internal_name": "AzureWolf",
     "reward_profile_id": "ordinary-wolf",
     "telemetry": "compact"
   }
   ```

3. 确认引用的奖励配置和可选等级曲线均已存在。
4. 修改目录后重启 Game Service。
5. 按照 MythicMobs 的常规管理流程重新加载或重启其内容。

未知 ID 会返回 `not_rewardable`。系统特意不提供默认奖励。

## 奖励目录

JSON 目录包含：

- `level_curves`：以十进制字符串表示的最低/最高等级和每级奖励；
- `reward_profiles`：基础奖励及可选曲线；
- `mobs`：准确的内部名称、奖励配置和遥测模式。

`compact` 会保存不可变事实和聚合计数器。对于价值较高的遭遇，`detailed` 还会
保留配置的位置详情载荷。目录修改属于启动内容变更，需要重启 Game Service。

## 归属判定

Paper 当前会记录以下伤害来源：

- 玩家直接造成的伤害；
- 发射者为玩家的弹射物。

MythicMobs 发出死亡事件时，致命伤害来源必须仍然存在且尚未过期。ImmortalMC
不会回退使用 MythicMobs 的 `getKiller()`。

每条可奖励事实都会携带记录伤害时观察到的 `source_life_id`。身份缺失或对应的
人生已失效时会得到 `current_life_unavailable`；延迟送达的发件箱事件绝不会绑定
到转世后新建的人生。

Paper 监听器目前尚未捕获其他战斗来源类型。

## 持久化发件箱

Paper 会将捕获到的每条事实写入：

```text
plugins/ImmortalMC/combat-outbox.sqlite3
```

SQLite 数据库使用 WAL 和完全同步。感知负载的工作器会将有限大小的批次发送到：

```http
POST /api/v1/combat/mythicmob-kills/batch
```

Paper 运行时请勿删除或编辑此文件。可用以下命令检查队列状态：

```bash
sqlite3 plugins/ImmortalMC/combat-outbox.sqlite3 \
  "select delivery_status, count(*) from kill_outbox group by delivery_status;"
```

终态结果会在确认后删除。可重试的传输失败会持续保留，直到重试或耗尽策略完成处理。

## 处理结果

| 结果 | 含义 |
|---|---|
| `accepted` | 新的权威事件；奖励、计数器和任务事务已提交 |
| `duplicate` | 相同事件内容已保存；不会再次变更状态或进行展示 |
| `not_rewardable` | 怪物 ID/等级在目录中没有奖励 |
| `account_not_found` | 击杀者没有权威账户 |
| `current_life_unavailable` | 来源人生缺失、已失效或不可用 |

使用同一个事件 UUID 但修改不可变事实会产生冲突，而不是被视为重复事件。

## 玩家展示

只有结果为 `accepted` 时才会生成视觉经验球。这些经验球：

- 不包含原版经验值；
- 仅归获得奖励的玩家所有；
- 无法合并；
- 只根据怪物等级选择有上限的视觉经验球数量；
- 被拾取时会刷新修炼和任务投影。

经验球数量绝不代表权威奖励数值。

## 击杀任务

MythicMobs 击杀目标使用完全相同的 `internal_name`。只有在接取任务后，目标才会
在战斗事务中推进。当前人生累计击杀计数不会追溯复制到任务进度中。参见
[任务系统](quests.md)。

## 验证

1. 确认日志包含 `mythicmobs_integration_enabled`。
2. 确认 MythicMobs 键与 Game Service 的 `internal_name` 完全相同。
3. 生成怪物，并通过玩家直接伤害或玩家发射的弹射物将其击杀。
4. 检查 Game Service 响应/日志及发件箱数量。
5. 重放同一事件后，确认只出现一次奖励。
6. 确认接取任务前的击杀不会推进击杀目标。
