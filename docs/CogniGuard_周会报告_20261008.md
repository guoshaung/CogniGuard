# CogniGuard 周会实验报告

## 面向教育多智能体的隐私、版权、文本水印与统一安全控制

## 1. 研究问题与阶段结论

CogniGuard 面向教育多智能体对话中的四类风险：学生画像过度披露、教师资源被多轮重构、生成文本水印在改写后失效，以及多个保护模块之间缺少统一控制。

系统由三个领域模块和一个通用控制层组成：

- **MM-FOPD**：按任务选择最小必要学生画像信息，并控制隐私成本；
- **C²-RAG**：控制教师资源的检索、返回粒度、累计版权暴露和多轮重构；
- **HSW-ST**：在保护术语、公式和数字的同时嵌入可检测文本水印；
- **CGC（CogniGuard Controller）**：统一执行身份、Capability、用途、信任、预算、审计与回滚。

本阶段的核心结论是：

1. MM-FOPD 在几乎不选择高敏感画像记录的条件下，保留了较多任务必要信息；
2. C²-RAG 在正常会话仍可用的条件下，降低了多轮版权重构；
3. Selective HSW-ST 显著提高了公式、数字和术语保真度；
4. CGC 规则层具有较好的可解释性和较低误拦，但危险表达覆盖仍需提升；
5. NeMo self-check policy + MiMo 的安全召回更高，但 JailbreakBench 正常误拦较高，因此暂作为可选边界判别器。

## 2. 系统流程

```text
用户请求
   ↓
CGC 输入规则与上下文边界检查
   ↓
MM-FOPD：最小必要学生画像
   ↓
C²-RAG：受控检索、版权预算与候选粒度
   ↓
Teaching Agent：生成教学回答
   ↓
HSW-ST：关键内容保护、水印嵌入与来源绑定
   ↓
CGC：融合证据、权限、信任、审计与回滚
   ↓
allow / sanitize / summarize / variant / refuse / block
```

NeMo self-check 的位置是 CGC 的可选第二阶段：规则层先处理硬约束和明显风险，边界请求再交给 NeMo self-check policy + MiMo 判断。

## 3. 核心伪代码

### 3.1 MM-FOPD

```text
Algorithm MM-FOPD(Profile P, Task q, PrivacyBudget B)                  // 输入完整画像、当前任务和隐私预算
    RequiredUnits ← InferRequiredInformation(q)                       // 推断任务真正需要的画像信息单元
    Knowledge, Preference, Sensitive ← OrthogonalDecompose(P)         // 拆分知识、偏好和敏感信息
    Candidates ← ScoreByAttentionRelevanceSensitivity(P, q)           // 综合注意力、相关性和敏感度评分
    Candidates ← RemoveIdentityAndLocalOnlyFields(Candidates)         // 删除身份字段和禁止外发字段
    Selected ← SelectRequiredUnitsUnderBudget(Candidates, RequiredUnits, B) // 在隐私预算内选择必要单元
    Selected ← TemporalAggregateAndResolveConflicts(Selected)         // 聚合多时段记录并解决冲突
    Card ← CompressIntoStructuredTaskCard(Selected)                   // 压缩为结构化任务画像卡
    Evidence ← MeasureReleasedExposureAndUtility(Card, P, RequiredUnits) // 计算暴露、成本和任务效用
    return Card, Evidence                                              // 返回画像卡和证据
```

### 3.2 C²-RAG

