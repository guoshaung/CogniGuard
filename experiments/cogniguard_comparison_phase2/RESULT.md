# CogniGuard Phase 2 横向对比：结果

> 预注册：`PREREG.md`（冻结 `c290653`）。判定代码在 `4f418d2`（A0–A4 判定规则）提交，同样在正式运行之前推送。基线等级见 `BASELINE_AUDIT.md`。
> 被评价方法 M3 = CogniGuard-NoWM（Phase 1，`2d8e9b8`）。**不含水印、不含 RKW。**
> 正式运行：种子 0–29 × {phase1, eedi, sumleaks} × {low, high} × k ∈ {1, 2, 3}，共 **24,000 条运行汇总**（snapshot：全部规则与全部参数点；path：主要规则）。
> 文件（`results/formal/`）：
> - `analysis.json`、`metrics_table.csv`（统一指标表，含 95% 区间）；
> - `matched_targets.json`、`classification_descriptive.json`、`sensitivity_unbounded_oracle.json`；
> - `runs.jsonl.gz`；
> - `requests.jsonl.gz`（全部逐请求记录，snapshot 中每条请求带每个规则的决定）；
> - 图：`results/figures/fig1_pareto`、`fig2_coalition_size`、`fig3_efficiency`。

## 1. 有效性（A0）

| 条件 | 结果 |
|---|---|
| 未授权成功 | **0**（全部运行） |
| CA-PD 与精确联盟枚举 | 162,000 条 snapshot 请求中 **0 处不一致**（三个数据集各 54,000 条） |
| 初始状态 | eedi、sumleaks 历史违规为 0；phase1 冻结世界含历史违规（METHOD §2），另报"排除历史目标"的危险放行率（`metrics_table.csv`） |

## 2. 预注册判定 A1–A3（冻结规则：M3 效用差的下界 > 0，且危险放行率差的上界 ≤ 0.01）

| 基线 | k = 1（6 格） | k = 2、3（12 格） |
|---|---|---|
| OCELOT-PF field @ 5% | 支持 2 / 6 | 支持 7 / 12 |
| OCELOT-PF trajectory @ 5% | 支持 2 / 6 | 支持 8 / 12 |
| Sum Leaks Local | 支持 0 / 6 | 支持 0 / 12 |
| Sum Leaks CoDef | NA（k = 1 时与 CA-PD 相同） | 支持 0 / 12 |
| Sum Leaks ToM @ 5% | 支持 0 / 6 | 支持 8 / 12；4 格为 NA（phase1 开发集达不到 5%） |
| Staddon-def = CrowdControl | 支持 2 / 6 | 支持 5 / 12 |
| WS04 配额 | 支持 0 / 6 | **支持 12 / 12** |

冻结规则要求 M3 **更有用且不更危险**。"不支持"有三种含义，需要看第 3 节的分类：M3 在效用相同的情况下明显更安全、两者取舍不同、或两者等价。

## 3. 描述性分类（配对 95% 区间，M3 − 基线；不是预注册判定）

主口径：有界联盟，即 Oracle 用同一 k。k = 2、3 的 12 个单元格：

| 基线 | M3 占优 | M3 更安全、效用相同 | M3 更有用、安全相同 | 取舍（M3 更有用，基线更安全） | 等价 | 基线占优 |
|---|---|---|---|---|---|---|
| Sum Leaks Local / CoDef | — | **12 / 12** | — | — | — | 0 |
| WS04 配额 | 4 | — | 8 | — | — | 0 |
| Staddon-def = CrowdControl | — | — | 4 | 2 | 6 | 0 |
| OCELOT-PF field（6 个工作点 × 12 格） | 12 | 16 | 15 | 5 | 24 | 0 |
| OCELOT-PF trajectory | 6 | 2 | 22 | 3 | 17 | 0 |
| Sum Leaks ToM（全部工作点） | 11 | 29 | 21 | — | — | 0 |

**等目标比较**（`matched_targets.json`）：

