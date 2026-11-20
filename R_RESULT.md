# R_RESULT — MM-FOPD-R

## V3 方案 B（2026-11-20）

方法是 ReasoningBank，对照 NO-MEM，只做第一阶段。门槛仍是配对增益 ≥ 11.75 pp，且配对 bootstrap 95% 区间下界 > 0。

冒烟已经由官方评分跑完。NO-MEM 4 条成功率 1.0000，ReasoningBank 8 条成功率 0.8750。这不是研究结果。费用外推见 `R_PREREG.md` §9：合计空闲 6.29 元、高峰 12.30 元，低于 150 元。

NO-MEM 满量已完成，目录 `artifacts/full_deepseek/no_memory/`。200 条，API/runtime 失败 0。官方成功率 0.7300；四个环境 80.0 / 80.0 / 88.0 / 44.0。原文 DeepSeek-V3.2 同一列是 64 / 36 / 54 / 26，等权 45.0。骨干不同，绝对值只作对照，不参与判定。这次 NO-MEM 的 DeepSeek token 是输入 11,897,396（缓存命中 11,025,152，未命中 872,244）、输出 358,995。按当天价目，空闲 2.53 元，高峰 5.06 元。开跑时是周五 21:03 CST，空闲时段。

ReasoningBank 满量还在跑。配对增益、bootstrap 和 `per_item.csv` 还没有。

DeepSeek 模型是 `deepseek-flash`（DeepSeek-V4.1-Flash-1017）。嵌入是 DashScope `text-embedding-v4`。密钥只在本地 `.env`。适配层在 `adapters/ark_client_deepseek.patch`。没有推到 `DSAIL-Memory`。

## Grok 冒烟存档

> 以下是 grok-4.7 冒烟和 150 元预算停止的记录。不参与方案 B 的判定。
>
> 日期：2026-11-20
> 标注：*same-code / same-benchmark / different-model (grok-4.7 via Grok CLI proxy)*
> *not same-model strict repro*
> 状态：**烟雾已由官方评分完成。满量 200×2 因标价外推约 290 元、高于 150 元硬顶而停止。下面的 100% 是 n=1 或 n=2 的烟雾，不是研究结果。**

---

## 1. 已完成

| 项 | 结果 |
|---|---|
| EvoMemBench 上游 SHA | `3efc221fd8d5f4de7c2dc2022357e600d26325c7` |
| 本地客户端 | `5670db5`，以及 CLI 头 `647bbef`。`run_batch_evaluate.py` 未改 |
| 模型 / 端点 | `grok-4.7`，`https://cli-chat-proxy.grok.com/v1`，CLI `1.0.89` |
| 鉴权 | `mmfopd-repro/.env` 不存在。按用户要求使用 `~/.grok/auth.json` 的 CLI 会话。token 未写入本仓库 |
| 论文表 | Table 6 / 10 / 11 已抄录。锁定方向 ACE − DeepSeek-V3.2 = −2.0 pp |
| NO-MEM 烟雾 | `cross_episode_results/runs/xai_smoke_nomem_20261120_175202_no_memory_20261120_175203` |
| ACE 烟雾 | `cross_episode_results/runs/xai_smoke_ace_20261120_175420`（仅 Phase 1） |
| 拷贝 | `artifacts/no_mem/smoke_combined_*.` 与 `artifacts/ace/smoke_combined_*.` |
| 满量 | **未跑** |
| 12 对跨环境 | **未跑** |

文件时间（本机 UTC+8）：NO-MEM 目录名 17:52:02，汇总文件 17:52:34。ACE 目录名 17:54:20，汇总文件 17:59:12，跨度约 292 秒。ACE 四个环境并行，环境内 workers=1。

## 2. 烟雾成功率（官方汇总，不是 200 条研究）

api/runtime 失败均为 0。`errors.log` 四个环境都是空文件。

