# CogniGuard 组会汇报稿

## 汇报主题

**面向教育多智能体的隐私、版权、文本水印与跨层治理实验进展**

## 一、先给出结论

本阶段完成了四个模块的开发集实验：

1. MM-FOPD：从“记录级选择”升级为“信息单元级最小披露”。
2. C²-RAG：从普通版权过滤升级为多轮累计暴露和正常—攻击配对评价。
3. HSW-ST：从单纯 KGW 水印升级为“可改写文本水印 + 关键公式/数字/术语保护”的选择性水印。
4. CGC（CogniGuard Controller）：消费三个模块提交的证据，并统一处理 capability、跨域冲突、信任、审计与回滚。

当前最重要的开发结论是：

> CogniGuard 的优势不在于某一个单项指标始终第一，而在于相同正常任务可用性下，MM-FOPD 保留更多必要画像信息，C²-RAG 降低多轮资源重构，选择性 HSW-ST 同时保持水印检测和关键教学内容，CGC 负责跨模块 capability、信任、审计与安全回滚。

当前结果仍是 development evidence，不是最终论文 test 结果。

## 二、系统如何工作

```text
用户请求
   ↓
CogniGuard Lifecycle Hooks（可接 NeMo/Fides/AgentGateway adapter）
   ↓
MM-FOPD：选择最小学生上下文
   ↓
C²-RAG：检索教师资源并生成版权候选
   ↓
Teaching Agent：生成教学回答
   ↓
HSW-ST：选择性水印、关键内容保护、来源绑定
   ↓
CGC：综合领域证据、权限、上下文边界、信任和审计
   ↓
最终 allow / summarize / variant / degrade / refuse / block
```

CGC 是框架无关的跨 Agent、跨模块、跨轮控制层。NeMo、Fides 和 AgentGateway 都是可选 adapter 或外部比较对象，不是 CGC 的必选基座。隐私预算归 MM-FOPD，版权预算和重构历史归 C²-RAG，水印策略归 HSW-ST；CGC 不重复计算三个领域的成本。

## 三、核心伪代码

### 1. MM-FOPD

```text
Algorithm MM-FOPD(Profile P, Task q, PrivacyBudget B)
    RequiredUnits ← InferRequiredInformation(q)
    K, P_strategy, S_sensitive ← OrthogonalDecompose(P)
    Candidates ← ScoreByRelevanceAttentionSensitivityAndRedundancy(P, q)
    Candidates ← RemoveIdentityAndLocalOnlyFields(Candidates)
    Selected ← SelectRequiredUnitsUnderBudget(Candidates, RequiredUnits, B)
    Aggregated ← TemporalAggregateAndResolveConflicts(Selected)
    Card ← CompressMasteryErrorAndPreference(Aggregated)
    Evidence ← MeasureActualReleasedExposure(Card, P)
    return Card, Evidence
```

### 2. C²-RAG

```text
Algorithm C2-RAG(Query q, Resources D, History H, Budget B)
    Authorized ← FilterByRolePurposeAndLicense(D, q)
    Candidates ← DenseRetrieveAndRerank(q, Authorized)
    CurrentRisk ← MeasureVerbatimFragmentAndReconstructionIntent(q, H)
    Cumulative ← MeasureCumulativeDisclosure(H)
    Actions ← BuildCandidates(summary, concept, variant, excerpt, hint, refuse)
    for each action in Actions do
        action.cost ← MeasureActualCopyrightCost(action.content)
        action.residualRisk ← EstimateReconstructionRisk(action, H)
    end for
    return Actions, CopyrightRiskEvidence(CurrentRisk, Cumulative, B)
```

### 3. 选择性 HSW-ST

```text
Algorithm Selective-HSW-ST(Draft y, SourceTrace S, Key k)
    Terms, Formulas, Numbers ← ExtractCriticalSpans(y)
    ProtectedDraft, Map ← ReplaceCriticalSpansWithPlaceholders(y)
    EditableRegions ← IdentifyNonCriticalText(ProtectedDraft)
    Generated ← ApplyKGWOnlyToEditableRegions(ProtectedDraft, k)
    Missing ← FindMissingCriticalSpans(Generated, Map)
    if Missing is not empty then
        Generated ← AppendAuditableCriticalContentCapsule(Generated, Missing, Map)
    end if
    Output ← RestoreCriticalSpans(Generated, Map)
    Evidence ← DetectWatermarkAndMeasureFidelity(Output, y)
    Evidence ← BindToAgentResourceAndAuditHash(Evidence, S)
    return Output, Evidence
```