```text
Algorithm C2-RAG(Query q, Resources D, History H, CopyrightBudget B)  // 输入查询、资源、历史和版权预算
    Authorized ← FilterByRolePurposeLicenseAndProvenance(D, q)        // 过滤角色、用途、许可不匹配的资源
    Retrieved ← DenseRetrieveRerankAndFuse(q, Authorized)             // Dense 候选、RRF 融合和晚交互精排
    IntentRisk ← EstimateReconstructionIntent(q, H)                   // 判断是否存在重构意图
    CumulativeRisk ← MeasureMultiRoundDisclosure(H)                   // 统计多轮累计披露
    Candidates ← Build(summary, concept, variant, excerpt, hint, refuse) // 构造不同返回粒度
    for each candidate in Candidates do                                // 逐一评价候选动作
        candidate.cost ← MeasureActualCopyrightExposure(candidate, Retrieved) // 计算实际版权成本
        candidate.risk ← EstimateResidualReconstruction(candidate, H)  // 估计剩余重构风险
    end for
    return BestFeasibleCandidate(Candidates, B, IntentRisk, CumulativeRisk) // 返回预算内最优候选
```

### 3.3 Selective HSW-ST

```text
Algorithm Selective-HSW-ST(Draft y, SourceTrace S, SecretKey k)       // 输入草稿、来源轨迹和密钥
    Terms, Formulas, Numbers ← ExtractCriticalSpans(y)               // 提取术语、公式和数字
    ProtectedDraft, Map ← ReplaceCriticalSpansWithPlaceholders(y)    // 占位符保护关键内容
    EditableRegions ← LocateNonCriticalText(ProtectedDraft)          // 定位可改写区域
    Watermarked ← ApplyWatermarkOnlyTo(EditableRegions, k)           // 只对可编辑文本嵌入水印
    Missing ← FindMissingProtectedSpans(Watermarked, Map)            // 检查关键内容是否缺失
    Watermarked ← DeterministicallyRepair(Missing, Watermarked, Map) // 确定性修复缺失内容
    Output ← RestoreCriticalSpans(Watermarked, Map)                  // 恢复公式、数字和术语
    Evidence ← DetectWatermarkAndMeasureFidelity(Output, y)          // 检测水印并测量保真度
    return Output, BindSourceTrace(Evidence, S)                       // 返回输出和来源证据
```

### 3.4 CGC

```text
Algorithm CGC(Request q, RetrievedContext R, Evidence E, State S)     // 输入请求、检索内容、证据和状态
    RuleRisk ← DetectPromptInjectionAndActionableHarm(q)              // 第一阶段规则检测
    R_clean ← QuarantineInstructionsFromUntrustedContext(R)           // 隔离检索内容中的间接指令
    if IsBoundaryCase(q, RuleRisk) then                               // 只对边界样本调用语义判别
        SemanticRisk ← NeMoSelfCheckPolicy(q)                         // 可选 NeMo self-check + MiMo
    end if
    Capability ← ValidateSenderReceiverPurpose(q)                     // 校验身份、接收者和用途
    AuditValid ← VerifyPreviousAuditHash(S)                            // 验证审计链
    Risks ← FusePrivacyCopyrightWatermarkTrustEvidence(E, S)          // 融合跨模块风险证据
    Decision ← SelectFeasibleAction(RuleRisk, SemanticRisk, Risks, Capability, AuditValid) // 选择动作
    Output ← ExecuteWithinAllowedPayload(Decision, R_clean)           // 在允许范围内执行
    CommitActualCostsAndAppendAudit(Output, S)                         // 更新预算、状态和审计
    return Output, Decision, UpdatedState                             // 返回结果和新状态
```

## 4. 主要指标

### 4.1 MM-FOPD

- **高敏感选择任务率↓**：选择层中包含敏感度达到 0.7 的画像记录的任务比例；用于观察选择风险，不等于最终输出属性推断成功率。
- **加权选择暴露↓**：选中画像记录的敏感度加权总量与完整画像敏感度总量之比。
- **必要单元召回↑**：任务所需画像单元中成功保留的比例。
- **单元 F1↑**：画像信息单元精确率和召回率的调和平均。
- **PBCR↑（本文定义）**：`(1 − 高敏感画像暴露率) / 平均隐私成本`。只作为辅助指标，不包含教学效用。

### 4.2 C²-RAG

