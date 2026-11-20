# RUNBOOK — 本机用 xAI Grok 跑 MM-FOPD-R

> **存档。** 方案 B 禁止再跑这条 Grok 路径。`scripts/run_crossep_tool_phase1.sh` 现在会直接退出。方法选定之前不要开评测。



工作目录：`/Users/MBP/Exp/RSILab`。不要把 key 或 CLI token 贴进对话，也不要提交。

## 0. 已完成

```text
上游 HEAD = 3efc221fd8d5f4de7c2dc2022357e600d26325c7
本地分支 codex/mmfopd-repro
  5670db5  LLM_BACKEND=xai 时走 OpenAI chat.completions
  647bbef  cli-chat-proxy 附加 CLI 请求头
```

依赖已装好。Miniforge 在 `$HOME/miniconda3`。环境 `CROSSEP-TOOL` 和 `bfcl` 都是 Python 3.11.18。日志 `/tmp/mmfopd_conda_install.log` 以 `DONE 2026-11-20T09:34:47Z` 结束。系统 Python 3.14 打 CLI 代理会证书失败，脚本使用 conda。

2026-11-20 已用 CLI 会话跑完烟雾。满量因外推约 290 元超过 150 元而没有启动。见 `R_RESULT.md`。

## 1. 鉴权

优先读 `mmfopd-repro/.env`：

```bash
LLM_BACKEND=xai
XAI_API_KEY=...
XAI_BASE_URL=https://api.x.ai/v1
XAI_MODEL=grok-4.7
```

该文件不存在时，`scripts/run_crossep_tool_phase1.sh` 读取 `~/.grok/auth.json`，并把端点设为 `https://cli-chat-proxy.grok.com/v1`、模型设为 `grok-4.7`。这是本次烟雾的实际路径。脚本把映射写进 `CROSSEP-TOOL/.env`（权限 600），退出时删除该文件。它被 EvoMemBench 的 `**/.env` 忽略。

不要把 `grok-2-latest` 写进 `XAI_MODEL`。驱动会拒绝。

## 2. 冒烟（已完成）

```bash
cd /Users/MBP/Exp/RSILab/mmfopd-repro
bash scripts/run_crossep_tool_phase1.sh ping
bash scripts/run_crossep_tool_phase1.sh smoke no_memory   # 每环境 1 条
bash scripts/run_crossep_tool_phase1.sh smoke ace         # 每环境 2 条，仅 Phase 1
```

结果目录：

```text
xai_smoke_nomem_20261120_175202_no_memory_20261120_175203
xai_smoke_ace_20261120_175420
```

拷贝在 `artifacts/no_mem/` 与 `artifacts/ace/`。

## 3. 满量第一阶段

当前外推超过 150 元，**不要跑**下面两条，除非硬顶被明确提高：

```bash
bash scripts/run_crossep_tool_phase1.sh full no_memory
bash scripts/run_crossep_tool_phase1.sh full ace
```

不要直接跑 `run_eval_ace_inenv_allcrossenv_fc.sh`，那个脚本会继续跑 12 对跨环境。

产物在：

```text
EvoMemBench/Cross-Episode-Execution/Tool-Using/CROSSEP-TOOL/cross_episode_results/runs/
```

## 4. 收尾

烟雾的 token、标价和停止决定已写入 `R_RESULT.md` 与 `final_decision.md`。`per_item.csv` 仍只有表头。满量完成之前不要把烟雾 id 填进去。

## 5. 不要做

- 改 `run_batch_evaluate.py`
- 改 temperature、缩小样本，或换成别的模型来凑 150 元
- 提交 `.env` 或 `~/.grok/auth.json`
- 在没有放宽硬顶时启动 `full`