| 组 | n | 总体 | gorilla_fs | vehicle_control | trading_bot | travel_api | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---|
| NO-MEM | 4 | 1.0000 | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) | 1.0000 (n=1) | 不做 |
| ACE | 8 | 1.0000 | 1.0000 (n=2) | 1.0000 (n=2) | 1.0000 (n=2) | 1.0000 (n=2) | 不做 |

不在 n=1–2 上做 bootstrap，也不把这些格子写成研究结论。`per_item.csv` 保持只有表头。四分类未做。10 条 playbook 摘录未做。ACE 烟雾的 playbook 在运行目录 `phase1/<env>/memory/playbook.txt`，留给以后的满量。

### 2.1 NO-MEM 逐条（官方 per_sample）

| id | env | success | steps | input | output | total |
|---|---|---:|---:|---:|---:|---:|
| multi_turn_ours_0 | gorilla_fs | 1 | 18 | 96911 | 349 | 97260 |
| multi_turn_ours_50 | vehicle_control | 1 | 2 | 7728 | 56 | 7784 |
| multi_turn_ours_100 | trading_bot | 1 | 7 | 23773 | 213 | 23986 |
| multi_turn_ours_150 | travel_api | 1 | 7 | 30166 | 200 | 30366 |
| 平均 |  | 1.0000 | 8.50 | 39644.5 | 204.5 | 39849.0 |

NO-MEM 没有 memory token。平均延迟 12.99 秒/条。

### 2.2 ACE 逐条（官方 per_sample，total = inference + memory）

| id | env | success | steps | input | output | total |
|---|---|---:|---:|---:|---:|---:|
| multi_turn_ours_0 | gorilla_fs | 1 | 20 | 116422 | 1620 | 118042 |
| multi_turn_ours_1 | gorilla_fs | 1 | 14 | 69403 | 1750 | 71153 |
| multi_turn_ours_50 | vehicle_control | 1 | 2 | 13925 | 943 | 14868 |
| multi_turn_ours_51 | vehicle_control | 1 | 16 | 93666 | 2579 | 96245 |
| multi_turn_ours_100 | trading_bot | 1 | 6 | 26786 | 1962 | 28748 |
| multi_turn_ours_101 | trading_bot | 1 | 8 | 51349 | 2469 | 53818 |
| multi_turn_ours_150 | travel_api | 1 | 7 | 37072 | 2042 | 39114 |
| multi_turn_ours_151 | travel_api | 1 | 12 | 91107 | 2550 | 93657 |
| 平均 |  | 1.0000 | 10.62 | 62466.25 | 1989.38 | 64455.62 |

ACE 总体再拆开：推理 input 54136.5 / output 277.25；记忆 input 8329.75 / output 1712.12。平均延迟 122.83 秒/条（推理 18.30，记忆 104.53）。

日志中若干轮打印了仓库原句 `Failed to decode the model response. Proceed to next turn.` 官方评分仍给了 success=1。没有另写解析器去追成功率。

## 3. 与原文并列

原文（DeepSeek-V3.2，Table 6，成功率 %，各环境 50 条）：

| 环境 | 无记忆 DeepSeek-V3.2 | ACE | 差 |
|---|---:|---:|---:|
| Gorilla File System | 64.0 | 68.0 | +4.0 |
| Vehicle Control | 36.0 | 56.0 | +20.0 |
| Trading Bots | 54.0 | 14.0 | −40.0 |
| Travel Booking | 26.0 | 34.0 | +8.0 |
| 四环境等权平均（派生） | 45.0 | 43.0 | **−2.0 pp** |

本次 Grok 的 200 条等权差：**不可判**。烟雾四环境都是 100%，样本太小，不能拿去比 −2.0 pp。

## 4. 预算

| 项 | 值 |
|---|---|
| 硬顶 | 150 元人民币 |
| 汇率 | Frankfurter 2026-11-19，1 USD = 6.6667 CNY。150 元 = 22.50 美元 |
| 标价 | grok-4.7，prompt &lt; 200k：输入 $2/1M，缓存输入 $0.50/1M，输出 $6/1M |
| 烟雾花费（标价估算） | 约 $1.42 ≈ **9.46 元**。见 §4.2。这是标价，不是账单 |
| 200×2 外推 | 不计缓存 **289.85 元**。高于硬顶。满量未启动 |

