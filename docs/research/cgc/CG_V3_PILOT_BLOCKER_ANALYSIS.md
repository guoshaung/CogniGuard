# CG V3 Pilot 阻塞分层分析

## 分析范围

本分析只读取冻结的旧 Pilot 结果，不修改：

- `experiments/datasets/cg_v3_pilot/episodes.jsonl`
- `experiments/results/cg_v3_pilot/`
- `docs/CG_V3_THREE_MODE_PILOT_REPORT.md`

旧 Pilot 结果来自 30 个 synthetic episodes、每模式 90 轮。版权攻击和跨域攻击各 6 个 episode，逐轮诊断 trace 将写入新目录 `experiments/results/cg_v3_pilot_v3_1/diagnostic_traces.jsonl`。

## 根因判断

### 1. Full-CG V3 版权攻击 6/6

初步证据显示主要不是 `Pi_copy` 检测失败：高版权风险请求中 Full 选择了 `minimize + summarize` 等非 `allow` 动作，候选列表也将原始 `allow` 标记为不可行。问题出在执行/观测闭环：旧 `_allowed_outputs` 只构造了摘要资源，但旧 Pilot runner 在没有 `allowed_chunks` 时把请求 chunk 重新当作已披露资源，导致摘要被 oracle 当成原始 chunk。该部分属于 **Oracle failure / Accounting measurement failure**，需要用结构化 disclosure measurement 区分摘要、元数据和逐字 chunk。

### 2. Full-CG V3 跨域攻击 6/6

Full 的隐私候选已拒绝全部字段，版权候选已拒绝原始资源，最终动作通常是组合的 `minimize + summarize` 或预算不足时 `block`。因此当前证据不支持“未识别版权风险”结论。旧 oracle 的 chunk fallback 会把合规摘要记成资源重构，属于 **Oracle failure**；同时必须验证执行 payload 不能绕过联合约束，避免遗漏 **Execution failure**。

### 3. Static/Budget-Only 跨域末轮预算违规

旧 `degrade` 计划的 projected copyright cost 低于完整资源成本，但 `_allowed_outputs` 对 `degrade` 仍保留完整 `CR_t`，runner 随后按请求 chunk 计费。因此出现计划成本、实际资源和 ledger commit 不一致。这是明确的 **Execution failure + Accounting failure**，不是通过调阈值解决的问题。

### 4. 各层级排除情况

- **Detection failure**：旧 trace 中 Full 的 `Pi_copy` 已含 `allow_original: false` 或低 exposure 约束，暂未发现是主因。
- **Composition failure**：Full 候选中已有版权风险对应的 summarize/controlled action；暂未发现是主因，但 V3.1 trace 会显式保存联合约束。
- **Planning failure**：需要保留每个候选的可行性和分项评分；目前没有证据表明评分是唯一根因。
- **Execution failure**：已确认 `degrade` 可以泄漏完整资源；必须由执行契约阻断。
- **Accounting failure**：已确认 projected/actual/committed 不一致；必须分别记录 projection、reservation、actual、commit。
- **Oracle failure**：已确认旧 runner 把无 `allowed_chunks` 的摘要 fallback 成 chunk，版权和跨域成功率因此可能被高估。

## V3.1 修复边界

V3.1 只修复实验内核、evaluation adapter、harness 和测试：统一结构化 allowed payload、执行前预算检查、输出后 disclosure measurement、违规 rollback 和审计账本字段。Static 仍调用旧 `CGPolicyEngine`，允许记录预算违规，但不允许计划与实际输出不一致；Budget-Only 仍只使用双预算；Full 仍使用动态 composer、状态与审计反馈。不会修改前端、`server.py`、正式 Teaching Agent、旧 orchestrator 或旧结果。
