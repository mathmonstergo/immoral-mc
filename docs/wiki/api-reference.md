# API 参考

Game Service 提供实时 OpenAPI 定义：

- Swagger UI：<http://127.0.0.1:8000/docs>
- ReDoc：<http://127.0.0.1:8000/redoc>
- OpenAPI JSON：<http://127.0.0.1:8000/openapi.json>

请求和响应字段的精确定义以实时接口文档为准。本页说明当前的接口分组与权威性规则。

## 健康状态

```http
GET /health
GET /ready
```

## 玩家与灵根

```http
POST /api/v1/players/login
POST /api/v1/players/{account_id}/current-life/spirit-root
```

登录接口接收 Minecraft UUID 和名称信息。灵根结果由 Game Service 生成并存储，
不能由 Paper 提交。

## 任务

```http
GET  /api/v1/quest-providers
POST /api/v1/players/{account_id}/current-life/quest-interaction-state
PUT  /api/v1/players/{account_id}/current-life/quests/{quest_id}/accept
PUT  /api/v1/players/{account_id}/current-life/quests/{quest_id}/turn-in
```

交互状态接口接收去重后的 `provider_ids` 列表，最多包含 32 项。接取和交付任务时
必须提供：

- `Idempotency-Key: <UUID>` 请求头；
- 请求界面打开时观察到的当前人生 ID：`expected_life_id`；
- 当前任务提供者 ID：`provider_id`；
- 交付任务时还要提供去重后的 `inventory_item_instance_ids`。

`expected_life_id` 只是一道写入保护，不是靠近 NPC 说话的规则条件。服务端在锁定账号和
当前人生后进行比较；如果玩家已经转生，旧界面的接取/提交请求返回 HTTP 409 和
`quest.stale_life`，不会把旧人生的点击写到新人生。任意新人生只要其当前权威任务状态、
境界等事实满足靠近规则，仍然可以触发同一句话。

当前交互状态响应使用 `contract_version: 2`。每个 `providers[].quests[]` 项包含
`description`、`state`、当前提供者对应的 `action`、`objectives` 和 `reward_previews`：

- 每个目标包含准确的 `objective_type`；物品交付目标还包含非空 `item_code`，其他目标的
  `item_code` 为 `null`；
- 每个奖励预览包含 `reward_id` 和 `kind`。`fixed_item` 使用 `item_code` 与 `quantity`，
  `unrefined_cultivation` 使用 `cultivation_amount`；
- `revision.objectives` 是当前人生目标输入的单调修订。实体物品从背包移除、放回或以相同
  数量替换时也会推进该修订；当提供者靠近规则依赖境界时，权威 cultivation revision 也会
  纳入该分量。因此客户端必须按完整修订向量丢弃过期响应，不能按物品总数或本地等级推测
  新旧；
- `providers[].proximity_bark` 是可空的已解析结果。命中规则时包含稳定 `key`、非空
  `speaker`、非空 `text` 和正整数 `cooldown_seconds`；规则、优先级和玩家条件不会下发给
  Paper。没有配置或没有命中时返回 `null`，客户端不得创建兜底任务话语。

```http
Idempotency-Key: <UUID>
Content-Type: application/json
```

```json
{
  "provider_id": "old-man",
  "expected_life_id": "20000000-0000-0000-0000-000000000001"
}
```

交付任务使用独立请求体，并且必须显式提交玩家背包中扫描到的实体物品 ID；没有物品目标时
也提交空列表：

```json
{
  "provider_id": "old-man",
  "expected_life_id": "20000000-0000-0000-0000-000000000001",
  "inventory_item_instance_ids": []
}
```

首次成功或领域失败的 HTTP 响应正文会被冻结；使用相同操作标识重试时，将重放该响应。

## 战斗

```http
POST /api/v1/combat/mythicmob-kills/batch
```

每个批次包含 1 到 200 个唯一事件 ID。`mob_level` 必须是十进制数字符串，
`occurred_at` 必须包含时区。Paper 只提交事实，不提交奖励数值或任务计数。
可获得奖励的事件必须携带匹配的 `source_life_id`。

## 修炼与物品

```http
GET  /api/v1/players/{account_id}/current-life/cultivation
GET  /api/v1/players/{account_id}/current-life/cultivation/techniques
POST /api/v1/players/{account_id}/current-life/cultivation/techniques/learn
POST /api/v1/players/{account_id}/current-life/cultivation/quest-rewards/{grant_id}/claim
POST /api/v1/players/{account_id}/current-life/cultivation/techniques/{life_technique_id}/abandon
POST /api/v1/players/{account_id}/current-life/cultivation/techniques/{life_technique_id}/transfer
POST /api/v1/players/{account_id}/current-life/items/adjustments
POST /api/v1/players/{account_id}/current-life/cultivation/seclusions
GET  /api/v1/players/{account_id}/current-life/cultivation/seclusions/{session_id}
POST /api/v1/players/{account_id}/current-life/cultivation/seclusions/{session_id}/settle
POST /api/v1/players/{account_id}/current-life/cultivation/breakthroughs
GET  /api/v1/players/{account_id}/current-life/cultivation/breakthroughs/{session_id}
POST /api/v1/players/{account_id}/current-life/cultivation/breakthroughs/{session_id}/settle
```

启动会话、功法变更和物品调整操作按照 OpenAPI 定义使用 UUID 幂等键。状态查询和
结算接口读取或推进此前创建的权威会话；客户端不得自行生成结算数值。

功法学习请求只提交权威 `item_instance_id`；`technique_id`、目录版本、资格和初始层数由
Game Service 从实体物品与功法目录推导。

实体物品投递与背包对账接口：

```http
GET /api/v1/players/{account_id}/current-life/items/pending-deliveries
GET /api/v1/players/{account_id}/current-life/items/inventory
PUT /api/v1/players/{account_id}/current-life/items/{item_instance_id}/delivery-confirmation
```

公开投影只包含物品身份、定义版本、可选功法 ID、状态和位置，不暴露内部来源字段。

## 地区仓库

```http
GET  /api/v1/players/{account_id}/current-life/storage/{area_id}?page=1
POST /api/v1/players/{account_id}/current-life/storage/{area_id}/moves
```

仓库快照包含页码、页数、45 个物品槽和容器修订版本。移动请求必须携带 UUID
`Idempotency-Key` 和预期修订版本；客户端只能提交稳定槽位/物品实例身份，不能提交可信
的最终槽位内容。过期修订会返回稳定冲突错误，客户端应重新获取页面。

## 错误封装格式

领域失败使用稳定的封装格式：

```json
{
  "error": {
    "code": "quest.not_ready",
    "message": "Quest objectives are not complete.",
    "retryable": false
  }
}
```

客户端应根据 `code` 和 `retryable` 分支处理，不要解析供人阅读的文本。只有使用
相同幂等键和请求正文时，才可以重试可重试的状态变更。

## 权威性规则

客户端可以发送操作或事实 ID、所选功法 ID、区域 ID、丹药数量、任务提供者 ID 和
事件标识。客户端不得提交需要被信任的伤害、奖励、目标进度、物品余额、功法层数、
境界、成功概率或结算结果。
