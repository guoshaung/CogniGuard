# 领域代理与协调器

- `protected_orchestrator.py`：CGController 与受保护代理协调器。
- `research_orchestrator.py`：离线机制研究的协调器。
- `*_agent.py`：画像诊断、受控资源、教学、学生和评估角色。
- `base_agent.py`：代理协议与输入约束。

LangGraph 实际图已集中到 `cogniguard/workflows/education/`，模型客户端在
`cogniguard/providers/mimo.py`。本目录不再同时承载提供方客户端和图的实现。
`agent_orchestrator.py`、`orchestrator.py`、`mimo_client.py` 与旧 `*_flow_graph.py`
仅保留兼容导入，同名旧入口不会执行另一份策略实现。
