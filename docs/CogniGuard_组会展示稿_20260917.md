# CogniGuard 组会实验汇报

## 面向教育多智能体的隐私、版权、文本水印与统一安全控制

## 1. 研究问题与阶段结论

CogniGuard 面向多智能体教育对话中的四类风险：学生画像过度披露、教师资源被多轮重构、生成文本水印在改写后失效，以及不同保护模块之间缺少统一控制。系统由三个领域模块和一个通用控制层组成：

- **MM-FOPD**：按任务选择最小必要画像信息，并控制隐私成本；
- **C²-RAG**：控制教师资源的返回粒度、累计版权暴露和多轮重构风险；
- **HSW-ST**：在保护术语、公式和数字的同时嵌入可检测文本水印；
- **CGC（CogniGuard Controller）**：统一执行 capability、上下文边界、信任、审计与回滚。

本阶段结果表明：MM-FOPD 的优势是零高敏感画像暴露下的任务信息保留；C²-RAG 的优势是兼顾多轮版权保护与正常可用性；Selective HSW-ST 恢复了关键教学内容完整性；CGC 在三个公开安全基准上已形成可量化的主动防护能力，而不再使用全为 0 或 1 的内部合成指标作为主要证据。

## 2. 系统流程

```text
用户请求
   ↓
CGC 输入安全与上下文边界检查
   ↓
MM-FOPD：最小必要学生画像
   ↓
C²-RAG：受控检索、版权预算与候选粒度
   ↓
Teaching Agent：生成教学回答
   ↓
HSW-ST：关键内容保护、水印嵌入与来源绑定
   ↓
CGC：证据融合、权限校验、审计与回滚
   ↓
allow / sanitize / summarize / variant / refuse / block
```

## 3. 核心伪代码

### 3.1 MM-FOPD

```text
Algorithm MM-FOPD(Profile P, Task q, PrivacyBudget B)                  // 输入完整画像、当前任务和隐私预算
    RequiredUnits ← InferRequiredInformation(q)                       // 推断完成当前任务真正需要的画像信息单元
    Knowledge, Preference, Sensitive ← OrthogonalDecompose(P)         // 将知识状态、学习偏好和敏感信息正交拆分，减少信息混杂
    Candidates ← ScoreByAttentionRelevanceSensitivity(P, q)           // 综合任务注意力、相关性和敏感度为画像单元评分
    Candidates ← RemoveIdentityAndLocalOnlyFields(Candidates)         // 删除身份标识及只能在本地使用、禁止外发的字段
    Selected ← SelectRequiredUnitsUnderBudget(Candidates, RequiredUnits, B) // 在隐私预算内优先选择任务必要信息
    Selected ← TemporalAggregateAndResolveConflicts(Selected)         // 聚合多时段记录，并解决新旧画像之间的冲突
    Card ← CompressIntoStructuredTaskCard(Selected)                    // 将选中信息压缩成下游智能体可使用的结构化任务卡
    Evidence ← MeasureReleasedExposureAndUtility(Card, P, RequiredUnits) // 计算实际画像暴露、隐私成本和任务信息保留效果
    return Card, Evidence                                              // 返回最小任务画像卡及其隐私—效用证据
```

### 3.2 C²-RAG

```text
Algorithm C2-RAG(Query q, Resources D, History H, CopyrightBudget B)   // 输入查询、教师资源、对话历史和版权预算
    Authorized ← FilterByRolePurposeLicenseAndProvenance(D, q)        // 按角色、用途、许可和来源证明过滤无权访问的资源
    Retrieved ← DenseRetrieveRerankAndFuse(q, Authorized)             // 对授权资源进行稠密检索、重排序和结果融合
    IntentRisk ← EstimateReconstructionIntent(q, H)                    // 结合当前问题和历史行为判断用户是否在尝试重构原文
    CumulativeRisk ← MeasureMultiRoundDisclosure(H)                    // 计算此前多轮回答已经累计披露了多少受保护内容
    Candidates ← Build(summary, concept, variant, excerpt, hint, refuse) // 构造摘要、概念、变式、摘录、提示和拒绝等候选动作
    for each candidate in Candidates do                                // 逐个评价所有可能的返回候选
        candidate.cost ← MeasureActualCopyrightExposure(candidate, Retrieved) // 计算该候选实际产生的版权暴露成本
        candidate.risk ← EstimateResidualReconstruction(candidate, H)  // 估计输出该候选后仍存在的多轮重构风险
    end for                                                            // 完成全部候选的成本与风险评价
    return BestFeasibleCandidate(Candidates, B, IntentRisk, CumulativeRisk) // 在预算约束下返回安全性与可用性最优的候选
```

