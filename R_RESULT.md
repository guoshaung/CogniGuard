# R_RESULT — MM-FOPD-R

> 日期：2026-11-20
> 标注：*same-code / same-benchmark / different-model (Grok via xAI)*
> *not same-model strict repro*
> 状态：**未产生任何 Grok 成功率。缺 `XAI_API_KEY`，冒烟和满量都没有跑。**

---

## 1. 已完成

| 项 | 结果 |
|---|---|
| EvoMemBench SHA | `3efc221fd8d5f4de7c2dc2022357e600d26325c7`，已写入 `R_PREREG.md` |
| 论文表 | Table 6 / 10 / 11 已抄录。ACE 行存在 |
| 客户端 | `ark_client.py` 在 `LLM_BACKEND=xai` 时走 xAI。评分脚本未改 |
| 第一阶段驱动 | `scripts/run_crossep_tool_phase1.sh`（不跑 12 对） |
| 密钥 | `mmfopd-repro/.env` **不存在**。进程环境里也没有 `XAI_API_KEY` |

## 2. 成功率

没有 per-sample，下表留空。不填估计值。

| 组 | 总体 | gorilla_fs | vehicle_control | trading_bot | travel_api | 95% CI |
|---|---|---|---|---|---|---|
| NO-MEM | 未跑 | 未跑 | 未跑 | 未跑 | 未跑 | 未跑 |
| ACE | 未跑 | 未跑 | 未跑 | 未跑 | 未跑 | 未跑 |

`per_item.csv` 只有表头，零行。四分类未做。playbook 抽样未做。token、费用、墙钟都没有实测。

## 3. 与原文并列

原文（DeepSeek-V3.2，Table 6，成功率 %）：

| 环境 | 无记忆 DeepSeek-V3.2 | ACE | 差 |
|---|---:|---:|---:|
| Gorilla File System | 64.0 | 68.0 | +4.0 |
| Vehicle Control | 36.0 | 56.0 | +20.0 |
| Trading Bots | 54.0 | 14.0 | −40.0 |
| Travel Booking | 26.0 | 34.0 | +8.0 |
| 四环境等权平均（派生，表内没有这一格） | 45.0 | 43.0 | **−2.0 pp** |

原文方向：等权成功率上 ACE 略低于无记忆基线。本次 Grok 方向：**不可判**。

## 4. 预算

| 项 | 值 |
|---|---|
| 硬顶 | 150 元人民币 |
| 已花费 | 0。本回合没有调用 xAI HTTP |
| 冒烟外推 | **没有**。门禁未触发，满量也未获准 |

### 4.1 论文 token 的风险提示（不是门禁）

Table 11 的 CrossEp-Tool 平均 token：无记忆 55787 / 条，ACE 109272 / 条。若 Grok 的条均 token 与论文相同，200 × 2 组合计约 3.30×10^7 token。这是 DeepSeek 的用量，不是 Grok 冒烟。

公开标价（docs.x.ai 模型页，2026-11 核对，美元 / 100 万 token，prompt &lt; 200k）：`grok-4.3` 输入 1.25、输出 2.50；`grok-4.7` 输入 2.00、输出 6.00；`grok-build-0.1` 输入 1.00、输出 2.00。即便全部按最便宜档的输入价估算，3.30×10^7 token 也要大约 33 美元，高于 150 元人民币（按约 7.2 元/美元粗算约 21 美元）。所以满量很可能会被冒烟门禁拦住。

这条提示**不**代替冒烟外推。密钥到位后必须先冒烟，用实测 token 再决定是否满量。超了就停，写回本节，不砍样本。

## 5. 判定

- 严格同模型复现：不适用
- Grok 迁移信号：不可判。流程没有跑通到 per-sample
- 缺密钥是阻塞，不是「增益方向相反」那种失败
- 教学任务迁移：停止

## 6. 解锁后的一条命令

在 `mmfopd-repro/.env` 写入 `XAI_API_KEY` 和精确 `XAI_MODEL`（不要贴进对话），然后：

```bash
cd /Users/MBP/Exp/RSILab/mmfopd-repro
bash scripts/run_crossep_tool_phase1.sh ping
bash scripts/run_crossep_tool_phase1.sh smoke no_memory
bash scripts/run_crossep_tool_phase1.sh smoke ace
```

用冒烟日志里的 `input_tokens_*` / `output_tokens_*` 外推 200×2。不超过 150 元再跑：

```bash
bash scripts/run_crossep_tool_phase1.sh full no_memory
bash scripts/run_crossep_tool_phase1.sh full ace
```

原始输出在 `EvoMemBench/Cross-Episode-Execution/Tool-Using/CROSSEP-TOOL/cross_episode_results/runs/`。汇总后再填本文件、`per_item.csv`、`final_decision.md`。仍不改 `run_batch_evaluate.py`。
