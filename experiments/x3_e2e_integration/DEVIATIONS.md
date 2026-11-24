# X3-E2E 偏离记录

冻结版本：`PREREG_X3E2E.md`，sha256 见 `PREREG_X3E2E.sha256`（冻结提交 `5d6ce72`）。以下各条都在**正式运行之前**登记。冻结的判定规则、成功门槛、臂、种子都不改。

## 1. 软件工程场景延期（登记于正式运行前）

本轮只运行教育场景。软件工程场景没有任何检测器在代码产物上的真实输出，延期另行运行，不报告其结果，也不用教育结果代替。

## 2. 数据提交（登记于正式运行前）

- **教育场景**：沿用 `codex/hsw-st@065bb82` 的真实试点输出。`codex/gate-w0-real@40213d3` 以 `065bb82` 为祖先，只新增 `experiments/gate_w0_real/`，没有给试点终点新增检测输出。所以预注册第 4 节"换一次 SHA"不触发。没有重新生成任何数据。
- **Gate W0-Real 交付的两份 pe-0.1 证据**（`provenance_evidence.jsonl` 7,440 条，`gate_evidence.jsonl` 910 条）：
  - 用 `cogniguard/provenance/compat.py` 转换到 pe-1.0，0 条失败，两份都通过正式提供方契约（`provider --formal`）；
  - 不进入教育网格。片段证据的持有者是占位符，转换后为 `UNKNOWN`；回放证据属于 Gate W0 合成控制层，Codex 已完成回放：BM25 与 BM25∪M2 在 60/60 配对运行中三项治理指标相同；
  - 源文件 sha256：`provenance_evidence.jsonl` = `08901f26…`，`gate_evidence.jsonl` = `7ec8c50b…`。

## 3. 消费者契约 C4 的实现对齐文本（登记于正式运行前）

`PROVENANCE_INTERFACE.md` 第 8 节写的是"重复、冲突、伪造的事件只计一次或不计"。`contract.py` 原来要求恰好计 1 次，比文本更严，会把"从不抵扣"这种更保守的实现判为失败。现改为与冻结文本一致：计数不超过 1，伪造不增加。接口与 schema 不变（`PROVENANCE_INTERFACE.sha256` 不变）。

## 4. 机制分解表：只增加汇总，不加臂、不改门槛（登记于正式运行前）

另外输出一张聚焦表，所用单元格都是网格中已有的：

| 列 | 臂 / 模式 / (k, f) |
|---|---|
| 仅回执 | R0_receipts / static / (1, 0) |
| 最强内容指纹 | F_STRONG / dyn_knowledge / (1, 0) |
| 动态知识状态（全部真实非水印证据） | CONTENT_ALL / dyn_knowledge / (1, 0) |
| CA-PD 联盟检查（仅回执） | R0_receipts / static / (2, 0) |
| 联合机制（动态知识状态 + CA-PD） | CONTENT_ALL / dyn_knowledge / (2, 0) |
| 理想证据上界 | IDEAL / dyn_knowledge / (1, 0) 和 (2, 0) |

**事先声明**（依据：种子 99 空跑）：在本叠加场景中，所有 k = 2 单元格的 Oracle 可放行请求数都是 0。原因是发行把每个配对事实交给了某个学生，任何考题放行都能与该学生组成 2 人联盟，补齐见证。所以：

- "动态知识状态"的独立贡献，按冻结的 H-Evidence、A-dynamic 在 k = 1 上判定；
- "CA-PD"的独立贡献无法在本场景检验，只依据已冻结的 E5–E7、E9、E10 判断；
- "联合机制相对单一机制的增量"在本场景记为**不可检验（场景退化）**，不另找场景补救。

## 5. Grok 治理实现不纳入（登记于正式运行前）

`dev/source-evidence` 尚未推送，只读探针检查了本机提交 `0e48995`：

- 经过薄适配后，消费者契约只剩 C5 失败：已核验的内容持有不进入其知识状态，只有可信日志和理想证据进入；
- 按预注册第 7 节，不纳入正式运行；
- 其历史 X1–X5 判定保持不变。

## 6. 水印结论