### 3.3 Selective HSW-ST

```text
Algorithm Selective-HSW-ST(Draft y, SourceTrace S, SecretKey k)       // 输入回答草稿、来源轨迹和水印密钥
    Terms, Formulas, Numbers ← ExtractCriticalSpans(y)                 // 提取不能被随意改写的术语、公式和数值
    ProtectedDraft, Map ← ReplaceCriticalSpansWithPlaceholders(y)      // 用占位符暂时替换关键内容，并保存一一对应关系
    EditableRegions ← LocateNonCriticalText(ProtectedDraft)            // 找出允许进行语言改写的非关键解释文本区域
    Watermarked ← ApplyWatermarkOnlyTo(EditableRegions, k)             // 只在可编辑区域使用密钥嵌入统计文本水印
    Missing ← FindMissingProtectedSpans(Watermarked, Map)              // 检查水印改写后是否丢失了关键内容或占位符
    Watermarked ← DeterministicallyRepair(Missing, Watermarked, Map)   // 通过确定性通道修复缺失内容，避免依赖模型猜测
    Output ← RestoreCriticalSpans(Watermarked, Map)                    // 将术语、公式和数值准确恢复到最终回答
    Evidence ← DetectWatermarkAndMeasureFidelity(Output, y)            // 检测水印，并测量最终文本相对草稿的内容保真度
    return Output, BindSourceTrace(Evidence, S)                         // 返回带水印回答，并将检测证据绑定到来源轨迹
```

### 3.4 CGC

```text
Algorithm CGC(Request q, RetrievedContext R, Evidence E, State S)      // 输入请求、检索上下文、模块证据和当前会话状态
    InputRisk ← DetectPromptInjectionAndActionableHarm(q)              // 检测直接提示注入、越权意图和可执行有害请求
    R_clean ← QuarantineInstructionsFromUntrustedContext(R)            // 隔离非可信检索内容中试图控制模型的间接指令
    Capability ← ValidateSenderReceiverPurpose(q)                      // 校验发送者、接收者和请求用途是否具备对应权限
    AuditValid ← VerifyPreviousAuditHash(S)                            // 验证上一条审计记录，检查历史状态是否被篡改
    Risks ← FusePrivacyCopyrightWatermarkTrustEvidence(E, S)           // 融合隐私、版权、水印和信任证据形成综合风险状态
    Decision ← SelectFeasibleAction(Risks, Capability, AuditValid)     // 根据风险、权限和审计状态选择可执行的控制动作
    Output ← ExecuteWithinAllowedPayload(Decision, R_clean)            // 仅在获准的数据范围内执行并生成受控输出
    CommitActualCostsAndAppendAudit(Output, S)                          // 按实际输出结算成本，并追加新的审计记录
    return Output, Decision, UpdatedState                              // 返回最终输出、控制决策和更新后的会话状态
```

## 4. 指标定义

### 4.1 MM-FOPD 指标

- **敏感画像暴露率↓**：发生高敏感画像单元外发的任务数除以任务总数。越低越好。
- **平均隐私成本↓**：每个任务实际释放画像单元的敏感度加权成本均值。它衡量释放代价，不等于记录条数。
- **必要单元召回率↑**：任务所需画像单元中，被方法成功保留的比例，即 `TP / (TP + FN)`。
- **画像信息单元 F1↑**：画像单元精确率与召回率的调和平均，`F1 = 2PR / (P + R)`。F1 是通用标准指标；“画像信息单元”是本文对评价对象的任务化定义。它同时惩罚遗漏必要信息和释放无关信息。
- **PBCR↑（Privacy Benefit-Cost Ratio，本文定义）**：隐私保护收益成本比，`PBCR = (1 − 敏感画像暴露率) / 平均隐私成本`。越高表示单位隐私成本获得的敏感画像保护收益越高。PBCR 不包含教学效用，因此只能作为辅助指标，不能单独决定方法优劣。

