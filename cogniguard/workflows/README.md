# 工作流与研究调度

本包是 LangGraph 流程编排的正式实现位置。图负责节点顺序、条件路由、调用边界和运行记录；
画像选择、版权释放、水印与治理决策仍由对应领域实现负责。

- `pipeline.py`：教育参考保护图，复用既有授权、画像选择、C²-RAG 与可注入接点。
- `education/`：课堂、自由问答和受保护 Agent 等教育应用图。
- `teachers/`：可信教师配置、交接检查、教师 DAG 与本地审计存储。
- `experiments.py`：版本化实验计划和隔离的 worker 执行。
- `experiment_catalog.py`：按领域、执行风险与托管等级浏览实验。
- `tool_jobs.py`：发现、计划和调度经允许的研究 CLI。
- `benchmarks/`：公共语料准备、计划与独立评估轨道。
- `adapters.py`：教育图的显式模型和水印接点；不会在导入时加载真实模型。
- `model_site.py`：模型专用 worker 的既有重依赖环境接入。

新代码从 `cogniguard.workflows.*` 导入。监控基础来自
`cogniguard.observability.telemetry` 与 `cogniguard.observability.graphs`；
项目路径使用 `core.paths` 的统一常量，不根据源码文件层级猜测项目根。

```sh
python -m cogniguard.workflows graph
python -m cogniguard.workflows experiments list
```

`list`、`show` 和计划不会运行模型；正式执行仍需对应条目的明确参数、数据和风险授权。
调度入口统一不表示历史研究脚本内部全部改写为原生 LangGraph 节点，也不改变旧评估口径。

`core.langgraph_runtime.*` 只保留兼容模块：普通模块导入与新模块保持同一对象，
旧 CLI 委托此包。历史测试留在 `core/langgraph_runtime/tests/`，新增命名空间契约测试
位于 `tests/test_workflow_namespace.py`。新实验会记录新路径下的实现指纹，已有冻结记录不改写。
