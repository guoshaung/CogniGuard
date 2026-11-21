# C²-RAG R45 教学收益评分只读审计

审计日期：2026-11-07。结论：**8428.55 是 384 条非退化合成请求流中 M1 即时贪心的
规定分数之和，不是学生学习收益，也不是准确率。** 权重按回答类型硬编码；不同接收者、
知识原子、题目和请求次数没有各自的教学价值系数。建议在独立新实验中做收益与需求
敏感性分析；本审计不重跑策略、不重新生成数据、不修改原实验。

## 原始证据与版本

- 同步仓库固定提交 `fd93c708527009d76eae162338f16dae38d512f1`：
  [RESULT.md](https://github.com/guoshaung/research-sync/blob/fd93c708527009d76eae162338f16dae38d512f1/CG/experiments/2026-11-02-c2rag-r45-nondegenerate-forecast/RESULT.md)、
  [PROTOCOL.md](https://github.com/guoshaung/research-sync/blob/fd93c708527009d76eae162338f16dae38d512f1/CG/experiments/2026-11-02-c2rag-r45-nondegenerate-forecast/PROTOCOL.md)、
  [原始 run.py](https://github.com/guoshaung/research-sync/blob/fd93c708527009d76eae162338f16dae38d512f1/CG/experiments/2026-11-02-c2rag-r45-nondegenerate-forecast/run.py)、
  [per_stream.csv](https://github.com/guoshaung/research-sync/blob/fd93c708527009d76eae162338f16dae38d512f1/CG/experiments/2026-11-02-c2rag-r45-nondegenerate-forecast/per_stream.csv)、
  [evidence.tar.gz](https://github.com/guoshaung/research-sync/blob/fd93c708527009d76eae162338f16dae38d512f1/CG/experiments/2026-11-02-c2rag-r45-nondegenerate-forecast/evidence.tar.gz)。
- 压缩包内的 `config.json`、`freeze.json`、`frozen_streams.json`、`raw_traces.jsonl`、
  `per_stream.csv` 和 `MANIFEST.json` 是本次核查对象。包内 2912 条方法×流轨迹，每条
  `steps` 记录接收者、请求、动作、位掩码和 u。原包 SHA-256 为
  `3ae21311572ba6e42771d700a3c24c6baa716868323edee270e5723d835b8acc`，与远端
  `ARCHIVE_MANIFEST.json` 一致；包内冻结输入均通过 freeze SHA 核对；`run.py`、
  `raw_traces.jsonl`、`per_stream.csv`、`frozen_streams.json` 和 `config.json` 通过
  MANIFEST SHA 核对。局部已有源码快照 SHA-256 与原包 run.py 一致，下面用其行号导航：
  [r45_source_snapshot.py.txt](../../experiments/autonomous_research_20261106/r45_source_snapshot.py.txt)。
  审计读取压缩包内内容，未解压覆盖历史文件或执行原实验。

## 1–2. 每次请求如何评分、权重来源

实际 [actions(q,r)](../../experiments/autonomous_research_20261106/r45_source_snapshot.py.txt:83)
直接返回固定四种动作 `(bits, utility, name)`：

| 动作 | 释放内容 | 固定分数 |
| --- | --- | ---: |
| full | 请求原子 `q`，`bits = 1 << q` | 1.00 |
| alternative | 下一个环形原子 `(q+1) % r` | 0.80 |
| degraded | 不释放受保护原子，`bits = 0` | 0.25 |
| refuse | 不释放受保护原子，`bits = 0` | 0.00 |

即 `u(t) = 1·I(full) + 0.8·I(alternative) + 0.25·I(degraded) + 0·I(refuse)`；
收益由**选中动作类型**决定，代码没有逐学生或逐知识点权重。0.8 和 0.25 是研究者
在合成契约中事先规定的部分分值；不是从数据随机抽取，不是按知识重要性计算，也不是
来自学生或教师评价。原协议明确标记 stipulated partial-credit utilities；不能据此
认为循环下一原子的回答对原问题一定正确、有 80% 真实教学价值。

[options](../../experiments/autonomous_research_20261106/r45_source_snapshot.py.txt:90)
按安全判据筛选，[greedy](../../experiments/autonomous_research_20261106/r45_source_snapshot.py.txt:102)
在安全动作中选择即时 `u` 最大的；M2 将当前 u 加 8 条抽样未来中的平均后续贪心收益
（最多 6 步）进行选择，见 [select](../../experiments/autonomous_research_20261106/r45_source_snapshot.py.txt:150)。
`options` 无可选动作的兜底直接返回 0.25；原报告说明 spread 初态 M0 的 global union
判据已不满足，所以不能把 M0 在这一层的差距归为预测收益。

## 3. 8428.55 的逐请求复核

范围：`method=M1`、`quality=none`、`degenerate=0`；384 条不同流，每条 24 个请求，
共 **9216 条实际步骤**，不含 32 条退化对照流。对 `raw_traces.jsonl` 用十进制精确加总
每条 `steps[].u`，与 `per_stream.csv` 的 384 条流分数逐一核对，并逐步与冻结流的
`events` 匹配：**0 个不一致**。

| 实际动作 | 次数 | 分值 | 小计 |
| --- | ---: | ---: | ---: |
| full | 7443 | 1.00 | 7443.00 |
| alternative | 986 | 0.80 | 788.80 |
| degraded | 787 | 0.25 | 196.75 |
| refuse | 0 | 0.00 | 0.00 |
| **合计** | **9216** | — | **8428.55** |

例如 `8-2-3-uniform-empty-s0` 有 16 次 full、8 次 alternative：
`16×1+8×0.8=22.4`；`s1` 有 18 次 full、6 次 alternative，合计 22.8。
这是对归档逐步记录的**加总检查**，不验证真实教学质量，也不证明动作在真实课堂正确。
源码 [run.py:363](../../experiments/autonomous_research_20261106/r45_source_snapshot.py.txt:363)
初始化流分数，381–389 行逐步加分并写 trace；[finalize:398](../../experiments/autonomous_research_20261106/r45_source_snapshot.py.txt:398)
以各流 `utility` 加总为 method summary（412 行）。

## 4–5. 个体差异和教学含义

请求为抽象 `[recipient, q]`，recipient 是合成接收者索引，不是具备画像或身份标签的
真实学生；q 是 `a0…a(r-1)` 的请求索引，不是标注课程、难度或先修关系的教学题。
不同请求实际得分可以因安全状态导致选中不同动作而不同，但**同一种动作的分值对于
任何接收者、知识原子和时间均相同**。没有按个体、知识点或任务内容分配收益。

R45 的完整目标是所有 r 个原子组合恢复 TARGET 的合成保护规则（run.py 38–40 行），
不是教学先修图；历史位掩码用于安全可行性而不是学习者掌握度。没有已有掌握度、
教师评分、正确答案判定、课堂任务完成率或学习增益；degraded 的 0.25 也是人为给分。
因而 `8428.55/9216` 是平均合成效用分，不能叫 91.46% 正常答对率。

## 6. 是否天然有利于贪心？

有可能压缩长期优化空间，但现有证据**不能证明实验被设计成让贪心普遍最优**：

1. 权重静态且每轮独立相加；同样的回答即使没有增加接收者的状态，仍给相同分数。
   根据每流初态和原始 bits 逐步只读核算，M1 的 7443 个 full 中 **2335** 次、986 个
   alternative 中 **787** 次对该接收者的已披露原子集合没有新增（包括 spread 预持有）。
   重复讲解仍可能有真实教学价值，但 R45 没有数据证明其等同首次解释。
2. 已规定 `1 > 0.8 > 0.25 > 0`，M1 每轮选当前最高，M2 的模拟未来又使用 M1 作为
   continuation；这有利于可解释的即时策略，但并不等于 M2 被禁止选 alternative。
   6 步、8 样本的有限回看也可能漏掉更长期收益，不应将 M2–M1 差距直接归因于效用。
3. [probs/gen_stream](../../experiments/autonomous_research_20261106/r45_source_snapshot.py.txt:110)
   明确预置 uniform 和 burst：burst 请求原子 0 基础概率 0.6，其余各 `0.4/(r-1)`；
   第二轮起 `P(q=j|last)=0.75·I(j=last)+0.25·base[j]`；接收者 80% 集中在前
   `min(N,2r)` 个、20% 均匀。前后请求相关、重复和有限 24 步可能影响策略收益，
   但这是预注册随机生成规则，不是已证明按输赢挑选的序列。
4. 在 384 非退化流、9216 步中，同一流内之前出现过相同 `(recipient,q)` 的请求共
   2520 次，其中 2052 次 full；这与动作 no-op 不完全相同，不能互换统计。M2-trained
   的实际差值为 +19.90，即 +0.2361%；30 胜、305 平、49 负，既不是贪心处处最好，
   也不足以证明训练预测稳定占优。

## 建议的敏感性分析：只提出，不在本审计运行

- 在新独立实验、预注册候选权重和评价规则，覆盖 alternative、degraded 的合理多组值，
  包含保守低值与零值；分别报告安全、真实问题答对及部分教学事实，不将提醒自动算正确。
- 增加基于任务重要性、先修状态、掌握度的异质权重及重复解释的边际收益；权重来自独立
  教师标注或公开教学证据，不能拿测试结果反向调权重。明确区分教学任务完成与学习增益。
- 分开固定轨迹重计分与在同一冻结请求上重新决策：前者仅说明已选动作对评分敏感，
  不能推断策略在新权重下的表现；后者需新实验、同预算和共同随机数，保留历史结果。
- 改变请求重复率、热点/转移、顺序和 horizon，并作按相同初态及同一请求的配对；
  报告分层结果、所有负例、预测误差和条件离线上界。离线上界不是可实现的在线收益。

本轮只完成读取和既有结果算术复核；未进行敏感性实验、重生成数据或改动 R45 原始记录。
