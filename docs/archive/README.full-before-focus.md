# CogniGuard

<p align="center">
  <img src="docs/assets/cogniguard-logo.svg" alt="CogniGuard logo" width="760">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/JavaScript-ES2023-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="JavaScript">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=001018" alt="React">
  <img src="https://img.shields.io/badge/Vite-8-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite">
  <img src="https://img.shields.io/badge/Pytest-87%20passed-0A7F3F?style=for-the-badge&logo=pytest&logoColor=white" alt="Pytest">
  <img src="https://img.shields.io/badge/JointRisk-Full%2BCG%200.124-8B5CF6?style=for-the-badge" alt="JointRisk">
</p>

<p align="center">
  <b>面向个性化教育大模型的学生隐私保护、教师资源版权保护与生成内容审计追踪闭环系统</b>
</p>

CogniGuard 是一个面向硕士毕业论文实验与演示的教育 AI 保护平台。项目关注个性化教学中三个同时存在的风险：学生画像泄漏、教师资源版权重构、生成内容难以追责。系统由三类保护机制和一个横向治理控制器组成，并通过多智能体教学流程串联成闭环。

## 核心创新

| 模块 | 全称 | 解决的问题 | 主要输出 |
|---|---|---|---|
| `MM-FOPD` | Multimodal Minimum Field-Oriented Profile Disclosure | 学生画像过度披露、raw multimodal profile 进入第三方模型 | 最小上下文卡片、画像选择记录、披露指标 |
| `C2-RAG` | Copyright-Constrained Retrieval-Augmented Generation | 教师资源被逐轮重构、原文片段泄漏 | 受控返回模式、暴露预算、资源级溯源 commitment |
| `HSW-ST` | Hybrid Semantic Watermarking and Source Tracing | 生成内容被篡改、复制、争议归因 | 水印记录、审计链、篡改检测与追踪证据 |
| `CG` | Trustworthy Policy Control System | 三机制之间缺少统一策略约束 | 横向策略控制、降级、拒答、合规审计 |

关键设计不是简单堆叠三个模块，而是让它们互相提供受控证据：

- `FOPD -> C2-RAG`：只把最小学习上下文交给资源检索，不暴露 raw profile。
- `C2-RAG -> HSW-ST`：把 `resource_provenance_commitment` 交给生成审计，不把水印职责放进版权模块。
- `HSW-ST -> CG`：把篡改、相似度、重构风险反馈给横向治理控制器。
- `CG -> all`：统一决定是否最小化、降级、拒答、删除或 hash-only 保留。

## 系统流程

```mermaid
flowchart LR
    A["Raw student multimodal data"] --> B["MM-FOPD<br/>minimum profile disclosure"]
    B --> C["Minimum context card"]
    C --> D["CG<br/>privacy/compliance pre-check"]
    D --> E["Profile diagnosis agent"]
    E --> F["C2-RAG<br/>copyright-aware retrieval"]
    F --> G["Controlled resource<br/>summary / outline / variant / refuse"]
    G --> H["Pedagogical teaching agent"]
    H --> I["HSW-ST<br/>watermark + audit chain"]
    I --> J["Protected teaching answer"]
    J --> K["Learning assessment"]
    K --> L["CG profile update gate"]
    L --> B
```

## 联合协同实验效果

当前已经增加端到端联合实验 `experiments/evaluation/eval_joint_synergy.py`，比较单模块、双模块、三模块和 `Full+CG`。核心指标是 `JointRisk`，越低越好。

| 方法 | JointRisk ↓ | Utility ↑ | 说明 |
|---|---:|---:|---|
| `None` | `1.000` | `0.602` | 无保护 |
| `Best single: FOPD-only` | `0.603` | `0.718` | 最强单模块 |
| `Best pair: FOPD+HSWST` | `0.394` | `0.759` | 最强双模块 |
| `Full CogniGuard w/o CG` | `0.291` | `0.811` | 三机制联合 |
| `Full CogniGuard+CG` | `0.124` | `0.832` | 三机制 + 横向治理 |

结论：`Full CogniGuard+CG` 的联合风险低于任意单模块和任意双模块组合。

```text
SynergyGain vs best pair = 0.2706
CG gain                 = 0.1667
Full beats best pair      = True
```

### 图示

论文图默认不入库。运行下面的“联合实验与绘图”命令后，会在
`experiments/results/joint_synergy/figures/` 下生成 bridge、heatmap
等 PNG/SVG 图。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