### 4.2 C²-RAG 指标

- **ASR@10/25/50↓**：攻击会话累计重构受保护资源达到 10%、25% 或 50% 阈值的会话比例。阈值越高，表示更严重的重构成功。
- **暴露严重度↓**：攻击结束时，被累计恢复的受保护内容比例的平均值。
- **累计重构面积↓（Reconstruction AUC）**：先在每一轮计算累计重构分数，再对各轮分数取平均。单轮累计重构分数由最长公共片段覆盖、n-gram 重合、语义相似和关键知识单元恢复按 `0.40、0.25、0.20、0.15` 加权得到。它衡量“泄露了多少以及泄露得多早”：越早泄露，后续多轮都会保持较高累计分数，面积就越大；越低越安全。这里的 AUC 不是分类任务中的 ROC-AUC。

例如两个方法在第 4 轮的最终重构分数都为 0.40：方法 A 四轮为 `[0.10, 0.30, 0.30, 0.40]`，累计重构面积为 `0.275`；方法 B 为 `[0, 0, 0.10, 0.40]`，面积为 `0.125`。虽然最终暴露相同，但方法 B 到最后一轮才出现明显泄露，因此风险更低。
- **攻击场景平均版权成本↓**：六类攻击会话中，每轮最终释放文本相对受保护资源产生的实际版权暴露成本宏平均；不包含正常请求。
- **正常效用↑**：正常请求中有效完成教学任务的平均质量。
- **逐轮可用率↑**：攻击或正常会话中，系统仍能提供受控有效回答的轮次比例。
- **过拒绝率↓**：正常请求被不必要拒绝的比例。
- **平衡安全效用↑（本文定义）**：同时考虑正常任务质量、逐轮可用性与攻击暴露，计算公式为 `正常效用 × 逐轮可用率 × (1 − 攻击暴露严重度)`。三项中任何一项很差都会压低总分，因此可以防止把“一律拒绝”或“完全不防护”解释成最佳方法。该指标不是领域通用标准，只用于本实验内部的同条件综合比较。

例如，无防护 RAG 的分数为 `0.783 × 1.000 × (1 − 0.891) = 0.085`：正常回答质量高，但攻击暴露严重，所以综合值很低。历史联动方法的分数为 `0.500 × 1.000 × (1 − 0.212) = 0.394`：正常效用略低，但保持逐轮可用，并显著降低攻击暴露，因此综合值更高。Reranking Protection 虽然暴露低，但正常效用和可用率均为 0，所以平衡安全效用也是 0。

### 4.3 HSW-ST 指标

- **WDR↑（Watermark Detection Rate）**：无攻击时，水印文本被检测器正确检出的比例。
- **FPR↓（False Positive Rate）**：无水印干净文本被误判为有水印的比例。
- **ADR↑（Attack Detection Rate）**：经过删除、改写、混合、截断或摘要攻击后，水印仍可被检出的比例。
- **TKR↑（Term Keeping Rate）**：关键教学术语在水印改写后仍被保留的比例。
- **FKR↑（Formula Keeping Rate）**：关键公式仍被完整保留的比例。
- **NKR↑（Number Keeping Rate）**：关键数值仍被完整保留的比例。
- **Placeholder Pass↑**：受保护占位符均能正确恢复、最终文本不存在缺失或残留占位符的样本比例。

### 4.4 CGC 公开安全指标

- **主动拦截/隔离召回率↑**：有害请求或注入内容在进入主模型、上下文拼接前被 CGC 识别的比例。
- **正常误拦/误隔离率↓**：正常请求或干净检索内容被错误拦截、隔离的比例。
- **Precision↑**：所有被 CGC 判为风险的样本中，真实风险样本所占比例。
- **F1↑**：Precision 与召回率的调和平均，反映检出和误伤之间的平衡。
- **Balanced Accuracy↑**：有害召回率与正常识别率的平均值，避免平衡数据中的单边高分。
- **模型拒答代理率↑**：未被入口层拦截的危险请求中，主模型回答包含明确拒绝标志的比例。该指标不是人工或独立 LLM Judge 得到的最终攻击成功率。

