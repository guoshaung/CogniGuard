# 结构化知识泄露与双重熵 V2：查新对照表

> 检索时间：2026-11-25。下表只列出**本次检索核实过书目信息**的文献（作者、年份、venue 与检索结果一致）。
> 多数条目只读到摘要或书目页，没有读全文；"已有的数学思想"一栏只写摘要层面能确认的内容。
> 与 DEGC 查新（`../cogniguard_degc/NOVELTY_AUDIT.md`）重叠的条目（OCELOT、PrivacyFlow、SBFE、EC2、DRD、Filstroff 等）不再重复核实，结论沿用。

## 1. 结论

- **"部分泄露"不是新问题。** 用攻击者猜中概率（Bayes vulnerability / min-entropy）或增益函数（g-leakage）度量"尚未完整重构、但候选空间已缩小"的风险，是 QIF 的标准做法（Smith 2009；Alvim 等 2012；Alvim 等 2020 专著）。
- **"按攻击者信念阈值拒绝查询"也已有。** Mardziel 等 2011/2013 跟踪查询者对秘密的信念，若某查询可能让信念超过阈值就拒绝。这正是"部分泄露门控"。
- **"拒绝本身泄露信息"是数据库审计的经典结论。** Kenthapadi 等 2005 的 simulatable auditing 指出拒绝会泄露，并引入概率化的部分泄露（partial compromise）。本工作的精确实验复现了这一点（`RESULT_V2.md` §3）。
- **"治理方不确定攻击者知道什么"可以写成 QIF 的超分布（hyper-distribution）。** 把 K 的后验推到攻击者后验上，得到的就是 McIver 等 2014 的 hyper。基于它的放行决策是经典贝叶斯决策；核验选择属于 VoI / EC2 / DRD（见 DEGC 查新）。
- **可能剩下的空间**（未检到 ≠ 不存在）：
  - 把上述工具组合到"多智能体、联盟（含 k = N 全体联盟）、见证结构 + 检测漏检"的 LLM 智能体治理里；
  - 实证说明完整见证判定（CA-PD）在哪些结构下漏掉部分泄露。
  这属于**应用与实证**层面，不是新的理论量。

## 2. 逐项对照

