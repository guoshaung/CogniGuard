# CogniGuard 研究状态（唯一记录）

> 更新：2026-11-24，集成负责人（Mac 上的 Claude）。**这是唯一的状态文件**；其他文件中的状态描述与本文冲突时，以本文为准，并在此处登记更正。
> 规则：每个模块以"分支 + 提交 SHA + 实验清单"追溯。大型模型权重和敏感数据（`../cogniguard_raw/`、`../cogniguard_data/`、资产包原文）不进 GitHub。

## 1. 论文收束结论（2026-11-24，X3-E2E 正式运行后）

**结论：以 CA-PD 为唯一核心单独成文。** 来源感知动态治理降级为论文中的应用 / 集成一节，不作为独立贡献。水印作为负结果收束（附录或不写）。不再寻找新命题。

| 原层次 | 名称 | 最终状态 | 依据 |
|---|---|---|---|
| 核心 | 来源感知的动态联合安全控制 | **不成立为独立算法贡献**；保留为"证据入账的安全语义"集成章节 | X3-E2E：动态知识状态在 k = 1 时把危险放行减少 41%–51%、效用不变，但增益全部来自最强内容指纹（F_STRONG 单独即达到同一数值）。集成贡献只是安全语义（核验后入账、疑似层、证据不授权、不扣预算）。并行扫描 X1–X3 也显示，现有门 + 提交复核 + 签名凭证已覆盖测到的安全洞 |
| 拓展一 → **唯一核心** | CA-PD 有界联盟组合泄露控制 | **可独立成文**（需写明三处局限，见第 1.1 节） | E5–E7（结构保证；预算类基线在连接型泄露上失明）、E9（正确、精确、与 k 无关，m ≤ 12 实时）、E10（相同 k 下比 WS04 配额高 6.6–56.8 个百分点，42/42） |
| 拓展二 | 知识来源追踪水印 | **STOP（负结果）** | Gate W0-Real：M2 末五词检出 0/382，治理指标 60/60 无差别；X3-E2E H-WM 三个变体都不支持；单独使用时不如内容指纹 |
| — | 联合机制（动态证据 + CA-PD） | **本场景不可检验** | 教育叠加场景在 k = 2 时 Oracle 可放行数为 0，场景退化（事先声明）。不另找场景补救 |

### 1.1 CA-PD 论文必须写明的局限（不再新增命题）

1. **相对全局并集账本没有优势**：k ≥ max\|W\| 时两者等价（命题 4），现有基准中 k ≥ 3 即等价。优势只在 k < \|W\| 时出现，代价是不防守超过 k 人的联盟。
2. **相对 OCELOT 的证据不充分**：没有忠实复现（OCELOT-Edu 只是提示词近似，阶段 1b 暂停）；OCELOT 附录是否有跨接收方联合视图计费仍【待核】。论文只能写威胁模型和记账粒度的差异（按接收方、有界联盟 vs 按轨迹、成对校准），以及对结构近似基线（预算类、pairwise_only、union_view）的结果，**不得写"优于 OCELOT"**。
3. **计量假设在真实改写上不成立**：A1、A2 在 E3b-v2 中都不支持，保证只在结构层面成立。
4. 算法本身（集合覆盖 DP）不是原创；贡献在建模、归约、运行时约束和评估。

### 1.2 贡献结构（论文）

| 编号 | 贡献 | 证据 |
|---|---|---|
| C1 | 组合推断下离散秘密的形式化：谓词单元、单调泄露、见证集（引理 1），以及 g-泄露与两个特例 | `FORMAL_DEFINITION_v0.1.md` |
| C2 | 有界联盟放行判定：归约为包含接收方的最小覆盖，精确 DP 的复杂度与 k 无关；运行时预留与提交复核 | E9；MySQL 可靠性测试 |
| C3 | 评估：结构保证（E5–E7）；相对预算类、成对校准、配额基线的安全—效用比较（E5–E7、E10）；与全局账本的等价条件（命题 4） | E5–E7、E10 |
| C4（应用节） | 真实来源证据入账的安全语义，以及在真实传播文本上的端到端验证：内容证据带来安全增益，水印没有 | X3-E2E、Gate W0-Real |
| 局限 | 计量 A1、A2；OCELOT；全局账本等价 | E3b-v2、命题 4 |

> 历史登记：`docs/RESEARCH_DECISIONS_20261124.md` 第 3 节（CA-PD 为核心、不纳入水印）原文不改。2026-11-24 任务书曾把来源感知控制列为核心，本次收束后回到 CA-PD 为核心。

