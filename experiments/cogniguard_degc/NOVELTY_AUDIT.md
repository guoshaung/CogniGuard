# DEGC 查新报告（Novelty Audit）

> 审核日期：2026-11-25。下文只列出已抓取页面、核对过标题、作者和年份的文献。标注“未能核实”的条目不得直接写进论文参考文献。

## 1. 结论摘要

- **数学主体是已有方法。** 每个单元的后验经 noisy-OR 得到；k 有界联盟的见证覆盖是单调 DNF，所以 P(Z=1) 就是 SBFE（随机布尔函数求值）在乘积分布下求的那个概率。“上界 ≤ δ 放行、下界 ≥ δ 拒绝”是二元 Bayes 决策加上 credal（鲁棒 Bayes）区间。“按代价选单元去降低决策变量熵”是决策变量上的 EIG（Filstroff 等），也可以看作 EC2/DRD（Golovin–Krause–Ray；Javdani 等）在两个决策区域下的近亲。
- **“双熵”只是叙事框架，不是两个独立量。** 在见证模型下，泄露熵（min-entropy vulnerability）和状态熵 H(Z) 都是同一个 P(Z=1)（及其校准区间）的单调函数。信息量上，DEGC 只有一个后验概率加一个置信区间。
- **应用扩展：** 把 SBFE/DRD 的测试对象换成自然语言检测器（精确/归一化匹配、BGE+NLI）的有噪证据，用 Beta 后验刻画漏检率这一二阶不确定性，并放进 LLM 多智能体发布门控。
- **可能独立的贡献（需实验支撑）：** (a) 把 k 有界联盟见证覆盖（CA-PD）当作被求值的布尔函数，并与有噪 NL 检测结合；(b) 多轮累积中，治理方的信念与真实知识状态逐步偏离（state divergence），并且会通过后续见证覆盖复利放大。我们没有检到直接处理 (b) 的工作。这两点更适合写成“问题刻画 + 系统组合”，不宜写成新的决策理论。
- **与 OCELOT 的关系：** 它是最接近的 LLM 工作（min-entropy 预算、bootstrap UCB 校准、credal audit），但没有对漏检做概率建模，也没有自适应地花费验证调用。DEGC 的增量是“检测不确定性的显式后验 + 预算化主动验证”，不是“熵控制”本身。

## 2. 逐项对照表

