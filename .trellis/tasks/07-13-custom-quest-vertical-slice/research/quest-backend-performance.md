# Quest Backend Performance And State Contract Research

## 结论

当前垂直切片应继续使用进程内仓库，但必须把它明确限定为单进程、重启即丢失的开发阶段实现。API 从第一版就应返回一个由 Game Service 生成的完整交互快照，使 Paper Adapter 一次异步请求即可得到：

* 指定 NPC provider 下所有任务的可操作状态；
* 本次右键应使用的对话/动作提示；
* 私有靠近发言所需的状态键和文案键；
* 当前自动追踪任务及计分板标题、进度和下一步提示；
* 可用于缓存校验的 contract version、状态 revision vector 和 ETag。

接受和提交应设计为幂等的资源状态转换。Paper 不推导任务状态，不为靠近检测逐 tick 发 HTTP，也不分别请求每个任务或每个计分板字段。

## 现有代码与约束

当前实现有以下事实：

* `player/repository.py` 使用 `dict` 保存 account/current life，进程重启后全部丢失。
* `PlayerService` 是当前生命和灵根状态的权威入口；quest 模块不得直接读取 player repository。
* `POST /api/v1/players/{account_id}/current-life/spirit-root` 已经保证重复检测返回同一灵根。
* FastAPI app 当前在 `app.state` 中组装单例 `PlayerService`，quest 应沿用 route -> service -> repository 的边界。
* Paper `GameServiceClient` 使用 `sendAsync`，请求超时为 2 秒；任何结果落回 Bukkit API 前必须回到主线程。
* `PlayerSessionCache` 当前只缓存登录快照，没有 TTL、revision 或 quest 交互状态。
* PRD 要求一个 NPC provider 支持多个主线/支线任务、靠近发言不逐 tick 请求、计分板只展示一个自动追踪任务，并在没有活跃任务时隐藏。

因此，MVP 可以验证业务闭环，但不能把进程内仓库描述为持久化完成，也不能启动多个 Uvicorn worker。多 worker 会各自拥有不同的玩家和任务字典。

## 推荐状态模型

### Quest definition

任务定义是不可变、可审查的数据内容，启动时校验后加载到内存：

```text
QuestDefinition
  quest_id: "first-steps"
  title: "初入凡尘"
  category: main | side
  prerequisites: [quest_id]
  objectives: [{type: "spirit_root_detected", target: 1}]
  dialogue_keys: available/active/ready/completed
  presentation: scoreboard labels and next-action keys
```

NPC 与任务通过 `QuestProviderDefinition` 绑定，不把单个 `quest_id` 写死在 Citizens 监听器中：

```text
QuestProviderDefinition
  provider_id: "old-man"
  main_quest_ids: ["first-steps"]
  side_quest_ids: []
  proximity_radius: 6
```

定义版本应在加载时生成稳定的内容摘要，例如所有已校验定义规范化 JSON 的 SHA-256。它参与 ETag，改配置后即使玩家状态未变，也不会错误返回旧 UI。

### Quest progress

进度归属 `life_id`，最小记录为：

```text
QuestProgress
  life_id
  quest_id
  status: active | completed
  revision
  accepted_at
  completed_at
```

`available` 不是持久化行，而是“前置满足且没有 progress”的派生状态。`ready_to_turn_in` 也优先作为 `active + 当前权威目标已满足` 的派生状态，避免灵根已经存在但 quest 行仍停留在旧状态。第一条任务不需要冗余保存 `0/1`、`1/1` 或 unlock flag：

* 未检测灵根：active -> progress `0/1`；
* 已检测灵根：active -> ready_to_turn_in，progress `1/1`；
* completed 记录本身就是未来任务的前置解锁事实。

后续击杀、采集等累计目标需要 quest 模块自己保存 objective progress，但不要把所有可查询字段埋进一个 JSON；至少 `life_id`、`quest_id`、`status`、`revision` 保持为显式列。

### Cross-module player snapshot

QuestService 通过显式的 PlayerService 查询接口一次获取当前生命快照，例如：

```text
get_current_life_quest_facts(account_id)
  -> life_id, life_status, spirit_root_detected, player_revision
```

QuestService 不读取 player repository，也不接受 Paper 上报的“已检测灵根=true”。未来增加目标事实时，应扩充明确的 service contract 或引入模块内领域事件投影，不能在 quest repository 中拼接 player 表。

## 聚合 API

### Inspect/UI state

建议提供一个批量聚合端点，而不是为 dialogue、NPC 状态、proximity speech 和 scoreboard 分别建读取接口：

