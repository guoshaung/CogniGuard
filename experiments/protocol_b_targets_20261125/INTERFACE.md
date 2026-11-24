# 保护目标接口（Claude 综合实验 / 本侧正确性审计）

生成器在 `experiments/protocol_b_targets_20261125/generate_targets.py`。它不读攻击计划、攻击目标或 `final_inference_result`。CA-PD 内核 `check_release` 不改。

```python
from experiments.protocol_b_targets_20261125.generate_targets import (
    from_scenario_record,
    gate_targets,
    knowledge_units,
    units_owned_by,
    load_tables,
)

tables = load_tables(record["data_distribution"])
plan = from_scenario_record(
    record,
    initial_units=units_owned_by(tables, "Alice"),
    external_units=(),
    scene_id=str(scenario_id),
)
registry = TargetRegistry(gate_targets(plan))
knowledge = {"Alice": knowledge_units(plan)}
```

`from_scenario_record` 只用 `data_distribution` 和 `defense`。其余键即使在同一条记录里也不参与生成。

`plan.declared_units` 是所有者声明里点名的表，对应现在 Protocol B2 的 `policy` 臂（整组一个见证）。`plan.targets` 是完整候选：声明范围内、由 `_id` 连接唯一确定、且最小见证至少两张表的每一个属性。声明能解析但没有任何这样的属性时，才退回一个 `policy_combination` 见证，内容就是 `declared_units`。

见证类别：

| 类别 | 含义 | 是否放进 `gate_targets` |
|---|---|---|
| `initial_held` | 见证已全部在调用方给出的初始持有里（Sum Leaks 上是 Alice 自己的表） | 否 |
| `external_propagation` | 不是初始持有，但初始持有并上外部传入的单元已经盖住见证 | 否 |
| `system_new` | 至少有一个单元两边都没有，只能靠本次系统回答补齐 | 是 |

`gate_targets` 返回的是现成的 `ProtectedTarget`（`kind="student_attribute"`）。单元是 `("sl", "Agent.table")`。判定仍调用原来的 `check_release(..., k=1)`。不要把已持有目标注册进去，否则提及这些单元的回答会被当成新的违规。

综合实验仍由 Claude 做：文本计量、回放、Sensitive Blocked。这一侧只提供目标和 `audit_cases.py` 的结构审计。不要把 `gold.py` 的标签写进生成器。
