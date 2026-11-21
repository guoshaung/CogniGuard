# 历史项目同步记录

此文是阶段性检查记录，不作为当前安装或公共接口指南。
当前入口见 [项目主页](../../README.md)，物理目录见 [目录布局](../REPOSITORY_LAYOUT.md)。

> 原始检查截至 2026-08-26；目录与 HTTP 入口说明已同步到 2026-10-26 的整理结果。
> 下文保留研究实现与外部能力的原有核验边界，不代表所有内容已提交或已发布。

当前命名：`cogniguard/` 是安全保护框架 Python 包，包含 Agent、治理适配、工作流与 HTTP 接口；
`visualization/` 是研究可视化工具，包含 React 看板与实验展示。
下文记录整理阶段的包名与业务路径；当前公共治理入口及教育接入见项目主页。
共享图运行时仍在 `core/`，领域算法仍在 `protection/`。

## 1. 项目一句话定义

CogniGuard 是面向个性化教育大模型的研究型安全保护框架：在学生画像最小披露、教师资源版权/暴露控制、生成内容水印与审计追踪之间进行多 Agent 协同，并提供攻击评估、实验脚本和研究可视化工具。

主要依据：`README.md`、`cogniguard/agents/agent_orchestrator.py`、`cogniguard/demo/classroom_session.py`、`cogniguard/protection/image_watermarking.py`、`protection/student_profile`、`protection/teacher_resource`、`protection/audit_trace`。

## 2. 当前可运行状态

### 已完成或有真实实现

- 根目录轻量 HTTP 演示服务器：`server.py`，默认端口 8000；能提供 dashboard 数据、案例、会话、文本/图像水印相关接口，且包含 deterministic demo 数据和本地回退。
- 研究可视化工具的 Vite/React 面板：`visualization/src/App.jsx` 及 `visualization/src/components/`；有 classroom、C2-RAG、审计、水印、攻击评估等页面和请求。
- 教室多轮流程与自由聊天：`cogniguard/demo/classroom_session.py`、`cogniguard/demo/free_chat.py`；包含学习状态、教学回答、攻击轮次、隐私/版权/审计状态。
- CG v2 的消息封装、能力注册、风险评分、预算、路由、审计链：`cogniguard/protection/cg/protocol.py`；对应策略引擎：`cogniguard/protection/cg/policy_engine.py`。
- 本地确定性图像水印/检测/攻击预览及可选远程 SCE-LocGuard/图像服务适配：`cogniguard/protection/image_watermarking.py`。
- FOPD、C2-RAG、暴露预算、资源检索、返回策略、来源追踪和文本水印模块：`protection/student_profile/`、`protection/teacher_resource/`、`protection/audit_trace/`。
- 既有测试覆盖较广，尤其是 `cogniguard/tests/`、`protection/*/tests/`、`experiments/*/tests/`。

### 部分完成、占位或无法确认

- 旧 FastAPI `APIRouter` 原型位于 `cogniguard/api/legacy/`，未挂载；实际 HTTP 接口由 `cogniguard/api/routes/` 注册，通过 `server.py` 启动。
- `cogniguard/agents/mimo_client.py`、`image_watermarking.py` 的远程模型/服务调用依赖外部 URL、Key 和服务状态；无 Key 时会走 mock/deterministic fallback，外部链路未在本次检查中实际验证。
- `protection/audit_trace` 中有更重的 Transformers/Torch/模型水印流水线，属于实验/论文验证路径，不能等同于轻量 dashboard 已使用的路径。
- `third_party/editguard/` 是 EditGuard 上游模型源码，权重不在仓库；训练、真实模型推理可用性无法确认。
- `visualization/src/components/AcademicFigurePanel.jsx` 含大量 demo figure fallback 数据；界面展示不一定代表后端产生了对应实测结果。

### 正确启动方式（按 README 与入口核对）

1. 使用 `.venv-langgraph` 安装 `requirements.txt`；研究可视化工具在 `visualization/` 执行 `npm install` 后 `npm run dev`。
2. HTTP 演示服务：在项目根目录执行 `serve.cmd 8000`，默认 `http://localhost:8000/`。
3. 前端：在 `visualization/` 执行 `npm run dev`；`visualization/vite.config.js` 将 `/api` 代理到 `http://localhost:8000`。
4. 主线 demo 使用 `run.cmd demo --json`；框架演示模块可通过 `.venv-langgraph\Scripts\python.exe -m cogniguard.demo.run_demo` 运行。实验使用 `run.cmd experiments`，具体配置取决于实验目录。