前端依赖：

```bash
cd frontend
npm install
```

### 2. 运行后端演示服务

```bash
python server.py 8000
```

默认会启动轻量 HTTP 服务，并提供 `/api/*` 数据接口。没有真实 LLM key 时，系统会使用 deterministic fallback，方便本地演示和测试。

### 3. 运行前端面板

```bash
cd frontend
npm run dev
```

Vite 开发服务会把 `/api` 请求代理到 `http://localhost:8000`。

### 4. 运行完整闭环 demo

```bash
python -m backend.app.demo.run_demo --case-index 0
```

输出会包含：

- `workflow_steps`
- `agent_outputs`
- `protection_logs`
- `compliance_state`
- `compliance_policy`
- `audit_trace`
- `final_protected_teaching_answer`

## 实验入口

### 联合协同实验

```bash
python -m experiments.evaluation.eval_joint_synergy --config protection/student_profile/configs/default.yaml
```

生成：

- `experiments/results/joint_synergy/joint_synergy_rows.csv`
- `experiments/results/joint_synergy/joint_synergy_summary.csv`
- `experiments/results/joint_synergy/joint_risk_reduction.csv`
- `experiments/results/joint_synergy/joint_synergy_gain.csv`
- `experiments/results/joint_synergy/joint_synergy_results.json`

生成论文图：

```bash
python -m experiments.common.plot_joint_synergy
```

### 隐私与版权 baseline 对比

```bash
python -m experiments.baselines.run_baseline_comparisons --config protection/student_profile/configs/default.yaml
```

覆盖的隐私 baseline：

- `PII-Redaction`
- `PresidioStyle-PII-Masking`
- `RBAC-only`
- `ABAC-PurposeOnly`
- `DP-NoisyTopK`
- `LocalOnly-NoThirdParty`

覆盖的版权 baseline：

- `ProtectedMaterialDetector`
- `MemFree-Ngram`
- `SHIELD-Agent`
- `BloomScrub-Rewrite`
- `R-CAD-Approx`

### 组件消融

```bash
python -m experiments.ablation.run_protection_ablations --config protection/student_profile/configs/default.yaml
```

FOPD 消融包括：

- `BasicFOPD`
- `EnhancedFOPD-Full`
- `EnhancedFOPD-w/o-Orthogonal`
- `EnhancedFOPD-w/o-TaskAttention`
- `EnhancedFOPD-w/o-Bottleneck`
- `EnhancedFOPD+CG`

C2-RAG 消融包括：

- `C2RAG-full`
- `C2RAG-w/o-Budget`
- `C2RAG-w/o-Variant`
- `PlainRAG`
- `RAG-Truncation`
- `RAG-SummaryOnly`
- `GuardrailOnly`

### HSW-ST 文本水印实验

```bash
cd protection/audit_trace
python src/main.py --config configs/config.yaml --mode demo
```

批量消融：

```bash
python -m experiments.ablation.run_all_ablations --mode experiment
```

### 图像水印（EditGuard wrapper 基线）

当前可运行分支是 EditGuard 单图嵌入/盲检、64 位 HMAC 来源胶囊和服务端注册表；
DFG 特征提取与训练闭环尚未完成，不能把当前结果命名为已训练的 DFG-LocGuard。
论文模式禁止 `fallback/local_preview/skeleton` 进入结果。

生成约 1,200 张可复现的合成教育图并构建可移植清单：

```bash
python -m dfg_locguard.experiments.generate_synthetic_education \
  --output data/image_watermark/cogniguard_edufig \
  --count-per-domain 134 --size 512 --seed 20260802
python -m dfg_locguard.experiments.build_manifest \
  --config dfg_locguard/configs/paper_benchmark.yaml \
  --output outputs/image_watermark_manifests/paper_core.jsonl \
  --allow-missing-sources
python -m dfg_locguard.experiments.paper_benchmark \
  --config dfg_locguard/configs/paper_benchmark.synthetic_pilot.yaml \
  --validate-only
```

正式服务器配置、严格预检和 Slurm 示例见
`deploy/image_watermark/README.md`。正式主表必须补齐逐图许可审计的外部数据，
并使用固定 manifest、相同攻击、显式 seeds 和源图级 bootstrap 置信区间。

## 项目结构

