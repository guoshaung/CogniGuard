# EvoMemBench → xAI：已落地的接法

评测主路径已经改在仓库里，不必再手改导入。

## 改了什么

`EvoMemBench/Cross-Episode-Execution/Tool-Using/CROSSEP-TOOL/bfcl_eval/memory/ark_client.py`

`ArkBatchClient` 在 `LLM_BACKEND=xai` 时用 OpenAI SDK 打 `XAI_BASE_URL` 的 `chat.completions.create`。否则仍走火山方舟 `batch.chat.completions`。

本地提交：`5670db5`（路由）、`647bbef`（CLI 代理头）。上游仍是 `3efc221`。

FC 推理（`ArkBatchFCHandler`）和 ACE reflector/curator 都调用这个类。`run_batch_evaluate.py` 没动。

请求体保持调用方原来的字段：`model`、`messages`、可选 `tools`。不补 temperature，不补 max_tokens。

当 `XAI_BASE_URL` 含 `cli-chat-proxy.grok.com` 时，额外带上：

- `X-XAI-Token-Auth: xai-grok-cli`
- `x-grok-model-override: <model>`
- `x-grok-client-version: <XAI_CLI_VERSION>`（缺省 `1.0.89`）
- `User-Agent: grok-cli/<version>`

少了版本头，代理返回 HTTP 426。

## 密钥

`mmfopd-repro/.env` 里的 `XAI_API_KEY` 优先。文件不存在时，驱动读取 `~/.grok/auth.json`，端点用 `https://cli-chat-proxy.grok.com/v1`，模型用 `grok-4.7`。

```bash
bash mmfopd-repro/scripts/run_crossep_tool_phase1.sh ping
```

脚本把 key 映射为 `DEEPSEEK_API_KEY`，把模型映射为 `BATCH_MODEL`，写入 `CROSSEP-TOOL/.env`，退出时删除。不要把 token 提交或贴进对话。

## 第一阶段

NO-MEM 走官方 `scripts/run_eval_no_memory_inenv_fc.sh`。

ACE 不走 `run_eval_ace_inenv_allcrossenv_fc.sh` 全文，因为那个脚本会接着跑 12 对跨环境。Phase 1 用同一对官方 Python 模块，见 `scripts/run_crossep_tool_phase1.sh`。

## 预算

2026-11-20 的烟雾外推约 290 元，高于 150 元。满量未跑。数字在 `R_RESULT.md`。