### 已知报错或阻塞

- 当前工作树不是干净状态：大量文件已修改、删除或新增；不能把当前状态视为 `HEAD` 的稳定发布版本。
- 根目录的 `AGENTS.md` 和 `CONTRIBUTING.md` 定义当前维护入口及目录约定。
- `.env` 存在但未纳入同步内容；`.env.example` 是主要配置清单。
- 真实外部 MIMO、NARRA、SCE-LocGuard、Ollama、Transformers/Torch 路径需要服务、模型、权重或密钥；缺失时只能依赖回退，是否满足研究结论需单独复验。
- `visualization/dist/`、`visualization/node_modules/`、`.understand-anything/`、缓存、实验结果和 `artifacts/packages/cogniguard_spatial_migration_v3.tar` 是生成物/环境物，不能作为源代码完成度证据。
- 未执行完整测试套件；本同步包是静态代码与 Git 证据审计，不声称当前所有测试通过。

## 3. 当前架构

| 层 | 真实实现与文件证据 |
|---|---|
| 前端 | Vite 配置与代理在 `visualization/vite.config.js`；React 入口/页面状态在 `visualization/src/App.jsx`；功能面板在 `visualization/src/components/`。 |
| 后端 | `server.py` 为启动兼容入口；HTTP 处理器在 `cogniguard/api/http_server.py`，29 个接口统一注册于 `cogniguard/api/routes/`；共享服务在 `api/services/`。旧 FastAPI router 明确保留在 `api/legacy/`，不挂载。 |
| 数据层 | 主要是 JSON/JSONL 文件，不是关系数据库：`data/datasets/`、`data/raw/`、`data/processed/`、`data/scenario_layers/`、`experiments/datasets/`；运行日志/产物在 `var/logs/`、`var/outputs/`、`experiments/results/`。 |
| AI/Agent | Agent 编排在 `cogniguard/agents/agent_orchestrator.py`；旧/并行编排在 `cogniguard/agents/orchestrator.py`；远程聊天客户端在 `cogniguard/agents/mimo_client.py`；实验级 FOPD/C2-RAG/水印模块在 `protection/`。 |
| 安全保护 | 学生画像最小披露、版权受控返回、CG、审计链、文本/图像水印分别见 `cogniguard/compliance/`、`cogniguard/protection/cg/`、`protection/student_profile/`、`protection/teacher_resource/`、`protection/audit_trace/`、`cogniguard/protection/image_watermarking.py`。 |
| 测试与部署 | Python 测试分布在 `cogniguard/tests/`、`protection/**/tests/`、`experiments/**/tests/`、`scripts/server/`；前端构建由 `visualization/package.json`；部署资料主要在 `deploy/image_watermark/`、`scripts/server/`。 |

## 4. 核心执行流程

### A. 当前前端 dashboard 主路径

1. 浏览器加载 `visualization/src/App.jsx`。
2. `App.jsx` 请求 `/api/runtime/status`、`/api/cases` 等数据；其他面板请求 `/api/c2-rag/cases`、`/api/attack-eval-results` 等。
3. Vite 开发代理将请求转到 8000：`visualization/vite.config.js`。
4. `api/http_server.py` 的处理器调用 `api/routing.py` 注册表选择端点，`api/routes/` 解析请求并调用业务服务；`api/services/` 提供共享的案例执行、水印和历史指标。
5. JSON 返回给 `App.jsx` 和各面板，图表/审计链/攻击状态渲染到页面。

### B. 教室闭环 demo 路径

1. 输入场景或学生消息，进入 `cogniguard/demo/classroom_session.py:run_classroom_turn`。
2. 初始化/规范化 session、learning state、dialogue mode。
3. 通过 `_run_learning_turn`、`StudentLearningAgent`、`LearningAssessmentAgent` 计算学生状态、错误类型、掌握度与下一步教学动作。
4. `AgentOrchestrator`/`CGController`（`cogniguard/agents/agent_orchestrator.py`）处理 Agent 间权限、数据类别、风险和最小披露。
5. 教师回答经 `_teaching_answer` 或动态/Vertex 分支生成；版权返回模式、图片生成条件、语义水印和 HMAC/audit 字段被加入状态。
6. 结果由 `_pipeline_snapshot`、`_message` 等函数整理，返回 round history、audit/protection/attack 状态。

