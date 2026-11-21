# NeMo self-check + MiMo 完整评测结果

## 运行方式

官方 NeMo Guardrails `self check input`/`self check output` 配置已通过加载验证。由于 NeMo 0.16 的 LangChain OpenAI adapter 会向 MiMo 传递不兼容参数并出现空响应，本轮使用相同 NeMo self-check policy prompt，通过 MiMo 原生 OpenAI-compatible API 执行。

因此本表准确名称是：**MiMo-native execution of NeMo self-check policy**，不是官方 NeMo LangChain runtime 的完整端到端结果。

## 完整公开文件结果

| 基准 | 样本 | 有害召回↑ | 正常误拦↓ | Precision↑ | F1↑ | Balanced Accuracy↑ |
|---|---:|---:|---:|---:|---:|---:|
| JailbreakBench | 100 harmful + 100 benign | 99.0% | 33.0% | 75.0% | 0.853 | 0.830 |
| XSTest | 200 unsafe + 250 safe | 98.5% | 10.4% | 88.3% | **0.931** | **0.940** |

## 结论

NeMo self-check policy 的危险请求覆盖明显高于当前 CGC 规则版，但它在 JailbreakBench 上误拦 33%，不能直接作为主控制器。它可以作为高风险或边界样本的二阶段候选，最终决策仍需结合 CGC 规则、语境和权限状态。

按两个基准的宏平均 F1 为 `(0.853 + 0.931) / 2 = 0.892`，没有达到“两个基准都超过 90%”的目标；XSTest 单项超过 90%。

## 与规则版的定位

| 方案 | JBB F1 | XSTest F1 | 主要问题 |
|---|---:|---:|---|
| CGC 扩展规则 | 0.735 | 0.593 | 召回不足 |
| NeMo policy + MiMo | 0.853 | 0.931 | JailbreakBench 正常误拦过高 |
| 规则 + NeMo 边界级联 | 待校准 | 待校准 | 需要 calibration split 决定何时调用 self-check |

当前不把 NeMo self-check 直接写入 CGC 主路径；下一步只在规则命中或语义边界样本上调用它，并用 JailbreakBench benign、XSTest safe 作为误拦校准集。