### 4.1 外推

条均用官方 aggregate 行。每条费用 = input × 输入价 + output × $6，再乘 200。

| 假设 | NO-MEM 200 条 | ACE 200 条 | 合计 |
|---|---:|---:|---:|
| 输入全部按 $2/1M | $16.10 / 107.36 元 | $27.37 / 182.49 元 | $43.48 / **289.85 元** |
| 输入的 25% 按缓存价 | $13.13 / 87.53 元 | $22.69 / 151.26 元 | $35.82 / 238.79 元 |
| 每次调用固定 1152 token 缓存（见下） | $13.17 / 87.77 元 | $23.01 / 153.40 元 | **241.18 元** |

ACE 只算输入、完全不缓存：62466.25 × $2/1M × 200 = $24.99 = **166.58 元**，这一项已经超过 150 元。

固定前缀的算法：PONG 探测里 1152 个 token 被标成 cached。NO-MEM 平均 8.5 步，1152×8.5 / 39644.5 = 24.7%。ACE 按平均 10.625 个推理步再加 2 次记忆调用估计，缓存比例 23.3%。多轮上下文变长以后，这段固定前缀的占比还会下降。

要让两组合计正好 150 元，全部输入 token 里大约 **68.5%** 得按 $0.50/1M 计（其余按 $2，输出仍按 $6）。烟雾里的缓存比例在 25% 附近，到不了 68.5%。

CSV 的 output 不含 reasoning。PONG 探测是 `completion_tokens=2`、`reasoning_tokens=84`。官方 `openai_completion.py` 只记 `prompt_tokens` 与 `completion_tokens`。少计的是输出侧。ACE 的输入一项已经超过硬顶，所以少计不会把结论改成「可以开满量」。

单次请求留在 20 万 token 标价档内。116422 是一条样本多轮输入的合计。

### 4.2 烟雾已发生的标价

| 部分 | 美元 |
|---|---:|
| NO-MEM 4 × $0.080516 | 0.322 |
| ACE 8 × $0.136869 | 1.095 |
| PONG，`cost_in_usd_ticks=12840000` | 0.001284 |
| `get_weather` 探测，ticks `10780000` | 0.001078 |
| 合计 | **1.419 ≈ 9.46 元** |

评测结果 JSON 的 usage 里没有 `cost_in_usd_ticks`。上表的评测部分用记录到的 token 乘标价。ticks/1e10 与 PONG 的拆价一致：未缓存 96×$2 + 缓存 1152×$0.50 + 输出 86×$6 = $0.001284。

### 4.3 论文 token 只作对照

Table 11 的 CrossEp-Tool 平均 token：无记忆 55787 / 条，ACE 109272 / 条。本次烟雾条均 total token：NO-MEM 39849，ACE 64456。Grok 这条路径比论文表更短，但按 Grok 标价仍然过线。论文用量没有被拿来当门禁。

## 5. 判定

- 严格同模型复现：不适用
- 管道：烟雾规模上，官方生成与官方评分都跑通，评分代码未改，per-sample 合法
- 200 条 ACE − NO-MEM 方向：没有数据，不能对照 −2.0 pp
- 满量停止的原因是预算门禁，不是方法跑不通，也不是方向相反
- 教学任务迁移：停止。还没有 200 条上的 Grok 信号
- 12 对跨环境：未做

## 6. 若以后放宽 150 元

保持 `grok-4.7` 与现有载荷，不要为了预算换模型或改温度。然后：

```bash
cd /Users/MBP/Exp/RSILab/mmfopd-repro
bash scripts/run_crossep_tool_phase1.sh full no_memory
bash scripts/run_crossep_tool_phase1.sh full ace
```

脚本退出时会删掉 `CROSSEP-TOOL/.env`。满量跑完后再填 `per_item.csv` 的 200 行、本节的成功率与 95% CI，并抽 10 条 playbook。在那之前这些格子保持空白。