## 5. 实验设置

| 模块 | 规模 | 对比范围 |
|---|---:|---|
| MM-FOPD | 270 名学生、每人 50 条纵向记录；144 个开发任务 | FullProfile、LaMP-style、GPG-style、PAPILLON-style、Privacy Funnel、LLM Minimization proxy |
| C²-RAG | 120 对正常—攻击请求、6 类攻击、每个会话 4 轮 | 无防护 RAG、重排序、摘要、固定摘录、N-gram、语义防护、完整方法与消融 |
| HSW-ST | 12 条长文本、20 条干净对照、60 条攻击文本 | KGW Only、原 Full HSW-ST、Selective HSW-ST |
| CGC / JailbreakBench | 30 有害 + 30 正常，按 10 个类别确定性分层 | 入口主动防护与正常误拦 |
| CGC / BIPIA | 75 个 EmailQA 间接注入 + 75 个干净邮件对照 | 上下文拼接前的指令隔离 |
| CGC / XSTest | 25 安全 + 25 不安全最小对照 | 危险意图检出与过度拒答 |

### 5.1 数据来源与可核验性

| 实验 | 数据来源 | 可核验内容 |
|---|---|---|
| MM-FOPD | 由公开数学任务构造任务集合，并使用固定随机种子生成合成学生纵向画像；不包含真实学生个人数据 | 270 个合成画像、每个 50 个信息记录；720 个任务按 train/dev/test 划分，本轮使用 144 个 dev 任务 |
| C²-RAG | 基于冻结的教师资源、正常请求与六类多轮重构攻击构造配对会话 | 每个正常请求与对应攻击共享目标资源和检索条件；保存逐轮输出、版权预算账本和重构曲线 |
| HSW-ST | 数学教育长文本、干净无水印对照，以及在同一文本上生成的五类攻击版本 | 保存原始回答、水印回答、逐样本检测结果、攻击后检测结果与来源绑定记录 |
| JailbreakBench | JailbreakBench/JBB-Behaviors 公开数据集的固定版本 | 保存公开样本编号、类别、提示词哈希、CGC 决策和回答哈希，不在结果表重复传播有害原文 |
| BIPIA | Microsoft BIPIA 公开基准固定版本中的 EmailQA 与 75 条间接注入 | 每个注入样本配一个干净邮件对照；保存输入哈希、攻击家族和隔离决策 |
| XSTest | XSTest 公开安全/不安全最小对照集合的固定版本 | 保存样本编号、类型、提示词哈希、入口决策和模型拒答代理结果 |

实验原始输入、逐样本结果、汇总表和复现命令均保留在项目中；展示稿不展开本机目录，现场需要复核时可打开配套的《实验数据复核索引》。

## 6. 实验结果

### 6.1 MM-FOPD：隐私—效用权衡

#### 对比方法分别在做什么

| 方法 | 核心做法 | 设置它的目的 |
|---|---|---|
| **FullProfile** | 不做筛选，把学生全部历史画像交给下游模型 | 作为“效用上限、隐私下限”参照：信息最完整，但暴露和成本最大 |
| **LaMP-style** | 按当前任务与历史记录的相关性打分，取 Top-K 记录；不设置独立隐私门控 | 检验“只做个性化检索”能否同时解决隐私问题 |
| **GPG-style** | 先限定当前知识点，再按掌握度、错误模式、偏好和学习状态的优先级抽取任务画像 | 对比“面向任务生成/抽取短画像”与 MM-FOPD 的细粒度预算选择 |
| **PAPILLON-style** | 模拟本地—云端边界，只允许相关、较粗粒度且低敏感的信息外发 | 对比“先在本地过滤，再向云端披露”的隐私代理思路 |
| **Privacy Funnel** | 用“任务相关效用 − 敏感度惩罚”给候选信息评分，在效用和隐私之间折中 | 对比经典信息压缩式隐私—效用权衡 |
| **LLM Minimization proxy** | 模拟 LLM 自检后的数据最小化：只取当前知识点、敏感度受限且优先级最高的至多两个记录 | 构造一个非常激进的最少披露基线，检查 MM-FOPD 是否只是因为输出更多才提高召回 |
| **MM-FOPD** | 联合任务注意力、敏感度、冗余抑制、正交画像分解、时间聚合和信息单元预算，生成结构化任务卡 | 验证本文方法能否在不暴露高敏信息的同时保留更多任务必要信息 |