| 单元格 | 危险 ≤ 1% | 危险 ≤ 5% | 危险 ≤ 10% | 效用 ≥ 90% | 效用 ≥ 95% | 效用 ≥ 99% |
|---|---|---|---|---|---|---|
| phase1/high/k2 | OCELOT-PF field（效用 0.418） | **M3**（危险 0.041，效用 0.994）；CrowdControl 0.698，OCELOT-PF 0.418 / 0.654 | **M3** | **M3** | **M3** | **M3** |
| phase1/high/k3 | OCELOT-PF field | **M3**（0.025，0.999）；CrowdControl 0.903 | **M3** | Staddon / CrowdControl | **M3** | **M3** |
| eedi/high/k2 | **M3**（0.001，1.000）；CrowdControl 0.984 | **M3** | **M3** | Staddon | Staddon | **M3** |
| sumleaks/high/k2 | **M3**；CrowdControl、OCELOT-PF 几乎相同（0.995–0.999） | **M3** | **M3** | **M3** | **M3** | **M3** |
| phase1/high/k1 | ToM（效用 0.786） | ToM | OCELOT-PF trajectory | M3 = CoDef | 同左 | 同左 |

phase1 中 M3 自身危险放行率为 0.025–0.041，达不到 1% 目标。k = 1 时，M3、CoDef、WS04(1) 相同，危险放行率 0.11（phase1/high）；只有更保守的方法能达到 ≤ 5%，代价是效用 0.22–0.79。

## 4. 威胁模型敏感性（事后分析，未预注册）

若 Oracle 改为**不设上限的联盟**（全体主体之并）：

- CrowdControl / Staddon-def 正是这一威胁模型下的精确规则。它们在 k = 1 的 6 格全部占优，在 k = 2、3 的 12 格中 5 格占优、7 格等价。例如 phase1/high/k2：M3 的危险放行率 0.252，CrowdControl 0.021，效用都是 1.0。
- OCELOT-PF（按全体接收方之并计费）在部分单元格对 M3 占优：field 10 格（全部在 k = 1），trajectory 13 格（k = 1 有 5 格，k ≥ 2 有 8 格）。
- 对 Sum Leaks 防御与 WS04 的结论不变。

**结论**：M3 的优势**依赖"联盟规模有界"这一威胁模型**。若部署方要防任意规模的合谋，crowd control 或 OCELOT 式全局记账才是对的选择，M3 不占优。

## 5. path 模式：联盟违规与新增秘密恢复（高传播，`metrics_table.csv`）

| 单元格 | M3 | CrowdControl | WS04 | OCELOT-PF field | Sum Leaks CoDef | B0 |
|---|---|---|---|---|---|---|
| phase1/high/k2：新增恢复 | 0.071 | 0.071 | 0.029 | **0.015** | 0.171 | 0.208 |
| phase1/high/k3：新增恢复 | 0.085 | 0.085 | **0.004** | 0.017 | 0.179 | 0.217 |
| eedi/high/k2：新增恢复 | 0.007 | **0.000** | 0.011 | 0.004 | 0.871 | 0.943 |
| sumleaks/high/k2：新增恢复 | **0.000** | **0.000** | 0.001 | **0.000** | 0.646 | 0.738 |

在 phase1 中，M3 放行更多，后续又有未记录传播，所以结束时由系统放行造成的新增恢复（0.07–0.09）**高于** WS04 与 OCELOT-PF（0.004–0.03）。这些更保守的方法以效用 0.42–0.74 换得这一点。

## 6. 效率（A4，规则判定，不含证据检测）

| 单元格 | CA-PD P50 / P95（μs） | 精确枚举 P50 / P95（μs） | P95 之比 |
|---|---|---|---|
| phase1/high/k1 | 8.4 / 22.5 | 3.1 / 8.4 | 2.7 |
| phase1/high/k2 | 9.3 / 25.4 | 6.6 / 17.9 | 1.4 |
| phase1/high/k3 | 9.5 / 26.6 | 7.2 / 54.4 | 0.49 |
| eedi/high/k3 | 57.7 / 233.8 | 183.2 / 1091.4 | 0.21 |