### C. 自由聊天路径

输入进入 `cogniguard/demo/free_chat.py:run_free_chat`，先进行 `_free_chat_safety_block`，再选择 deterministic 回答或可选 LLM/图片路径，最后由 `_build_guardrail_text` 与 `_maybe_generate_free_chat_images` 组装输出。

### D. 实验/保护层路径

实验脚本加载 JSONL profile/resource/task，依次调用 `ProfileSelector`/FOPD、`CopyrightAwareRetriever`/`ExposureBudget`/`return_policy`、`HybridWatermarkSystem` 或 `semantic_protector`，再由 `source_tracer`、`audit_chain` 与 evaluator 写出 CSV/JSON 结果。代表入口为 `experiments/evaluation/eval_joint_synergy.py`、`experiments/evaluation/eval_unified.py`、`protection/audit_trace/src/main.py`。

## 5. 功能清单

| 功能 | 完成度 | 关键文件 | 是否被实际调用 | 验证证据 | 存在的问题 |
|---|---|---|---|---|---|
| 前端 dashboard | 部分完成 | `visualization/src/App.jsx`、`visualization/src/components/` | 是，前端请求明确存在 | fetch 路径、Vite proxy | 部分面板有 fallback/demo 数据 |
| 轻量后端服务 | 可运行 demo | `server.py` | 是 | `start_server()`、HTTP handler | 与 FastAPI 路由存在两套接口架构 |
| 教室多轮学习 | 真实实现+demo分支 | `cogniguard/demo/classroom_session.py` | 是，demo/测试引用 | `run_classroom_turn`、相关 tests | 动态/数据集/回退分支并存 |
| 自由聊天 | 真实实现 | `cogniguard/demo/free_chat.py` | 是 | `run_free_chat`、安全测试 | 真实 LLM 是否启用取决于 env |
| Agent/CG | 真实实现，仍需集成核验 | `cogniguard/agents/agent_orchestrator.py`、`cogniguard/protection/cg/protocol.py` | 教室路径调用；FastAPI 路径未确认 | 类和调用关系、tests | 旧 `orchestrator.py` 并行存在 |
| MM-FOPD | 实验实现并接入部分流程 | `protection/student_profile/`、`cogniguard/compliance/` | 实验路径明确；dashboard 多为适配数据 | FOPD tests、evaluation | 真实模型/生产持久化缺失 |
| C2-RAG/版权控制 | 实验实现并有 demo 适配 | `protection/teacher_resource/`、`cogniguard/demo/run_demo.py` | demo/实验调用 | retriever/return policy/tests | 多个 Layer/teacher_resource 版本重复 |
| 文本水印/审计链 | 轻量闭环有真实 HMAC/链逻辑；重模型路径实验性 | `classroom_session.py`、`protection/audit_trace/` | 教室路径调用 | audit 字段、链测试/结果 | 前端也有静态示例结果 |
| 图像水印 | 本地 wrapper 可用；外部服务可选 | `cogniguard/protection/image_watermarking.py` | 教室/服务函数调用 | external/local tests | 外部 SCE/API 与权重依赖未确认 |
| 攻击评估 | 代码和结果齐全，API 挂载不确定 | `experiments/attacks/`、`cogniguard/api/legacy/attack_eval_api.py` | CLI/实验明确；FastAPI入口不确定 | attack tests、results | 结果目录有多版本，需锁定口径 |
| 数据生成/加载 | 已有数据与生成器 | `cogniguard/supporting/data_generation/`、`scripts/`、`data/` | 部分 demo/实验调用 | manifest、JSONL、脚本 | raw/processed/generated 版本较多 |
| 旧 EditGuard 源码 | 保留的研究代码 | `third_party/editguard/` | 未证实被当前 dashboard 调用 | 独立 CLI/训练脚本 | 权重不在仓库，疑似独立旧架构 |

## 6. 目录和文件分类

### 当前核心文件