| 方向 | 代表文献（作者, 年份, venue, URL） | 已有的数学思想 | 与 DEGC 的关系 | 必须作为基线？ |
|---|---|---|---|---|
| LLM 智能体推断泄露预算 | Xie, Li, *OCELOT: Inference-Leakage Budgets for Privacy-Preserving LLM Agents*, 2026, arXiv:2606.12341 — https://arxiv.org/abs/2606.12341 | 每次发布按 min-entropy 计费，预算按 sink 信任加权；不可信 defender 出证据，确定性 verifier 审计；算子代价取 bootstrap UCB；credal audit；未标注 atom 一律按最高风险计；多 sink 共谋用共享预算加次可加性（条件独立假设）处理。原文称挑战式二次检查是 “empirical evasion detector, not a soundness mechanism” | 部分重叠：泄露熵和校准上界都重叠。OCELOT 不对 defender 漏检做后验建模，没有自适应验证，也没有见证集/并集式联盟覆盖。另外原文是单智能体加多 sink 的设定 | 是（保守默认 + UCB 预算变体） |
| LLM 智能体隐私信息流 | Staab, Wollschläger, Mirrokni, Shokri, *PrivacyFlow: Privacy in AI Agents through Information Flow Analysis and Consequence-Aware Risk Management*, 2026, arXiv:2610.40714 — https://arxiv.org/abs/2610.40714 | 执行前做 CI 式流追踪、对接收方背景知识建模、模拟推断，然后选择执行最小化计划、阻断或询问用户；摘要页没有给出定量泄露度量或不确定性的形式化 | 不同（定性推理式门控）；“不确定时询问用户”和 DEGC 的升级验证在精神上相近 | 建议（作为 LLM 推理式门控代表） |
| 组合式多智能体泄露 | Patil, Stengel-Eskin, Bansal, *The Sum Leaks More Than Its Parts*, 2025, arXiv:2509.14284 — https://arxiv.org/abs/2509.14284 | 定义组合式隐私泄露；ToM 防御；CoDef 共识防御 | 问题设定重叠（聚合推断）；摘要页未见对检测不确定性的建模 | 是（ToM/CoDef） |
| 多智能体信息论隐私 | Asif, Amiri, *Information-Theoretic Privacy Control for Sequential Multi-Agent LLM Systems*, 2026, arXiv:2603.05520 — https://arxiv.org/abs/2603.05520 | 用互信息刻画组合泄露并给出放大界；方法是训练期正则 | 不同（训练期，没有运行时门控或验证） | 否（相关工作即可） |
| QIF 基础 | Smith, *On the Foundations of Quantitative Information Flow*, 2009, FoSSaCS, LNCS 5504 — https://alastairreid.github.io/RelatedWork/papers/smith:fossacs:2009 ；Alvim, Chatzikokolakis, Palamidessi, Smith, *Measuring Information Leakage Using Generalized Gain Functions*, 2012, IEEE CSF — https://researchportal.ip-paris.fr/en/publications/measuring-information-leakage-using-generalized-gain-functions/ | min-entropy 泄露；g-leakage 用增益函数刻画“猜中某种性质” | 等价：见证重构就是一个 g-vulnerability（增益 = 1[覆盖见证]） | 否（作为定义来源） |
| QIF 中的信念 / 信道不确定 | Clarkson, Myers（及 Schneider），*Belief in Information Flow*, 2005 — https://ptolemy.berkeley.edu/projects/truststc/pubs/561.html （**venue 与作者列表未完全核实**；页面显示作者为 Clarkson, Myers，venue 写作 JCS，但检索元数据显示 CSFW 2005 / JCS 2009 期刊版有 Schneider）；统计 QIF：Chatzikokolakis, Chothia, Guha, *Statistical Measurement of Information Leakage*, 2010（**仅见检索摘要，未抓取原页，未能核实**） | 攻击者信念的准确度；用统计方法估计信道泄露并给置信区间 | 部分重叠：都承认“信道/泄露量本身需要估计”。区别在于，这些工作建模的是攻击者的信念或信道估计误差，DEGC 建模的是防御方对“已披露了什么”的不确定性。我们没有找到专门做“防御方知识状态不确定”的 QIF 工作（未检到 ≠ 不存在） | 否 |
| SBFE / 序贯测试 | Deshpande, Hellerstein, Kletenik, *Approximation Algorithms for Stochastic Boolean Function Evaluation and Stochastic Submodular Set Cover*, 2013/SODA 2014 — https://arxiv.org/abs/1303.0726 ；Allen, Hellerstein, Kletenik, Ünlüyurt, *Evaluation of DNF Formulas*, 2013 arXiv（后发表于 Algorithmica 2017，期刊信息仅见检索结果）— https://arxiv.org/abs/1310.3673 ；Ünlüyurt, *Sequential Testing Problem: A Follow-up Review*, 2025, Discrete Applied Mathematics 377 — https://arxiv.org/abs/2511.15742 （2004 年原综述的页面未能抓取） | 乘积分布下以最小期望代价确定单调 DNF 的取值；k-DNF 是 NP-hard，有近似算法 | **核心等价**：测试无噪时，“验证单元直到能判定是否覆盖见证”就是单调 DNF 的 SBFE。DEGC 不同在三处：测试有噪、有阈值 δ（不需要把 Z 完全确定）、有预算截断 | 是（SBFE 自适应贪心） |
| 自适应次模 / 有噪主动学习 | Golovin, Krause, *Adaptive Submodularity*, 2010, arXiv:1003.3967 — https://arxiv.org/abs/1003.3967 ；Golovin, Krause, Ray, *Near-Optimal Bayesian Active Learning with Noisy Observations*, 2010, NIPS — https://arxiv.org/abs/1010.3091 | 自适应贪心有近似保证；EC2 在有噪、非均匀代价下识别等价类 | 部分等价：把“放行”“拒绝”两个决策区域当等价类，EC2 直接适用 | 是（EC2） |
| 决策区域判定 | Javdani, Chen, Karbasi, Krause, Bagnell, Srinivasa, *Near Optimal Bayesian Active Learning for Decision Making*, 2014, AISTATS (PMLR 33) — https://proceedings.mlr.press/v33/javdani14.html | 区域可以重叠的决策区域判定，用 HEC 算法 | **最接近的决策理论对应**：DEGC 的“上界 ≤ δ / 下界 ≥ δ 即停止”就是在判定状态落在哪个决策区域 | 是（HEC/DRD） |
| 决策导向主动学习 | Filstroff et al., *Targeted Active Learning for Bayesian Decision-Making*, 2021, arXiv:2106.04193 — https://arxiv.org/abs/2106.04193 ；Houlsby et al., *BALD*, 2011, arXiv:1112.5745 — https://arxiv.org/abs/1112.5745 | 在最优决策的后验上最大化 EIG；BALD 是参数上的互信息 | **等价**：DEGC 的“决策变量熵下降 / 代价”就是 Filstroff 的准则加上代价归一化 | 是（EIG-on-decision、BALD 风格的 max-H(Z)） |
| VoI | Howard, *Information Value Theory*, 1966, IEEE Trans. SSC（**未能核实**：DOI 10.1109/TSSC.1966.300074 可解析到 IEEE Xplore，但页面内容没有抓到） | 短视 VoI | 部分等价：取 0-1 损失、阈值 δ 时，短视 VoI 和决策熵 EIG 是同一个贪心框架下的两种打分 | 是（已有） |
| 不确定性分解 / 分布鲁棒机会约束 | Hüllermeier, Waegeman, *Aleatoric and Epistemic Uncertainty in Machine Learning*, 2019 arXiv（MLJ 2021）— https://arxiv.org/abs/1910.09457 ；Calafiore, El Ghaoui, *On Distributionally Robust Chance-Constrained Linear Programs*, 2006, JOTA 130(1) — https://people.eecs.berkeley.edu/~elghaoui/pubs_dist_rob_jota.html | 认知/偶然不确定性、二阶（credal）不确定性；在歧义集上取最坏情形的机会约束 | 等价：Beta 后验给出的上下界，就是以 Beta 可信区间为歧义集的 DR 机会约束 | 否（作为消融：点估计 vs 鲁棒界） |
| 弃权 / 延迟决策 / 级联裁判 | Geifman, El-Yaniv, *Selective Classification for DNNs*, 2017 — https://arxiv.org/abs/1705.08500 ；Madras, Pitassi, Zemel, *Learning to Defer*, NeurIPS 2018 — https://arxiv.org/abs/1711.06664 ；Jung, Brahman, Choi, *Trust or Escalate*, 2024 — https://arxiv.org/abs/2407.18370 | 低置信时弃权或上报；从便宜到强模型的级联 | 部分重叠：DEGC 的“验证调用”就是一种 escalation，区别在于选择的是哪个单元 | 是（置信度阈值级联） |
| 智能体安全中间件 | Chennabasappa et al., *LlamaFirewall*, 2025 — https://arxiv.org/abs/2505.03574 ；Shi et al., *Progent*, 2025 — https://arxiv.org/abs/2504.11703 ；Tsai, Bagdasarian, *Contextual Agent Security (Conseca)*, HotOS 2025 — https://arxiv.org/abs/2501.17070 ；Greenblatt et al., *AI Control*, 2023 — https://arxiv.org/abs/2312.06942 | 护栏扫描器；最小权限策略；按任务生成策略；可信监控超过阈值时交给人审 | 不同（不建模泄露概率），但阈值加升级的模式相同 | AI Control 式“可疑度阈值 → 审核”建议作为基线 |
| CI 隐私智能体 / 基准 | Bagdasarian et al., *AirGapAgent*, 2024 — https://arxiv.org/abs/2405.05175 ；Shao et al., *PrivacyLens*, 2024 — https://arxiv.org/abs/2409.00138 | 按任务最小化数据访问；隐私规范评测 | 不同 | AirGapAgent 作为“最小化”对照（可选） |
| 推断控制 | Staddon, Golle, Zimny, *Web-Based Inference Detection*, 2007, USENIX Security — https://www.usenix.org/legacy/events/sec07/tech/staddon.html | 用外部语料估计发布后的推断可能性，高风险的交人工 | 部分重叠：都是“估计接收方已知 + 推断风险”。Staddon 的 “crowd control”/“dynamic inference control” 原文**未能核实** | 否 |