### 4. CGC

```text
Algorithm CGC(Request q, PrivacyEvidence, CopyrightEvidence,
               WatermarkEvidence, State S)
    Capability ← ValidateAgentRoute(q.sender, q.receiver, q.purpose)
    AuditValid ← VerifyPreviousAuditHash(S.auditHead)
    Risks ← FusePrivacyCopyrightWatermarkAuditEvidence(...)
    Plans ← ComposeCandidatePlans(Risks, S.remainingBudgets)
    for each plan in Plans do
        plan.score ← Utility(plan)
                    − PrivacyRisk(plan)
                    − CopyrightRisk(plan)
                    − AuditRisk(plan)
        plan.feasible ← CheckCapabilityBudgetAndProvenance(plan)
    end for
    Selected ← HighestScoringFeasiblePlan(Plans)
    if not AuditValid then
        Selected ← RefuseOrBlockWithAuditEscalation(Selected)
    end if
    Output ← ExecuteUnderAllowedPayload(Selected)
    CommitActualCostsAndUpdateHistory(Output, S)
    AppendHashChainedAuditRecord(Output, Selected, S)
    return Output, UpdatedState, AuditRecord
```

## 四、实验设置

| 模块 | 数据/规模 | 主要对比 |
|---|---|---|
| MM-FOPD | 720 任务、270 学生、13,500 条纵向画像、144 dev 任务 | LaMP、GPG、PAPILLON-style、Privacy Funnel、DP Retrieval、LLM Minimization proxy |
| C²-RAG | 120 对正常—攻击请求、6 类攻击、4 轮 | No-defense、Summarization、N-gram/Semantic Guard、Full C²-RAG、关键消融 |
| HSW-ST | 12 条 long 文本、20 条 clean control、60 条攻击文本 | No Watermark、Protect Only、KGW Only、Full HSW-ST、Selective HSW-ST |
| CGC | 60 episodes、4 轮、5 种模式 | No-CGC、Independent、Static、Audit/Trust、Full-CGC |
| 外部控制器适配对比 | 60 episodes、7 个上层控制器 | Rule Guard、AgentSpec-style、GuardAgent-style、旧 NeMo-compatible adapter、Full CGC |

## 五、主结果与相对指标

### 1. MM-FOPD：信息单元召回

#### 与上次组会指标保持一致

上次组会使用“隐私 ASR、敏感画像暴露率、正常流程通过率、平均隐私成本”。这些指标不能被必要单元召回和单元 F1 替换。本次增加老师要求的除法指标：

```text
PPE = (1 − 敏感画像暴露率) / 平均隐私成本
```

PPE 越高，表示每单位隐私成本获得的敏感画像保护收益越高。直接使用“暴露率/成本”会使所有零暴露方法同时等于 0，因此不采用为主指标。

PPE 的全称是 **Privacy Protection Efficiency（隐私保护成本效率）**。它只用于 MM-FOPD，因为分母是画像选择产生的平均隐私成本。PPE 不用于 C²-RAG；C²-RAG 的对应成本是攻击场景平均版权成本，不是平均隐私成本。

上次组会的原始口径补充 PPE 后如下：

| 方法 | 隐私 ASR↓ | 敏感画像暴露率↓ | 正常流程通过率↑ | 平均隐私成本↓ | PPE↑ |
|---|---:|---:|---:|---:|---:|
| FullProfile | 18/18 (100%) | 96/96 (100%) | 48/48 (100%) | 0.5456 | 0.00 |
| Relevance-Only | 0/18 (0%) | 16/96 (16.7%) | 48/48 (100%) | 0.1395 | 5.97 |
| Static-Minimization | 0/18 (0%) | 0/96 (0%) | 48/48 (100%) | **0.1321** | **7.57** |
| Full MM-FOPD | 0/18 (0%) | 0/96 (0%) | 48/48 (100%) | 0.1445 | 6.92 |

