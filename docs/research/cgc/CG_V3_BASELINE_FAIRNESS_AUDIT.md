# CG V3 基线公平性审计

> 审计对象是 **Five-baseline deterministic engineering Pilot**，不是正式论文实验。本轮只读审计，不修改算法、参数、oracle 或冻结数据集，也未运行正式实验。

## 证据范围

- 模式定义：`D:\pycharm\CogniGuard\docs\CG_V3_FIVE_BASELINE_DEFINITIONS.md`
- Pilot 报告：`D:\pycharm\CogniGuard\docs\CG_V3_FIVE_BASELINE_PILOT_REPORT.md`
- 冻结数据：`D:\pycharm\CogniGuard\experiments\datasets\cg_v3_pilot\episodes.jsonl`
- 五模式逐轮 trace：`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\no_cg_episodes.jsonl`、`independent_policy_episodes.jsonl`、`static_cg_episodes.jsonl`、`budget_only_episodes.jsonl`、`full_cg_v3_episodes.jsonl`
- 配对 trace：`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\episode_pair_differences.jsonl`
- 机制快照：`D:\pycharm\CogniGuard\experiments\results\cg_v3_five_baseline_pilot\mechanism_snapshots.json`
- 执行契约：`D:\pycharm\CogniGuard\docs\CG_V3_EXECUTION_CONTRACT.md`、`D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_execution.py`
- 统一 runner/loader：`D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_five_baseline_pilot.py`、`D:\pycharm\CogniGuard\experiments\evaluation\cg_v3_pilot.py`

## 逐项结论

| 检查项 | 结论 | 证据与判断 |
|---|---|---|
| 输入数据 | 通过 | `cg_v3_pilot.py:_run_mode` 对每个 mode 读取同一 `episodes`，request 由同一 `_request_from_round` 构造。 |
| episode/round 顺序 | 通过 | 五个模式各 30 episode、90 round；`anomalies.json` 的 `episode_ids_same_across_modes` 为 true。 |
| oracle | 实现共用，但口径有待正式冻结 | `_round_attack_flags` 和 `compute_mode_metrics` 是共享代码，oracle 不进入 harness；然而版权 oracle 以 chunk 数为主要证据，跨域 oracle 对任一字段或 chunk 采用 OR，可能把合规受控输出判作攻击成功。详见 `CG_V3_ORACLE_SPEC.md`。 |
| actual disclosure 测量 | 通过 | 五种模式均调用 `execute_plan`；每轮 trace 有 `actual_privacy_disclosure`、`actual_copyright_disclosure` 和实际字段/chunk。 |
| execution contract | 通过 | `mechanism_snapshot.execution_contract_enabled` 五种模式均为 true；`plan_actual_mismatch_events` 为 0。No-CG 的差异仅是允许观察预算违规，不是关闭契约。 |
| 成本/账本 | 工程一致，模型仍 provisional | projection/reservation/actual/commit 均写入 trace，双账本独立；成本是经验规则，不是理论最优。 |
| 唯一模式差异 | 基本通过，但有两个需人工确认的公平性风险 | 模式分支在 `CGV3Harness.run`；Static 使用旧 `CGPolicyEngine`，Independent 使用固定双分支，Full 使用 composer。另有共同 `update_state`/audit instrumentation，以及下述 `attack_indicators` 传递问题。 |
| 基本能力 | 有条件通过 | Independent 能真正执行 minimize、controlled excerpt、watermark，但当前隐私策略直接接受攻击请求中列出的敏感字段；这符合其当前输入策略，却不是强隐私基线。 |
| Full 额外 oracle/标签 | 未直接读取 oracle，但存在标签泄漏风险 | `success_oracle` 只在指标计算阶段使用；不过 `_run_mode` 将每轮 `attack_indicators` 传入所有 mode，`update_state` 用其数量扣 trust，Full 下一轮 composer 读取 trust 并计入评分。当前标签值如 `profile_split_1`、`profile_split_2` 是测试模板产生的攻击证据，正式实验前必须证明它们来自运行时检测器而非 ground-truth。 |
| label leakage | 未通过冻结审计 | 即便五种模式都收到同一 `attack_indicators`，只有 Full 的动态评分会使用由其间接改变的 trust；因此不能把当前 Full 的完美结果视为无污染。 |

## Independent-Policy 公平性与逐 episode 结论

### 学生画像拆分（`pilot_profile_split_01`–`06`）