```http
POST /api/v1/players/{account_id}/current-life/quest-interaction-state
If-None-Match: "..."
Content-Type: application/json

{
  "provider_ids": ["old-man"]
}
```

`provider_ids` 必须去重、限制数量（例如最多 32 个），空数组允许用于登录时只刷新追踪计分板。右键时通常只传一个 provider；将来玩家同时进入多个 NPC 检测区时，可以把本 tick 新进入的 provider 合并成一次请求，避免 N+1。

建议响应：

```json
{
  "contract_version": 1,
  "account_id": "...",
  "life_id": "...",
  "revision": {
    "player": 2,
    "quest": 4,
    "definitions": "sha256:..."
  },
  "providers": [
    {
      "provider_id": "old-man",
      "state_key": "first-steps:available",
      "proximity_speech_key": "first-steps.available.proximity",
      "quests": [
        {
          "quest_id": "first-steps",
          "title": "初入凡尘",
          "category": "main",
          "state": "available",
          "action": "offer",
          "dialogue_key": "first-steps.available"
        }
      ]
    }
  ],
  "tracked_quest": null
}
```

接受后，同一响应中的 `tracked_quest` 示例：

```json
{
  "quest_id": "first-steps",
  "title": "初入凡尘",
  "objective_label": "灵根检测",
  "current": 0,
  "target": 1,
  "next_action": "前往鉴灵师处",
  "state": "active"
}
```

灵根检测后变为 `1/1`、`next_action = 返回老村民处`；提交成功后为 `null`，Paper 立即隐藏侧边栏。Paper 只渲染这些字段，不自行根据灵根或 NPC 推断状态。

响应应设置：

```http
ETag: "qis-<canonical-response-hash>"
Cache-Control: private, no-cache
```

`no-cache` 表示可保存但复用前必须验证，不等于禁止 Adapter 做短 TTL 的应用缓存。相同 provider 集合和 revision vector 可返回 `304 Not Modified`。

### Accept

使用幂等的 `PUT`：

```http
PUT /api/v1/players/{account_id}/current-life/quests/{quest_id}/accept
Idempotency-Key: <adapter operation UUID>
```

返回当前 canonical quest state，并附带完整 `interaction_state`/`tracked_quest` 聚合结果，Paper 不需要接受成功后再发一次 scoreboard 请求。

状态规则：

| 当前权威状态 | 结果 |
|---|---|
| available | 原子创建 active；`changed=true` |
| active / ready_to_turn_in | 返回现有记录；`changed=false` |
| completed | 返回 completed；不重新开启；`changed=false` |
| 前置不满足、任务不存在或不适用于当前生命 | 稳定 domain error；不创建记录 |

MVP 即使没有物品奖励，也要防止两个并发 accept 创建两行。进程内仓库用锁保护“检查 + 创建”；PostgreSQL 用 `(life_id, quest_id)` 主键/唯一约束和 `INSERT ... ON CONFLICT`。

### Turn-in

同样使用幂等 `PUT`：

```http
PUT /api/v1/players/{account_id}/current-life/quests/{quest_id}/turn-in
Idempotency-Key: <adapter operation UUID>
```

状态规则：

| 当前权威状态 | 结果 |
|---|---|
| ready_to_turn_in | 在一个事务中完成任务和奖励；`changed=true` |
| completed | 返回同一完成结果；`changed=false` |
| active 但目标未完成 | `409 quest.objectives_incomplete` |
| available / 不存在 | `409 quest.not_active` 或稳定 not-found/rule error |

当前奖励只是 completed 事实，因此 conditional update 足够。未来增加物品、货币或跨模块奖励时，必须把以下步骤放在一个数据库事务/工作单元中：锁定 progress、重新校验目标、发放奖励、写 completed、保存 operation result。若有无法加入本地事务的外部投递，则写 transactional outbox，不能先返回成功再“尽量发奖励”。

`Idempotency-Key` 对网络超时重试很重要。第一版可以依赖 PUT + progress 唯一约束得到结果幂等，但应保留请求头，并在有真实奖励前增加 `quest_operations` 去重记录。Paper 重试时必须复用相同 key，不能生成新 key。

## Version、revision 与乱序响应

这三个概念应分开：

* `contract_version`: API JSON 结构版本，当前为整数 `1`。
* `revision.player`: PlayerService 当前生命可见事实的单调 revision；首次灵根检测时递增，重复检测不递增。
* `revision.quest`: quest 模块该 life 的单调 revision；accept/turn-in 真正改变状态时递增，幂等重放不递增。
* `revision.definitions`: 任务/provider 内容摘要。
* `ETag`: 上述 revision vector、请求 provider 集合和规范化响应的摘要，只用于相等性校验。

