# CogniGuard 研究状态（唯一记录）

> 更新：2026-11-24，集成负责人（Mac 上的 Claude）。**这是唯一的状态文件**；其他文件中的状态描述与本文冲突时，以本文为准，并在此处登记更正。
> 规则：每个模块以"分支 + 提交 SHA + 实验清单"追溯。大型模型权重和敏感数据（`../cogniguard_raw/`、`../cogniguard_data/`、资产包原文）不进 GitHub。

## 1. 论文结构（2026-11-24 用户任务书确定）

| 层次 | 名称 | 负责人 | 贡献状态 |
|---|---|---|---|
| 核心 | 来源感知的动态联合安全控制 | Grok | **候选，未成立**。闭环能跑不等于增量成立；见第 5 节审查 |
| 拓展一 | CA-PD 有界联盟组合泄露控制 | Claude（Mac） | **证据最完整**：E5–E7、E9、E10 均冻结并有结果；局限见命题 4 |
| 拓展二 | 知识来源追踪水印 | Codex（RTX 5090） | **候选，目前无正向证据**：W0 无法判定，X3 STOP，KOSW/AFK 门未过 |

> 结构变化登记：`docs/RESEARCH_DECISIONS_20261124.md` 第 3 节原定"不纳入水印"、CA-PD 为核心。本次任务书把来源感知控制列为核心、CA-PD 列为拓展一、水印列为拓展二。原文件不改，以本条为准。

## 2. 分支与提交（2026-11-24 核对）

| 设备 / 负责人 | 分支 | SHA | 是否已推送 | 内容 |
|---|---|---|---|---|
| GitHub main | `main` | `5827e4e` | — | 合并到 PR #15（E9、E10、MySQL 可靠性） |
| 集成 | `integration/provenance-governance` | 见本文件所在提交 | 是 | `pe-0.1` 接口、状态、协议草案、统一组会文档 |
| Mac / Grok | `dev/source-evidence`（主检出 `/Users/MBP/Exp/CogniGuard/CogniGuard`） | `a9f122e` | **否**，比 main@`1cb6f7b` 多 2 个提交 | `experiments/parallel_x_20261124/`（X1–X5 开发扫描、x1/x3 诊断、组会记录） |
| Mac / Grok 子代理 | 8 个 `~/.grok/worktrees/.../subagent-*`，都在 `dev/confidential-secrets@893c6b3` | `893c6b3` | 基点已推送；每个工作树有 3 个未提交文件 | 未触碰 |
| GPU / Codex | `codex/hsw-st` | `9be4d73`（GitHub 最新，11-21） | 是 | KOSW 阶段 1、AFK 阶段 0 |
| GPU / Codex | 含 `d7239c4` 的分支、`experiments/hsw_provenance/` | `d7239c4` | **否**：CogniGuard 和 research-sync 两个仓库都查不到 | 无法审查 |
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
| **`ProvenanceEvidence`（pe-0.1）**、`augment_knowledge`、`trusted_event_credits` | `cogniguard/governance/provenance_evidence.py` | **本分支新增**；门尚未接线（Grok） |

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
| Gate W0 | `2e963d8` | W0-0：发行身份从未改变决策；W0-1 最终**无法判定**（F4/F5 NOT_RUN）。**保持原判** |
| 并行扫描 X1–X5 | 开发扫描，非正式；`a9f122e`（未推送） | X1、X2、X3 **STOP**；X4、X5 ANALYZE。**保持原判** |
| KOSW 阶段 1 / AFK 阶段 0 | `codex/hsw-st` | 都按预注册停止（容量不足、改写分离不够；AFK 有效证据 0.64–0.79 比特，要求 ≥ 7） |

## 5. 未解决问题（按优先级）

| # | 问题 | 负责人 | 阻塞什么 |
|---|---|---|---|
| 1 | `d7239c4` 及 `experiments/hsw_provenance/` 未推送 | Codex | 水印审查、X3-E2E |
| 2 | Gate W0 F4/F5（BGE、重排序）未补跑；需要下载模型权重（约 133 MB 起） | Claude（需用户同意下载） | W0-1 最终判定、F-strong 基线 |
| 3 | 核心机制的增量价值：并行扫描显示，现有门 + 提交复核 + 签名凭证已覆盖 X1–X3 的安全洞 | Grok | 核心贡献能否成立 |
| 4 | 门接线 `augment_knowledge` | Grok | X3-E2E |
| 5 | CA-PD 相对全局并集账本的优势需要 w > k+1 的真实场景 | Claude | 拓展一的定位 |
| 6 | E10 的 Eedi 用的是镜像数据（MANIFEST `35ebd79c…` ≠ E6 的 `d4401ef4…`），需要在本机用官方数据补跑 | Claude | E10 Eedi 部分与 E6 逐字节对应 |
| 7 | 语义计量（名称类单元）、更细的谓词 | Claude | A1、A2 |
| 8 | Toland 2010、Chen & Chu 2008 原文 | 用户（图书馆） | 相关工作 |

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

## 7. 协作规则

- Grok、Codex 各自分支开发，**不共同修改 main 或同一个核心文件**；合入一律经本集成分支审查后开 PR。
- 不强推、不删分支、不重置他人分支、不中断运行中的实验、不覆盖未提交工作。
- 冻结实验不改；偏离写 `DEVIATIONS.md`；历史 STOP 不做事后阈值调整。