当前 144-task 实验扩大了画像并改进了方法，但它是选择与披露开发实验，没有重新运行 18 条隐私攻击和 48 条完整正常教学流程。因此下表不沿用旧版隐私 ASR和正常流程通过率，只报告本轮真实重新计算的敏感暴露、成本与效用；后续正式实验需在同一新数据上重新补齐 ASR 和正常通过率。

| 方法 | 敏感画像暴露率↓ | 平均隐私成本↓ | PPE↑ | 必要单元召回↑ | 单元 F1↑ |
|---|---:|---:|---:|---:|---:|
| FullProfile | 144/144 (100%) | 2.8131 | 0.00 | 1.000 | 1.000 |
| LaMP-style | 8/144 (5.6%) | 0.1496 | 6.31 | 0.574 | 0.680 |
| GPG-style | 65/144 (45.1%) | 0.1629 | 3.37 | 0.539 | 0.673 |
| PAPILLON-style | 0/144 (0%) | 0.1132 | 8.83 | 0.606 | 0.744 |
| Privacy Funnel | 0/144 (0%) | 0.0924 | 10.83 | 0.523 | 0.665 |
| LLM Minimization proxy | 0/144 (0%) | **0.0839** | **11.92** | 0.505 | 0.654 |
| **MM-FOPD** | **0/144 (0%)** | 0.1423 | 7.03 | **0.745** | **0.829** |

这张表的科学结论是：MM-FOPD 的纯隐私成本效率不是最高，但它在零高敏感画像暴露的前提下保留了最多的任务必要信息。详细口径见 `docs/MMFOPD_指标口径与组会对照表_20260917.md`。

| 方法 | 必要单元召回 | 单元 F1 | 外发暴露 | 相对 MM-FOPD 的召回比 |
|---|---:|---:|---:|---:|
| LaMP-style | 0.574 | 0.680 | 0.088 | 0.770 |
| GPG-style | 0.539 | 0.673 | 0.067 | 0.724 |
| PAPILLON-style | 0.606 | 0.744 | 0.090 | 0.813 |
| Privacy Funnel | 0.523 | 0.665 | 0.090 | 0.702 |
| **MM-FOPD** | **0.745** | **0.829** | 0.088 | **1.000** |

相对于 GPG-style：

- 信息单元召回比：`0.745 / 0.539 = 1.38`，约提升 38.2%；
- 单元 F1 比：`0.829 / 0.673 = 1.23`，约提升 23.2%；
- 外发暴露比：`0.088 / 0.067 = 1.31`，说明 GPG 的输出更短，MM-FOPD 用略高暴露换取了更多任务信息。

更公平的解释是比较“单位外发暴露带来的必要信息召回”：

```text
MM-FOPD: 0.745 / 0.088 ≈ 8.47
GPG:     0.539 / 0.067 ≈ 8.04
```

MM-FOPD 的单位暴露效用约为 GPG 的 `1.05×`。

### 2. C²-RAG：多轮版权重构

#### 完整对比矩阵说明

本实验实际运行了 11 种配置，而不是下表中原先为了精简而展示的 4 种。所有配置共享相同的 BM25、MiniLM Dense Retrieval、RRF、Cross-Encoder、资源集合、正常—攻击配对和离线 evaluator；比较变量是检索后的版权保护与多轮状态机制。

| 类别 | 方法 | 主要区别 |
|---|---|---|
| 无保护现代 RAG | Advanced RAG No Defense | 共享现代检索底座，但不启用版权防护 |
| 检索/返回基线 | Reranking Protection | 重排序阈值过滤 + 受控短引用 |
| 返回基线 | Summarization Only | 始终返回摘要，无累计语义状态 |
| 返回基线 | Static Excerpt | 固定长度摘录 |
| 词面防护 | Independent N-gram Guard | 按 n-gram 重叠过滤，无累计语义预算 |
| 语义防护 | Semantic Similarity Guard | 按语义相似度降级，无跨轮联合状态 |
| 本文方法 | Full C²-RAG | 来源校验、实际输出计费、累计预算和重构历史 |
| 历史联动实验 | Full C²-RAG + CGC | 旧实验中由控制层辅助选择候选；职责拆分后版权候选选择已下沉到 C²-RAG |
| 消融 | w/o Provenance | 去除来源校验 |
| 消融 | w/o Cumulative Budget | 去除累计版权预算 |
| 消融 | w/o Reconstruction History | 去除会话重构历史 |