| 方向 | 文献（核实情况） | 已有的数学思想 | 与本任务的关系 | 是否作为基线 |
|---|---|---|---|---|
| min-entropy QIF | Smith, *On the Foundations of Quantitative Information Flow*, FoSSaCS 2009, LNCS 5504, pp. 288–302, doi:10.1007/978-3-642-00596-1_21 | Shannon 熵不能界定"一次猜中"的威胁，改用 vulnerability 与 min-entropy | **等价**："部分泄露风险 = 猜中概率上升"即 min-entropy leakage | 是（MINENT） |
| g-leakage | Alvim, Chatzikokolakis, Palamidessi, Smith, *Measuring Information Leakage Using Generalized Gain Functions*, IEEE CSF 2012, pp. 265–279, doi:10.1109/CSF.2012.26 | 增益函数刻画猜中部分、性质、相近值或多次猜测；容量界 | **等价**：串行/并行结构的"部分正确"度量就是 g-vulnerability | 是（GLEAK） |
| hyper-distribution | McIver, Morgan, Smith, Espinoza, Meinicke, *Abstract Channels and Their Robust Information-Leakage Ordering*, POST 2014, LNCS 8414, pp. 83–102 | 信道的抽象表示：后验分布上的分布（hyper）；强 g-leakage 序 | **核心等价**：治理方对 K 的后验 → 攻击者后验上的分布 = hyper；"双熵"中的 H(K|E) 只通过 hyper 影响决策 | 理论依据 |
| QIF 专著 | Alvim, Chatzikokolakis, McIver, Morgan, Palamidessi, Smith, *The Science of Quantitative Information Flow*, Springer 2020, doi:10.1007/978-3-319-96131-6 | 信道、hyper、g-vulnerability、精化、容量的系统理论 | 定义来源 | — |
| 信念与准确度 | Clarkson, Myers, Schneider, *Quantifying Information Flow with Beliefs*, J. Computer Security 17(5):655–701, 2009, doi:10.3233/JCS-2009-0353（会议版 CSFW 2005） | 区分攻击者信念与真实秘密；用信念准确度度量泄露；多轮交互可组合 | 部分重叠："攻击者信念 ≠ 真值"。没有建模防御方对攻击者知识的不确定 | 否 |
| 基于知识的策略执行 | Mardziel, Magill, Hicks, Srivatsa, *Dynamic Enforcement of Knowledge-based Security Policies*, IEEE CSF 2011, pp. 114–128；期刊版 JCS 21:463–532, 2013 | 跟踪查询者信念（概率分布），若查询可能使知识超过阈值则拒绝；用概率抽象解释给出可靠上界 | **最接近**：就是"部分泄露阈值门控"。差别：它假设查询者的先验与查询历史已知；本任务的检测漏检、背景知识与多主体联盟不在其模型中 | 是（MINENT / MINENT_SIM 即其离散精确版） |
| 可模拟审计 | Kenthapadi, Mishra, Nissim, *Simulatable Auditing*, PODS 2005, pp. 118–127, doi:10.1145/1065167.1065183；期刊版 *Denials Leak Information: Simulatable Auditing*, JCSS 2013 | 拒绝会泄露；只依赖已公开信息的审计器是可模拟的；概率化部分泄露 | **直接相关**：用真实秘密值判定的 QIF 门控不可模拟，会通过拒绝泄露；CA-PD 的见证判定不依赖取值，天然可模拟 | 是（REAL vs SIM 对照） |
| 隐私破坏放大 | Evfimievski, Gehrke, Srikant, *Limiting Privacy Breaches in Privacy Preserving Data Mining*, PODS 2003, pp. 211–222, doi:10.1145/773153.773174 | ρ1→ρ2 隐私破坏：性质的后验概率越过阈值 | 部分重叠：部分泄露按"性质概率越阈"定义 | 否 |
| 自适应多轮攻击 | Köpf, Basin, *An Information-Theoretic Model for Adaptive Side-Channel Attacks*, CCS 2007, pp. 286–296, doi:10.1145/1315245.1315282 | 剩余不确定性随交互次数变化 | 部分重叠：单主体多轮累积 | 否 |
| 有噪主动学习 | Golovin, Krause, Ray, *Near-Optimal Bayesian Active Learning with Noisy Observations*, NeurIPS 2010, arXiv:1010.3091 | 有噪时 GBS（信息增益式贪心）可能很差；EC2 有近似保证 | **等价**：按 H(K|E) 下降选核验 = GBS 式启发；应对比 VoI/EC2 | 是（VOI、VOI2） |
| 多智能体组合泄露 | Patil, Stengel-Eskin, Bansal, *The Sum Leaks More Than Its Parts*, 2025, arXiv:2509.14284 | 组合式泄露的基准与防御 | 问题设定 | 已在 Protocol B |
| 多智能体信息论隐私 | Asif, Mohammadi Amiri, *Information-Theoretic Privacy Control for Sequential Multi-Agent LLM Systems*, 2026, arXiv:2603.05520（摘要逐字核实；正文只读到约 30%） | 用互信息 I(O;S) 刻画逐级泄露并给放大界；训练期正则 | 不同：互信息（Shannon 类）、训练期、无联盟、无运行时门控 | 否 |
| LLM 智能体推断泄露预算 | OCELOT（见 DEGC 查新） | 每次发布按 min-entropy 计费 | **重叠**：部分泄露按 min-entropy 计费已有 | 已有 |

## 3. 判定建议（理论层面，实验前）

新版双熵的两部分分别归约为：

1. 攻击者侧 H(S|V)：即 min-entropy 或 g-leakage（Smith 2009；Alvim 等 2012）。
2. 治理侧 H(K|E)：它只通过 hyper 影响损失。决策是经典贝叶斯或机会约束；核验是 VoI / EC2。

只有在**相同信息、相同预算、相同安全目标**下，在决策或计算上表现出可验证的优势，才可能有独立贡献。这一点由 `RESULT_V2.md` 的实验检验。
