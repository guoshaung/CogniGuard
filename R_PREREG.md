# R_PREREG — MM-FOPD-R 预注册

> 状态：**代码与论文数字已冻结；正式评测未开跑（缺 `XAI_API_KEY`）**
> 修订日期：2026-11-20
> 执行者：Grok CLI
> 协议：same-code / same-benchmark / different-model (Grok via xAI)。不是同模型严格复现。

---

## 0. 一句话目标

在同一套 EvoMemBench 代码、同一 CrossEp-Tool 第一阶段（4 环境 × 50 = 200）上，用 xAI Grok 跑 NO-MEM 与 ACE，看 ACE − NO-MEM 的成功率增益方向是否与原文一致。

---

## 1. 复现对象

| 项 | 内容 |
|---|---|
| 基准 | EvoMemBench，arXiv:2605.18421v2（2026-06-15 修订） |
| 代码 | `https://github.com/DSAIL-Memory/EvoMemBench` |
| 本地路径 | `mmfopd-repro/EvoMemBench` |
| commit | `3efc221fd8d5f4de7c2dc2022357e600d26325c7`（短 SHA `3efc221`，与任务书参考一致） |
| 提交说明 | Update README with dataset information，2026-11-03 +0800 |
| 子任务 | `CROSSEP-TOOL` 第一阶段。id 文件各 50 条：`gorilla_fs`、`vehicle_control`、`trading_bot`、`travel_api` |
| 不做 | 12 对跨环境；MAS-Lab / A-Evolve；`reflexion/` |

### 1.1 两组

| 组 | 官方入口 | 本次实际调用 |
|---|---|---|
| NO-MEM | `Cross-Episode-Execution/Tool-Using/CROSSEP-TOOL/scripts/run_eval_no_memory_inenv_fc.sh` | 该脚本。`--memory-type none`，`--mode FC`。只做 4 个环境 |
| ACE | `scripts/run_eval_ace_inenv_allcrossenv_fc.sh` | **只用其中 Phase 1** 的同一对命令：`run_batch_generate --memory-type ace --mode FC`，再 `run_batch_evaluate`。不跑脚本后半的 12 对 |

评分脚本 `run_batch_evaluate.py` 未改。

### 1.2 原文数字（arXiv HTML v2 抄录）

出处：<https://arxiv.org/html/2605.18421v2>，§5.2.4，**Table 6**（Success rate %，CrossEp-Tool / Web / Emb）。Tool Using 四列依次是 Gorilla File System、Vehicle Control、Trading Bots、Travel Booking，其后是 **Avg. Rank**（名次，不是成功率）。

论文没有名为 NO-MEM 的行。无记忆对照是 Long-Context LLM 下的 **DeepSeek-V3.2**。记忆方法的骨干也是 DeepSeek-V3.2。ACE 行存在，不改用 SkillWeaver。

| 环境 | DeepSeek-V3.2（无记忆） | ACE |
|---|---:|---:|
| Gorilla File System | 64.0 | 68.0 |
| Vehicle Control | 36.0 | 56.0 |
| Trading Bots | 54.0 | 14.0 |
| Travel Booking | 26.0 | 34.0 |
| Avg. Rank（越小越好） | 13.5 | 9.8 |

表内没有四环境平均成功率。按四个成功率做等权平均（每个环境 50 条，与本仓库 id 文件一致）得到：

| 派生量 | DeepSeek-V3.2 | ACE | ACE − DeepSeek-V3.2 |
|---|---:|---:|---:|
| 四环境等权成功率 | 45.0 | 43.0 | **−2.0 个百分点** |

分环境方向：File System +4.0，Vehicle +20.0，Trading **−40.0**，Travel +8.0。三个环境 ACE 更高，Trading Bots 大幅更低，等权总体 ACE 略低。

**原文增益方向（预注册锁定）**：CrossEp-Tool 第一阶段的等权成功率上，ACE 没有高于无记忆 DeepSeek-V3.2。这是「总体不增益」，不是「总体正增益」。

同页 Table 10（CrossEp-Tool 平均步数，越低越好）：

| 环境 | DeepSeek-V3.2 | ACE |
|---|---:|---:|
| Gorilla File System | 14.82 | 18.62 |
| Vehicle Control | 13.44 | 16.02 |
| Trading Bots | 10.40 | 7.94 |
| Travel Booking | 10.90 | 10.60 |
| Average | 12.39 | 13.30 |

同页 Table 11（CrossEp-Tool token，越低越好）：

| 环境 | DeepSeek-V3.2 | ACE |
|---|---:|---:|
| Gorilla File System | 67664 | 139608 |
| Vehicle Control | 60192 | 127034 |
| Trading Bots | 39266 | 67865 |
| Travel Booking | 56026 | 102581 |
| Average | 55787 | 109272 |

---

## 2. 模型与端点

| 项 | 值 |
|---|---|
| 后端 | `LLM_BACKEND=xai` 时，`ArkBatchClient` 改走 `https://api.x.ai/v1` 的 `chat.completions` |
| 代码 | `EvoMemBench/.../bfcl_eval/memory/ark_client.py` |
| Base URL | `XAI_BASE_URL`，默认 `https://api.x.ai/v1` |
| 模型 id | **未锁定**。`mmfopd-repro/.env` 不存在。开跑前把控制台精确 id 写入 `XAI_MODEL` |
| 密钥 | 只放 `mmfopd-repro/.env` 的 `XAI_API_KEY`。禁止入仓、禁止写入聊天 |
| 解码 | 不改仓库载荷。`chat_completions` 只传 `model`、`messages`、可选 `tools`。运行器构造 handler 时写了 `temperature=0`，但 Ark 客户端本来就不把 temperature / max_tokens 发给端点。xAI 分支保持这一行为 |

`.env.example` 里曾经的 `grok-2-latest` 不在 2026-11-20 公开模型列表上。驱动脚本拒绝空模型和 `grok-2-latest`。

---

## 3. 冒烟与预算（冻结）

1. NO-MEM：`--limit-per-subset 1`（4 条）
2. ACE Phase 1：`--limit-per-subset 2`（8 条）
3. 用冒烟日志里的 token 外推 200 × 2 组，单位人民币
4. 硬顶 **150 元人民币**。外推超过则停，不砍样本、不改温度

本次没有冒烟日志，因此**没有**费用外推，也没有开满量。论文 token 量级只作风险提示，不代替这条门。见 `R_RESULT.md`。

---

## 4. 必须报告

1. 两组成功率（总 + 4 环境）+ 样本 bootstrap 95% CI
2. 与上表并列
3. ACE − NO-MEM 方向：本次 vs 原文等权 −2.0 pp
4. `per_item.csv` 四分类：`both_win` / `only_ace` / `only_no_mem` / `both_fail`
5. 10 条 ACE playbook，各 2–4 句
6. token（agent vs memory）、费用、墙钟

以上 1–6 都还没有实测数字。

---

## 5. 判定规则（冻结）

- **严格同模型复现**：不适用
- **Grok 迁移信号成功**：全流程跑通且未改评分，并且 ACE − NO-MEM 的等权成功率方向与原文一致（原文为负，−2.0 pp）
- **部分**：只满足一条
- **失败**：跑不通或没有合法 per-sample；或增益方向与原文相反
- 缺密钥导致未开跑：**不记成方法失败**。记为阻塞。教学任务迁移仍然不做
