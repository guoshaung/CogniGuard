# CogniGuard 四模块算法伪代码

> 本文档描述 MM-FOPD、C²-RAG、选择性 HSW-ST 和 CG 的算法逻辑。以下内容是论文式伪代码，不对应某一种编程语言，也不包含工程异常处理、文件路径或框架调用细节。

## Algorithm 1：MM-FOPD 学生画像最小披露

```text
Algorithm MM-FOPD(Profile P, Task q, PrivacyBudget B_priv)
Require:
    P          完整本地学生画像记录集合
    q          当前教学任务
    B_priv     本轮画像披露预算
Ensure:
    C_task     最小化结构化任务上下文卡
    E_priv     实际画像披露证据

1:  U_required ← InferRequiredUnits(q)
2:  Z_K, Z_P, Z_S ← OrthogonalDecompose(P)
3:  Candidates ← ∅
4:
5:  for each profile record r ∈ P do
6:      relevance ← TaskRelevance(r, q)
7:      attention ← TaskAttention(r, q)
8:      projection ← Project(Z_K, Z_P, r, q)
9:      privacyCost ← Sensitivity(r) × DisclosureGranularity(r)
10:     redundancy ← CrossModalRedundancy(r, Candidates)
11:     utility ← α·relevance + β·attention + γ·projection
12:                − λ·privacyCost − μ·redundancy
13:
14:     if IsLocalOnly(r) or IsIdentityField(r) then
15:         continue
16:     end if
17:
18:     Candidates ← Candidates ∪ {(r, utility, privacyCost)}
19: end for
20:
21: Selected ← ∅
22: consumed ← 0
23:
24: for each information unit u ∈ U_required do
25:     r* ← HighestUtilityRecord(Candidates, unit = u)
26:     if r* exists and consumed + Cost(r*) ≤ B_priv then
27:         Selected ← Selected ∪ {r*}
28:         consumed ← consumed + Cost(r*)
29:     end if
30: end for
31:
32: Aggregated ← TemporalAggregate(Selected)
33: Aggregated ← ResolveConflicts(Aggregated)
34:
35: for each unit u ∈ Aggregated do
36:     if Type(u) = mastery then
37:         u ← ConvertScoreToLevel(u)
38:     else if Type(u) = error_pattern then
39:         u ← SummarizeAsErrorCategory(u)
40:     else if Type(u) = preference then
41:         u ← ReleasePreferenceCategoryOnly(u)
42:     end if
43: end for
44:
45: C_task ← BuildStructuredContextCard(Aggregated, q)
46: C_task ← RemoveLocalOnlyValues(C_task, P)
47: E_priv ← MeasureReleasedProfileExposure(C_task, P)
48:
49: return C_task, E_priv
```

## Algorithm 2：C²-RAG 版权约束检索与候选生成

```text
Algorithm C2-RAG(Query q, Resources D, History H, CopyrightBudget B_copy)
Require:
    q          当前资源请求
    D          教师资源集合及其权利元数据
    H          当前主体针对同一资源族的历史披露状态
    B_copy     剩余版权预算
Ensure:
    A          多粒度候选动作集合
    E_copy     版权风险证据

1:  D_authorized ← FilterByRolePurposeAndLicense(D, q)
2:  R_sparse ← BM25Retrieve(q, D_authorized)
3:  R_dense ← DenseRetrieve(q, D_authorized)
4:  R_fused ← ReciprocalRankFusion(R_sparse, R_dense)
5:  R_ranked ← CrossEncoderRerank(q, R_fused)
6:  d* ← TopAuthorizedResource(R_ranked)
7:
8:  currentRisk.verbatim ← DetectVerbatimRequest(q)
9:  currentRisk.fragment ← DetectAdjacentFragmentRequest(q, H)
10: currentRisk.reconstruction ← DetectSemanticReconstruction(q, H)
11:
12: cumulativeDisclosure ← MeasureCumulativeDisclosure(H, d*)
13: reconstructionAUC ← AreaUnderReconstructionCurve(H, d*)
14: remainingBudget ← B_copy − CommittedCopyrightCost(H)
15:
16: A ← ∅
17: A ← A ∪ BuildCandidate(CONTROLLED_QUOTE, d*)
18: A ← A ∪ BuildCandidate(ABSTRACTIVE_SUMMARY, d*)
19: A ← A ∪ BuildCandidate(GENERATED_VARIANT, d*)
20: A ← A ∪ BuildCandidate(CONCEPT_ONLY, d*)
21: A ← A ∪ BuildCandidate(MINIMAL_HINT, d*)
22: A ← A ∪ BuildCandidate(REFUSE, d*)
23:
24: for each candidate a ∈ A do
25:     a.content ← RenderAtGranularity(a.type, d*)
26:     a.estimatedCost ← MeasureCopyrightExposure(a.content, d*)
27:     a.residualRisk ← EstimateResidualReconstruction(a, H)
28:     a.utility ← EstimateTeachingUtility(a.content, q)
29:     a.provenanceRequired ← RequiresVerifiedSource(a.type)
30: end for
31:
32: E_copy ← {
33:     currentRisk,
34:     cumulativeDisclosure,
35:     reconstructionAUC,
36:     remainingBudget,
37:     provenance = ProvenanceStatus(d*),
38:     candidateActions = A
39: }
40:
41: return A, E_copy
```

