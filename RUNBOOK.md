# RUNBOOK — 本机用 xAI Grok 跑 MM-FOPD-R

工作目录：`/Users/MBP/Exp/RSILab`。密钥只放 `mmfopd-repro/.env`。

## 0. 已完成

```bash
# 已克隆，HEAD = 3efc221fd8d5f4de7c2dc2022357e600d26325c7
# 客户端已改：LLM_BACKEND=xai 时走 api.x.ai
```

依赖已装好。Miniforge 在 `$HOME/miniconda3`。环境 `CROSSEP-TOOL` 和 `bfcl` 都是 Python 3.11.18。日志 `/tmp/mmfopd_conda_install.log` 以 `DONE 2026-11-20T09:34:47Z` 结束。

## 1. 密钥

复制 `mmfopd-repro/.env.example` 为 `mmfopd-repro/.env`，填写：

```bash
LLM_BACKEND=xai
XAI_API_KEY=...
XAI_BASE_URL=https://api.x.ai/v1
XAI_MODEL=...    # 控制台精确 id，不要用 grok-2-latest
```

不要把这份文件提交，也不要把 key 贴进对话。

## 2. 冒烟

```bash
cd /Users/MBP/Exp/RSILab/mmfopd-repro
bash scripts/run_crossep_tool_phase1.sh ping
bash scripts/run_crossep_tool_phase1.sh smoke no_memory   # 每环境 1 条
bash scripts/run_crossep_tool_phase1.sh smoke ace         # 每环境 2 条，仅 Phase 1
```

脚本会把 key 映射进 `CROSSEP-TOOL/.env`（`DEEPSEEK_API_KEY`、`BATCH_MODEL`），权限 600，且被 EvoMemBench 的 `**/.env` 忽略。

从 `per_sample.csv` 的 token 列外推 200×2 的人民币费用。超过 150 元：停，写 `R_RESULT.md`，不砍样本。

## 3. 满量第一阶段（仅预算通过后）

```bash
bash scripts/run_crossep_tool_phase1.sh full no_memory
bash scripts/run_crossep_tool_phase1.sh full ace
```

不要直接跑 `run_eval_ace_inenv_allcrossenv_fc.sh`，那个脚本会继续跑 12 对跨环境。

产物在：

```text
EvoMemBench/Cross-Episode-Execution/Tool-Using/CROSSEP-TOOL/cross_episode_results/runs/
```

把 `combined_summary.*` 和 `combined_per_sample.csv` 拷到 `mmfopd-repro/artifacts/{no_mem,ace}/`。

## 4. 收尾

填 `per_item.csv`、`R_RESULT.md`、`final_decision.md`。用仓库官方汇总，不手写 judge。

## 5. 不要做

- 改 `run_batch_evaluate.py`
- 改 temperature 或缩小样本来凑 150 元
- 提交 `.env`
- 用 Grok CLI 的 OIDC 登录态冒充 `XAI_API_KEY`
