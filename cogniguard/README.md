# CogniGuard Security Framework

公开治理接口从包根导入，例如 `from cogniguard import LifecycleGuard, EvidenceEnvelope`。
实现位于 `governance/`，只依赖 Python 标准库，见 [治理约定](governance/README.md)。

教育参考流程从 `cogniguard.integrations.education` 接入，需要 `runtime` 可选依赖。
可运行示例见 [examples/README.md](../examples/README.md)。

- `governance/`：能力、证据、上下文边界、审计、信任与生命周期决策。
- `integrations/`：显式领域集成，当前提供教育参考流程。
- `agents/`：教育 Agent 角色与受保护执行图。
- `protection/`：CG 治理策略、Guardrails 适配与图像保护集成。
- `compliance/`：数据分类与治理信息。
- `runtime/`：运行模式和请求级配置。
- `demo/`：自由问答、课堂与研究演示工作流。
- `api/`：研究 API、路由注册和共享服务，见 [API 维护说明](api/README.md)。
- `data_generation/`、`scenario_loader.py`：合成示例与评估场景加载。
- `tests/`：框架集成与接口回归。

`api/` 提供研究 HTTP 服务，启动入口为 `serve.cmd 8000`；
可视化工具位于 `../visualization/`。`create_router()` 是服务内部路由装配函数。
教育图和研究执行实现位于 `../core/`，领域算法位于 `../protection/`，实验定义位于 `../experiments/`。
