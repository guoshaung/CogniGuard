# R_PREREG — MM-FOPD-R v3（方案 B）

> 状态：**方法已定为 ReasoningBank。DashScope 密钥缺失，冒烟和满量都没有开跑。**
> 日期：2026-11-20。本版任务书时限 7 天，到 2026-11-27。
> 协议：换模型的重复（replication with a different backbone）。不得称为复现。
> 代码：`mmfopd-repro/EvoMemBench` @ `3efc221fd8d5f4de7c2dc2022357e600d26325c7`

---

## 0. 这一步停在哪里

原文骨干 DeepSeek-V3.2 已下架。用户选择方案 B：代码、基准、评分、样本量按原文，只把骨干换成 DeepSeek 官方 API 上的当前模型。

用户已选定 ReasoningBank，对照组 NO-MEM，只做第一阶段。判定门槛已写入 §6。2026-11-20 核对价目后没有开跑：`text-embedding-v4` 仍在售，但本地没有 `DASHSCOPE_API_KEY`，本机无法开通百炼。任务书规定的备选 AgentKB 在 `3efc221` 里同样会构造 `DashScopeEmbedder`，没有密钥会在初始化时失败。没有改嵌入实现，没有冒烟，没有满量。

DeepSeek 密钥在本地 `mmfopd-repro/.env`，已 gitignore。DashScope 密钥不在该文件，也不在环境变量里。

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
| AgentKB | `agent_kb_provider.py` 的 `AgenticKnowledgeBase` | 脚本注释写本地句向量。实际代码 `self.embedding_model = DashScopeEmbedder()`。缺 `DASHSCOPE_API_KEY` 时构造函数抛出 `ValueError`。默认模型是 `text-embedding-v3`，不是 v4 |
| ReasoningBank | `reasoning_bank_backend.py` | 检索要 DashScope `text-embedding-v4` |
| Mem0、A-MEM、MemOS、MemoryOS、GraphRAG、Qwen3-Emb | 各自 backend | DashScope 或同类嵌入端点 |
| MemEvolve | 论文有这一行 | `factory.py` 没有这个 `memory_type`。现有代码跑不了 |

预定规则（任务书，供决定）：在这一列里选相对 DeepSeek-V3.2 增益最大、且只需 LLM 密钥、不需要 DashScope 嵌入的方法。需要嵌入则另行讨论。

按这条规则能直接排出来的事实：

- ACE 的等权增益是 −2.0 pp。任务书认为这种情况下重复 ACE 没有意义。
- 上一版把 AgentKB 写成不调用 DashScope。`3efc221` 的提供者代码会创建 `DashScopeEmbedder`。脚本注释和代码不一致，以会执行的代码为准。AgentKB 不能在没有 DashScope 密钥时初始化。
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

冒烟、费用外推、200 条结果、`per_item.csv` 数据行、`final_decision.md`。阻塞是 DashScope 密钥，不是预算。

## 6. 已锁定的方法与判定门槛

| 项 | 值 |
|---|---|
| 方法 | ReasoningBank。官方脚本 `scripts/run_eval_reasoning_bank_inenv_allcrossenv_fc.sh`，只跑其中 Phase 1 |
| 对照 | NO-MEM，官方 `scripts/run_eval_no_memory_inenv_fc.sh`，`--memory-type none --mode FC` |
| 不做 | 该脚本后半的 12 个跨环境对 |
| 原文等权增益 | ReasoningBank 68.5 − DeepSeek-V3.2 45.0 = **+23.5 pp** |
| 重现门槛 | 配对增益 ≥ **11.75 pp**（原文增益的一半），且配对 bootstrap 95% 区间下界 > 0 |
| AgentKB 备选门槛 | 若改用 AgentKB，原文增益 +14.35 pp，门槛 ≥ **7.2 pp**，同样要求区间下界 > 0 |
| 样本量 | 每环境 50，共 200。冒烟计划是 NO-MEM 每环境 1 条，方法每环境 2 条 |
| 预算 | DeepSeek 与 DashScope 分开列，合计 150 元。不超过才满量 |

绝对成功率不与原文比。不得换方法、换子任务或改参数后重跑来凑门槛。

## 7. 2026-11-20 的模型与价目

当天 `GET https://api.deepseek.com/models` 只返回两个 id：`deepseek-flash`、`deepseek-v4-pro`。通用对话模型锁定为 **`deepseek-flash`**，文档版本 **DeepSeek-V4.1-Flash-1017**。`deepseek-chat` 不在列表里。思考模式按官方默认，适配层不额外传 temperature、max_tokens 或思考开关。仓库 handler 上的 `temperature=0` 本来就不会进入 Ark 请求。

价目截图：`artifacts/paper/deepseek_pricing_20261120.png`，页面 <https://api-docs.deepseek.com/zh-cn/quick_start/pricing>。单位是元 / 百万 tokens。高峰为北京时间周一至周五 9:00–12:00、14:00–18:00，不含法定节假日。2026-11-20 是周五。

| 模型 | 输入缓存命中 空闲/高峰 | 输入缓存未命中 空闲/高峰 | 输出 空闲/高峰 |
|---|---|---|---|
| deepseek-flash | 0.02 / 0.04 | 1 / 2 | 4 / 8 |
| deepseek-v4-pro | 0.15 / 0.30 | 4.5 / 9.0 | 13.5 / 27.0 |

DashScope `text-embedding-v4` 仍在售。截图 `artifacts/paper/dashscope_embedding_20261120.png`，页面更新时间 2026-11-18，<https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api>。北京地域单价 **0.0005 元 / 千输入 token**，即 **0.50 元 / 百万 token**。批量调用半价。页面写明需自行开通并配置 API Key。默认维度 1024，单行最长 8192 token。仓库 ReasoningBank 使用的就是 `text-embedding-v4` 和 1024 维。

## 8. 适配层

`adapters/ark_client_deepseek.patch`。`LLM_BACKEND=deepseek` 时，`ArkBatchClient` 改打 `https://api.deepseek.com` 的 `chat.completions`。请求体仍是 `model`、`messages`、可选 `tools`。评分脚本未改。这个补丁已在本地工作树应用，没有提交到 EvoMemBench，也没有推送到 `DSAIL-Memory`。

可选环境变量 `DEEPSEEK_USAGE_LOG` 只追加 token 计数，供缓存命中和外推使用。评测 CSV 不读它。
