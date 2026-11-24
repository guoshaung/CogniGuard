# 来源证据接口 pe-1.0（冻结版）

> 冻结方式：本文件、`cogniguard/provenance/schemas/pe-1.0/*.json` 与 `PROVENANCE_INTERFACE.sha256` 同一提交推送。之后任何字段或语义变化都升版本（pe-1.1 起），并写进 `docs/integration/INTEGRATION_STATUS.md` 的变更表。
> 取代：集成分支上的 pe-0.1（`cogniguard/governance/provenance_evidence.py`，已删除）。与 Grok 本地 `SourceEvidence`（`0e48995`，未推送）的对应关系见第 9 节。
> 参考实现：`cogniguard/provenance/`（`schema.py`、`interfaces.py`、`verify.py`、`state.py`、`decision.py`、`mock.py`、`contract.py`）。参考实现的行为就是规范；文字与代码不一致时，以契约测试（`contract.py`）为准并修文字。

## 1. 五种身份，各占一个字段

| 身份 | 回答的问题 | 字段 | 能改变什么 |
|---|---|---|---|
| 来源候选（内容身份） | 这份产物出自哪份登记来源文本 | `source_candidates` | 本身不改变任何决策；只用于审计和派生单元声明 |
| 发行候选（发行身份） | 这份内容来自哪次发行 / 哪张回执 | `issuance_candidates`；可核验的只有 `credential` | **永不授权，永不扣减 f**；核验通过也只记"发行身份已证实" |
| 知识单元 | 产物里含有哪些事实 | `unit_claims`（`[resource_id, unit_id]` + present / absent / unknown） | 核验通过 → 确认持有；未核验 → 只进"疑似"层 |
| 主体身份 | 产物现在在谁手里 | `holder_principal_id`（或 `UNKNOWN`） | 决定持有写到谁名下 |
| 传播事件 | 一次传播确实发生：谁 → 谁 | `event_claim`（只限 `trusted_log`、`ideal`、`mock`） | 签名有效 → 接收方按最坏情况计入发送方全部持有；在执行预算下计入 d |

当前保留知识**不是**上面任何一个字段，而是状态层（第 5 节）的结果，只增不减。

## 2. 记录类型

### 2.1 Observation（检测输出，Codex 产出）

| 字段 | 类型 | 语义 |
|---|---|---|
| `schema_version` | `"pe-1.0"` | 不符即拒收 |
| `observation_id` | id | 全局唯一；状态层按它去重 |
| `artifact_id` / `artifact_sha256` | id / hex | 被检测的产物；正文不进记录 |
| `holder_principal_id` | id 或 `UNKNOWN` | 产物持有者 |
| `evidence_type` | 枚举 | `fingerprint`、`retrieval`、`watermark`、`joint`（水印且内容核验）、`knowledge_bound_watermark`、`signed_credential`、`trusted_log`、`ideal`（仅上界对照）、`mock`（仅工程测试） |
| `method_version` | id | 模型、检测器、码本或密钥轮次、阈值集合；以 `mock` 开头即视为 mock |
| `detector_status` | `ok` / `error` | `error` 时两个候选集都是 `error`、无单元声明 |
| `source_candidates`、`issuance_candidates` | `{status, items:[{id, score}]}` | `status`：`found`（≥1 项）/ `none`（检查过、无匹配）/ `not_checked`（本方法不产出此身份）/ `error`（失败，视同 UNKNOWN）。`score` 为方法原生分数，**不是概率** |
| `unit_claims` | `[{unit, presence, score}]` | 同一单元在一条记录中只能出现一次 |
| `confidence` / `confidence_kind` / `calibration_id` | 见第 3 节 | — |
| `policy_version` | int | 观测时的策略版本 |
| `observed_at` | number | 观测时间；回放按它排序 |
| `event_claim` | `{event_id, sender_principal_id, receiver_principal_id, issuance_id, signature}` | 仅 `trusted_log`（必填）、`ideal`、`mock` |
| `credential` | `{issuance_id, signature}` | 当且仅当 `signed_credential` |
| `extra` | object | 方法私有；治理代码不读 |

