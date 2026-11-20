# DEVIATIONS — MM-FOPD-R

日期：2026-11-20。

## V3 状态（当前有效）

链路：DeepSeek-V3.2 已下架，严格复现不可行 → 用户指示改用 grok-4.7 做冒烟 → 标价外推约 290 元，超过 150 元上限，满量停止 → 用户选择方案 B。

方案 B：只换骨干模型，做换模型的重复（replication with a different backbone）。代码、基准、评分、样本量按原文。端点只允许 DeepSeek 官方 API `https://api.deepseek.com`。不得使用 Grok、聊天订阅额度或 CLI 会话代理。

Grok 冒烟只作存档，不参与任何判定。存档文件是 `BUDGET_STOP_GROK.md`、`R_RESULT.md` 里带存档标记的烟雾表，以及 `artifacts/no_mem/`、`artifacts/ace/`。

EvoMemBench 分支：

- `codex/mmfopd-repro` 已回到上游原始提交 `3efc221fd8d5f4de7c2dc2022357e600d26325c7`
- Grok 客户端改动 `5670db5` 与请求头改动 `647bbef` 在分支 `grok-smoke` 上。当前工作树没有 `cli-chat-proxy` 代码
- 没有推送到 `DSAIL-Memory/EvoMemBench`。文档仓没有用户 remote

方法尚未选定。Table 6 抄录之后停下等确认。下面 D-001R 至 D-010 是 Grok 路径的历史记录，不是方案 B 的偏差清单。

## D-001R 模型换成 xAI Grok

原文与仓库默认是火山方舟批量 + DeepSeek-V3.2。本次按用户要求改走 xAI。结果必须标注 *same-code / same-benchmark / different-model*。

烟雾锁定的模型 id 是 **`grok-4.7`**。端点是 Grok CLI 代理 `https://cli-chat-proxy.grok.com/v1`，用本机 CLI 会话额度。用户明确说 `.env` 里没有 key，授权走这个额度。没有改用更便宜的模型来凑 150 元。

## D-002 代码已克隆（关闭旧阻塞）

- 路径：`mmfopd-repro/EvoMemBench`
- 上游 HEAD：`3efc221fd8d5f4de7c2dc2022357e600d26325c7`
- 与任务书参考短 SHA `3efc221` 相同
- 本地分支 `codex/mmfopd-repro` 在其上增加 `5670db5` 与 `647bbef`

## D-003 论文数字已抄录（关闭旧阻塞）

来源：arXiv:2605.18421v2 HTML，Table 6 / Table 10 / Table 11。ACE 行存在，没有改对照为 SkillWeaver。数字见 `R_PREREG.md` §1.2。等权 ACE − DeepSeek-V3.2 = −2.0 pp 已锁定。

## D-004 客户端最小 diff

评分文件 `run_batch_evaluate.py` 未改。

- `EvoMemBench/Cross-Episode-Execution/Tool-Using/CROSSEP-TOOL/bfcl_eval/memory/ark_client.py`
- 当 `LLM_BACKEND=xai`：`OpenAI(base_url=XAI_BASE_URL)` 的 `chat.completions.create`
- 否则仍是 `volcenginesdkarkruntime.Ark` 的 `batch.chat.completions.create`
- 载荷仍是 `model`、`messages`、可选 `tools`
- 不新增 temperature、max_tokens。仓库的 `ArkBatchFCHandler` 本来就不把 handler 上的 `temperature=0` 放进这次调用
- 重试仍用原来的 tenacity
- ACE 的 reflector / curator 和 FC 推理都走这个类，所以一次切换覆盖两组
- 仅当 base URL 含 `cli-chat-proxy.grok.com` 时附加四个请求头（D-010）。提交 `647bbef`

`adapters/xai_openai_client.py` 保留为独立 ping 形状，评测主路径不导入它。

运行时映射（由 `scripts/run_crossep_tool_phase1.sh` 写入 `CROSSEP-TOOL/.env`，该文件被 `**/.env` 忽略，进程退出时删除）：

| 仓库变量 | 来源 |
|---|---|
| `DEEPSEEK_API_KEY` | CLI 会话 token，或 `XAI_API_KEY` |
| `BATCH_MODEL` | `grok-4.7`（或 `XAI_MODEL`） |
| `DEEPSEEK_BASE_URL` | `https://cli-chat-proxy.grok.com/v1` |
| `LLM_BACKEND` | `xai` |
| `XAI_CLI_VERSION` | `1.0.89` |

## D-005 不跑官方 ACE 脚本的 Phase 2