```text
CogniGuard/
├── backend/                         # 后端 API、多智能体编排、demo 服务
│   └── app/
│       ├── agents/                  # 教学智能体与受保护通信
│       ├── api/                     # 前端数据适配接口
│       ├── compliance/              # FERPA/COPPA 风格合规治理闭环
│       ├── demo/                    # 完整闭环 demo
│       └── protection/              # 图像水印、CG 等后端 wrapper
├── frontend/                        # React + Vite 可视化面板
├── protection/
│   ├── student_profile/             # MM-FOPD 学生画像隐私保护
│   ├── teacher_resource/            # C2-RAG 教师资源版权保护
│   ├── audit_trace/                 # HSW-ST 文本水印与审计追踪
│   ├── cg_guardrails/             # 横向治理控制配置
│   └── common/                      # 跨层 schema、文本工具、trace binding
├── experiments/
│   ├── attacks/                     # 隐私、版权、水印、污染等攻击脚本
│   ├── baselines/                   # 隐私与版权 baseline
│   ├── evaluation/                  # 分层与联合评估脚本
│   ├── ablation/                    # 组件消融批量运行
│   ├── common/                      # 实验绘图与公共工具
│   └── results/                     # 实验输出，默认不纳入版本管理
├── code/                             # EditGuard 上游模型源码（权重另行传输）
├── dfg_locguard/                     # 图像水印 API、来源胶囊与论文 benchmark
├── deploy/image_watermark/           # Linux/GPU 部署与资产校验说明
├── scripts/server/                   # 服务器预检、单 worker 启动与 Slurm 脚本
├── docs/                            # 论文建议、架构说明、API 文档
└── server.py                        # 本地演示 HTTP 服务
```

## 机制边界

### C2-RAG 的资源侧溯源

C2-RAG 负责资源级 provenance：

- `resource_id`
- `chunk_id`
- `license_policy`
- `return_mode`
- `exposure_before`
- `exposure_after`
- `policy_reason`
- `retrieval_trace`
- `quote_span_hash`
- `controlled_output_hash`
- `resource_provenance_commitment`

### HSW-ST 的生成侧审计

HSW-ST 负责生成内容级别的水印和审计：

- `watermark_id`
- `audit_hash`
- `seed_commitment`
- `watermarked_answer_sha256`
- `tamper_suspicion`
- `TraceBindRate`

HSW-ST 绑定 C2-RAG 的资源级 commitment，但不重新定义资源版权溯源；C2-RAG 也不承担生成水印检测职责。

## 合规治理闭环

项目包含一个合规治理模块，作为 CG 的横向策略来源，而不是第四个主创新机制。当前覆盖：

- `compliance_state`
- `compliance_policy`
- `compliance_audit_log`
- `data_category`
- FERPA/COPPA 风格策略判断
- 删除请求后的 hash-only 处理
- 审计 hash chain

核心规则包括：

- COPPA 场景未获得父母同意时，不收集或发送儿童个人信息。
- FERPA 场景下，教育记录必须处于授权和合法教育目的范围内。
- 第三方 LLM 默认只能接收 sanitized context card，不能接收 raw profile。
- audit chain 仅保存 hash commitment，不保存原始学生数据。

## 测试

```bash
python -m pytest backend/app/tests protection/student_profile/tests protection/teacher_resource/tests experiments/attacks/tests -q
```

当前验证结果：

```text
71 passed
```

前端构建：

```bash
cd frontend
npm run build
```

## 论文写作建议

推荐将实验组织为四个研究问题：

1. `RQ1`：CogniGuard 是否比常规隐私/版权 baseline 更能降低风险？
2. `RQ2`：FOPD、C2-RAG、HSW-ST 的组件分别贡献多少？
3. `RQ3`：三者联合是否优于任意单模块和任意双模块？
4. `RQ4`：CG 是否进一步提升跨模块治理效果，同时保持教学可用性？

当前最能支撑创新性的结果是联合协同实验：

```text
JointRisk(None)              = 1.000
JointRisk(best single)       = 0.603
JointRisk(best pair)         = 0.394
JointRisk(Full+CG)         = 0.124
SynergyGain vs best pair     = 0.271
```

这可以直接作为“大论文系统创新”主线：CogniGuard 不是三个独立保护器的拼接，而是一个由 CG 协调的教育 AI 全生命周期保护闭环。

## License

This project is released under the repository license. It is intended for research prototyping, thesis experiments, and educational AI safety demonstrations.