## 3. 等价性分析

1. **机会约束等价于 Bayes 后验风险。** 设放行后真重构的损失为 a，误拒的损失为 b。Bayes 规则是 P(Z=1) ≤ b/(a+b) 时放行。取 δ = b/(a+b)，DEGC 的点估计机会约束与它**完全等价**。加上 Beta 校准区间后，就变成 Γ-minimax / 分布鲁棒的机会约束（Calafiore–El Ghaoui 一类）。这里没有新数学。
2. **H(Z) 不是正确的决策不确定度。** H(Z) 在 P=0.5 处最大，阈值决策关心的却是 P 相对 δ 的位置。δ≠0.5 时，最大化 H(Z) 下降会把验证预算花错地方。如果 DEGC 实际用的是“决策变量 D=1[P≥δ] 的熵”或 P(决策翻转)，那它等价于 Filstroff 的“最优决策上的 EIG”。按代价归一化后，它是 EC2/HEC 的短视近似：两个区域（放行/拒绝），区间 [下界, 上界] 跨过 δ 就是“未判定”。0-1 损失下的短视 VoI 是同一框架下的另一种打分，未必更差。论文必须说明用的是哪一种，并在 δ≪0.5 的设定下比较 H(Z) 与 H(D)。
3. **无噪退化。** 检测器完美、δ→0 时，问题退化为单调 DNF 的 SBFE（Allen 等）。所以 DEGC 的选择规则至少要和 SBFE 贪心比较，最好也和 HEC 比较。
4. **“双熵”。** 在见证模型下，泄露熵 = f(P(Z=1))，状态熵 = g(P(Z=1))，两者共用一个充分统计量。“双熵”不宜宣称为两个独立维度，只能说两个视角。
5. **可能真正新的部分（只能写成组合与问题刻画）：**
   - 被求值的布尔函数是“任一规模 ≤ k 的联盟持有单元的并集覆盖某个见证”。这仍是单调 DNF，但项数随 k 组合增长，需要 CA-PD 精确判定，再与 SBFE 近似结合。
   - 证据来自异构 NL 检测器，用 noisy-OR 和 Beta 漏检率建模。注意：noisy-OR 的独立性假设和 SBFE 的乘积分布假设，在 BGE/NLI 误差相关时都会失效，这一点要实测。
   - **状态偏离失效模式**：多轮中未被检出的披露不断累积，治理信念与真实状态背离，后续见证覆盖会被系统性低估。OCELOT 的“unknown = 最高风险”保守默认，是对这个问题的一种非概率处理。我们没有检到把它形式化并做预算化主动修正的工作。
   - “预算耗尽后回落到机会约束”这一设计是工程选择（防止高熵直接导致拒答），不算理论贡献。