- `server.py`、`visualization/src/App.jsx`、`visualization/src/components/`
- `cogniguard/demo/`、`cogniguard/agents/agent_orchestrator.py`、`cogniguard/runtime/mode.py`
- `cogniguard/protection/cg/`、`cogniguard/protection/image_watermarking.py`
- `protection/student_profile/`、`protection/teacher_resource/`、`protection/audit_trace/`
- `data/datasets/`、`data/scenario_layers/`、`experiments/attacks/`、`experiments/evaluation/`

### 辅助文件

- `cogniguard/api/dashboard_data.py`、`cogniguard/compliance/`、`cogniguard/scenario_loader.py`
- `scripts/`、`deploy/image_watermark/`、`docs/`、`pytest.ini`、`requirements.txt`、`visualization/package.json`

### 自动生成文件

- `visualization/dist/`、`visualization/node_modules/`
- `__pycache__/`、`.pytest_cache/`、`.ruff_cache/`、`.understand-anything/`
- `var/logs/`、`var/outputs/`、`experiments/results/` 中的运行结果
- `data/raw/`、`data/processed/` 中按 task 编号批量生成的文件（具体数据集除外）

### 实验性文件

- `experiments/` 下的 ablation、sampling、attacks、evaluation、dataset builders
- `protection/audit_trace/` 的重模型流水线
- `protection/supporting/image_watermark/`、`scripts/server/` 的服务/阈值/冻结配置
- `third_party/editguard/` 下 EditGuard 训练与模型源码

### 疑似重复文件

- `cogniguard/agents/orchestrator.py` 与 `cogniguard/agents/agent_orchestrator.py`
- `protection/Layer1_fopd_c2rag/`、`protection/Layer2_c2rag/`、`protection/student_profile/`、`protection/teacher_resource/` 中的相似 FOPD/C2-RAG 实现
- `protection/audit_trace/src/hybrid_watermark.py` 与 `cogniguard/demo/classroom_session.py` 中的审计/水印逻辑
- `server.py` 启动兼容入口与 `cogniguard/api/legacy/` 中未挂载的历史 FastAPI 原型

### 疑似废弃文件

- 根 `main.py` 仅为 PyCharm hello-world 样式入口，不连接 CogniGuard。
- `third_party/editguard/test.py`、`third_party/editguard/test_gradio.py`、部分旧训练脚本和旧输出目录。
- `visualization/dist/`、`.tmp/`、大 tar 包属于构建/迁移/临时物，不应当作为源码维护。

### 无法判断的文件

- `protection/supporting/image_watermark/`、`artifacts/packages/cogniguard_spatial_migration_v3.tar` 的完整迁移边界。
- `docs/` 中新增的实验说明与当前代码版本的对应关系。
- 多套 `experiments/results/*` 的正式基准版本和论文引用口径。
- 工作树中大量未提交新增/修改文件是否代表当前目标版本，需由维护者确认。

## 7. 设计与实现的不一致

- HTTP 服务沿用标准库实现，入口为 `server.py`，正式接口位于 `cogniguard/api/routes/`，没有迁移到 FastAPI 或 LangGraph Server。
- `visualization/vite.config.js` 指向 8000 的现有 URL 保留；未挂载 FastAPI 原型已移至 `api/legacy/`，当前前端请求由正式注册表处理。
- 同一 Agent 功能存在新旧两套：`agent_orchestrator.py` 是 CG/权限/数据类别更完整的实现，`orchestrator.py` 直接组装 FOPD/C2-RAG/水印组件；调用方分散，需确认保留哪套。
- C2-RAG/FOPD 存在 Layer1、Layer2、student_profile、teacher_resource 多套目录；它们均有 retriever/metrics/pipeline 类，部分实验直接导入不同路径，说明架构尚未收敛。
- 前端 `AcademicFigurePanel.jsx` 直接提供 demo 行、攻击和链状态 fallback；因此“界面显示某指标”不能证明后端实际计算过该指标。
- 历史 `api/legacy/dialogue_api.py` 暴露不同的 `/next-round`、`/reset-session` 契约；正式前端使用 `api/routes/dialogue.py` 的 `/api/dialogue/*` 接口。
- 历史 `api/legacy/attack_eval_api.py` 不挂载；当前攻击结果由 `api/routes/attacks.py` 提供，episode 和模板由 `api/routes/scenarios.py` 提供。
- README 提到真实 LLM 与外部服务可选，但默认 `COGNIGUARD_RUNTIME_MODE=mock`，所以默认启动验证的是 deterministic demo，不是完整真实模型链路。
- README/实验报告与当前未提交工作树不能直接等同：`git status` 显示 README、requirements、多个核心模块和实验代码均被修改。