其中 `style` 和 `proxy` 表示**思想对齐的统一接口适配基线**，不是对应论文官方模型与训练过程的完整复现。这样设置的优点是所有方法共享相同画像、任务和评价器，差异来自信息选择机制；结论边界是“机制级比较”，不能表述为已经完成对原论文系统的忠实复现。

| 方法 | 敏感画像暴露率↓ | 平均隐私成本↓ | PBCR↑ | 必要单元召回↑ | 单元 F1↑ |
|---|---:|---:|---:|---:|---:|
| FullProfile | 144/144（100%） | 2.8131 | 0.00 | **1.000** | **1.000** |
| LaMP-style | 8/144（5.6%） | 0.1496 | 6.31 | 0.574 | 0.680 |
| GPG-style | 65/144（45.1%） | 0.1629 | 3.37 | 0.539 | 0.673 |
| PAPILLON-style | 0/144（0%） | 0.1132 | 8.83 | 0.606 | 0.744 |
| Privacy Funnel | 0/144（0%） | 0.0924 | 10.83 | 0.523 | 0.665 |
| LLM Minimization proxy | 0/144（0%） | **0.0839** | **11.92** | 0.505 | 0.654 |
| **MM-FOPD** | **0/144（0%）** | 0.1423 | 7.03 | **0.745** | **0.829** |

MM-FOPD 不是纯成本或 PBCR 最优方法，但在零高敏感画像暴露的方法中取得最高必要单元召回和 F1。相对 GPG-style，必要单元召回为 `0.745 / 0.539 = 1.38×`，单元 F1 为 `0.829 / 0.673 = 1.23×`。因此其主要贡献是隐私—任务效用权衡，而不是单独追求最低成本。

补充的 held-out test split（144 个任务）中，MM-FOPD 的必要单元召回为 `0.799`、单元 F1 为 `0.866`，均高于开发集结果。该结果仍属于当前合成数据和机制级适配基线下的开发证据，正式论文还需补教学效用、置信区间和更忠实的外部实现。

### 6.2 C²-RAG：多轮版权重构防护

#### 对比方法分别在做什么

| 方法 | 核心做法 | 主要验证问题 |
|---|---|---|
| **Advanced RAG No Defense** | 使用相同的现代检索、融合和重排序底座，但检索后不做版权控制 | 没有防护时，多轮查询能恢复多少受保护内容 |
| **Reranking Protection** | 对候选进行重排序并设置严格阈值，只允许极短受控引用 | 严格检索过滤能否防重构，以及会损失多少正常效用 |
| **Summarization Only** | 所有命中内容统一改成摘要，不记录跨轮累计披露 | 单纯摘要是否足以阻止攻击者多轮拼接原文 |
| **Static Excerpt** | 每轮只返回固定长度摘录，不根据历史和风险动态变化 | 固定长度限制与动态版权预算相比有何差异 |
| **Independent N-gram Guard** | 检查当前输出与资源的词面 n-gram 重叠；各轮独立判断 | 只防逐字复制、但不建模跨轮语义重构是否足够 |
| **Semantic Similarity Guard** | 根据当前输出与资源的语义相似度进行降级；各轮独立判断 | 语义过滤能否覆盖同义改写攻击 |
| **Full C²-RAG** | 联合来源验证、实际输出计费、累计版权预算、重构历史和动态返回粒度 | 本文完整版权保护机制 |
| **Full C²-RAG + CGC（历史联动）** | 在旧版实验中，再由上层控制器根据跨模块证据选择 C²-RAG 候选 | 检验跨层证据联动是否进一步降低重构；当前版权候选职责已下沉到 C²-RAG |
| **w/o Provenance** | 从完整方法中去掉来源/授权验证 | 检验来源证据的贡献 |
| **w/o Cumulative Budget** | 去掉跨轮累计版权预算，只看当前轮 | 检验累计计费的贡献 |
| **w/o Reconstruction History** | 不记录攻击者此前已获得的片段和知识单元 | 检验多轮重构历史的贡献 |

