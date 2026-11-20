# R_PREREG — MM-FOPD-R v3（方案 B）

> 状态：**Table 6 已从 arXiv v3 抄录。方法未选定。评测未开跑。**
> 日期：2026-11-20。本版任务书时限 7 天，到 2026-11-27。
> 协议：换模型的重复（replication with a different backbone）。不得称为复现。
> 代码：`mmfopd-repro/EvoMemBench` @ `3efc221fd8d5f4de7c2dc2022357e600d26325c7`

---

## 0. 这一步停在哪里

原文骨干 DeepSeek-V3.2 已下架。用户选择方案 B：代码、基准、评分、样本量按原文，只把骨干换成 DeepSeek 官方 API 上的当前模型。

CrossEp-Tool 第一阶段（同环境）的原文表已抄完。ACE 相对无记忆 DeepSeek-V3.2 的四环境等权成功率低 2.0 个百分点。按任务书，这里停下，等用户选定方法。不改适配层，不调用 API，不冒烟。

密钥在本地 `mmfopd-repro/.env`，已 gitignore。模型名留空，开跑当天再从官方文档锁定。

## 1. 出处

| 项 | 值 |
|---|---|
| 论文 | EvoMemBench: Benchmarking Agent Memory from a Self-Evolving Perspective |
| 版本 | arXiv:2605.18421v3，2026-10-30 修订。abs 页写明 v1 为 2026-05-18，v2 为 2026-06-15，v3 为 2026-10-30 |
| PDF | <https://arxiv.org/pdf/2605.18421>，文件元数据 `/arXivID` 为 `https://arxiv.org/abs/2605.18421v3`，33 页 |
| 表 | **Table 6**，PDF 印刷页 **9**，节 **5.2.4 Cross-Episode Execution Evolution** |
| HTML | <https://arxiv.org/html/2605.18421v3>，`figure id="S5.T6"` |
| 截图 | `artifacts/paper/table6_v3_crop.png`（表本身），`artifacts/paper/table6_v3_page9.png`（整页） |
| 同环境协议 | PDF 印刷页 **6**：跨 episode 时，记忆在同一环境的后续 episode 里复用，换到新的独立环境组时重置。跨环境迁移是另做的：先在源环境建记忆，再在目标环境冻结评估。Table 6 是各环境成功率。Figure 3 才是 CROSSEP-TOOL 的跨环境迁移 |

表题原文：Success rate (%) comparison across CROSSEP-TOOL, CROSSEP-WEB and CROSSEP-EMB. Best results among memory methods are bolded, and runner-up results are underlined. All memory-augmented methods use DeepSeek-V3.2 as the backbone.

无记忆对照在表里叫 Long-Context LLM 的 **DeepSeek-V3.2**，没有名为 NO-MEM 的行。每个工具环境 50 条，见 PDF 第 5 页 Table 2：CROSSEP-TOOL，BFCL-MultiTurn-Base，Gorilla File System (50)、Vehicle Control (50)、Trading Bots (50)、Travel Booking (50)。

数字同时从 PDF 文本和 HTML 表解析核对，与截图一致。

## 2. Table 6 的 Tool Using 列（成功率 %）

Avg. Rank 是名次，不是成功率，越小越好。等权平均是四个成功率的算术平均，表内没有这一格，标为派生。增益 = 方法 − DeepSeek-V3.2，也是派生。

| 类别 | 方法 | Gorilla | Vehicle | Trading | Travel | Avg. Rank | 等权平均 | 相对 V3.2 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Long-Context LLM | Gemini-3-Flash | 74.0 | 62.0 | 88.0 | 54.0 | 3.0 | 69.5 | +24.5 |
| Long-Context LLM | GPT-5-mini | 50.0 | 50.0 | 72.0 | 44.0 | 9.5 | 54.0 | +9.0 |
| Long-Context LLM | DeepSeek-V3.2 | 64.0 | 36.0 | 54.0 | 26.0 | 13.5 | **45.0** | 0 |
| Retrieval | BM25 | 68.0 | 88.0 | 66.0 | 32.0 | 5.8 | 63.5 | +18.5 |
| Retrieval | Qwen3-Emb-4B | 68.0 | 82.0 | 78.0 | 34.0 | 4.0 | 65.5 | +20.5 |
| Retrieval | GraphRAG | 66.0 | 68.0 | 72.0 | 40.0 | 6.5 | 61.5 | +16.5 |
| General long-term | Mem0 | 76.0 | 58.0 | 48.0 | 30.0 | 8.5 | 53.0 | +8.0 |
| General long-term | A-MEM | 68.0 | 62.0 | 70.0 | 26.0 | 8.8 | 56.5 | +11.5 |
| General long-term | MemOS | 72.0 | 60.0 | 36.0 | 28.0 | 9.8 | 49.0 | +4.0 |
| General long-term | MemoryOS | 72.0 | 72.0 | 56.0 | 36.0 | 5.8 | 59.0 | +14.0 |
| Procedural | AWM | 64.0 | 56.0 | 74.0 | 24.0 | 11.0 | 54.5 | +9.5 |
| Procedural | SkillWeaver | 66.0 | 48.0 | 44.0 | 28.0 | 12.3 | 46.5 | +1.5 |
| Procedural | AgentKB | 62.0 | 71.4 | 74.0 | 30.0 | 8.3 | 59.35 | +14.35 |
| Procedural | ACE | 68.0 | 56.0 | 14.0 | 34.0 | 9.8 | 43.0 | **−2.0** |
| Procedural | ReasoningBank | 64.0 | 82.0 | 86.0 | 42.0 | 4.8 | 68.5 | +23.5 |
| Meta-evolution | MemEvolve | 66.0 | 70.0 | 66.0 | 28.0 | 8.8 | 57.5 | +12.5 |

