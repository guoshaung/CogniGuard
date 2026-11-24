# Phase 2 基线审计：原文、可得性、复现等级与公式—代码映射

> 2026-11-24。原文读取方式：arXiv HTML v1 全文（OCELOT、Sum Leaks）；Staddon 2003 和 Woodruff–Staddon 2004 的全文在本环境无法打开（ACM 返回 403，Semantic Scholar 返回 403），只能使用 `docs/research/PRIOR_ART_AUDIT_20261124.md` 中用户读原文后提供的定义 [U]。
> 复现等级：
> - **FAITHFUL**：原代码或权重加原协议；
> - **PF**：按论文公式与决策规则实现，学习部件用本数据上的精确量替代；
> - **DEF**：原算法文本不可得，按已发表的定义精确实现；
> - **STR**：LLM 判断型防御的结构化形式化，回路中没有 LLM。
> 本文件中没有任何结构代理被称为 OCELOT 本身。

## 1. OCELOT（Xie & Li，arXiv:2606.12341，2026-06-10，v1）

**可得性**：

- 没有代码、权重或基准链接（论文写了"release OCELOT-Traj-500"，但没给链接）；
- 防御器是 Qwen-3.5-9B 经 SFT（82,400 条）和 GRPO 训练得到；
- 每类 rubric 的 B_0、最终的 C(op, f) 表、U_R 谓词都未公开。

→ **FAITHFUL 不可行**；Protocol B 中的 OCELOT 原生系统记为 **NA**。

**PF 实现**：`baselines.OcelotPF`。

| 论文 | 内容 | 本实现 |
|---|---|---|
| Eq.(4) | L̂_inst = log2[max_s P̂(S=s\|op(x)) / max_s P(S=s)]，P̂ 是代理对手的后验 | 精确后验：bit 模型下 L = \|A∩W\|；Eedi / Sum Leaks 用冻结的 `Secret.leakage`（均匀先验、恒等增益，即 v0.1 的 L） |
| Eq.(7) | c_i = max_f C(o_i, f) | 原子单元只有 identity 一种运算，所以 c = 该单元在并集视图上的精确增量泄露 = **oracle 校准成本**（OCELOT 校准能达到的最好情况） |
| Eq.(8)、Pre-Reg. A | cost = μ(z)·Σc_i；μ 为 1 / 2 / 4（required-service / semi-trusted / adversarial） | TA、辅导员 = 1，学生 = 2，EXT = 4 |
| App. C-D | "each release is costed against the union of prior cross-sink releases" | 增量以**全体接收方持有之并**为条件（任意合谋，不设上界） |
| Eq.(1)、Phase 4、Thm SP-1 | L_cum + cost ≤ B 才提交，否则升级（identity → … → drop） | 原子单元没有 generalize / substitute，超出即 drop（拒绝） |
| §IV-D | B = B_0 为每条轨迹的预算 | 两种范围：`field`（每个受保护目标一本账，最宽松）与 `trajectory`（同一所有者的全部目标共用 B） |
| Ledger | 哈希链、Ed25519 | 不影响判定，未实现。L_cum 由共享状态推出：μ_min·L(并集∩W)（增量成本的伸缩和；μ_min 取持有者中最便宜的信任级，对 OCELOT 有利） |

**B 的选择**：网格 {0.25, …, 12} 比特，在开发种子上按目标工作点选定（见 PREREG）。论文的 B⋆ = 4.0 比特只是跨系统的统一上限，不是 OCELOT 的工作预算。

**与论文的已知差异**：

1. 我们用精确后验替代代理对手的校准成本，所以 PF 的成本**更准确**，是对 OCELOT 有利的条件；
2. OCELOT 的 U_R 与 rubric 必要性检查无法复现，这里以授权代替"必要性"；
3. 论文自身的不一致（Lemma 1 的独立性假设与附录 A 的 Remark）不影响本实现，因为我们直接用精确的联合泄露。