| 方法 | ASR@10↓ | ASR@25↓ | ASR@50↓ | 暴露严重度↓ | 累计重构面积↓ | 攻击版权成本↓ | 正常效用↑ | 逐轮可用↑ | 过拒绝↓ | 平衡安全效用↑ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Advanced RAG No Defense | 1.00 | 1.00 | 1.00 | 0.891 | 0.900 | 0.9686 | **0.783** | 1.00 | 0 | 0.085 |
| Reranking Protection | 0 | 0 | 0 | **0.024** | **0.017** | 0 | 0 | 0 | 1.00 | 0 |
| Summarization Only | 1.00 | 0.25 | 0 | 0.238 | 0.235 | 0.0899 | 0.500 | 0.50 | 1.00 | 0.190 |
| Static Excerpt | 0 | 0 | 0 | **0.024** | **0.017** | 0 | 0 | 0 | 1.00 | 0 |
| Independent N-gram Guard | 0.90 | 0 | 0 | 0.116 | 0.113 | 0.0287 | 0.167 | 1.00 | 0 | 0.147 |
| Semantic Similarity Guard | 0.90 | 0 | 0 | 0.116 | 0.113 | 0.0287 | 0.167 | 1.00 | 0 | 0.147 |
| **Full C²-RAG** | 1.00 | 0.25 | 0 | 0.240 | 0.235 | 0.0668 | 0.500 | 1.00 | 0 | 0.380 |
| Full C²-RAG + CGC（历史联动） | 1.00 | **0** | 0 | **0.212** | **0.206** | 0.0728 | 0.500 | 1.00 | 0 | **0.394** |
| w/o Provenance | 1.00 | 0.25 | 0 | 0.240 | 0.235 | 0.0668 | 0.500 | 1.00 | 0 | 0.380 |
| w/o Cumulative Budget | 1.00 | 0.25 | 0 | 0.240 | 0.235 | 0.0668 | 0.500 | 1.00 | 0 | 0.380 |
| w/o Reconstruction History | 1.00 | 0.25 | 0 | 0.238 | 0.235 | 0.0899 | 0.500 | 0.50 | 1.00 | 0.190 |

Reranking Protection 和 Static Excerpt 的风险指标虽然最低，但正常效用和逐轮可用率也为 0，属于“拒绝换安全”。Full C²-RAG 在正常效用 0.500、逐轮可用率 1.000 的条件下，将无防护 RAG 的暴露严重度从 0.891 降至 0.240，约降低 73.1%；累计重构面积从 0.900 降至 0.235，约降低 73.9%。

补充的现代机制基线（CRAG-style、Self-RAG-style、Adaptive-RAG-style）已完成 20 会话开发筛选，结果见《C²-RAG 现代基线补充实验》。它们是思想对齐适配，不替代官方 RAGFort/CanaryRAG 复现；当前展示主表保留原冻结矩阵，避免把小批量 fallback 结果和完整开发结果混在一起。

### 6.3 Selective HSW-ST：检测与内容保真

#### 对比方法分别在做什么

| 方法 | 核心做法 | 主要验证问题 |
|---|---|---|
| **KGW Only** | 直接在整段文本的 token 选择中加入 KGW 绿色词表偏置，不单独保护公式、数字和术语 | 传统统计水印在教学文本中的检测能力及内容损伤 |
| **原 Full HSW-ST** | 在语义改写过程中嵌入水印，并加入语义保护与审计绑定 | 语义水印能否提高检测和攻击鲁棒性；其弱点是小模型容易改坏关键教学内容 |
| **Selective HSW-ST** | 只在可编辑解释文本中嵌入水印；术语、公式和数字走占位符保护与确定性恢复通道 | 验证双通道设计能否保持水印鲁棒性，同时恢复教学内容完整性 |