## 8. 当前真实数据结构

- 输入：场景 case、学生消息、教师资源、攻击消息；来源为 `cogniguard/demo/demo_cases.py`、`data/datasets/`、`data/scenario_layers/`、`experiments/datasets/`。
- 学生状态：profile/context card、mastery、confidence、error type/status、learning stage、hint dependency、round history；由 `classroom_session.py` 维护并输出。
- 教师资源：`TeacherResource`、resource/chunk/source/license/copyright level、retrieval score、exposure budget、return mode；定义/使用在 `protection/common/schemas.py`、`protection/teacher_resource/src/c2rag/`。
- Agent/CG 状态：message envelope、capability、risk score、budget、policy decision、degraded payload、route logs；见 `cogniguard/protection/cg/protocol.py` 和 `agent_orchestrator.py`。
- 审计/水印状态：answer id、watermark id、seed commitment、semantic watermark、source trace、previous hash、audit hash、chain validity、tamper suspicion；见 `classroom_session.py`、`protection/audit_trace/src/source_tracer.py`、`audit_chain.py`。
- 图像产物：PNG/数据 URL、visible logo、hidden payload/confidence、攻击结果、外部 job/artifact URL；见 `image_watermarking.py`，目录由 `SCE_LOCGUARD_OUTPUT_DIR` 等配置决定。
- 最终输出：教学回答、学生下一问、workflow steps、protection logs、audit trace、attack result、dashboard metrics；通过 demo 函数或 `server.py` JSON 接口流向前端。
- 数据库：未发现 SQLite/PostgreSQL/ORM 表或迁移；项目主要使用 JSON/JSONL、内存 session 和文件日志/结果。

## 9. 安全机制现状

| 机制 | 已真实实现 | 只存在接口/占位 | 只写文档/缺失 |
|---|---|---|---|
| 学生隐私/MM-FOPD | `ProfileSelector`、context card、最小字段摘要、泄露指标与污染检测：`protection/student_profile/`、`cogniguard/agents/agent_orchestrator.py` | 外部模型真实传输边界与生产存储未确认 | 不能仅凭 README 证明所有论文指标均由默认 demo 计算 |
| 教师版权/C2-RAG | resource index、retriever、exposure budget、controlled return、source trace：`protection/teacher_resource/src/c2rag/` | 多套 Layer/teacher_resource 实现并存 | 正式版权数据来源/线上授权流程缺失 |
| CG 多 Agent 防护 | envelope、capability、risk、budget、router、sanitize/degrade、audit chain：`cogniguard/protection/cg/protocol.py` | `policy_engine.py` 使用 closed-loop 适配，是否主流程统一使用需核验 | 生产级跨服务身份/密钥管理缺失 |
| 文本生成审计/水印 | HMAC、语义锁定字段、链式 hash、验证字段：`classroom_session.py`、`protection/audit_trace/src/` | 重模型 watermark 依赖 tokenizer/model；默认 demo 有 deterministic 路径 | 抗攻击研究结论不能由静态 fallback 证明 |
| 图像水印/攻击防护 | 本地 embed/detect/attack、payload HMAC、可选外部服务：`cogniguard/protection/image_watermarking.py` | SCE-LocGuard/远程图像生成由 env 控制 | 真实远程服务、模型权重、长期注册表运维未确认 |
| 审计日志防篡改 | 内存/文件化 hash chain 与 tamper 字段、测试和结果：`audit_chain.py`、`server.py` | server 的日志/registry 持久化策略需确认 | 数据库级不可抵赖、访问控制和告警缺失 |
| 攻击防护 | privacy/copyright/audit/watermark attack runner 与策略分支：`experiments/attacks/` | 部分 API 路由未确认运行 | 不能把实验结果目录当作线上防护证明 |

## 10. 待确认问题

