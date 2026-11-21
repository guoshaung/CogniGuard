# 源码地图与执行边界

现行调用链和允许写入的目录见 [架构](ARCHITECTURE.md)。
按“公共治理 → 场景接入 → 工作流 → 领域算法 → 研究评估”阅读。
完整目录见 [目录职责](REPOSITORY_LAYOUT.md)。

## 公共治理与教育接入

- [cogniguard/governance/](../cogniguard/governance/)：证据、能力、上下文、生命周期、审计和信任；只依赖标准库。
- [包根](../cogniguard/__init__.py) 导出公开治理原语；最小调用见 [quickstart](../examples/quickstart.py)。
- [integrations/education.py](../cogniguard/integrations/education.py)：教育场景入口与可信访问范围。
  `run_protected_education()` 进入统一交付边界；`ProtectionPipeline.run()` 仍可作为可信应用或离线研究组合点使用。
- [applications/education/protected_access.py](../cogniguard/applications/education/protected_access.py)：
  教育接入的服务端执行、学生绑定及同意状态与网关协调；SDK 重导出同一函数。
- [runtime/gateway.py](../cogniguard/runtime/gateway.py)：服务器会话、幂等、领域成本、最终校验与交付绑定。
- [runtime/sessions.py](../cogniguard/runtime/sessions.py)：SQLite 状态与跨请求预算；不负责证明用户身份。

## 应用、角色和模型接入

- [applications/education/](../cogniguard/applications/education/)：课堂、自由问答、案例运行与案例加载。
  `classroom.py`、`conversation.py`、`case_study.py` 提供场景调用，图结构集中在 workflows。
- [agents/protected_orchestrator.py](../cogniguard/agents/protected_orchestrator.py)：受保护的教育 Agent 协作。
- [agents/research_orchestrator.py](../cogniguard/agents/research_orchestrator.py)：原有研究 Agent 流程。
- [providers/mimo.py](../cogniguard/providers/mimo.py)：模型供应方调用适配，与教学角色分开。
- [cogniguard/demo/](../cogniguard/demo/) 与旧 orchestrator/mimo_client 模块保留导入兼容，不维护第二份应用实现。

## 哪些流程实际由 LangGraph 编排

业务图定义集中在 [cogniguard/workflows/](../cogniguard/workflows/)：

- [pipeline.py](../cogniguard/workflows/pipeline.py)：授权、画像最小化、可选检索/受控返回、隐私计量、治理、生成、水印与输出复核。
  检索需要与否、治理是否阻断均有条件边。
- [education/conversation.py](../cogniguard/workflows/education/conversation.py)：输入检查、后端选择、生成与输出检查；拒绝时提前结束。
- [education/classroom.py](../cogniguard/workflows/education/classroom.py)：案例加载、服务器状态初始化，按 attack/learning 分支执行。
- [education/classroom_learning.py](../cogniguard/workflows/education/classroom_learning.py)：选取学生问题、教学草稿、媒体、水印审计、评估、下一步与状态提交。
  图逐 phase 推进应用层生成器；领域计算仍是普通 Python，不声称所有内部计算都被拆成独立节点。
- [education/case_study.py](../cogniguard/workflows/education/case_study.py)：案例加载、保护 Agent、媒体/水印、合规与展示结果组装。
- [education/protected_turn.py](../cogniguard/workflows/education/protected_turn.py)：准备、诊断、资源、教学、评估、审计与结果组装。
- [education/research.py](../cogniguard/workflows/education/research.py)：研究输入准备、画像选择、资源控制、答案审查与完成。
- [teachers/dag.py](../cogniguard/workflows/teachers/dag.py)：按教师组合建立节点、父节点 join 和并发执行，最后汇总。

研究任务有两种外层调度图：

- [experiments.py](../cogniguard/workflows/experiments.py)：`validate_plan → execute_adapter → collect_artifacts`。
- [tool_jobs.py](../cogniguard/workflows/tool_jobs.py)：`validate → freeze → execute → collect`。

这两类调度器会启动受风险门约束的 worker 或历史 runner 子进程。被调度的实验脚本内部通常
仍是普通 Python 顺序逻辑；使用任务图不等于其算法已经逐节点迁移。基准 runner 的循环和
数据构建脚本也不能一概称作业务图。上述主框架包含 10 类具名图：6 类教育业务图、保护
pipeline、教师 DAG 和 2 类研究任务图；这不是全仓图总数，兼容模块的同名导出不重复计数。

## 独立研究图与历史任务的区别

部分研究 runner 自己已有实际的节点与条件边，不能把它们都归为外层 job 包装：