#### 11 种配置的完整结果

| 方法 | ASR@10↓ | ASR@25↓ | ASR@50↓ | 暴露严重度↓ | AUC↓ | 攻击场景平均版权成本↓ | 正常效用↑ | 逐轮可用↑ | 过拒绝↓ | 平衡分↑ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Advanced RAG No Defense | 1.00 | 1.00 | 1.00 | 0.891 | 0.900 | 0.9686 | **0.783** | 1.00 | 0 | 0.085 |
| Reranking Protection | 0 | 0 | 0 | **0.024** | **0.017** | 0 | 0 | 0 | 1.00 | 0 |
| Summarization Only | 1.00 | 0.25 | 0 | 0.238 | 0.235 | 0.0899 | 0.500 | 0.50 | 1.00 | 0.190 |
| Static Excerpt | 0 | 0 | 0 | **0.024** | **0.017** | 0 | 0 | 0 | 1.00 | 0 |
| Independent N-gram Guard | 0.90 | 0 | 0 | 0.116 | 0.113 | 0.0287 | 0.167 | 1.00 | 0 | 0.147 |
| Semantic Similarity Guard | 0.90 | 0 | 0 | 0.116 | 0.113 | 0.0287 | 0.167 | 1.00 | 0 | 0.147 |
| Full C²-RAG | 1.00 | 0.25 | 0 | 0.240 | 0.235 | 0.0668 | 0.500 | 1.00 | 0 | 0.380 |
| **Full C²-RAG + CGC（历史联动实验）** | 1.00 | **0** | 0 | **0.212** | **0.206** | 0.0728 | 0.500 | 1.00 | 0 | **0.394** |
| w/o Provenance | 1.00 | 0.25 | 0 | 0.240 | 0.235 | 0.0668 | 0.500 | 1.00 | 0 | 0.380 |
| w/o Cumulative Budget | 1.00 | 0.25 | 0 | 0.240 | 0.235 | 0.0668 | 0.500 | 1.00 | 0 | 0.380 |
| w/o Reconstruction History | 1.00 | 0.25 | 0 | 0.238 | 0.235 | 0.0899 | 0.500 | 0.50 | 1.00 | 0.190 |

“攻击场景平均版权成本”是六类攻击会话中，每轮最终释放文本相对受保护资源产生的实际版权暴露成本宏平均，越低越好；它与 MM-FOPD 的平均隐私成本完全不同，也不包含正常请求。Reranking 和 Static Excerpt 的成本为 0，是因为正常效用和可用率也为 0，不能解释为综合效果最好。N-gram/Semantic Guard 成本较低，但正常效用只有 0.167。历史联动实验在正常效用 0.500、逐轮可用率 1.000 的条件下取得最高平衡分；职责拆分后，相同的版权候选选择逻辑已归入 C²-RAG。

#### 当前没有完成的外部强 RAG

此前计划过 Self-RAG-style、GraphRAG-style、RAGFort 和 CanaryRAG，但本阶段没有完成它们的忠实数值复现：

- Self-RAG 与 GraphRAG 尚未接入统一版权输出契约；
- RAGFort 官方实现依赖对比重索引、训练条件及级联模型，当前标记为 `NOT_RUN`；
- CanaryRAG 缺少冻结的 canary 构造、流式检测和执行配置，当前标记为 `NOT_RUN`。

因此，当前表格是“同一现代 RAG 底座上的版权保护机制比较 + C²-RAG 消融”，不能表述成已经覆盖全部前沿 RAG 架构。

| 方法 | ASR@25 | 暴露严重度 | 重构 AUC | 正常效用 | 平衡安全效用 |
|---|---:|---:|---:|---:|---:|
| No-defense RAG | 1.00 | 0.891 | 0.900 | 0.783 | 0.085 |
| Full C²-RAG | 0.25 | 0.240 | 0.235 | 0.500 | 0.380 |
| **C²-RAG+CGC（历史联动）** | **0** | **0.212** | **0.206** | 0.500 | **0.394** |

相对 Full C²-RAG：

- 暴露严重度比：`0.212 / 0.240 = 0.88`，降低约 11.7%；
- 重构 AUC 比：`0.206 / 0.235 = 0.88`，降低约 12.3%；
- 平衡安全效用比：`0.394 / 0.380 = 1.04`。

