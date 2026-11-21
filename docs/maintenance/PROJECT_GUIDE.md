# CogniGuard 项目导览

新读者先读 [源码地图](../code-map.md)。多教师安全实验集中在 [experiments/teacher_security/](../../experiments/teacher_security/README.md)，按任务、攻击、评分、防护、运行拆分；`focused/agent_pollution` 保留为历史先导版本。

## 执行主线

`python -m cogniguard` 提供 CLI，`python -m cogniguard.api` 提供 HTTP 服务，实际教育保护编排由 LangGraph 执行。`core.pipeline.ProtectionPipeline` 是图实现的兼容导入名，不再包含独立顺序版流程。

```text
可信访问范围 → 画像白名单与最小选择 → 教师资源受控检索 → 双预算计量
              → 教学输入边界 → 教师 DAG / 模型适配 → 水印与输出治理
```

核心图在 `core/langgraph_runtime/pipeline.py`；教师组合在 `core/langgraph_runtime/teachers/`；看板多 Agent 回合在 `cogniguard/agents/protected_flow_graph.py`；课堂与自由问答在 `cogniguard/demo/*_graph.py`。领域算法不复制，分别从 `protection/student_profile/`、`protection/teacher_resource/`、`protection/audit_trace/` 和 `core/governance/` 调用。

教学 Agent 的可信配置由 `configs/teacher-prompts.yaml`、`configs/teacher-skills.yaml` 与 `configs/teacher-teams.yaml` 共同定义。标准教师批次将提示词和技能版本导入 SQLite 后读回执行；审计表只存元数据。内容交接与最终交付校验默认开启，原历史公开基准适配器显式保留旧口径。真实模型污染靶场及限制见 [TEACHER_POLLUTION_LAB.md](../research/cgc/TEACHER_POLLUTION_LAB.md)。

## 实验

`run.cmd experiments list/show/plan/run` 是全部已发现第一方实验的统一入口；`core/langgraph_runtime/experiment_catalog.py` 将 162 个 CLI 与版本化矩阵按领域、托管等级、风险分层。矩阵使用 `configs/langgraph-experiments.yaml` 和 `core/langgraph_runtime/experiments.py`；各 CLI 使用 `core/langgraph_runtime/tool_jobs.py` 调度图。新运行统一有 `experiment-index.json`，记录名称、模块、领域、等级、风险、状态及底层 manifest 哈希。只有逐一审核过输出参数的 `managed` 条目自动写入独立 `artifacts/`；其余 `compatible` 条目维持脚本输出规则与严格风险门，不伪称已经完成内部标准化。`experiments/focused/*/graph.py` 为注入、权限、工具、记忆、属性推断、事实、提示泄漏、CGC 与供应链等专项子图。旧 `tools` 与 `python -m cogniguard` 命令仅保留兼容，纯计算函数不搬迁。详见 [实验目录](../design/EXPERIMENT_CATALOG.md)。

`experiments/mmfopd_v3/`、`c2rag_v3/`、`formal_v2/` 的主要 runner 已提供逐任务或逐轮图；`rag_real/` 的真实检索和控制探针有批次图，2026-10-14 已在 12 个固定 HotpotQA 案例上重跑锁定的神经检索/控制阶段，并离线配对分析先前 SciFact 排名。2026-10-15 又利用 SciFact 官方 train qrels 校准现有模型的融合系数并一次性评估 test，未训练/下载新模型。`experiments/mmfopd_uci/` 新增等预算字段对齐诊断与葡语科跨学科压力测试。`experiments/evaluation/` 的 CG V3 核心已图化，其他历史单文件评估仍需逐项处理。数据和旧结果保留；是否完成以 [LANGGRAPH_MIGRATION_STATUS.md](LANGGRAPH_MIGRATION_STATUS.md) 的实际验收为准。

## 数据边界

图状态只携带阶段、计数和布尔值；学生画像、教师资料、问题、回答在单次调用 context 中。关闭 checkpoint、自动重试与原生内容追踪，避免泄露或重放有副作用的预算/工具动作。LangSmith 可选且默认关闭；只输出白名单指标。

`data/`、`models/`、`checkpoints/`、`experiments/results/`、`outputs/` 为保留的输入与制品，不因架构迁移而覆盖。迁移前源码快照在项目旁的 `CogniGuard-migration-backup-20261013`。