- **ASR@10/25/50↓**：多轮累计重构达到 10%、25%、50% 阈值的攻击会话比例。
- **暴露严重度↓**：攻击结束时恢复内容比例的平均值。
- **累计重构面积↓**：每轮累计重构分数的平均值；泄露越早、越多，面积越大。
- **攻击场景平均版权成本↓**：攻击会话中实际释放文本产生的版权暴露成本均值。
- **正常效用↑、逐轮可用率↑、过拒绝率↓**：分别衡量正常任务质量、回答可用性和正常请求误拒绝。

### 4.3 HSW-ST

- **WDR↑**：无攻击时水印被正确检测的比例；
- **FPR↓**：干净文本被误判为有水印的比例；
- **ADR↑**：攻击后仍检测到水印的比例；
- **TKR/FKR/NKR↑**：术语、公式、数字在改写后保留的比例；
- **Placeholder Pass↑**：关键占位符均被正确恢复的比例。

### 4.4 CGC

- **召回率↑**：风险请求在进入主模型前被发现的比例；
- **误拦率↓**：正常请求被错误拦截的比例；
- **Precision、F1、Balanced Accuracy↑**：综合评价风险检出和正常请求保留。

## 5. 实验设置

| 模块 | 数据规模 | 对比方法/设置 |
|---|---:|---|
| MM-FOPD | 270 个合成画像、13,500 条记录、144 个 test 任务 | FullProfile、LaMP-style、GPG-style、PAPILLON-style、Privacy Funnel、DP、LLM Minimization、MM-FOPD |
| C²-RAG | 20 个 paired development 会话、每会话 4 轮 | 无防护 RAG、CRAG-style、Self-RAG-style、Adaptive-RAG-style、Full C²-RAG |
| HSW-ST | 12 条长文本、20 条干净对照、60 条攻击 | KGW Only、原 Full HSW-ST、Selective HSW-ST |
| CGC 规则 | JailbreakBench 100+100、XSTest 200+250、BIPIA 75+75 | 完整公开文件/EmailQA |
| NeMo self-check policy + MiMo | JailbreakBench 100+100、XSTest 200+250 | MiMo 原生执行 NeMo self-check policy |
| 公开检索 | BEIR SciFact，5,183 篇文档、300 条查询 | BM25、Dense、RRF、Late Interaction、Cross-Encoder |

## 6. 实验结果

### 6.1 MM-FOPD：隐私—效用权衡

| 方法 | 高敏感选择任务率↓ | 加权选择暴露↓ | 必要单元召回↑ | 单元 F1↑ |
|---|---:|---:|---:|---:|
| Privacy Funnel | 0 | 0.0335 | 0.539 | 0.672 |
| LLM Minimization proxy | 0 | **0.0302** | 0.512 | 0.660 |
| GPG-style | 0.479 | 0.0568 | 0.563 | 0.691 |
| DP-Exponential Retrieval | 0.597 | 0.0590 | 0.199 | 0.282 |
| **MM-FOPD** | **0.0069** | 0.0495 | **0.799** | **0.866** |

MM-FOPD 不是成本最低的方法，但在几乎不选择高敏感记录的条件下保留了最多必要任务信息。该结果仍基于合成画像和机制级适配基线。

### 6.2 C²-RAG：多轮版权控制

| 方法 | 重构成功率↓ | 累计重构面积↓ | 版权成本↓ | 正常会话可用率↑ | 逐轮可用率↑ |
|---|---:|---:|---:|---:|---:|
| Advanced RAG No Defense | 1.00 | 0.849 | 0.963 | 1.00 | 1.00 |
| CRAG-style correction | 0 | 0.217 | 0.071 | 1.00 | 0.95 |
| Self-RAG-style reflection | 0 | 0.221 | **0.060** | 1.00 | 0.95 |
| Adaptive-RAG-style router | 0 | 0.218 | 0.048 | 0 | 0.475 |
| **Full C²-RAG** | **0** | **0.203** | 0.068 | **1.00** | 0.95 |

