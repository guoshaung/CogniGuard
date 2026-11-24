# 来源证据接口 `pe-0.1`

> 代码：`cogniguard/governance/provenance_evidence.py`，测试：`cogniguard/tests/test_provenance_evidence.py`。
> 理论依据：`docs/research/THEORY_PROPAGATION_EVIDENCE_20261124.md` 第 4、5 节。不修改 `FORMAL_DEFINITION_v0.1.md`。
> Grok（核心治理）和 Codex（水印）**都按本版本产出、消费证据**。要改字段或语义时，在 `integration/provenance-governance` 上提版本号（`pe-0.2`），不在各自分支上各改一份。

## 1. 四种身份，必须分开

| 身份 | 回答的问题 | 字段 | 谁能提供 | 能改变什么 |
|---|---|---|---|---|
| 内容身份 | 这份产物里有哪些知识单元 | `matched_knowledge_units` | 指纹、检索、水印加知识核验、知识绑定水印 | 只能**增加**持有者的知识 → 门更严 |
| 发行身份 | 这份内容可能来自哪几张回执 | `candidate_issuance_ids` | 水印载荷、签名凭证、主动变体 | **只用于归因和审计**，不改变任何决策 |
| 传播事件 | 内容是否确实经一次未中介传播从 u 到了 v | `trusted_event_id`、`event_sender_principal_id` | **只有**可信通道日志（签名、平台计数器） | 唯一能计入 d、使 k+(f−d) 放宽的东西 |
| 当前保留知识 | 门在 `check_release` 里用的持有集合 | 回执 `holders_of` ∪ `augment_knowledge` 的增量 | 系统 | 单调不减；证据"知识丢失"不能删除持有 |

## 2. 字段

| 字段 | 类型 | 数学 / 安全语义 |
|---|---|---|
| `schema_version` | `"pe-0.1"` | 版本不符直接拒收（fail closed） |
| `evidence_id` | str | 证据记录自身的唯一号，用于审计和去重 |
| `artifact_id` | str | 被检测的产物（文本、文件）编号；正文不进证据 |
| `holder_principal_id` | str | 产物的持有者 v。内容证据写入的是 H(v) 的下界 |
| `evidence_type` | 枚举 | `fingerprint`、`retrieval`、`signed_credential`、`watermark`、`watermark_knowledge`、`knowledge_bound_watermark`、`trusted_event` |
| `candidate_issuance_ids` | list[str] | 与证据相容的回执集合 I。\|I\| > 1 即来源歧义；**不得**据此授权 |
| `matched_knowledge_units` | list[(resource_id, unit_id)] | 产物中被证实（或被检出）的单元 A ⊆ U。写入 K(v) ← K(v) ∪ A |
| `confidence` | [0, 1] | 对"内容声明成立"的置信度，**不是**事件发生的概率 |
| `verification_status` | 枚举 | `unverified` / `content_verified` / `event_verified`（仅 `trusted_event`）/ `inconclusive` / `rejected` |
| `trusted_event_id` | str 或 null | 仅 `trusted_event` 可非空；去重键。内容证据带此字段直接拒收 |
| `policy_version` | int | 评估时 `AccessRegistry` 的策略版本；提交复核时版本变了，按现有 `commit` 规则作废 |
| `model_and_detector_version` | str | 生成模型、检测器、密钥轮次、阈值版本；实验清单据此追溯 |
| `observed_at` | float | 观测时间 |
| `event_sender_principal_id` | str 或 null | 仅 `trusted_event`：发送方 u。接收方按最坏情况计入 u 当时的全部持有 |
| `extra` | dict | 方法私有字段；决策代码不读 |

## 3. 进入联合决策的唯一两条路径

```
K_obs   = DisclosureStore.holders_of(witness units)          # 回执
K_aug   = augment_knowledge(K_obs, evidences, min_conf)      # 只增不减
verdict = check_release(targets, recipient, release, K_aug, k + f − d)
d       = trusted_event_credits(evidences)                   # 只数可信事件
```

1. **持有证据（所有内容类证据）**：K_aug(v) ⊇ K_obs(v)。由于 `check_release` 对 knowledge 单调，**检出错误只会造成误拒，不会造成漏防**。`min_confidence` 默认 0（最保守），调高是"用安全换效用"的参数，必须在实验中报告。
2. **事件证明（仅 `trusted_event` + `event_verified`）**：按 `trusted_event_id` 去重后计数 d。只有同时满足理论 4.2 的三个条件（f 是可强制执行的总预算；事件真实、可去重、属于计入 f 的那一类；接收方按发送方全部持有入账）才允许使用 k+(f−d)。

**水印检出、签名凭证、指纹匹配，无论置信度多高，都不能：授权、扣减 f、删除持有。** 授权永远只由 `AccessRegistry.is_authorized` 决定；发行身份只进审计。

## 4. 复用而不是平行

- 封装：`ProvenanceEvidence.to_domain_evidence()` 放进现有 `DomainEvidence(domain="provenance")`，随 `EvidenceEnvelope` 流转。
- 判定：`check_release`、`ReleaseGate`、`DisclosureStore`、`ProtectedTarget`、`TargetRegistry` 都不复制。门的接线（在 `_knowledge_for` / `_reconstruction` 处调用 `augment_knowledge`）由 Grok 在自己的分支上做，集成时审查。
- 禁止：另写一套 knowledge 存储、另写一个 coalition 检查、让检测器直接返回 allow/deny。

## 5. 给各方的要求

| 角色 | 产出 | 验收 |
|---|---|---|
| Codex（水印） | 每次检测输出一条 `pe-0.1` 记录（JSONL），`evidence_type` 区分普通水印、水印+知识核验、知识绑定水印；同时输出同一产物上指纹、检索、签名凭证基线的记录 | `ProvenanceEvidence.from_dict` 全部通过；`trusted_event_id` 全为 null |
| Grok（核心治理） | 在门上接入 `augment_knowledge` 和 `trusted_event_credits`；可信事件来自哪个通道日志、f 由谁强制执行，写清楚 | 现有全量测试不退化；加一条"水印检出不改变 d"的测试 |
| 集成（本分支） | X3-E2E 统一协议、对比表、状态文件 | 见 `X3_E2E_PROTOCOL_DRAFT.md` |