## 4. 必须加入的对比

1. **SBFE 自适应贪心**（单调 DNF，按 p_i/c_i 排序或 Allen 等的近似算法）。
2. **EC2 / HEC（DRD）**，两个决策区域，有噪测试。
3. **决策变量 EIG**（Filstroff），以及 **max-H(Z)**（BALD 风格），用来检验 H(Z) 和 H(D) 的差别。
4. **短视 VoI**（已有）、风险驱动、低置信优先、随机（已有）。
5. **OCELOT 式保守基线**：未确认单元一律视为已披露，配合 UCB 代价和累计预算，不做验证。
6. **级联 / 升级基线**：Trust-or-Escalate 或 AI Control 式“置信度/可疑度阈值 → 强验证器”，不做单元级选择。
7. **消融**：点估计 P vs Beta 鲁棒界；去掉 k 联盟（k=1）；去掉回落规则；Oracle（已知真实状态）作上界。
8. **LLM 推理式防御**：Sum Leaks 的 ToM/CoDef；PrivacyFlow 代码若公开也应加入。
9. **相关误差压力测试**：检测器误差相关时，noisy-OR 的校准是否失效。

## 5. 风险与可写的贡献表述

**风险：** 审稿人若熟悉 SBFE、EC2 或 Filstroff，很可能认为“决策导向信息增益 + 机会约束”是已知方法的直接套用。如果标题或摘要写成“提出新的双熵决策理论”，有被判为重复发明的风险。OCELOT 和 PrivacyFlow 都是 2026 年的工作，需要在相关工作中正面对比。PrivacyFlow 只核实了摘要页。

**建议表述（ESWA）：**
- “我们把 LLM 多智能体发布门控中检测器的不确定性，形式化为对 k 有界联盟见证覆盖事件的后验推断，并指出状态偏离失效模式。”
- “在此基础上，我们把决策导向信息增益（Filstroff 等，2021）和决策区域判定（Javdani 等，2014）的思想实例化为预算化验证调度，并用 Beta 校准区间得到分布鲁棒的机会约束。”
- “实验表明，在相同验证预算下，相对于 SBFE/EC2/VoI/保守预算等基线……”（以实测为准）。

**避免：** “首个”“新的熵理论”“双熵是两个独立不确定性”。也避免声称 OCELOT 等工作“完全没有处理不确定性”，因为 OCELOT 有 UCB 校准和 credal audit。