### 3. HSW-ST：关键内容与检测

| 方法 | WDR | FPR | ADR | TKR | FKR | NKR | Placeholder |
|---|---:|---:|---:|---:|---:|---:|---:|
| KGW Only | 0.833 | 0 | 0.750 | 1.000 | 0.563 | 0.950 | N/A |
| 原 Full HSW-ST | 1.000 | 0 | 0.850 | 0.604 | 0.167 | 0.388 | 0 |
| **Selective HSW-ST** | **1.000** | **0** | **0.850** | **1.000** | **1.000** | **1.000** | **1.000** |

相对原 Full HSW-ST：

- FKR 比：`1.000 / 0.167 ≈ 6.00`；
- NKR 比：`1.000 / 0.388 ≈ 2.58`；
- Placeholder 通过率从 0 提升到 1；
- WDR 和 ADR 保持不变。

### 4. CGC：跨层治理

| 模式 | 隐私 ASR | 版权 ASR | 跨域 ASR | 正常可用率 | 篡改检测 |
|---|---:|---:|---:|---:|---:|
| No-CGC | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| Independent | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| Static | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| Budget-Only | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| **Full-CGC** | **0** | **0** | **0** | **1.00** | **1.00** |

由于基线风险分子为 0，不能直接报告普通“风险除法比”。这里使用风险降低率：

```text
Privacy risk reduction   = 1 − 0 / 1 = 100%
Copyright risk reduction = 1 − 0 / 1 = 100%
Cross-domain reduction  = 1 − 0 / 1 = 100%
```

同时保留正常可用率 100%，避免把“一律拒绝”误认为最佳方法。

## 六、当前问题与科学解释

1. 这些结果主要是 development evidence，尚未冻结 held-out test。
2. MM-FOPD 的外部方法目前是接口对齐 adapter，不是全部官方实现。
3. C²-RAG 的外部攻击和 CGC 控制仍主要是确定性开发 harness。
4. HSW-ST 的选择性关键内容通道能够保证最终内容，但 12 条文本都发生过确定性修复，因此不能称为 0.5B 模型原生遵循成功。
5. NeMo 官方 runtime 当前未安装，NeMo 部分是项目内可执行 deterministic adapter；AgentSpec/GuardAgent 是 style adapter。

## 七、明天汇报时可以直接说的三句话

1. **“本轮重点不是把某个单指标调到最好，而是把四个模块放入同一套正常—攻击—审计协议中，并区分真实外发、累计重构和逐轮可用性。”**
2. **“MM-FOPD 负责画像隐私预算与最小披露；C²-RAG 负责版权预算、重构历史和返回粒度；Selective HSW-ST 负责水印策略与来源恢复；CGC 只负责 capability、跨域冲突、信任、审计和回滚。”**
3. **“当前结果支持继续做正式实验，但还不能直接声称最终优于所有前沿方法；下一步是冻结 development 参数、补官方/忠实 baseline、运行 held-out test 和统计置信区间。”**

## 八、结果文件位置

- [本次汇报稿](D:\pycharm\CogniGuard\docs\CogniGuard_组会汇报稿_20260916.md)
- [四模块技术总结](D:\pycharm\CogniGuard\docs\COGNIGUARD_FOUR_MODULE_EXPERIMENT_SUMMARY_20260906.md)
- [四模块伪代码](D:\pycharm\CogniGuard\docs\COGNIGUARD_FOUR_MODULE_PSEUDOCODE_20260907.md)
- [MM-FOPD 原始汇总](D:\pycharm\CogniGuard\experiments\results\mmfopd_v3_development_compressed_card\summary.csv)
- [C²-RAG 最终开发表](D:\pycharm\CogniGuard\experiments\c2rag_v3\results\paired_differentiated_budget040\final_development_table.csv)
- [HSW-ST 汇总](D:\pycharm\CogniGuard\experiments\results\text_watermark_selective12\run_20260906_221459_352036\metrics_summary.csv)
- [CGC 汇总（历史目录名仍为 cg）](D:\pycharm\CogniGuard\experiments\results\cg_v3_integrated_dev\summary.csv)
- [共享 NeMo 基座控制器对比](D:\pycharm\CogniGuard\experiments\results\cg_external_controller_dev\summary.json)