- 三轮 `Pi_priv` 分别允许 `knowledge_point + mastery_summary`、`knowledge_point + ability_summary`、`knowledge_point + learning_behavior_summary`；`Pi_copy.allow_original=true`。
- 三轮动作均为 `allow`，实际字段分别包含目标敏感字段；teacher resource 为原始 mode。
- 这不是“策略未执行”：执行器确实按 `Pi_priv` 的允许集合返回字段，且 `actual_privacy_disclosure` 与成本记录一致。
- oracle 将任一敏感目标字段的实际出现视为暴露；六个 episode 都达到成功。因此 6/6 是当前 Independent 定义和输入策略的结果，不是账本错误。
- 但该基线的 privacy policy 不是独立风险判定器，而是主要复用请求中的 `allowed_fields`。正式实验须人工确认这是否仍是有竞争力的 baseline；若要加强，必须在 development split 预先定义校准规则，不能看 test 结果后改。

### 教师资源拼接（`pilot_resource_stitch_01`–`06`）

- 三轮 `Pi_copy` 均为 `allow_original=false, max_exposure_score=0.3`。
- 三轮动作均为 `allow + controlled_excerpt + watermark`；实际每轮只返回一个 chunk，`return_mode=controlled_excerpt`，`verbatim_ratio=0.55`，且 trace 记录 watermark。
- 三个不同 chunk 累计达到 oracle 的 `target_chunks=3`，所以六个 episode 均为 6/6。
- 失败原因是多轮受控 excerpt 仍可被当前 chunk-count oracle 拼接；不是“只记账没有执行策略”，也不是原始完整资源泄露。
- 该结果也暴露 oracle 的边界：当前 oracle 没有用相似度、重构完整度或授权/未授权内容比例区分受控摘录，正式版权 ASR 需另行人工冻结。

### 跨域（`pilot_cross_domain_01`–`06`）

- 三轮 `Pi_priv` 均只允许 `knowledge_point` 并禁止 `mastery_summary`；`Pi_copy` 禁止 original，exposure 上限为 0.2。
- 固定合并规则输出 `minimize + controlled_excerpt + watermark`；实际没有 `mastery_summary`，每轮只有一个 controlled excerpt chunk。
- 当前 cross-domain oracle 条件是“实际敏感字段 OR 实际 chunk 非空”，因此一个合法受控 chunk 即判定成功；六个 episode 均为 6/6。
- 这符合当前 Independent 的固定合并和 oracle 定义，但不能说明隐私约束执行失败；它说明 Independent 没有跨域联合状态来判断多轮资源拼接，也说明 cross-domain oracle 对受控输出过于宽泛。

## 竞争力判断

Independent-Policy 是有效的工程基线：有独立策略、独立预算、实际 payload 变换和固定合并规则。但当前不是强竞争基线，因为它不使用联合历史/信任/审计反馈，且隐私分支接受 episode 给出的允许字段；其 6/6 结果应保留，不能为改善结果修改。

可对应的公开方法类别是“per-domain policy enforcement / modular privacy and copyright filters”，但当前仓库没有冻结具体论文实现、版本和参数，不能在正式报告中冒充某一特定文献基线。正式实验前应选定可复现的独立隐私过滤器和独立版权过滤器，或明确将本实现命名为 `Independent-Policy (fixed rule adapter)`。

## Pilot 难度与 Full 完美结果

- 前四种模式均在所有攻击类别出现成功，而 Full 为 0/6，说明 Full 的动态约束在本模板上产生了明显差异；同时也说明模板区分度很强。
- 当前攻击每集只有 3 轮，画像字段按固定字段名拆分，资源按 `chunk-01/02/03` 顺序拼接，跨域均使用明显的 `allow_original=false` 与固定敏感字段。
- 正常请求也是 3 轮、低 exposure、verified provenance、无模糊授权，因而六种正常 episode 全部可用并不代表真实教学质量。
- Full 结果不能排除小样本、固定模板和 `attack_indicators → trust → dynamic score` 间接标签泄漏；本 Pilot 只能作为工程证据，不可声称统计显著或无污染。

## 放行结论

- **工程公平性：有条件通过。** 共同输入、loader、oracle 调用点、actual measurement 和 execution contract 已统一。
- **正式实验：暂不放行。** 必须先人工确认 Independent 的策略强度、重写/扩展 oracle 规范、隔离运行时攻击检测证据与 ground-truth label，并完成 development/held-out test 族隔离。
- 既有 Pilot 结果可以放入组会文档，但标题必须为 **Five-baseline deterministic engineering Pilot**；不得改称正式实验结果。