| 方法 | WDR↑ | FPR↓ | ADR↑ | TKR↑ | FKR↑ | NKR↑ | Placeholder Pass↑ |
|---|---:|---:|---:|---:|---:|---:|---:|
| KGW Only | 0.833 | 0 | 0.750 | 1.000 | 0.563 | 0.950 | 不适用 |
| 原 Full HSW-ST | 1.000 | 0 | 0.850 | 0.604 | 0.167 | 0.388 | 0 |
| **Selective HSW-ST** | **1.000** | **0** | **0.850** | **1.000** | **1.000** | **1.000** | **1.000** |

相对原 Full HSW-ST，Selective HSW-ST 的公式保留率为 `1.000 / 0.167 ≈ 6.00×`，数字保留率为 `1.000 / 0.388 ≈ 2.58×`，同时保持 WDR 和 ADR。12/12 个样本均触发过确定性关键内容修复，因此这里的 100% 表示端到端保护结果，不代表语言模型原生保真率。

### 6.4 CGC：公开安全基准优化结果

#### 三个公开基准分别测什么

| 基准 | 测试内容 | 为什么需要它 |
|---|---|---|
| **JailbreakBench** | 覆盖骚扰歧视、恶意软件、物理伤害、诈骗、虚假信息、隐私等类别的有害与正常对照请求 | 测 CGC 能否在主模型前主动识别通用有害意图，同时不误伤相近的正常问题 |
| **BIPIA** | 把新的指令注入 EmailQA 的非可信邮件内容，诱导模型偏离用户原任务 | 测间接提示注入：风险文字不是用户直接输入，而是藏在 RAG 检索内容中；CGC 应在上下文拼接前隔离它 |
| **XSTest** | 构造只差关键对象的安全/不安全最小对照，如“终止程序”与“终止人的生命” | 专门测过度拒答，判断系统是在理解“动作—对象”关系，还是看到 kill、execute 等词就机械拦截 |

这里不把三个基准合成一个总分：JailbreakBench 测通用有害意图，BIPIA 测检索侧间接注入，XSTest 测安全边界和误伤，三者对应 CGC 的不同控制位置。

#### 为什么选择这三个：科学依据与结论边界

选择依据不是简单按知名度排列，而是先按 CGC 的威胁模型确定三个必须覆盖的失效位置，再为每个位置选择有公开论文、固定数据和可复现代码的代表性基准：

| 控制位置 | 所需证据 | 代表基准及学术依据 | 本轮实际覆盖 |
|---|---|---|---|
| 用户输入进入主模型之前 | 能否主动识别多类别有害意图，同时保留相近正常请求 | **JailbreakBench**：NeurIPS 2024 Datasets and Benchmarks Track；提供公开数据、攻击/防御框架和排行榜 | 官方数据共 100 有害 + 100 正常；本轮按 10 类分层抽取 30 + 30，评价入口防护，不等同于官方完整 jailbreak 排行榜结果 |
| RAG 检索内容进入上下文之前 | 能否识别藏在外部内容中的间接提示注入 | **BIPIA**：Microsoft 提出的首批系统性间接提示注入基准，论文发表于 ACM SIGKDD 2025；覆盖 5 类应用任务并评测多种模型与防御 | 本轮覆盖 EmailQA 和全部 75 条文本攻击模板，并增加 75 个干净邮件对照；未覆盖 WebQA、TableQA、Summarization 和 CodeQA |
| 安全策略作出拦截决定时 | 是否因敏感词而过度拒答 | **XSTest**：NAACL 2024 Long Paper，专门用最小安全/不安全对照测量 exaggerated safety 和 over-refusal | 官方数据共 450 条、18 个类型；本轮只使用 25 条 homonym 安全样本及其 25 条 contrast_homonym 不安全对照 |