**评测金标禁入**：任何层级出现名字含 `gold`、`truth`、`oracle`、`label`、`true` 的字段，直接拒收（`GoldLeakError`；JSON Schema 用 `propertyNames` 同样拒绝）。

### 2.2 VerifiedEvidence（核验输出）

`verification_status` ∈ {`verified`, `unverified`, `conflict`, `rejected`, `unknown`}，加上 `confirmed_units`、`suspected_units`、`conflicting_units`、`verified_issuance_ids`、`candidate_issuance_ids`（仅审计）、`verified_event`。不变式（构造时强制）：

- `rejected` / `unknown`：没有任何效果；
- 只有 `verified` 能带确认单元、已证实发行或已证实事件；
- 一个单元要么确认、要么疑似；
- `UNKNOWN` 持有者不能有确认单元。

### 2.3 DisclosureRequest / DisclosureDecision

决策记录：`allowed`、`reason`（`allow` / `unauthorized` / `reconstruction`）、`governance_mode`、`coalition_k_effective`、`trusted_event_credits`、`knowledge_layer`。

## 3. 置信分数

- `confidence_kind = calibrated`：`confidence` 是在校准分区 `calibration_id` 上估计的"本条最强声明为真"的概率，必须在 [0, 1]。
- `confidence_kind = uncalibrated`：`confidence` 必须为 null，只给方法原生 `score`。
- **治理代码不用 `confidence` 或 `score` 做授权、记账或预算决定。** 阈值属于检测器，写进 `method_version`，在检测器自己的校准分区上定好，不在 X3-E2E 中调整。

## 4. 核验规则（`RuleVerifier`）

| 情况 | 结果 |
|---|---|
| `detector_status = error` | `unknown`，无效果（失败关闭：不放宽任何东西） |
| `mock` 未被允许 / `ideal` 不在 IDEAL 臂 | `rejected` |
| `trusted_log` 签名无效 | `rejected` |
| `trusted_log` 接收方 ≠ 持有者（持有者已知） | `conflict` |
| `trusted_log` 签名有效 | 已证实事件；持有者 = 接收方 |
| `signed_credential` 签名无效 / 有效 | `rejected` / 已证实发行身份（不是事件，不是授权） |
| 单元声明 present，知识核验在产物文本中找到 | 确认持有（持有者已知时） |
| 单元声明 present，核验未找到 | **疑似**（词面未命中不能证明缺失） |
| 单元声明 present，产物文本为空 | `conflict`，该单元不确认 |
| 单元声明 absent / unknown | 忽略：缺失证据不删除知识 |
| 水印、联合水印、知识绑定水印的发行候选 | 只进 `candidate_issuance_ids`（审计） |

知识核验（`TextUnitChecker`）：句子词集包含登记表述词集的比例 ≥ 0.95（包含度，不是 Jaccard，避免载体词或前缀把完整事实遮掉）。登记表述是系统自己的知识（资产主人登记），不是评测金标。

## 5. 安全状态（`SecurityState`）

三层，只增不减：

- `receipts`：系统交付（`DisclosureStore.holders_of` 语义）；放行后 `record_delivery` 追加；
- `confirmed` = receipts ∪ 已核验持有 ∪ 已证实事件按最坏情况带来的持有（接收方计入发送方当时的全部 receipts ∪ confirmed）；
- `confirmed+suspected` = confirmed ∪ 未核验声明；持有者 `UNKNOWN` 的疑似单元记在伪主体 `UNKNOWN` 名下（建模选择：未知持有者可以作为联盟中的一员）。

去重：同一 `observation_id` 只应用一次；同一 `event_id` 只计一次；同一 `event_id` 端点不同 → 记冲突，不应用。

**未经核验的来源不写入 `confirmed`（账本）。** 疑似层只在治理模式明确选择时参与判定。

预算：只有在执行预算 f 下（`enforced_budget_f` 非空），端点已知、已证实的事件才计入 d，且 d ≤ f。

## 6. 披露决策（`CapdPolicy`）

1. 授权：对请求涉及的每个资源调用 `AccessRegistry.is_authorized`；证据不参与。
2. 联盟检查：现有 `check_release`（CA-PD），知识层与联盟规模由模式决定：