Full C²-RAG 的累计重构面积最低，并保持正常会话可用；Adaptive-RAG-style 主要通过拒答降低风险，不能视为更优。

### 6.3 HSW-ST：水印检测与教学内容保真

| 方法 | WDR↑ | FPR↓ | ADR↑ | TKR↑ | FKR↑ | NKR↑ | Placeholder↑ |
|---|---:|---:|---:|---:|---:|---:|---:|
| KGW Only | 0.833 | 0 | 0.750 | 1.000 | 0.563 | 0.950 | N/A |
| 原 Full HSW-ST | 1.000 | 0 | 0.850 | 0.604 | 0.167 | 0.388 | 0 |
| **Selective HSW-ST** | **1.000** | **0** | **0.850** | **1.000** | **1.000** | **1.000** | **1.000** |

Selective HSW-ST 的关键内容保真明显提高；摘要式攻击 ADR 仍为 0.25，是后续主要短板。

### 6.4 CGC 规则层与 NeMo self-check

| 方法 | 基准 | 召回率↑ | 误拦率↓ | Precision↑ | F1↑ | Balanced Accuracy↑ |
|---|---|---:|---:|---:|---:|---:|
| CGC 扩展规则 | JailbreakBench | 61.0% | 5.0% | 92.4% | 0.735 | 0.780 |
| CGC 扩展规则 | XSTest | 48.5% | 12.0% | 76.4% | 0.593 | 0.683 |
| NeMo policy + MiMo | JailbreakBench | **99.0%** | 33.0% | 75.0% | 0.853 | 0.830 |
| NeMo policy + MiMo | XSTest | **98.5%** | 10.4% | 88.3% | **0.931** | **0.940** |

NeMo self-check + MiMo 的召回更高，但 JailbreakBench 误拦达到 33%，因此暂作为 CGC 边界判别器，不直接替代规则层。

### 6.5 公开检索算法

| 方法 | Recall@10↑ | Recall@100↑ | MRR↑ | MAP↑ |
|---|---:|---:|---:|---:|
| BM25 | 0.803 | 0.897 | 0.637 | 0.626 |
| Dense | 0.793 | **0.927** | 0.611 | 0.603 |
| RRF | **0.833** | 0.907 | 0.648 | 0.640 |
| Late Interaction | 0.823 | 0.907 | **0.674** | **0.666** |

主检索组合采用 Dense → RRF → Late Interaction；BM25 和 Cross-Encoder 作为对比方法。

## 7. 综合架构结论

本文的创新重点不是四个模块分别全面超过所有领域方法，而是通过 CGC 将四类风险放入同一个教育多智能体安全控制架构：

```text
MM-FOPD：画像隐私证据
C²-RAG：版权和多轮重构证据
HSW-ST：水印和内容保真证据
          ↓
CGC：Capability、信任、预算、冲突、审计、回滚
```

当前阶段可以得出的结论是：

1. MM-FOPD 在低高敏感选择率下保留了较高的必要信息；
2. C²-RAG 在安全和正常可用性之间取得较好平衡；
3. Selective HSW-ST 显著减少公式、数字和术语损坏；
4. CGC 规则层可解释、误拦较低，NeMo self-check 提供了更高召回的可选语义后端；
5. 综合架构具备作为硕士论文系统创新的证据，但当前结果仍是阶段性开发证据，不能表述为四个模块整体 SOTA。

## 8. 下一步工作

- 在有许可真实教育资源上正式运行 C²-RAG；
- 继续降低 CGC 和 NeMo self-check 的误拦，完成规则—语义级联校准；
- 用独立 shadow profiles 完成 MM-FOPD 属性推断攻击；
- 针对摘要式压缩增强 HSW-ST，并扩大攻击样本；
- 完成 held-out test、置信区间和更忠实的外部基线复现。