- [focused/](../experiments/focused/) 的 redteam、injecagent、teaching_injection（单轮/多轮）、
  multiagent、privacy_attack、toolgov、supplychain、promptleak、memorypoison、factuality、
  cgc_e2e 各有图实现，覆盖生成、工具执行、防御、回合或评分步骤。
- [teacher_security/trial.py](../experiments/teacher_security/trial.py) 编排准备、教师、工具、
  评估与持久化；[adaptive.py](../experiments/teacher_security/adaptive.py) 编排开发集上的
  planner/collaborator/defender/feedback 循环，defender 再调用 trial 图。
- [c2rag_v3/graph.py](../experiments/c2rag_v3/graph.py) 控制 fixture、模型配置、方法、session
  与 round 的循环；[mmfopd_v3/graph.py](../experiments/mmfopd_v3/graph.py) 编排画像比较。
- [formal_v2/graph.py](../experiments/formal_v2/graph.py)、
  [formal_v2_llm/graph.py](../experiments/formal_v2_llm/graph.py) 和
  [evaluation/cg_v3_graph.py](../experiments/evaluation/cg_v3_graph.py)、
  [cg_v3_pilot_graph.py](../experiments/evaluation/cg_v3_pilot_graph.py) 执行相应的实验流程。
- [rag_real/graph.py](../experiments/rag_real/graph.py) 用 prepare/item/finalize 推进检索或
  控制实验生成器；[common/sequential_suite_graph.py](../experiments/common/sequential_suite_graph.py)
  用 execute_step/advance 编排历史 baseline 与 ablation 的 callable。
  这类图控制批次或函数调用顺序，单个计算函数仍是普通 Python。
- [student_profile 的 legacy_graph.py](../protection/student_profile/src/pipeline/legacy_graph.py)
  有选题、受控检索、回答/绑定、评分和推进节点；“legacy”名称不表示没有使用 LangGraph。

反过来，数据下载/构建脚本、各领域数值计算、仅被 ToolJobs 子进程调用的普通 CLI，
不能因被允许调度就宣称已具备逐节点治理或观测。这份审计没有改动或重新验收正在独立
研究的水印图、算法及其研究输出；相应覆盖应按水印模块自己的记录核对。

## 领域算法和观测

- [protection/student_profile/](../protection/student_profile/)：MM-FOPD 画像选择和隐私证据。
- [protection/teacher_resource/](../protection/teacher_resource/)：C²-RAG 资源策略与暴露预算。
- [protection/audit_trace/](../protection/audit_trace/) / [protection/supporting/image_watermark/](../protection/supporting/image_watermark/)：文本与图像水印实现，保持各自研究协议。
- [cogniguard/protection/](../cogniguard/protection/)：领域接入、候选检查、输出验证与来源交付适配。
- [core/access.py](../core/access.py)、[domain.py](../core/domain.py)、[teaching.py](../core/teaching.py)、[inputs.py](../core/inputs.py)：仍承载真实教育领域代码；未为目录外观搬动算法。
- [observability/telemetry.py](../cogniguard/observability/telemetry.py)：安全观测事件和可选 LangSmith 导出。
- [observability/graphs.py](../cogniguard/observability/graphs.py)：请求与图的观测接点。

HTTP 路由、SQLite、gateway、模型 provider 和领域算法函数本身不是 StateGraph。
观测只在配置允许时导出，整理目录不触发真实模型、外部遥测或正式实验。
部分独立研究图显式关闭原生 tracing；有 StateGraph 不等于所有内部节点都已经接入
请求级 LangSmith 观测，必须区分任务外层事件与内部算法执行。

## 服务、工具和兼容入口

- [API](../cogniguard/api/README.md)：传输、路由、参数和共享服务；`create_router()` 只负责组装 HTTP 路由。
- [可视化](../visualization/README.md)：研究界面，区分真实交付与合成预览。
- [实验目录](../experiments/README.md)：协议、runner、数据与历史版本。
- [CLI](../cogniguard/cli.py)：`python -m cogniguard`；HTTP 使用 `python -m cogniguard.api`。
- [实验发现](../cogniguard/workflows/experiment_catalog.py) 与 [工具调度](../cogniguard/workflows/tool_jobs.py)：风险门、隔离执行与结果索引。
- [依赖清单](../requirements/)、[工具配置](../pyproject.toml)、[编辑器工作区](../tools/editor/CogniGuard.code-workspace)。

`core/langgraph_runtime`、`core.pipeline` 和 `core/governance` 仅保留历史导入兼容。
历史实验和冻结清单保留原始口径；源码路径调整不构成实验结果重算。
