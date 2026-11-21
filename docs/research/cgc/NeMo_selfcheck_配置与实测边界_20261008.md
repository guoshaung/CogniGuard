# NeMo Guardrails self-check 配置与实测边界

## 当前已完成

- 已安装并固定 `nemoguardrails==0.16.0`；
- 已将 Transformers 调整为 `4.57.1`，解决 NeMo 依赖与原项目 Transformers 5.8 的冲突；
- 已配置官方 `self check input` 和 `self check output` flows；
- 已通过 `RailsConfig.from_path` 完成配置加载验证；
- input/output self-check prompt 已明确教育场景、隐私、版权、提示注入和危险意图策略。

## 当前不能报告 NeMo 分数的原因

官方 self-check 本身需要一个可调用的 LLM。当前环境没有 MIMO/OpenAI API key，Ollama 也未运行；本地 Qwen 0.5B 不是 NeMo 官方 `hf_pipeline_llama2_13b` 配置所需的模型适配器。因此本轮没有伪造 NeMo self-check 的 JailbreakBench 或 XSTest 分数。

配置验证命令：

```powershell
.\.venv\Scripts\python.exe -m experiments.evaluation.validate_nemo_selfcheck_config
```

## 真实 benchmark 所需条件

配置一个支持的 NeMo LLM backend 后，才能运行：

1. 纯 CGC deterministic adapter；
2. NeMo self-check input/output；
3. CGC 规则 + NeMo self-check 级联。

三种模式必须在相同 JailbreakBench、XSTest 和 BIPIA 切分上比较 Recall、误拦、F1、Balanced Accuracy、延迟和失败类型。

## 解释边界

NeMo self-check 是 CGC 的可选语义判别后端，不替代 CGC 的权限、预算、来源、审计和回滚。当前可以汇报“官方 self-check 配置已接入并通过配置验证”，不能汇报“NeMo self-check 已经达到 90% 以上”，因为尚未发生真实模型调用。
