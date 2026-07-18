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

```http
Idempotency-Key: <UUID>
Content-Type: application/json
```

```json
{"provider_id": "old-man"}
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
