# EvoMemBench → xAI：已落地的接法

评测主路径已经改在仓库里，不必再手改导入。

## 改了什么

`EvoMemBench/Cross-Episode-Execution/Tool-Using/CROSSEP-TOOL/bfcl_eval/memory/ark_client.py`

`ArkBatchClient` 在 `LLM_BACKEND=xai` 时用 OpenAI SDK 打 `XAI_BASE_URL`（默认 `https://api.x.ai/v1`）的 `chat.completions.create`。否则仍走火山方舟 `batch.chat.completions`。

FC 推理（`ArkBatchFCHandler`）和 ACE reflector/curator 都调用这个类。`run_batch_evaluate.py` 没动。

请求体保持调用方原来的字段：`model`、`messages`、可选 `tools`。不补 temperature，不补 max_tokens。

## 密钥

只写 `mmfopd-repro/.env`。运行：

```bash
bash mmfopd-repro/scripts/run_crossep_tool_phase1.sh ping
```

该脚本把 `XAI_API_KEY` 映射为评测脚本要求的 `DEEPSEEK_API_KEY`，把 `XAI_MODEL` 映射为 `BATCH_MODEL`，写入已被 gitignore 的 `CROSSEP-TOOL/.env`。

## 第一阶段

NO-MEM 走官方 `scripts/run_eval_no_memory_inenv_fc.sh`。

ACE 不走 `run_eval_ace_inenv_allcrossenv_fc.sh` 全文，因为那个脚本会接着跑 12 对跨环境。Phase 1 用同一对官方 Python 模块，见 `scripts/run_crossep_tool_phase1.sh`。

## 预算

冒烟 token 外推 200×2。超过 150 元人民币就停。