## 2. 分支与提交（2026-11-24 核对）

| 设备 / 负责人 | 分支 | SHA | 是否已推送 | 内容 |
|---|---|---|---|---|
| GitHub main | `main` | `5827e4e` | — | 合并到 PR #15（E9、E10、MySQL 可靠性） |
| 集成 | `integration/provenance-governance` | 见本文件所在提交 | 是 | pe-1.0 接口、X3-E2E 统一入口与冻结协议、状态、统一组会文档 |
| Mac / Grok | `dev/source-evidence`（主检出 `/Users/MBP/Exp/CogniGuard/CogniGuard`） | `0e48995` | **否**，比 main 多 3 个提交；另有未跟踪的 `provenance_link.py` | `experiments/parallel_x_20261124/`（X1–X5 开发扫描、x1/x3 诊断、组会记录） |
| Mac / Grok 子代理 | 8 个 `~/.grok/worktrees/.../subagent-*`，都在 `dev/confidential-secrets@893c6b3` | `893c6b3` | 基点已推送；每个工作树有 3 个未提交文件 | 未触碰 |
| GPU / Codex | `codex/hsw-st` | `9be4d73`（GitHub 最新，11-21） | 是 | KOSW 阶段 1、AFK 阶段 0 |
| GPU / Codex | `codex/hsw-st`（已含 `d7239c4`、`hsw_provenance/`、`hsw_provenance_next/`） | `065bb82` | 是 | KBPW M1–M3、内容基线、Qwen 7B 真实传播试点（X3-E2E 数据来源） |
| GPU / Codex | `codex/gate-w0-real` | `40213d3` | 是 | Gate W0-Real（STOP）；两份 pe-0.1 证据，已转换并通过正式提供方契约（Issue #16） |
| Windows | 无专属分支；`codex/hsw-st` 中有 Windows KOSW 入口（`ed52e02`） | — | — | 未能从本机直接核对 Windows 工作区 |
| Mac / Claude | `exp/e5-synthetic`、`exp/e6-eedi`、`exp/e3b2-paraphrase`、`dev/predicate-meter`、`data/confidential-datasets` | 均已并入 main | 是 | — |

本机未提交、且**不得触碰**：`experiments/ocelot_edu_20261122_real/`、`experiments/capd_e3b_20261123/`（主检出中未跟踪）。

## 3. 已实现接口

| 接口 | 位置 | 状态 |
|---|---|---|
| `AccessRegistry.is_authorized` / `RegistryHolder` | `cogniguard/governance/access_policy.py` | main |
| `check_release`（k 有界联盟，位掩码 DP，`max_free_units = 20`） | `cogniguard/governance/reconstruction.py` | main |
| `ReleaseGate.evaluate_and_reserve` / `select_and_reserve` / `commit`（提交复核） | `cogniguard/runtime/release_gate.py` | main |
| `DisclosureStore`（MySQL，命名锁） | `cogniguard/runtime/disclosure_store.py` | main；PR #15 加了跨进程可靠性测试 |
| `ProtectedTarget` / `TargetRegistry` | `cogniguard/governance/targets.py` | main |
| `LexicalMeter`、`PredicateMeter` | `cogniguard/runtime/meters.py` | main |
| `DomainEvidence` / `EvidenceEnvelope` | `cogniguard/governance/evidence.py` | main |
| **来源证据接口 pe-1.0**（Observation、核验、三层状态、四接口、契约） | `cogniguard/provenance/` | **本分支，已冻结**；取代 pe-0.1。模块与联动状态见 `INTEGRATION_STATUS.md` |

## 4. 正式冻结实验与结果