`run_eval_ace_inenv_allcrossenv_fc.sh` 在 Phase 1 之后会跑 12 个跨环境对。交接红线要求第一阶段做完再写结果，用户没加之前不做这 12 对。

ACE 第一阶段改由 `mmfopd-repro/scripts/run_crossep_tool_phase1.sh` 调用与官方脚本相同的两条 Python 命令：

- `python -m bfcl_eval.scripts.cross_episode.run_batch_generate --memory-type ace --mode FC --num-workers 1`
- `python -m bfcl_eval.scripts.cross_episode.run_batch_evaluate`

四个环境并行启动，每个环境内部 workers=1，playbook 在该环境内累积。NO-MEM 仍调用官方 `run_eval_no_memory_inenv_fc.sh`（它本身没有 Phase 2）。该脚本激活的 conda 环境名是 `bfcl`，ACE 路径激活的是 `CROSSEP-TOOL`。安装时两个名字指向同一套包。

## D-006 冒烟已跑，满量因预算停止

NO-MEM 4 条与 ACE 8 条都由官方评分写出，api/runtime 失败为 0。汇总在 `artifacts/no_mem/` 与 `artifacts/ace/`。

按 grok-4.7 标价把条均 token 乘到 200×2，合计约 290 元，高于 150 元硬顶。满量没有启动。没有伪造 200 条成功率，没有缩样本，没有改解码。详见 `R_RESULT.md` §4。

## D-007 依赖安装

本机原先没有 conda，也没有 Python 3.11。已装 Miniforge 到 `$HOME/miniconda3`（官方 Anaconda 源过慢，改从 GitHub 的 Miniforge 安装）。

- 环境 `CROSSEP-TOOL` 与 `bfcl`：Python 3.11.18，`pip install -e .` 已完成
- 日志末尾：`DONE 2026-11-20T09:34:47Z`，`import_ok`
- 系统 Python 3.14 访问 CLI 代理时证书校验失败。烟雾与 ping 用 conda `CROSSEP-TOOL` 加 certifi
- 连通性：conda 环境下 ping 返回 `PONG`，`cost_in_usd_ticks=12840000`。另一次 `get_weather` 工具调用返回 `{"city":"Paris"}`，ticks `10780000`

## D-008 Git

- EvoMemBench 克隆上的分支：`codex/mmfopd-repro`
  - `5670db5` Route ArkBatchClient to xAI when LLM_BACKEND=xai
  - `647bbef` Send Grok CLI session headers on the cli-chat-proxy path
- 文档仓：`mmfopd-repro/` 单独 git，同名分支；忽略 `.env` 和整个 `EvoMemBench/`（它自带 `.git`）
- 不 push。上游是 `DSAIL-Memory/EvoMemBench`，没有用户自己的 remote
- 提交者身份由主机名自动填入。按规则没有改 git config，也没有 amend
- `CROSSEP-TOOL/.env`（含会话 token）在烟雾后已删除，不入库

## D-009 仍遵守的红线

不改评分。不换子任务。不缩样本来凑预算。不手写 judge。不提交密钥。不用 `reflexion/`、MAS-Lab、A-Evolve。不跑 12 对跨环境。

## D-010 CLI 会话代理，而不是 api.x.ai

用户授权用 CLI 额度之后，请求打到 `cli-chat-proxy.grok.com`。这是科学偏差，记录在此。

- 少这些头时，代理返回 HTTP 426：`Your Grok CLI version (none) is outdated`。补上 `x-grok-client-version: 1.0.89` 与 `User-Agent: grok-cli/1.0.89` 后返回 HTTP 200
- 代理在每条请求上注入一段常驻提示。一次 5 词 PONG 的 `prompt_tokens=1248`，其中 `cached_tokens=1152`，`completion_tokens=2`，`reasoning_tokens=84`
- 官方记账只保存 `usage.prompt_tokens` 与 `usage.completion_tokens`（`openai_completion.py`）。reasoning 不进 CSV 的 output 列。ACE 只算输入已经超过 150 元，所以这个少计不能推翻停止决定
- 工具调用仍以 OpenAI `tool_calls` 形状返回。官方 FC 评分接受了全部 4+8 条烟雾样本
- 日志里出现仓库原有的 `Failed to decode the model response. Proceed to next turn.` 这是 handler 的 content 回退，不是另写的 judge。四个 `errors.log` 都是空的，官方仍记 success=1、n_failed=0
- 单次调用的 prompt 低于 20 万 token 的标价档。样本上最大的输入合计是 gorilla ACE `ours_0` 的 116422，那是多轮相加，不是单次请求

没有为了预算改温度、改 max_tokens，或换成 `grok-4.7-build-fast`。