ACE 分环境差：File System +4.0，Vehicle +20.0，Trading −40.0，Travel +8.0。等权 −2.0 个百分点。AgentKB 的 Vehicle Control 印刷值是 **71.4**，不是 2 的倍数。按 50 条计，一条样本是 2.0 个百分点。这个格子按印刷值保留。

Web Search 与 Embodied AI 列在截图里，不列入本次选择。本次任务只做 CrossEp-Tool 第一阶段。

## 3. 嵌入依赖（供选方法，来自该 commit 的代码，不是论文表内的字）

论文印刷页 6 写：除非方法自带嵌入模型，默认嵌入后端是 DashScope 的 `text-embedding-v4`。CROSSEP-TOOL 在 `3efc221` 的实现更细：

| 方法 | 仓库入口 | 嵌入 |
|---|---|---|
| ACE | `bfcl_eval/memory/ace_backend.py` | 文件写明无嵌入、无 top-k，整本 playbook 注入。只需 LLM |
| SkillWeaver | `skillweaver_memory.py` | 按技能名和 docstring 做关键词匹配。生成技能要用 LLM。无 DashScope |
| BM25 | `bm25_backend.py` | 文件写明无 LLM、无嵌入 API |
| AWM | `agent_workflow_memory.py` | 本地 sentence-transformer 余弦，不是 DashScope API |
| AgentKB | `agent_kb_memory.py` | 本地 TF-IDF + sentence-transformer，不是 DashScope API |
| ReasoningBank | `reasoning_bank_backend.py` | 检索要 DashScope `text-embedding-v4` |
| Mem0、A-MEM、MemOS、MemoryOS、GraphRAG、Qwen3-Emb | 各自 backend | DashScope 或同类嵌入端点 |
| MemEvolve | 论文有这一行 | `factory.py` 没有这个 `memory_type`。现有代码跑不了 |

预定规则（任务书，供决定）：在这一列里选相对 DeepSeek-V3.2 增益最大、且只需 LLM 密钥、不需要 DashScope 嵌入的方法。需要嵌入则另行讨论。

按这条规则能直接排出来的事实：

- ACE 的等权增益是 −2.0 pp。任务书认为这种情况下重复 ACE 没有意义。
- 程序记忆里、增益最大、又不调用 DashScope 的是 **AgentKB（+14.35 pp）**。它要本地句向量模型，不是第二个 API 密钥。
- 若连本地嵌入模型也不引入，程序记忆里只剩 **SkillWeaver（+1.5 pp）** 和增益为负的 ACE。
- 整列里不需要 DashScope、增益更高的还有 **BM25（+18.5 pp）**。它是检索，不是程序记忆，而且不用 LLM。
- **ReasoningBank（+23.5 pp）** 是这一列程序记忆里最大的增益，代码路径要求 DashScope 嵌入。按任务书要另行讨论，不能直接开跑。

方法选定之前，判定规则里的「原文增益」无法锁定。

## 4. 方案 B 的判定规则（方法选定后才生效）

换了模型，绝对成功率不与原文比。只看增益是否在新模型上重现：

- 增益重现：方法 − NO-MEM 的配对增益 ≥ 原文增益的一半，且配对 bootstrap 95% 区间下界 > 0
- 增益未重现：区间包含 0，或点估计 ≤ 0
- 绝对成功率与原文的差距只描述，不参与判定

不得换方法、换子任务、改参数后重跑来凑结果。样本量保持每环境 50，共 200。预算 150 元。超过则停，不缩样本。

## 5. 还没做

模型名与价目表、适配层 diff、冒烟、费用外推、200 条结果、`per_item.csv` 数据行、`final_decision.md`。这些都等方法确认之后。