| 实验 | 预注册 sha / 冻结提交 | 结果 |
|---|---|---|
| E5 合成 | `2283dfac…` / `c8628de` | H1–H3 支持；LexicalMeter 漏判约 67% |
| E6 Eedi | `a1617850…` / `b9f4fd7` | H1–H3 支持；DR_normal 0.11–0.14 |
| E7 Sum Leaks | `a9edef63…` / `4890f92` | H1、H3 支持；预算类对照组在连接型泄露上 VR = 1.00（由结构决定） |
| E3b-v2 改写 | `e32e64c9…` / `1e5faf3`；对照 `342f9536…` / `75071ee` | H1（A1）不支持、H2 支持、H3（A2）不支持；对照确认 A2 失败来自谓词粒度，与改写无关 |
| E9 可扩展性 | `1cac7109…` / `afbc6b0` | H1 正确性支持（0 不一致）；DP 与 k 无关、随 2^m 增长；m ≤ 12 时 P95 ≤ 100 ms |
| E10 可用性 | `0bf5f971…` / `ddc1a8d` | H-Q 42/42 支持（比 WS04 配额高 6.6–56.8 个百分点）；k ≥ 3 时与全局并集账本决策等价 |
| Gate 0–2 | `d464626` | 问题存在（仅合成 coalition 模式）；证据最多挽回 B1 与 Oracle 之间 0.73 个百分点中的 0.40 |
| Gate W0 | `2e963d8`；F4/F5 附录 `7bc96ff` | W0-0：发行身份从未改变决策。F4/F5 补跑后 W0-1 最终 = **有额外价值，仅在 fragment**，且只是理想水印（5 词可恢复）的上界；需片段长度—检出率曲线 |
| Gate W0-Real（Codex） | `codex/gate-w0-real@40213d3` | **STOP**：真实 M2 末五词检出 0/382；BM25 与 BM25∪M2 在 60/60 配对运行中三项治理指标相同 |
| X3-E2E 教育场景 | `5d6ce72`；偏离 `eec96b6` | 21,120 次运行，未授权成功 0。H-Evidence 支持（4/4 变体）；H-WM 不支持（3/3）；疑似层、日志只能用效用换安全；k = 2 单元格退化。见 `experiments/x3_e2e_integration/RESULT.md` |
| 并行扫描 X1–X5 | 开发扫描，非正式；`a9f122e`（未推送） | X1、X2、X3 **STOP**；X4、X5 ANALYZE。**保持原判** |
| KOSW 阶段 1 / AFK 阶段 0 | `codex/hsw-st` | 都按预注册停止（容量不足、改写分离不够；AFK 有效证据 0.64–0.79 比特，要求 ≥ 7） |

## 5. 收束前剩余事项（只限 CA-PD 论文，不再新增命题或算法）

| # | 事项 | 负责人 | 性质 |
|---|---|---|---|
| 1 | Toland 2010、Chen & Chu 2008、OCELOT 附录、Woodruff–Staddon 2004 原文核对 | 用户（图书馆） | 相关工作定位，**必须** |
| 2 | E10 的 Eedi 部分用官方数据按冻结协议补跑（当前为镜像数据） | Claude | 复现，不改协议 |
| 3 | 局限写作：命题 4、OCELOT、A1 / A2 | Claude | 写作 |
| 4 | 软件工程场景（X3-E2E 已延期） | — | 可选；论文若不写，就从应用节删掉软件案例 |
| 5 | Grok 推送 `dev/source-evidence`；若纳入，须通过消费者契约（当前 C5 失败） | Grok | 只影响应用节 |

已关闭：水印路线（STOP）；来源感知核心的独立贡献（不成立）；语义计量、w > k+1 新基准（不做，写进局限）。

## 6. 数据与模型版本

| 数据 | MANIFEST sha256 | 用于 |
|---|---|---|
| 合成秘密 | `91854349…` | E5、E10 |
| Eedi（官方 Kaggle） | `d4401ef4…` | E6、E3b-v2 |
| Eedi（GitHub 镜像） | `35ebd79c…` | E10 |
| Sum Leaks | `7c53e01b…` | E7、E10 |

| 模型 | 用途 | 位置 |
|---|---|---|
| deepseek-flash、qwen3.7-plus | E3b-v2 改写 | 付费 API（约 22.34 元） |
| glm-5.2（token plan） | E3b-v2 攻击者 | token plan |
| MPNet（KOSW）、本地压缩器（AFK） | 水印 | GPU 服务器，不上传 |
| `BAAI/bge-small-en-v1.5`@`5c38ec7`、`BAAI/bge-reranker-base`@`2cfc18c` | Gate W0 F4/F5、X3-E2E F-strong | Mac 本机 HF 缓存，不上传 |

## 7. 协作规则

- Grok、Codex 各自分支开发，**不共同修改 main 或同一个核心文件**；合入一律经本集成分支审查后开 PR。
- 不强推、不删分支、不重置他人分支、不中断运行中的实验、不覆盖未提交工作。
- 冻结实验不改；偏离写 `DEVIATIONS.md`；历史 STOP 不做事后阈值调整。
