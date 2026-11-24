# 组会可引用摘要：CogniGuard Phase 2 横向对比

**比较对象与复现等级**：

- OCELOT（2026）：论文公式复现。没有代码和权重，所以学习得到的成本换成精确后验，这对 OCELOT 有利；保留跨接收方并集计费和 μ 信任权重。
- Sum Leaks（2025）的本地防御、CoDef、ToM：结构化形式。
- Staddon 2003：只做到定义层，即 c-共谋抵抗加 crowd control；令牌算法未核实。
- Woodruff–Staddon 2004 固定配额。
- 精确联盟枚举。

没有把任何结构代理称为 OCELOT。

**协议**：

- Protocol A：同一信息，即同一授权、知识状态、BGE + NLI 证据、请求顺序和 k；所有方法在同一个 Oracle 快照上作答，分母相同。
- 三个世界：Phase 1（真实传播加 NLI）、Eedi（真实谓词见证）、Sum Leaks（真实连接见证）；
- 30 组配对种子，24,000 条运行；预注册在正式运行前冻结；工作点只在开发种子上选定。

**结论（有界联盟威胁模型）**：

1. **对 Sum Leaks 防御**：k ≥ 2 时，效用相同，危险放行率低 0.67–0.96（12 / 12 格）。它们只看单个提问者，看不到跨接收方的联盟。
2. **对固定配额（WS04）**：同一 k 下，12 / 12 格更有用且不更危险。
3. **对 OCELOT-PF**：危险放行率 ≤ 5% 时，M3 效用为 0.99–1.00，OCELOT-PF 为 0.13–0.65（phase1、Eedi）；在 Sum Leaks 上两者相同。
4. **对 Staddon crowd control**：见证大小 ≤ k 时两者等价（命题 4）。k < \|W\| 时，M3 效用高 0.10–0.38，但只防 ≤ k 人联盟。
5. **CA-PD 与精确枚举**：162,000 条请求中决策完全相同；小规模时 CA-PD 更慢，k = 3 时快 2–5 倍。端到端约 0.38 s / 产物，主要是 NLI。

**必须同时说明**：

- 若改为防**任意规模**联盟（事后敏感性分析），crowd control 与 OCELOT 式全局记账在部分格子中**优于** M3，例如 phase1/high/k2：M3 的危险放行率 0.25，crowd control 0.02。M3 的优势依赖"联盟规模有界"。
- path 模式下，phase1 中 M3 造成的新增秘密恢复（0.07–0.09）高于更保守的 WS04、OCELOT-PF（0.004–0.03），后者的效用只有 0.42–0.74。
- OCELOT 只有 PF，Staddon 只有 DEF，Sum Leaks 只有 STR；Protocol B 的原生运行未做；没有测实际教学任务完成质量。

**图**：`results/figures/fig1_pareto`、`fig2_coalition_size`、`fig3_efficiency`。