## Algorithm 3：选择性 HSW-ST 文本水印

```text
Algorithm Selective-HSW-ST(Draft y, SourceTrace S, WatermarkKey k)
Require:
    y          教学回答草稿
    S          Agent、资源和审计来源信息
    k          统计水印密钥
Ensure:
    y_w        最终带水印教学回答
    E_w        检测、保真和来源绑定证据

1:  Terms, Formulas, Numbers ← ExtractCriticalSpans(y)
2:  y_protected, Map ← ReplaceWithPlaceholders(
3:      y, Terms, Formulas, Numbers
4:  )
5:
6:  EditableRegions ← IdentifyNonCriticalRegions(y_protected)
7:  y_generated ← WatermarkedGenerate(
8:      input = y_protected,
9:      key = k,
10:     applyBiasOnlyTo = EditableRegions
11: )
12:
13: missing ← FindMissingPlaceholders(y_generated, Map)
14:
15: if missing ≠ ∅ then
16:     capsule ← BuildDeterministicCriticalContentCapsule(missing, Map)
17:     y_generated ← Append(y_generated, capsule)
18: end if
19:
20: y_w ← RestorePlaceholders(y_generated, Map)
21:
22: fidelity.terms ← TermKeepingRate(y, y_w)
23: fidelity.formulas ← FormulaKeepingRate(y, y_w)
24: fidelity.numbers ← NumberKeepingRate(y, y_w)
25: fidelity.semantic ← SemanticSimilarity(y, y_w)
26:
27: detection.global ← DetectWatermarkZScore(y_w, k)
28: detection.local ← SlidingWindowDetection(y_w, k)
29:
30: watermarkId ← GenerateWatermarkIdentifier()
31: traceBinding ← Bind(
32:     watermarkId,
33:     Hash(y_w),
34:     S.agentId,
35:     S.resourceId,
36:     S.auditHash
37: )
38:
39: E_w ← {
40:     watermarkId,
41:     detection,
42:     fidelity,
43:     repairedPlaceholderCount = |missing|,
44:     traceBinding,
45:     blindDetectionPositive = detection.global ≥ Threshold
46: }
47:
48: return y_w, E_w
```

## Algorithm 4：CG 跨层候选规划与最终决策

