# CogniGuard 四模块开发实验总结（2026-09-06）

> 状态：`DEVELOPMENT EVIDENCE; NOT FINAL PAPER RESULTS`。本报告汇总当前开发集实验，明确区分真实模型实验、确定性控制面实验与适配器基线。held-out test 尚未冻结运行。

## 1. 总体架构与 CG 的作用

CogniGuard 由三个保护模块和一个跨层控制面组成：

```text
学生画像 / 教学请求
        ↓
MM-FOPD：选择并压缩最小必要学生画像
        ↓ privacy evidence / context card
C²-RAG：检索教师资源、测量累计版权暴露、生成返回候选
        ↓ copyright evidence / candidate actions
HSW-ST：对最终教学文本嵌入可检测水印并绑定来源
        ↓ watermark / fidelity / trace evidence
CG：组合隐私、版权、水印、权限、预算、历史、信任和审计状态
        ↓
最终 allow / minimize / summarize / regenerate / watermark / degrade / refuse / block
```

CG 不是第四个并列过滤器，而是多智能体保护链的控制平面。MM-FOPD、C²-RAG 和 HSW-ST 分别产生本领域证据与候选；CG 负责跨域冲突消解、双预算结算、候选评分、审计反馈和最终动作。

## 2. MM-FOPD 学生画像最小披露

### 数据与改进

- 720 个数学任务，来自 GSM8K、AQuA-RAT 和 TheoremQA。
- 270 个合成学生，每人扩展为 50 条纵向画像，共 13,500 条画像记录。
- 信息单元拆分为 knowledge state、error pattern、teaching preference、learning state、behavior 和 multimodal summary。
- 修复正交投影未参与评分、信息瓶颈被固定 Top-k 回填抵消、内部选择成本被误作最终披露三个问题。
- 采用单元预算和结构化上下文卡；mastery 离散化、error pattern 摘要化、preference 类别化。

### 144-task development 结果

| 方法 | 必要单元召回↑ | 单元 F1↑ | 外发暴露↓ |
|---|---:|---:|---:|
| LaMP-style | 0.574 | 0.680 | 0.088 |
| GPG-style extractive adapter | 0.539 | 0.673 | 0.067 |
| PAPILLON-style adapter | 0.606 | 0.744 | 0.090 |
| Privacy Funnel adapter | 0.523 | 0.665 | 0.090 |
| LLM minimization proxy | 0.505 | 0.654 | 0.063 |
| **MM-FOPD** | **0.745** | **0.829** | 0.088 |

MM-FOPD 当前优势是以较低外发暴露获得最高的信息单元召回和 F1；不是每一个隐私列都最低。结果仍依赖合成画像和代理效用，不能宣称真实教学泛化。

证据：`experiments/results/mmfopd_v3_development_compressed_card/summary.csv`。

## 3. C²-RAG 教师资源版权控制

### 改进

- 统一 Dense Retrieval、Cross-Encoder 和最终输出测量。
- 修复 1-token 无效生成和 reranking 误过滤目标资源。
- 增加逐轮累计 LCS、n-gram、语义和知识单元恢复曲线。
- 增加 ASR@10/25/50、最终暴露严重度和 Reconstruction AUC。
- C²-RAG 生成 controlled quote、summary、variant、concept、minimal hint、refuse 候选；CG 选择最终候选。

### 120 对正常—攻击 development 结果

| 方法 | ASR@25↓ | 暴露严重度↓ | AUC↓ | 正常效用↑ | 逐轮可用率↑ | 平衡安全效用↑ |
|---|---:|---:|---:|---:|---:|---:|
| No-defense RAG | 1.00 | 0.891 | 0.900 | 0.783 | 1.00 | 0.085 |
| N-gram Guard | 0 | 0.116 | 0.113 | 0.167 | 1.00 | 0.147 |
| Full C²-RAG | 0.25 | 0.240 | 0.235 | 0.500 | 1.00 | 0.380 |
| **C²-RAG + CG** | **0** | **0.212** | **0.206** | **0.500** | **1.00** | **0.394** |

C²-RAG+CG 在保持正常效用和逐轮可用率的情况下，相比 C²-RAG 单独运行将累计重构 AUC 降低约 12.3%。来源伪造专项中，Full 拒绝未知许可；去 Provenance 版本不拒绝且知识恢复为 0.5。

证据：`experiments/c2rag_v3/results/paired_differentiated_budget040/final_development_table.csv` 与 `experiments/c2rag_v3/results/provenance_spoof_isolated/`。

## 4. 选择性 HSW-ST 文本水印

### 改进

原 Full HSW-ST 在本地 0.5B 模型上虽然 WDR=100%，但公式、数字和占位符严重丢失。新版本采用双通道：自由解释文本走 KGW；公式、数字、术语走确定性关键内容通道。自动修复数量被完整记录，不伪装成模型原生遵循。

### 12 条 long 文本真实 Qwen 结果

| 方法 | WDR↑ | FPR↓ | ADR↑ | TKR↑ | FKR↑ | NKR↑ | Placeholder↑ |
|---|---:|---:|---:|---:|---:|---:|---:|
| KGW only | 0.833 | 0 | 0.750 | 1.000 | 0.563 | 0.950 | N/A |
| 原 Full HSW-ST | 1.000 | 0 | 0.850 | 0.604 | 0.167 | 0.388 | 0 |
| **选择性 HSW-ST** | **1.000** | **0** | **0.850** | **1.000** | **1.000** | **1.000** | **1.000** |

选择性版本保持了检测和攻击鲁棒性，并恢复关键内容完整性。12/12 样本发生确定性修复，平均修复 26.25 个占位符，因此 100% 是端到端保护通道结果。摘要式攻击 ADR 仍只有 25%，其余四类规则攻击为 100%。

