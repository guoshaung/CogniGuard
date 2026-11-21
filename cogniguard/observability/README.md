# 安全观测

本模块维护本地阶段指标和显式启用的 LangSmith 导出。保护决策属于
CogniGuard 策略；远端客户端初始化、传输或导出故障不会改变保护结果。
原生内容追踪隔离无法建立或清理时，抛出不含原始异常的 `TraceIsolationError` 并停止交付。
清理错误不会覆盖已经发生的业务异常，不修改全局环境或 SDK 私有状态。

## 使用

```python
from cogniguard.observability import (
    LangSmithMonitor, SafeTelemetry, request_observation,
)

recorder = SafeTelemetry()
monitor = LangSmithMonitor.from_environment()
with request_observation(recorder):
    with recorder.span("gateway.request"):
        with recorder.span("gateway.input") as metrics:
            metrics["validated"] = True
        with recorder.span("gateway.budget") as metrics:
            metrics["requests_used"] = 1
monitor.export(recorder)
status = monitor.summary()
```

状态页和 CLI 配置查询使用 `configuration_status()`：只读取已经存在的 `os.environ`，
不构造 SDK Client、不加载 `.env`，也不进行远端探测。`configured` 仅表示启用配置和
凭证均存在，不表示已连接或提交成功。应用入口统一负责加载本地 `.env`，并保留已有环境值。

`request_observation()` 使用 ContextVar 共享当前 recorder，并在作用域内关闭原生
LangSmith tracing。`active_recorder()` 可供内部适配器查找当前记录器。
`graphs.observed_node()` / `graphs.invoke_observed_graph()` 为 LangGraph 节点和调用提供
同样的指标边界；位于请求上下文中的图复用同一树，由请求结束后统一导出。
独立图调用自行导出。嵌套阶段以随机 UUID 建立父子关系，不使用用户或会话标识。

固定阶段与数值指标清单位于 `telemetry.STAGES` / `METRICS`。请求阶段包括
`gateway.request/input/budget/operation/delivery/finalize`。实际模型调用数使用
`model_calls` 或 `model_calls_used`，禁止用估计值替代真实计数。
`provider.mimo` 记录实际 provider 调用；`input_tokens/output_tokens/total_tokens`
仅在 provider 返回真实 usage 时填写，不根据字数估算。
异常仅记录通用错误状态和耗时，不记录异常消息、栈、画像、资源、输入输出正文或凭证。
export 再次验证阶段、ID、时序格式和有限指标；远端 inputs / outputs 始终为空。
`summary()` 仅返回安全状态和配置标签，不回显 endpoint、API key 或任意错误文本。

## 配置与启动

- 默认 `COGNIGUARD_LANGSMITH_ENABLED=false`，本地 recorder 可独立使用，不导入 LangGraph
  或模型依赖；SDK 只在请求上下文或显式导出初始化时按需导入。
- 设置 `COGNIGUARD_LANGSMITH_ENABLED=true` 才允许应用导出；单独设置
  `LANGSMITH_TRACING` / `LANGCHAIN_TRACING_V2` 不会启用本模块。
- 项目：`COGNIGUARD_LANGSMITH_PROJECT` 优先，其次 `LANGSMITH_PROJECT`，最后
  `cogniguard-langgraph`。
- 地址：`COGNIGUARD_LANGSMITH_ENDPOINT` 优先，其次 `LANGSMITH_ENDPOINT`，最后 SDK 默认值。
- 凭证使用本地 `LANGSMITH_API_KEY`。缺失时状态为 `credential_missing`；初始化失败为
  `client_init_failed`；提交结果为 `submitted` / `export_failed`。这些状态不包含错误正文。
- `submitted` 表示记录已经交给 SDK，不代表云端确认接收；状态始终明确
  `remote_confirmed=false`。客户端单次传输 timeout 为 2000 ms，支持有限等待的 SDK
  `flush` 最多等待 0.25 秒，不支持 timeout 的自定义客户端不执行 flush。
  这不构成端到端耗时或云端送达保证，SDK 重试和后台队列仍由 SDK 管理。
- `python -m cogniguard.workflows langsmith status` 查看配置；`langsmith smoke` 只进行本地
  合成指标检查，必须显式添加 `--submit` 才提交。
- PowerShell：`scripts/launch_langsmith.ps1` 默认本地 smoke；`-Submit` 才启用远端导出，
  缺少 key 时隐藏输入。`-Mode demo` / `-Mode serve` 同样需要 `-Submit` 才开启导出。

旧 `core.langgraph_runtime.telemetry` 和 `workflow_monitor` 是相同模块对象的兼容入口，
新增代码使用本目录。所有测试使用假的客户端或拦截 SDK transport，不连接 LangSmith。