**OCELOT-Edu 1b**（`codex/ocelot-repro`）：用提示词近似的臂已暂停在代价网格（662 / 2,280），不是官方 OCELOT。本轮不恢复，也不把它称为 OCELOT。

## 2. Sum Leaks（Patil, Stengel-Eskin, Bansal，arXiv:2509.14284，2025）

**可得性**：

- 代码与数据：https://github.com/Vaidehi99/MultiAgentPrivacy；
- 119 个场景（本地原始文件在 `cogniguard_raw/sumleaks/`，E7 的 MANIFEST 为 `7c53e01b…`，本轮重新生成后逐字节一致）。

**判定方式**：Leakage Accuracy = I[ŝ = s\*]，由 Qwen3-32B 作为 LLM 判官判定。

**防御**：全是 LLM 判断。

- CoT、CoT + L、CoT + L + H_t；
- ToM；
- Self-voting；
- CoDef：防御者共享非私有的查询与回应历史，按 A / B / C 投票。论文中"任一阻断"与"多数表决"两种说法冲突。

论文报告的最强结果：

- Balanced：Gemini CoDef 79.8%；
- Overall：Gemini CoDef 61.8%，GPT-5 ToM 59.3%。

**本实现（STR，Protocol A）**：

| 论文防御 | 结构化规则 | 代码 |
|---|---|---|
| CoT + L + H_t | 每个防御者只看自己表（资源）上该提问者的历史，补齐敏感组合才阻断；防御者之间互不可见 | `SumLeaksLocal` |
| CoDef | 防御者共享对该提问者的全部回应（单一提问者的跨防御者并集），补齐才阻断；论文只研究单一对手，没有跨提问者聚合。**Protocol A 下它与 CA-PD(k = 1) 精确相同** | `SumLeaksCoDef` |
| ToM | 提问序列指向某组合的"全部或大部分"时阻断，以比例 ρ 形式化，ρ ∈ {0.34, 0.5, 0.67, 0.75, 1.0}，在开发种子上选定 | `SumLeaksToM` |

**Protocol B（原生 LLM 防御）**：本轮**未运行**。需要多智能体、多轮 LLM 推理（119 场景 × 防御 × 多轮），只引用论文自报数字，并标注模型不同。

## 3. Staddon 2003（Dynamic Inference Control，DMKD）与 Woodruff–Staddon 2004（CCS §8）

**可得性**：全文不可得。用户先前读原文提供了 [U]：

- Staddon 2003 Definition 1：c-共谋抵抗（任意 c 个用户合起来都不能查完一个推断通道）；
- crowd control：许多用户已合起来查过某通道除最后一个以外的全部对象时，任何人都不能再查最后一个；
- WS04 §8：每个用户在每个通道上至多 ⌊(w − 1)/k⌋ 个对象。

**未核实**：Staddon 2003 的令牌分配与撤销是否依赖他人的实际查询。

| 规则 | 等级 | 代码 |
|---|---|---|
| c-共谋抵抗 ∧ crowd control | DEF | `StaddonDef` |
| crowd control 单独 | DEF | `CrowdControl` |
| WS04 固定配额 | DEF（Phase 1 的 B2 沿用同一规则） | `WS04Quota` |

**定义层面的推论**（不是实验结果，可以直接证明）：crowd control 成立，意味着全体之并不含任何通道，于是任意规模的联盟都补不齐，所以 c-共谋抵抗自动成立。因此 **StaddonDef ≡ CrowdControl**，网格中两者逐请求一致。与 CA-PD 的关系：

- CA-PD 允许的集合 ⊇ CrowdControl 允许的集合；
- k ≥ max\|W\| 时两者相等（命题 4）；
- k < \|W\| 时，CA-PD 放行更多，代价是不防超过 k 人的联盟。

## 4. 精确联盟枚举（同证据、同定义）

`ExactEnum`：对包含接收方、至多 k 人的全部联盟暴力枚举，安全定义与 CA-PD 相同。开发集中 54,000 / 54,000 条请求，两者决策一致。它只用来比较**开销**：在 N = 9 的场景里 CA-PD 并不更快；扩展性见 E9。