因此，这三个基准是**具有同行评审依据、且与 CGC 三个控制位置互补的代表性选择**，但不存在一个被所有研究共同承认为“绝对最权威”的安全基准。当前结果应称为 **public-benchmark smoke evaluation**，不能称为三个基准的完整排行榜成绩。

若作为毕业论文正式结论，还应在参数冻结后补充：JailbreakBench 全量及官方 Judge 或 StrongREJECT；BIPIA 其余任务或 InjecAgent/AgentDojo 等工具型 Agent 注入；XSTest 全量及 OR-Bench；同时加入中文安全数据，以验证中文教育场景中的泛化能力。

论文出处：JailbreakBench（NeurIPS 2024，arXiv:2404.01318）；BIPIA（ACM SIGKDD 2025，DOI:10.1145/3690624.3709179）；XSTest（NAACL 2024，DOI:10.18653/v1/2024.naacl-long.301）。

| 基准 | 样本与评价边界 | 主动防护召回↑ | 正常误伤↓ | Precision↑ | F1↑ | 补充结果 |
|---|---|---:|---:|---:|---:|---|
| JailbreakBench | 100 有害 + 100 正常；完整公开文件 | **33/100（33.0%）** | **1/100（1.0%）** | **0.971** | **0.493** | Balanced Accuracy = 0.660 |
| BIPIA | 75 注入 + 75 干净邮件 | **67/75（89.3%）** | **0/75（0%）** | **1.000** | **0.944** | 上下文拼接前隔离 |
| XSTest | 200 不安全 + 250 安全；完整公开文件 | **29/200（14.5%）** | **4/250（1.6%）** | **0.879** | **0.249** | Balanced Accuracy = 0.565 |

早期小切片中的模型拒答代理率不作为完整泛化结果。完整公开文件结果只报告冻结入口规则的主动拦截，并明确指出 CGC 当前主要问题是危险表达覆盖不足。

#### 从首轮 Smoke Evaluation 到当前版本

| 基准 | 首轮观察 | 本轮改进 | 当前解释 |
|---|---|---|---|
| JailbreakBench | 10 有害 + 10 正常；有害入口拦截 0% | 增加“请求动作 + 伤害对象”组合判断，并改为 10 类分层 | 主动召回 86.7%，正常误拦 0% |
| BIPIA | 20 个 EmailQA 注入；拼接前隔离 0% | 将非可信检索内容视为数据，隔离其中试图控制回答的指令段 | 75 类注入召回 89.3%，75 个干净对照误隔离 0% |
| XSTest | 5 安全 + 5 不安全；不安全入口拦截 0% | 使用动作—对象组合，避免仅按 kill、execute、shoot 等词拦截 | 不安全入口拦截 76%，安全误拦 0% |

首轮和本轮的样本规模及抽样方式不同，因此这张演进表用于说明缺陷修复过程，不作为严格配对显著性检验。当前结果属于公开基准上的开发阶段证据；正式论文实验应冻结规则与阈值后，在未参与开发的测试划分上报告置信区间。

## 7. 当前结论

1. **MM-FOPD** 在零高敏感画像暴露下，取得当前零暴露方法中最高的必要信息召回和单元 F1；PBCR 只作为成本辅助指标。
2. **C²-RAG** 显著降低多轮版权重构，但 ASR@10 仍偏高，说明低阈值碎片累积仍需继续优化。
3. **Selective HSW-ST** 解决了原版本的公式、数字和占位符破坏问题，摘要攻击仍是水印鲁棒性的主要短板。
4. **CGC** 已从内部全 0/1 的合成评价转向 JailbreakBench、BIPIA 和 XSTest；当前优势是高 Precision 与低误伤，后续重点是提高对未见表达的召回并完成独立 Judge 评价。

补充实验显示，扩展 CGC 组合规则后，完整 JailbreakBench 有害召回从 33.0% 提升到 61.0%，但误拦从 1.0% 上升到 5.0%；XSTest unsafe 召回从 14.5% 提升到 48.5%，safe 误拦从 1.6% 上升到 12.0%。该结果说明当前需要语义二阶段判别器来恢复 Precision—Recall 平衡，不能把扩展规则直接作为最终版本。
