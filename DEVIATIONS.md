# DEVIATIONS — MM-FOPD-R

日期：2026-11-20。

## D-001R 模型换成 xAI Grok

原文与仓库默认是火山方舟批量 + DeepSeek-V3.2。本次按用户要求改走 xAI。结果必须标注 *same-code / same-benchmark / different-model*。

模型 id：**未锁定**。`mmfopd-repro/.env` 不存在，环境变量 `XAI_API_KEY` / `XAI_MODEL` 均未设置。Grok CLI 的 `~/.grok/auth.json` 是 OIDC 会话，不是 `XAI_API_KEY`，没有拿来调用 `api.x.ai`。

## D-002 代码已克隆（关闭旧阻塞）

- 路径：`mmfopd-repro/EvoMemBench`
- HEAD：`3efc221fd8d5f4de7c2dc2022357e600d26325c7`
- 与任务书参考短 SHA `3efc221` 相同

## D-003 论文数字已抄录（关闭旧阻塞）

来源：arXiv:2605.18421v2 HTML，Table 6 / Table 10 / Table 11。ACE 行存在，没有改对照为 SkillWeaver。数字见 `R_PREREG.md` §1.2。

## D-004 客户端最小 diff

只改这一处。评分文件 `run_batch_evaluate.py` 未改。

- `EvoMemBench/Cross-Episode-Execution/Tool-Using/CROSSEP-TOOL/bfcl_eval/memory/ark_client.py`
- 当 `LLM_BACKEND=xai`：`OpenAI(base_url=XAI_BASE_URL)` 的 `chat.completions.create`
- 否则仍是 `volcenginesdkarkruntime.Ark` 的 `batch.chat.completions.create`
- 载荷仍是 `model`、`messages`、可选 `tools`
- 不新增 temperature、max_tokens。仓库的 `ArkBatchFCHandler` 本来就不把 handler 上的 `temperature=0` 放进这次调用
- 重试仍用原来的 tenacity
- ACE 的 reflector / curator 和 FC 推理都走这个类，所以一次切换覆盖两组

`adapters/xai_openai_client.py` 保留为独立 ping 形状，评测主路径不导入它。

运行时映射（由 `scripts/run_crossep_tool_phase1.sh` 写入 `CROSSEP-TOOL/.env`，该文件被仓库 `**/.env` 忽略）：

| 仓库变量 | 来源 |
|---|---|
| `DEEPSEEK_API_KEY` | `XAI_API_KEY` |
| `BATCH_MODEL` | `XAI_MODEL` |
| `DEEPSEEK_BASE_URL` | `XAI_BASE_URL` |
| `LLM_BACKEND` | `xai` |

## D-005 不跑官方 ACE 脚本的 Phase 2

`run_eval_ace_inenv_allcrossenv_fc.sh` 在 Phase 1 之后会跑 12 个跨环境对。交接红线要求第一阶段做完再写结果，用户没加之前不做这 12 对。

ACE 第一阶段改由 `mmfopd-repro/scripts/run_crossep_tool_phase1.sh` 调用与官方脚本相同的两条 Python 命令：

- `python -m bfcl_eval.scripts.cross_episode.run_batch_generate --memory-type ace --mode FC --num-workers 1`
- `python -m bfcl_eval.scripts.cross_episode.run_batch_evaluate`

NO-MEM 仍调用官方 `run_eval_no_memory_inenv_fc.sh`（它本身没有 Phase 2）。该脚本激活的 conda 环境名是 `bfcl`，ACE 官方脚本激活的是 `CROSSEP-TOOL`。安装时两个名字指向同一套包。

## D-006 冒烟与满量未执行

原因：没有 `mmfopd-repro/.env`，也没有 `XAI_API_KEY`。没有伪造 per-sample 或成功率。费用外推没有做。论文 token 只在 `R_RESULT.md` 里当作风险提示，不充当 150 元门禁。

## D-007 依赖安装

按 `CROSSEP-TOOL` README：Miniconda + Python 3.11 环境 `CROSSEP-TOOL`，再 clone 出 `bfcl`。本机原先没有 conda，也没有 Python 3.11（只有系统 Python 3.14）。安装日志：`/tmp/mmfopd_conda_install.log`。完成与否以该日志末尾的 `DONE` 或报错为准，不在本文里提前写成已成功。

## D-008 Git

- EvoMemBench 克隆上的分支：`codex/mmfopd-repro`（只含客户端 diff）
- 文档仓：`mmfopd-repro/` 单独 `git init`，同名分支；忽略 `.env` 和整个 `EvoMemBench/`（它自带 `.git`）
- 不 push。上游是 `DSAIL-Memory/EvoMemBench`，没有用户自己的 remote

## D-009 仍遵守的红线

不改评分。不换子任务。不缩样本来凑预算。不手写 judge。不提交密钥。不用 `reflexion/`、MAS-Lab、A-Evolve。