| 模式 | 知识层 | 检查的联盟规模 |
|---|---|---|
| `static` | receipts | k + f |
| `dyn_knowledge` | confirmed | k + f |
| `dyn_full` | confirmed | k + max(f − d, 0) |
| `dyn_conservative` | confirmed+suspected | k + max(f − d, 0) |

三处动态的增量可以独立消融：知识更新（static → dyn_knowledge）、预算抵扣（→ dyn_full）、疑似层（→ dyn_conservative）。

## 7. 四个接口（`interfaces.py`）

| 接口 | 方法 | 实现方 | 失败处理 |
|---|---|---|---|
| `SourceDetector` | `detect(Artifact) -> [Observation]` | Codex（在线）；离线时直接给 JSONL | 不抛异常，返回 `detector_status = error` |
| `EvidenceVerifier` | `verify(Observation, Artifact?) -> VerifiedEvidence` | 集成（参考实现） | 拿不到产物 → 单元留在疑似层 |
| `StateUpdater` | `apply`、`record_delivery`、`knowledge(layer)`、`trusted_event_credits()` | 集成 / Grok | 冲突记录不应用 |
| `DisclosurePolicy` | `decide(DisclosureRequest, state) -> DisclosureDecision` | 集成 / Grok | 未授权一律拒绝 |

任何接口都拿不到评测金标。离线回放和在线联动对治理侧不可区分（`test_mock_replay_equals_online_and_scores`）。

## 8. 契约测试

- 提供方（Codex）：`python -m cogniguard.provenance.contract provider observations.jsonl --formal`。检查 schema、金标字段、`observation_id` 唯一、正式运行中无 mock / ideal。
- 消费方（Grok）：`check_consumer(make_state, make_policy)` 返回空列表即兼容。六条性质：C1 证据不授权；C2 未核验或冲突声明不进 confirmed；C3 非日志证据不产生预算抵扣；C4 重复、冲突、伪造的事件只计一次或不计；C5 内容证据只会收紧决定、动态模式不能忽略已核验持有；C6 检测错误不改变状态。
- 三个故意写错的消费者（把水印当事实、让证据授权、给非日志证据记抵扣）都会被契约抓到（`cogniguard/tests/test_provenance_interface.py`）。
- **契约通过只说明接口兼容，不说明检测效果或安全收益**；契约夹具是 mock 数据。

## 9. 与 Grok `SourceEvidence`（`0e48995`，本地未推送）的对应

| Grok 字段 / 取值 | pe-1.0 | 差异与处理 |
|---|---|---|
| `evidence_type`：fingerprint / watermark / signed_credential / trusted_log / ideal | 同名，另有 retrieval、joint、knowledge_bound_watermark、mock | 直接映射 |
| `candidate_issuance_ids` | `issuance_candidates.items[].id` | 加 status，区分"没查"和"查了没有" |
| `matched_knowledge_units` + `holdings_asserted` | `unit_claims[].presence` | `holdings_asserted = true` 且单元不在列表 → absent；pe-1.0 中 absent 不删除知识 |
| `verification_status`：verified / unverified / conflict / absent | 观测侧没有此字段；核验侧 verified / unverified / conflict / rejected / unknown | 状态由核验器给出，不由检测器自报；`absent` → `detector_status` 或候选集 `none` |
| `trusted_event_id` | `event_claim.event_id`（带端点与签名） | 事件必须带端点和签名，才能做最坏情况入账和去重 |
| `is_trusted_event()` 把 signed_credential、ideal 也当作可信 | 只有已证实的 `event_claim` 是事件；凭证只证实发行身份 | 与 Grok `confirms_propagation()` 的语义一致；`trusted_units()` 对凭证不写持有 |
| 只有可信日志和理想证据写入 K′ | 已核验的内容单元也写入 confirmed（核验 = 在持有者手里的产物中找到了该事实） | **语义差异**：pe-1.0 认为"产物里确有该事实"本身就是持有事实，与证据类型无关；未核验的一律不写 |
| 发行绑定参与授权（`independent_grant`） | 授权只看 `AccessRegistry` | Grok 的规则只会收窄注册表（仍要求 `is_authorized`），可以作为一个 `DisclosurePolicy` 变体接入，须通过契约 C1 |
