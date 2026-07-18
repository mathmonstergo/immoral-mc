# 闭关 10 秒周期模型

## 当前问题

现实现将普通闭关的 `completes_at` 设置为功法大境界的完整满层估算时间：练气 10 小时、
筑基 20 小时、结丹 50 小时、元婴 100 小时。Paper 首次等到该时间才调用结算，active
会话之后每 60 秒重试。Game Service 虽然能按任意累计秒数计算增量，但玩家实际看不到
10 秒级成长，而且字段和文案把速度估算错误表达成了强制完成时间。

## 新公式

固定周期：

```text
cycle_seconds = 10
base_per_cycle = max(1, floor(technique_capacity * 10 / full_mastery_seconds))
realm_ratio = player_speed_weight / technique_speed_weight
per_cycle = max(1, floor(
    base_per_cycle
    * player_speed_weight
    * area_speed_basis_points
    / technique_speed_weight
    / 10000
))
```

寿命/速度权重固定为：

```text
练气=1, 筑基=2, 结丹=5, 元婴=10
```

`base_per_cycle` 由功法自身 `group_code` 的共同容量决定；跨境界只使用玩家当前大境界
与功法大境界的权重比。为保持总速度不随勾选数量增加，一次闭关只允许同组、同容量
功法，生成总量仍由既有平均分配器分给 1 至 5 门功法。

这里的比值是速度倍率，不会改变功法容量、层数成本或修为价值。固定 10 秒结算只是把
速度离散化：筑基炼练气每周期按 `2/1` 速度，元婴炼筑基按 `10/2` 速度，元婴炼结丹按
`10/5` 速度。功法曲线的 `3:2`、`17:10`、`9:5`、`2:1` 不参与此公式。

累计生成量只使用完整周期：

```text
completed_cycles = floor(elapsed_seconds / 10)
cumulative_generated = completed_cycles * per_cycle
```

这样 9 秒为 0 个周期，10 秒为 1 个，25 秒为 2 个；分段结算与一次合并结算一致。
`yield_basis_points` 也按累计值换算：先计算填满当前累计生成上限所需的最小储备，再将
累计保留量截断到该上限。不能只选择“原始保留量不超过上限”的储备，否则 `15000` 这类
高产出区域在最后几个容量点会永久无法满层。

## 会话冻结

新会话冻结：

* `cycle_seconds`
* `technique_group`
* `base_cultivation_per_cycle`
* `player_major_realm` / `player_speed_weight`
* `technique_major_realm` / `technique_speed_weight`
* `speed_basis_points` / `yield_basis_points`
* `cultivation_per_cycle`
普通闭关的 `completes_at` 仅作为首次周期可结算时刻，值为 `started_at + 10s`。Paper 的
初次调度和 active 重试都使用 200 ticks；它不计算炼化量。

## 开发期数据库处理

当前数据可丢弃，旧连续时间模型和开放会话不属于兼容范围。会话表直接使用上述最终快照
字段；实现完成后删除本地 PostgreSQL volume，从空库运行 Alembic 到 head。运行时代码
只读取周期模型，不保留旧字段、旧公式分支或回填逻辑。