1. HTTP 服务已由 `server.py` 启动，正式路由在 `cogniguard/api/routes/` 注册；后续是否需要独立部署框架 API？
2. `agent_orchestrator.py` 与 `orchestrator.py` 哪一个是目标架构，另一个是否仅用于旧实验？
3. Layer1/Layer2 与 `student_profile`/`teacher_resource` 的正式边界和唯一实现是什么？
4. 当前未提交修改是否都是待交付版本，还是混入了个人实验和临时调参？
5. 默认 mock/deterministic 结果是否允许用于演示、论文图表或验收？
6. MIMO、NARRA、SCE-LocGuard 的真实服务地址、Key、健康检查和故障策略是什么？
7. 图像 watermark 的正式算法/配置是哪一套，`third_party/editguard/`、`protection/supporting/image_watermark/` 与 wrapper 如何对应？
8. `visualization` 的 fallback 数据哪些必须删除，哪些是离线演示的有意设计？
9. 实验结果中哪个目录/日期/数据集是唯一正式基准？
10. 是否需要数据库、用户/会话持久化和多用户并发，还是研究演示保持文件/内存模型？
11. CG 的预算单位、风险阈值和策略决策是否已经冻结？
12. “安全机制已实现”的验收标准是单元测试、端到端测试，还是外部服务实测？
13. `protection/audit_trace` 的重模型流水线是否仍是近期目标？
14. `artifacts/packages/cogniguard_spatial_migration_v3.tar` 和 `protection/supporting/image_watermark/` 是否需要纳入主项目交付？
15. 需要支持的 Python/Node 版本、GPU/CPU 和部署平台是什么？

## 11. 建议保留与整理顺序

### 必须保留

- 先保留 `server.py`、`visualization/src/`、`cogniguard/demo/`、`cogniguard/agents/agent_orchestrator.py`、CG 与图像 wrapper。
- 保留 `protection/` 的实验实现、测试、数据 manifest 和正式结果，但先标注实验版本。
- 保留 `README.md`、`docs/`、`.env.example`、`requirements.txt`、前端 package 配置和可复现实验命令。

### 建议合并

- 统一 `server.py` 与 FastAPI router 的服务入口和 API 契约。
- 在确认目标架构后合并两套 Agent orchestrator。
- 对 Layer1/Layer2/student_profile/teacher_resource 做唯一模块映射，保留兼容导入或迁移说明。
- 统一文本/图像水印、审计链和前端字段 schema。

### 建议归档

- 旧实验结果、调参脚本、论文图表快照、旧配置和 `third_party/editguard/` 上游源码可按日期/版本归档。
- 将 `visualization/dist/`、缓存、临时目录、`.understand-anything/` 和迁移 tar 放入明确的构建/归档区。

### 可以考虑删除

- 只有在确认不再需要后，才考虑删除根 `main.py`、旧测试入口、重复结果目录和无调用的旧模型脚本。

### 删除前必须人工确认

- 所有未提交文件、任何 `data/`、`experiments/results/`、`third_party/editguard/`、`protection/supporting/image_watermark/`、`deploy/` 内容，以及前端 fallback 数据。

## 12. 给另一个 AI 的交接摘要

CogniGuard 是面向个性化教育大模型的研究型安全闭环：学生侧做 MM-FOPD 最小画像披露，教师侧做 C2-RAG/暴露预算/受控资源返回，生成侧做文本与图像水印、来源追踪和审计链，并通过多 Agent/CG 做能力、风险、预算和降级控制。当前可直接确认的 demo 入口是根目录 `server.py`（8000 端口）和 Vite 前端 `visualization/`；默认运行模式是 mock/deterministic。教室多轮主逻辑在 `cogniguard/demo/classroom_session.py`，自由聊天在 `cogniguard/demo/free_chat.py`，Agent/CG 在 `cogniguard/agents/agent_orchestrator.py` 和 `cogniguard/protection/cg/`，外部 MIMO/图像/SCE 服务在 env 控制下可选。实验级实现集中在 `protection/student_profile`、`protection/teacher_resource`、`protection/audit_trace` 和 `experiments/`，已有大量测试、JSONL 数据及结果，但不应把结果目录或前端 fallback 当作线上实测证据。HTTP 服务当前由 `server.py` 启动，正式路由位于 `cogniguard/api/routes/`，旧 FastAPI 原型保留在 `api/legacy/`。仍有两套 Agent orchestrator、多类 FOPD/C2-RAG 实现、轻量水印与重模型水印并存。当前工作树有大量未提交修改/新增/删除，必须先冻结目标版本。后续收敛重点是 Agent/保护实现边界和正式实验结果版本；历史实现应先核对调用关系，再决定归档。
