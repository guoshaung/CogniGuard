# CogniGuard 当前实现实验报告（2026-08-12）

## 执行范围与可复核性

本轮未修改算法、阈值、攻击强度、随机种子、数据划分或评价定义。运行设备为 NVIDIA RTX 4070 Laptop GPU（8 GiB），Git HEAD 为 `d01953234add03996cb9200af3ff02c9592697e7`。工作树原本已存在未提交变更，因此结果仅与本次产物绑定，不能与旧提交混用。

- 默认配置 SHA-256：`586451eea82c9df4919f55aed3356f03bd080edaa8cc78793806b6393daf2b21`
- mixed-math split manifest SHA-256：`a55b5f963cdd36e85e02c09319497432157406813f2ab0532cf4cb2587aa75f6`
- 本次新增结果根目录：`experiments/results/current_validation_20260812/`
- 基础单元测试：22 passed（FOPD、C2-RAG、CG、compliance audit chain）

## 已执行结果

| 实验 | 状态 | 结果与解释 |
|---|---|---|
| MM-FOPD/CG 组件消融 | `PARTIAL` | 240 请求：EnhancedFOPD 的 PER=0.2730、TaskCoverage=1.000；FullProfile 的 PER=1.000、TaskCoverage=0.4387。尚无置信区间。 |
| C2-RAG 组件/版权重构 | `PARTIAL` | 62 资源：PlainRAG 泄露=1.000；C2RAG-full 泄露=0.3372、重构成功=0、availability=0.4758、refusal=0.5242。泄露下降伴随明显可用性代价。 |
| 扩展 episode 攻击 | `PARTIAL` | seed=2026，480 episodes（240 attack/240 clean）：拦截率=0.9792、攻击成功率=0.0167；prompt injection 最弱，成功率=0.0889。该 runner 是仓库内规则/概率模拟，不是 LLM 红队攻击。 |
| 九配置联合消融 | `PARTIAL` | Full+CG proxy JointRisk=0.0690，Full w/o CG=0.2356，best pair=0.3841。但 HSW 状态由开关推导，未调用真实文本水印，不能得出真实 synergy。 |
| HSW-ST 本地真实运行 | `FAIL` | 使用未改动的 `config.smoke.yaml`、本地 Qwen2.5-0.5B、seed=42，在 RTX 4070 上实际完成 100 条样本、500 条攻击文本。WDR=1.00，FPR=0，ADR=0.71，TraceBindRate=1.00；但 TKR=0.0744、FKR=0、NKR=0.3113、PlaceholderPass=0。水印可检出，但内容/受保护版权片段未被可靠保留，故不能作为合格保护结果。 |
| 审计链显式篡改 | `PASS`（backend compliance 实现） | 2 事件链原链校验为真；修改字段与删除首事件均被 `verify_compliance_audit_chain` 识别。该链与 HSW `AuditChain` 是不同实现，不能替代后者缺失的连续哈希链。 |
| 端到端多智能体 demo | `PARTIAL` | 一轮 FOPD→C2-RAG→CG→审计绑定流程成功；使用在线 MiMo LLM、无固定 seed 与批量评估集，只证明集成可运行。 |

## 关键复现发现

`config.smoke.yaml` 声明 `data.num_samples: 1`，但 `protection/audit_trace/src/main.py` 在 experiment 模式下直接使用数据文件全部 100 条，未读取该字段。这是配置—实现不一致：本次 HSW 结果的实际样本量为 100，而非配置文字所称的 1；报告按实际产物计数，不能将其称为“一条样本 smoke”。所有样本均用了 2 次改写尝试，100/100 占位符检查失败；这也是 HSW 保护失败的直接证据。

## 未通过、无效或未运行项

| 项目 | 状态 | 原因 |
|---|---|---|
| HSW-ST 论文级鲁棒性、FNR/CI | `NOT RUN` | 当前真实运行已显示内容保护失败，不应在失败实现上扩展并挑选结果；也未生成置信区间。 |
| 图像水印 SCE-LocGuard formal calibration/confirmation/test | `INVALID` | 历史校准候选的预检证明无效，fail-closed；没有 winner、confirmation 或 formal test。 |
| 图像 inpainting/replacement/style/re-render 攻击 | `NOT RUN` | 没有可用的已验证正式图像水印链，不能声明完成。 |
| HSW 审计连续哈希链篡改 | `INCOMPLETE` | `protection/audit_trace/src/audit_chain.py` 只绑定 watermark/source hash，没有 record `previous_hash` 链。 |
| 真实三机制端到端九配置与协同 | `INCOMPLETE` | 联合 runner 并未接入真实 HSW 运行。 |

## 原始产物与哈希

- FOPD：`component_ablations/fopd_component_ablation.json`，SHA-256 `906b81248ec81630734d23e071601cb73547415ec93700760515dcf8c08d2075`
- C2-RAG：`component_ablations/c2rag_component_ablation.json`，SHA-256 `ee33b9ac7c6605b5f5c10c4dfc797403d62488eb48a35c19f048e7ffb657e1f7`
- 攻击 runner：`episode_attacks_mixed_math_seed2026.json`，SHA-256 `9b9a8ee9a63d67edf391f12c62bb32fd3106f5d8e1d869e5e31f7d6d6467f5be`
- 联合代理：`joint_synergy_mixed_math/joint_synergy_results.json`，SHA-256 `e1f0d0ed7fa24ffdbd4c8bbf6d442667bd36f418de6ba3a6a94b4551dc9e0b7c`
- 篡改试验：`audit_chain_tamper_test.json`，原链 SHA-256 `4cbe4745e5daba617a3a54c0daa0392816ca5ce458b2cacb0f47400e3254a377`
- HSW 聚合：`protection/audit_trace/outputs/smoke/run_20260812_012519_480917/metrics_summary.csv`，SHA-256 `64AB7532F9367DC7355829F570800FD304B39759C055029B27DE3940DC884CB8`
- HSW 样本结果：同目录 `watermarked_answers.jsonl`，SHA-256 `A0A68AC3EBE2BA04806A9C39E0AB90AD0BD62498EB570F7181A942AA584F1423`

## 可用于论文的保守结论

1. 当前 MM-FOPD 与 C2-RAG 实现显示了隐私/版权暴露下降的趋势，但尚缺 CI 与独立数据验证。
2. 当前 HSW-ST 实现不能声称“兼顾可检测水印与内容保护”：其检测指标通过，而术语、公式和占位符保留失败。
3. 图像水印和真实三机制协同尚未形成有效证据链；不能写成已完成实验。
4. 下一步应先修复并重新验证 HSW 占位符/受保护片段保留，修复 `num_samples` 配置不生效问题；随后重新做文本攻击、CI 和真实联合实验。图像水印则须从有效正式校准链开始，而不是使用当前无效历史候选。