接受 Codex Gate W0-Real 的 STOP（真实 M2 在末五词观察中检出 0/382）。H-WM 仍按冻结规则计算并如实报告，不调整门槛。

## 7. BGE + 原版 NLI 证据条件（登记于任何 NLI 运行之前，2026-11-24）

Codex 报告：五组知识核验器对照完成，来源追踪采用 BGE + 原版 NLI（`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli@6f5cf0a`）。在 27 个无水印真实模型端点上，确认 99/137 个单元，F1 0.825；固定见证危险放行 137 → 38；不必要拒绝 4/835。**截至登记时，这些结果和逐条判定都没有推送到 GitHub**（已检查两个仓库的所有分支；最新为 `codex/gate-w0-real@631409e`，其中只有词面核验器的结果：6/137）。集成侧没有复现上述数字，也不重新推理 NLI。

正式运行前固定以下内容：

1. **证据条件**：
   - 新增臂 `F_BGE`：只读 `codex-bge@` 前缀的检索观测，即 BGE 候选资产，其登记单元作为声明；
   - 知识核验器两档：冻结的词面核验器 `lexical`，以及 `nli-replay`（回放 Codex 用冻结 NLI 给出的逐条判定，`checkers.py`）。映射：entailment → 确认，neutral / contradiction / 缺判定 → 疑似；
   - NLI 只是单元核验器，不能产生事件、凭证或预算抵扣（结构上由 `event_claim` 签名决定）；`trusted_event_credits` 恒为 0。
2. **对照与消融**（同一场景、请求、权限、CA-PD 内核）：

   | 编号 | 对照 |
   |---|---|
   | 1 | 仅回执（R0 / static） |
   | 2 | BGE + 词面核验（F_BGE / dyn_knowledge / lexical） |
   | 3 | BGE + NLI（F_BGE / dyn_knowledge / nli） |
   | 4 | BGE + NLI + 疑似层（dyn_conservative） |
   | 5 | 最强内容指纹 F_STRONG + NLI |
   | 6 | CA-PD k = 2（偏离第 4 条已声明退化） |
   | 7 | 理想上界 |

   主单元格 (k, f) = (1, 0)。
3. **主要测量是单元核验本身**（确认单元的 Precision、Recall、F1，对照标注）。危险放行的减少是它的**派生量**：在固定见证夹具中，每个被确认的单元正好挡住一个危险请求（137 − 38 = 99），所以两者不作为独立结果。独立的治理结果是误拒和效用。
4. **泛化**：
   - 如果 NLI 的任何参数（阈值、标签映射、候选数）是在试点端点上选的，就只在 Codex 指定的留出链上判定（`grid.py --test-chains`），并以链为簇报告区间；
   - 如果没有任何参数在试点上调过，则全部 15 条链都是测试样本，仍以链为簇做 bootstrap。
   - Codex 必须在推送时说明属于哪一种。不接受事后选择。
5. **门槛**：沿用 H-Evidence 的规则（下界 > 0 且效用下降 ≤ 0.01）。不调整。
6. **Grok 机制**：未推送；按设计，他的知识状态只接受可信日志或理想证据，所以 NLI 证据在他的机制下不改变知识状态。只描述，不纳入。

### 7.1 NLI 数据到位（登记于 NLI 运行之前）

- Codex 推送 `codex/gate-w0-real@fcf1374`，`unit_checker/results/judgments.jsonl`，sha256 `44b784c3…`（与其 `splits.json` 一致）。测试记录 891 条：entailment 490 条，其余为 neutral。另有 36 条校准记录，不参与运行。
- 阈值 0.9642（NLI）来自 6 个独立手写来源族的开发集，**没有使用试点端点**。所以按第 7 条第 4 款，15 条试点链全部是测试样本，不需要留出链过滤（`--test-chains` 不用）。
- 导出时，阈值后的"确认"记为 entailment，其余记为 neutral；历史上没有保留 contradiction，与映射规则一致。
- 运行：`grid --unit-checker nli-replay:<judgments.jsonl>:test`，种子 0–29，数据 `065bb82`，输出写到独立目录 `x3e2e_nli`。