使用 vector 而不是让 quest 模块修改 player 表，符合模块边界，也能解决“灵根变化但 quest 行没变，旧 ETag 错误命中”的问题。

ETag 不是排序号。Paper 还应给每个玩家的异步刷新维护本地 request generation：只把最新 generation 的响应应用到 NPC 私有标签和计分板，防止较慢旧请求覆盖较快新请求。mutation response 优先级高于它之前发出的 inspect；收到 mutation 成功后应使旧 inspect generation 失效。

## 缓存与失效

### Game Service

* Quest/provider definitions 启动时一次校验并加载为只读 map，按 ID O(1) 查询。
* 单个请求内只取一次 player facts、一次 quest progress 批量结果，后续对 provider/quest 的状态计算在内存完成。
* MVP 不需要 Redis。权威 progress 已经在进程内，再增加 Redis 只会制造双写和失效问题。
* PostgreSQL 阶段可以对 definitions 继续做进程缓存；玩家 progress 优先依赖正确索引，不急于加 Redis。

### Paper Adapter

建议缓存键为：

```text
(account_id, life_id, normalized provider_id set)
```

缓存值包含完整聚合响应、ETag、接收时间和 request generation。策略：

* 靠近检测只读取缓存；进入边缘时缓存缺失/过期才异步刷新。
* 展示缓存 TTL 可先设 2 秒到 5 秒；60 秒的 proximity speech cooldown 是防打扰规则，不是权威状态缓存 TTL。
* 登录、accept、spirit-root detect、turn-in、显式 refresh 成功时，用响应做 write-through 更新或主动失效。
* 任务状态 mutation 必须访问 Game Service，不能因为缓存显示 available 就在本地接受。
* HTTP 失败时可以保留现有非权威展示一小段时间，但不能伪造接受、完成、奖励或进度变化；计分板可保持最后已知值并记录 stale 状态到日志。
* 玩家退出、life_id 变化或转生时清除该玩家全部 quest cache。

为了让灵根检测只产生一次额外往返，推荐最终扩展检测响应，使 Game Service 在完成 PlayerService mutation 后调用 QuestService 生成新的 quest UI aggregate 并一并返回。若第一版保持模块 API 独立，则检测成功后 Paper 发一次明确 refresh 也可以，但不能轮询等待状态变化。

## 响应时间预算

Paper 每 tick 只有 50 ms，任何 HTTP 和 JSON 解析都不得阻塞主线程。建议目标：

| 环节 | p50 | p95 | p99/上限目标 |
|---|---:|---:|---:|
| Game Service handler（内存阶段） | < 2 ms | < 5 ms | < 10 ms |
| PostgreSQL 阶段服务端处理 | < 8 ms | < 20 ms | < 40 ms |
| localhost HTTP + JSON 端到端 | < 10 ms | < 30 ms | < 75 ms |
| 玩家可感知 click -> UI 更新 | < 50 ms | < 100 ms | < 200 ms |

当前 Java 请求 timeout 为 2 秒，可以保留为故障上限，但超过约 150 ms 时应允许显示简短的“处理中”表现，不能卡 Bukkit 主线程。inspect 不做自动重试风暴；accept/turn-in 因为是幂等 PUT，可在连接失败/超时后用同一个 `Idempotency-Key` 最多重试一次，并加小幅抖动。HTTP 4xx 规则错误不重试。

建议记录 `duration_ms`、cache hit/miss、provider_count、quest_count 和结果 revision，之后以实际 p95 调整，而不是先引入复杂缓存。

## 避免 N+1

每个 interaction-state 请求应采用固定次数的数据访问：

1. PlayerService 一次返回 current-life facts 和 player revision。
2. 根据所有 provider IDs 在内存定义 map 中展开、去重 quest IDs，并补齐它们的 prerequisites。
3. QuestRepository 一次加载该 life 对应的所有 progress；MVP 任务数少时甚至可以一次加载该 life 全部 progress。
4. 在内存中计算 available/active/ready/completed、排序 actionable quests、选择 tracked quest 和生成 scoreboard DTO。

不要做：

```text
for provider -> HTTP request
for quest -> repository query
for prerequisite -> repository query
scoreboard -> second API request
```

将来 provider 很多时，`provider_ids` 批量请求必须有数量上限，并只查询展开后的 quest/prerequisite 集合。定义内容不应每次从 PostgreSQL 逐条加载。