在 N = 9 的小场景中，k = 1、2 时 CA-PD 比朴素精确枚举慢；k = 3 时快 2–5 倍。扩展性结论见 E9。OCELOT-PF trajectory 的 P95 为 40–490 μs；其余规则 1–20 μs。

**端到端（Protocol B 中的 CogniGuard）**：

- 证据检测（Codex 在 RTX 4070 上实测、按批摊销）：BGE 约 4 ms / 端点，NLI 约 379 ms / 端点；
- 判定 ≤ 0.03 ms；
- 合计约 **0.38 s / 产物**，主要是 NLI 的开销。

## 7. Protocol B（原生完整方法）：已完成，详见 `protocol_b/RESULT_PROTOCOL_B.md`

| 方法 | 状态 |
|---|---|
| OCELOT 原生 | **NA**：没有代码、权重、C 表、B_0 或 U_R |
| Sum Leaks 原生防御（官方代码 `6e7af5d`，未修改） | 已运行：119 个场景 × 2 个目标，统一后端 glm-5.2，官方判官；留出 116 个场景 |
| CogniGuard 门控（同一任务、同一模型、同一判官） | Overall 0.336：**低于** CoDef 0.560、ToM 0.595、CoT + L + H 0.578（配对区间都在 0 以下）；高于无防御 0.216 |

**负结果**：在原生 LLM 任务上，CogniGuard-NoWM 门控不如原生 LLM 防御。主要原因是文本到单元的计量漏判（36 / 52 次泄露），其次是 E7 秘密与被攻击的推断不一致（13 次）。Protocol A 的优势建立在"单元由结构给出"之上，不能外推到端到端系统。

## 8. 结论：CogniGuard 相对现有方法是否有竞争优势

1. **相对 Sum Leaks 的防御**（本地防御、CoDef 的结构化形式）：k ≥ 2 时，M3 在效用相同的情况下明显更安全，危险放行率低 0.67–0.96，12 / 12 格如此。原因在结构上：这些防御只看单个提问者，不做跨接收方、跨防御者的联盟聚合。这是**算法差异**，因为两者用的是同一份信息。
2. **相对 OCELOT-PF**（全局并集计费、成本取精确后验）：在有界联盟口径、危险放行率 ≤ 5% 时，M3 的效用为 0.994–1.000，OCELOT-PF 为 0.13–0.65（eedi 与 phase1）；在 sumleaks 上两者几乎相同。但 OCELOT 的设计目标是防任意联盟；在不设上限的口径下，它与 crowd control 在部分格子中更好。**这是威胁模型的取舍，不是单向的优劣。**
3. **相对 Staddon（crowd control）**：
   - 在见证大小 ≤ k 的数据上（eedi、sumleaks 的多数格），两者等价，这符合命题 4；
   - 在 k < \|W\| 的 phase1 中，M3 效用高 0.10–0.38，但只防 ≤ k 人联盟；
   - 若要防任意联盟，crowd control 占优。
4. **相对 WS04 配额**：同一 k 下，M3 在 12 / 12 格中更有用且不更危险，与 E10 一致。
5. **CA-PD 相对等价精确算法**：决策完全相同；小规模下没有速度优势，k = 3 时快 2–5 倍。

**总结（Protocol A）**：在"联盟规模有界"的威胁模型下，CogniGuard-NoWM 对 Sum Leaks 式防御、固定配额，以及工作点设在低危险的 OCELOT 式全局预算，都有清晰的安全—效用优势。它不优于 crowd control 或全局记账防任意联盟的能力，这一点必须作为前提写进论文。**Protocol B 的端到端结果更差**：真实 LLM 文本下，计量漏判使 CogniGuard 门控低于 Sum Leaks 的原生 LLM 防御（见第 7 节）。

## 9. 局限

- 本轮只做到 OCELOT PF、Staddon DEF、Sum Leaks STR；没有任何忠实复现；
- Protocol B 没有原生运行；
- 第二阶段（原论文任务、新留出数据）未做；
- 实际教学任务完成质量没有测量；
- phase1 的见证为合成，eedi / sumleaks 的治理结构为合成；
- 第 4 节是事后敏感性分析，不是预注册判定。