证据：`experiments/results/text_watermark_selective12/run_20260906_221459_352036/`。

## 5. CG 跨层多智能体控制实验

### 实验设置

- 60 个 episode、每个 4 轮、五种控制模式，共 1,200 条控制面执行记录。
- 五类场景各 12 个：正常教学、画像拆分、教师资源拼接、隐私—版权跨域、审计/水印来源篡改。
- 五种模式：No-CG、Independent-Policy、Static-CG、Budget-Only、Full-CG V3。
- 所有模式共享输入、执行契约、实际披露测量和离线 oracle。
- 各轮输入包含当前开发版本的 MM-FOPD 暴露/召回证据、C²-RAG AUC/候选证据，以及 HSW-ST 检测/关键内容/来源绑定证据。

### 结果

| 模式 | 隐私 ASR↓ | 版权 ASR↓ | 跨域 ASR↓ | 预算违规↓ | 正常可用↑ | 篡改检测↑ | 反馈改变决策↑ |
|---|---:|---:|---:|---:|---:|---:|---:|
| No-CG | 1.00 | 1.00 | 1.00 | 0.80 | 1.00 | 0 | 0 |
| Independent-Policy | 1.00 | 1.00 | 1.00 | 0 | 1.00 | 0 | 0 |
| Static-CG | 1.00 | 1.00 | 1.00 | 0 | 1.00 | 0 | 0 |
| Budget-Only | 1.00 | 1.00 | 1.00 | 0 | 1.00 | 0 | 0 |
| **Full-CG V3** | **0** | **0** | **0** | **0** | **1.00** | **1.00** | **0.20** |

Full-CG 是唯一同时调用动态跨域 composer、独立双预算、history/trust/provenance/audit feedback 和候选动作评分的模式。它保持正常教学可用率 100%，同时阻断当前 oracle 下的隐私、版权和跨域攻击；12/12 篡改 episode 均触发拒绝、阻断或审计升级。Full 与 Static 的逐轮完整输出匹配率为 0，说明动态控制不是只增加日志字段。

证据：`experiments/results/cg_v3_integrated_dev/summary.csv`、`all_rounds.jsonl`、`episode_pair_differences.jsonl` 和 `anomalies.json`。

## 6. 论文中可以与不可以声称的内容

### 5.1 共享 NeMo 基座的外部控制器对比

当前环境没有安装官方 `nemoguardrails` Python runtime，因此本实验共享的是仓库真实执行的 `NeMoGuardrailsAdapter`（input/retrieval/action/output deterministic rails），不能写成官方 LLMRails 结果。AgentSpec 与 GuardAgent 也都是接口对齐的 style adapter，不是官方复现。

| 上层控制器（共享 NeMo-compatible rails） | Privacy ASR↓ | Copyright ASR↓ | Cross-domain ASR↓ | Normal availability↑ | False refusal↓ | Tamper detection↑ |
|---|---:|---:|---:|---:|---:|---:|
| NeMo Base | 1.00 | 1.00 | 1.00 | 1.00 | 0 | 0 |
| NeMo + Independent | 1.00 | 1.00 | 1.00 | 1.00 | 0 | 0 |
| NeMo + Static | 1.00 | 1.00 | 1.00 | 1.00 | 0 | 0 |
| NeMo + Budget-only | 1.00 | 1.00 | 1.00 | 1.00 | 0 | 0 |
| NeMo + AgentSpec-style | 1.00 | 0 | 0 | 1.00 | 0 | 0 |
| NeMo + GuardAgent-style | 0 | 0 | 0 | 0 | 1.00 | 0 |
| **NeMo + Full CG** | **0** | **0** | **0** | **1.00** | **0** | **1.00** |

AgentSpec-style 的固定 trigger/predicate/action 规则能覆盖版权与跨域条件，但不能识别当前画像分段重构；GuardAgent-style judge 通过普遍拒绝实现零 ASR，正常任务同时不可用。Full CG 在当前开发 oracle 下取得零 ASR，同时维持正常可用并检测审计篡改。

证据：`experiments/results/cg_external_controller_dev/summary.json`、各控制器 JSONL 和 `manifest.json`。

当前可以声称：

1. MM-FOPD 在合成 development 数据上表现出更好的信息单元召回—披露折中。
2. C²-RAG 的累计重构指标能够区分无防护、低效过滤、独立版权控制和 CG 联动。
3. 选择性 HSW-ST 在 12 条本地真实 Qwen long 文本上同时保持检测能力和端到端关键内容完整性。
4. CG 的动态 composer、双预算和反馈闭环在确定性控制面实验中真实改变了动作和最终 payload。

当前不可以声称：

1. 四模块已经在大规模真实学生和真实教师私有资源上验证。
2. GPG/PAPILLON/Privacy Funnel 或外部水印方法已经完成官方复现。
3. 12 条 0.5B 文本水印结果足以证明跨模型泛化。
4. CG 的 0% ASR 等价于真实红队攻击下绝对安全；当前数据和 oracle 仍为开发级确定性设置。

## 7. 下一阶段冻结要求

- 固定开发参数后，不再根据 held-out test 逐样本调参。
- MM-FOPD 补充独立教学效用和属性推断攻击。
- C²-RAG 用真实 Qwen 扩大 paired subset，并保存分攻击置信区间。
- 文本水印接入忠实外部基线并扩大模型、长度和攻击种类。
- CG 接入真实四 Agent 运行输出，而不是只使用已验证指标范围的结构化证据快照。
- 正式结果报告 bootstrap/Wilson 95% CI、配对显著性和失败案例。