## 进程内仓库实现阶段

推荐 quest repository 内部结构：

```text
progress_by_key[(life_id, quest_id)] -> immutable QuestProgress
quest_revision_by_life[life_id] -> int
operation_result_by_key[(life_id, idempotency_key)] -> result  # 可延后
```

写操作使用一个短临界区锁或按 life 分片锁，锁内完成状态检查、copy-on-write 更新和 revision 增加。不要在锁内调用 PlayerService、执行 HTTP、播放 Minecraft UI 或做日志 I/O。

限制必须写进 README/spec：

* 只支持单 Game Service 进程、单 worker；
* 重启丢失所有 account/life/quest 状态；
* 不提供跨实例一致性；
* 它只用于 MVP 交互验证，PostgreSQL 上线前不能视为可运营存档。

测试至少覆盖两个并发 accept 只有一个 `changed=true`，两个并发 turn-in 只有一个完成写入，以及幂等重放不增加 revision。

## PostgreSQL 迁移建议

### quest_progress

```sql
CREATE TABLE quest_progress (
    life_id uuid NOT NULL,
    quest_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('active', 'completed')),
    revision bigint NOT NULL DEFAULT 1,
    accepted_at timestamptz NOT NULL,
    completed_at timestamptz NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (life_id, quest_id)
);

CREATE INDEX ix_quest_progress_life_status
    ON quest_progress (life_id, status)
    INCLUDE (quest_id, revision, accepted_at, completed_at);
```

主键已覆盖精确 `(life_id, quest_id)` 查询；`life_id, status` 索引用于一次读取活跃/完成状态和前置判断。不要先为低基数字段 `status` 单独建索引。

若累计目标出现，增加 `quest_objective_progress(life_id, quest_id, objective_id, current, revision, updated_at)`，主键为三列；不要为第一条派生灵根目标提前建空泛的 JSON 事件仓库。

### quest_operations

有真实奖励前增加：

```sql
CREATE TABLE quest_operations (
    life_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    quest_id text NOT NULL,
    operation text NOT NULL CHECK (operation IN ('accept', 'turn_in')),
    result jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (life_id, idempotency_key)
);

CREATE INDEX ix_quest_operations_created_at
    ON quest_operations (created_at);
```

`result` 适合 JSONB，因为它是幂等重放的冻结响应，不是核心查询字段。应制定保留/清理周期；永久的完成事实仍在 `quest_progress`，不能只存在 operations 表。

### 并发与事务

Accept 可用 `INSERT ... ON CONFLICT DO NOTHING` 后读取 canonical row。Turn-in 推荐：

1. 开事务；
2. `SELECT ... FOR UPDATE` 锁定 `(life_id, quest_id)`；
3. 通过 PlayerService/统一 unit-of-work 重新获取权威目标事实；
4. 若 completed，读取保存的 operation/canonical result；
5. 若 ready，发放奖励并更新 completed、revision；
6. 保存 idempotency result；
7. 提交事务。

也可使用带 revision/status 条件的 optimistic update：

```sql
UPDATE quest_progress
SET status = 'completed', revision = revision + 1, completed_at = now(), updated_at = now()
WHERE life_id = :life_id
  AND quest_id = :quest_id
  AND status = 'active'
  AND revision = :expected_revision;
```

但有多项奖励时，显式行锁通常更容易审查。无论选择哪种，repository 只操作 quest-owned tables；跨模块事务由 service orchestration/unit-of-work 组合各模块公开接口，不允许 QuestRepository 直接更新 player/item 表。

## 推荐实现顺序

1. 定义 quest/provider schemas、固定 `first-steps` 内容和校验测试。
2. 增加 PlayerService 的 current-life quest facts contract 与 player revision。
3. 实现带原子锁和 per-life quest revision 的 InMemoryQuestRepository。
4. 实现一次批量读取并生成 provider + tracked scoreboard 的 QuestService aggregate。
5. 实现幂等 accept/turn-in，并让 mutation response 返回新的 aggregate。
6. Paper 增加有 TTL、ETag 和 request generation 的聚合缓存；靠近检测只消费缓存并在边缘异步刷新。
7. 用计时日志和测试确认无逐 tick HTTP、无 per-quest query、无旧响应覆盖新状态。
8. 在进入可运营测试前迁移 PostgreSQL、唯一约束、事务和 idempotency operation 表。

该方案在 MVP 中保持实现量可控，同时不会把计分板、NPC 私有发言或 Citizens 交互变成新的任务状态源。