```text
Algorithm CG-Controller(Request q, E_priv, E_copy, E_w, State S_t)
Require:
    q          当前多智能体请求
    E_priv     MM-FOPD 隐私披露证据
    E_copy     C²-RAG 版权风险和候选动作
    E_w        HSW-ST 检测、保真和来源证据
    S_t        隐私预算、版权预算、历史、信任和审计状态
Ensure:
    Plan*      最终联合动作计划
    S_(t+1)    更新后的跨层状态
    Audit_t    本轮审计记录

1:  capability ← ValidateCapabilityRoute(q.sender, q.receiver, q.purpose)
2:  auditValid ← VerifyPreviousAuditHash(q.previousHash, S_t.auditHead)
3:
4:  R_priv ← DerivePrivacyRisk(E_priv, S_t)
5:  R_copy ← DeriveCopyrightRisk(E_copy, S_t)
6:  R_watermark ← DeriveWatermarkRisk(E_w, S_t)
7:  R_audit ← DeriveAuditRisk(auditValid, E_w.traceBinding)
8:
9:  if capability = DENIED then
10:     CandidatePlans ← {BLOCK}
11: else
12:     CandidatePlans ← ComposeCrossLayerPlans(
13:         privacyCandidates = PrivacyActions(E_priv),
14:         copyrightCandidates = E_copy.candidateActions,
15:         watermarkCandidates = WatermarkActions(E_w)
16:     )
17: end if
18:
19: for each plan p ∈ CandidatePlans do
20:     p.projectedPrivacyCost ← ProjectPrivacyCost(p, E_priv)
21:     p.projectedCopyrightCost ← ProjectCopyrightCost(p, E_copy)
22:     p.residualRisk ← EstimateJointResidualRisk(
23:         p, R_priv, R_copy, R_watermark, R_audit
24:     )
25:     p.utility ← EstimateJointTeachingUtility(p, q)
26:
27:     p.feasible ←
28:         p.projectedPrivacyCost ≤ S_t.privacyBudgetRemaining
29:         and p.projectedCopyrightCost ≤ S_t.copyrightBudgetRemaining
30:         and ProvenanceRequirementsSatisfied(p, E_copy)
31:         and AuditRequirementsSatisfied(p, auditValid)
32:
33:     if p.feasible then
34:         p.score ← p.utility
35:                    − λ_priv·p.residualRisk.privacy
36:                    − λ_copy·p.residualRisk.copyright
37:                    − λ_w·p.residualRisk.watermark
38:                    − λ_audit·p.residualRisk.audit
39:                    − λ_cost·ExecutionCost(p)
40:     else
41:         p.score ← −∞
42:     end if
43: end for
44:
45: Plan* ← ArgMaxScore(CandidatePlans)
46:
47: if auditValid = false then
48:     Plan* ← EscalateToRefuseOrBlock(Plan*)
49: end if
50:
51: ReleasedOutput ← ExecuteUnderAllowedPayload(Plan*)
52: ActualPrivacyCost ← MeasureActualPrivacyDisclosure(ReleasedOutput)
53: ActualCopyrightCost ← MeasureActualCopyrightDisclosure(ReleasedOutput)
54:
55: if ActualPrivacyCost > Plan*.projectedPrivacyCost
56:      or ActualCopyrightCost > Plan*.projectedCopyrightCost then
57:     RollBack(ReleasedOutput)
58:     Plan* ← SafeFallback(REFUSE, AUDIT_ESCALATION)
59: end if
60:
61: S_(t+1) ← UpdateState(
62:     S_t,
63:     privacyCost = ActualPrivacyCost,
64:     copyrightCost = ActualCopyrightCost,
65:     risks = {R_priv, R_copy, R_watermark, R_audit},
66:     action = Plan*,
67:     trust = UpdateTrust(S_t, auditValid, E_w)
68: )
69:
70: Audit_t ← AppendHashChainedAuditRecord(
71:     previousHash = S_t.auditHead,
72:     request = q,
73:     candidatePlans = CandidatePlans,
74:     selectedPlan = Plan*,
75:     actualCosts = {ActualPrivacyCost, ActualCopyrightCost},
76:     nextState = S_(t+1)
77: )
78:
79: return Plan*, S_(t+1), Audit_t
```

## Algorithm 5：CogniGuard 多智能体端到端保护流程

```text
Algorithm CogniGuard-Protected-Turn(UserRequest q_t, GlobalState S_t)
Require:
    q_t        当前用户请求
    S_t        当前学生、会话、资源和审计状态
Ensure:
    response   最终受保护教学回答
    S_(t+1)    更新后的全局状态

1:  task ← TaskAgent.Parse(q_t)
2:
3:  profile ← LocalProfileStore.Read(task.studentId)
4:  C_task, E_priv ← MM-FOPD(
5:      profile,
6:      task,
7:      S_t.privacyBudgetRemaining
8:  )
9:
10: A_copy, E_copy ← C2-RAG(
11:     task.resourceQuery,
12:     TeacherResourceStore,
13:     S_t.copyrightHistory,
14:     S_t.copyrightBudgetRemaining
15: )
16:
17: prePlan, _, _ ← CG-Controller(
18:     q_t,
19:     E_priv,
20:     E_copy,
21:     EmptyWatermarkEvidence,
22:     S_t
23: )
24:
25: draft ← TeachingAgent.Generate(
26:     task,
27:     studentContext = prePlan.allowedStudentContext,
28:     teacherResource = prePlan.allowedTeacherResource
29: )
30:
31: protectedDraft, E_w ← Selective-HSW-ST(
32:     draft,
33:     SourceTrace(prePlan),
34:     WatermarkKey
35: )
36:
37: finalPlan, S_(t+1), Audit_t ← CG-Controller(
38:     q_t,
39:     E_priv,
40:     E_copy,
41:     E_w,
42:     S_t
43: )
44:
45: if finalPlan.action ∈ {BLOCK, REFUSE} then
46:     response ← SafeRefusal(finalPlan.reason)
47: else if finalPlan.action = REGENERATE then
48:     response ← RegenerateAtSaferGranularity(task, finalPlan)
49: else
50:     response ← ApplyFinalPlan(protectedDraft, finalPlan)
51: end if
52:
53: Commit(Audit_t)
54: return response, S_(t+1)
```

## 关键职责边界

```text
MM-FOPD:
    决定“哪些学生画像信息可以成为候选上下文”，不负责全局允许或拒绝。

C²-RAG:
    检索资源、测量累计版权风险并生成多粒度候选，不负责跨层最终决策。

Selective HSW-ST:
    嵌入和检测水印、保护关键教学内容并绑定来源，不决定全局策略。

CG:
    综合三类证据、权限、双预算、历史、信任和审计状态，选择并执行最终联合计划。

Offline Evaluator:
    读取隐藏标签计算攻击、效用和统计指标，不向运行时算法泄露答案。
```
