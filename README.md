# CogniGuard

CogniGuard is a minimum runnable demo for a closed-loop multi-agent personalized education protection system.

The project focuses on coordinated lifecycle protection around personalized tutoring rather than full-scale federated training. Its architecture is organized as three collaborating protection layers governed horizontally by TPCS.

## Three Protection Mechanisms

- **学生画像隐私保护子机制:** MM-FOPD / DIB-MM-FOPD performs multimodal student profile modeling, task-aware minimum disclosure, minimum context card generation, and governed profile-update feedback.
- **教师版权保护子机制:** C²-RAG performs copyright-constrained retrieval, resource exposure budgeting, return-mode control, controlled variants, and anti-reconstruction or reverse-inference detection. Its resource scope includes teacher-uploaded materials, school-purchased databases, publisher question banks, commercial course packages, open educational resources, and AI-derived teaching content.
- **大模型生成内容审计追踪机制:** HSW-ST now uses a semantic-aware, evidence-chain-bound, multi-round robust watermark mechanism. Each answer is bound to a canonical audit record, HMAC-derived hidden seeds, protected semantic-variant choices, source tracing, hash-chain evidence preservation, role-based permissions, and encrypted statistics for generated educational content.
- **TPCS (横向治理控制器):** TPCS is the horizontal governance controller across all three mechanisms. It enforces cross-mechanism permissions, privacy and copyright budgets, sanitization and degradation, refusal, encryption requirements, and audit policies.

The mechanisms are not treated as a one-way sequence. Each mechanism produces controlled feedback that can update later decisions in the same tutoring lifecycle or a subsequent authorized learning round.

## Closed-loop Feedback

The minimum closed-loop contract uses the following cross-layer signals:

- **学生画像隐私保护子机制 -> 教师版权保护子机制:** `context_card`, `student_level`, `knowledge_point`, and `risk_level` guide protected retrieval and resource adaptation.
- **教师版权保护子机制 -> 学生画像隐私保护子机制:** `resource_difficulty`, `variant_performance`, and `resource_fit` provide bounded evidence for profile-update review.
- **教师版权保护子机制 -> 大模型生成内容审计追踪机制:** `resource_id`, `chunk_id`, `return_mode`, `copyright_level`, and `exposure_score` bind generated content to its controlled resource provenance.
- **大模型生成内容审计追踪机制 -> 教师版权保护子机制:** `leakage_risk`, `similarity_risk`, and `multi_turn_reconstruction_risk` can trigger return-mode degradation, budget reduction, resource substitution, or refusal.
- **学生画像隐私保护子机制 -> 大模型生成内容审计追踪机制:** `modality_sensitivity` and `recording_scope` define what may be logged, retained, encrypted, or omitted from audit records.
- **大模型生成内容审计追踪机制 -> 学生画像隐私保护子机制:** `learning_evidence`, `abnormal_behavior`, and revocation/forgetting signals are returned as governed evidence and must pass TPCS approval before affecting the student profile.

TPCS mediates every feedback path. No mechanism may directly expand profile disclosure, expose teacher resources, update a persistent profile, or weaken an audit requirement without an explicit TPCS policy decision.

## Project Layout

CogniGuard 采用保护机制原型与集成服务分离的架构组织方式：

### 前后端服务层
- `frontend/`: Vue.js 前端展示层，提供可视化交互界面
- `backend/`: 后端服务层与 API 集成
  - `backend/app/agents/`: 受保护的 LLM tutoring agent 层，经 TPCS 中介通信
  - `backend/app/api/`: 前后端对接 API 和数据适配器
  - `backend/app/protection/`: 各保护机制的集成 wrapper 接口
  - `backend/app/demo/`: 完整系统演示入口

### 核心保护机制原型库（Protection Mechanisms）
这些模块是独立的研究原型，可单独运行、测试和发布：

- `protection/student_profile/`: **学生画像隐私保护子机制 / MM-FOPD** 学生画像最小化披露、上下文卡片生成和编排
- `protection/teacher_resource/`: **教师版权保护子机制 / C²-RAG** 版权约束检索、资源暴露预算、返回模式控制和反重构控制
- `protection/audit_trace/`: **大模型生成内容审计追踪机制 / HSW-ST** 水印嵌入、来源追踪、可信审计原语
- `protection/tpcs_guardrails/`: **TPCS** 横向治理控制器与 NeMo Guardrails 配置
- `protection/common/`: 跨层模式定义、度量标准、文本工具和追溯绑定合约

### 数据与实验
- `data/`: 原始数据和处理后数据（raw/processed/test）
- `experiments/`: 攻击回归测试、重构攻击、水印攻击、层级评估、消融实验和生成的研究结果
- `scripts/`: 项目级数据生成和工具脚本入口

### 文档与配置
- `docs/`: 架构文档和 API 接口文档
- `requirements.txt`: 根级便捷依赖文件（包含审计追踪层依赖）
- `server.py`: 开发用轻量级 HTTP 服务器

**架构设计说明：**
保护机制模块（protection/）保持独立性，便于：
1. 单独测试和迭代各保护机制
2. 作为独立研究成果发表或开源
3. 与其他系统集成时的模块化复用

后端服务层（backend/app/）提供统一集成接口，协调各保护机制形成完整的三层闭环架构。

## LLM Agent Configuration

The backend agent layer uses Xiaomi MiMo through its OpenAI-compatible chat API. Keep real keys out of git and configure them through environment variables or a local `.env` file:

```bash
COGNIGUARD_RUNTIME_MODE=guarded_llm
COGNIGUARD_NEMO_GUARDRAILS_ENABLED=true
MIMO_API_KEY=your_mimo_api_key_here
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5-pro
MIMO_STUDENT_MODEL=mimo-v2-flash
MIMO_STUDENT_MAX_TOKENS=420
```

If no `MIMO_API_KEY` is present, the agents run with deterministic fallback outputs for local demos and tests.

## Quick Start

Generate synthetic multimodal student data:

```bash
python scripts/generate_synthetic_multimodal_data.py --student-count 30
```

The generator writes raw multimodal artifacts to `data/raw/` and MM-FOPD-safe context cards to `data/processed/profile_cards/`. Agent code should only consume the profile cards.

Run the protected tutoring pipeline demo:

```bash
python -m backend.app.demo.run_demo --case-index 0
```

The demo keeps the top-level architecture as three protection layers plus horizontal TPCS governance; the four LLM agents run only as controlled tutoring nodes.

Run the FOPD + C2-RAG demo:

```bash
pip install -r protection/student_profile/requirements.txt
python -m protection.student_profile.src.pipeline.run_demo --profiles protection/student_profile/data/profiles.jsonl --questions protection/student_profile/data/student_questions.jsonl --resources protection/teacher_resource/data/teacher_resources.jsonl --config protection/student_profile/configs/default.yaml --out protection/student_profile/outputs/demo_results.jsonl
```

Run tests:

```bash
pytest backend/app/tests protection/student_profile/tests protection/teacher_resource/tests experiments/attacks/tests
```

Run the HSW-ST semantic evidence-chain watermark demo:

```bash
pip install -r protection/audit_trace/requirements.txt
cd protection/audit_trace
python src/main.py --config configs/config.yaml --mode demo
```

Run attacks, evaluations, and ablations from the repository root. See
`experiments/README.md` for the experiment entry points.

See the README files inside each module for detailed configuration notes.
