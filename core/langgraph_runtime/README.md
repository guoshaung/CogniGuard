# 兼容工作流命名空间

实际实现已迁至 [cogniguard/workflows](../../cogniguard/workflows/README.md)。
此目录只保留旧导入与 CLI 的薄兼容层，以及未移位的历史回归测试。

新调用使用 `cogniguard.workflows.*`；旧普通模块通过 `sys.modules` 指向同一正式模块，
因此类身份、可变模块状态与测试 monkeypatch 不会分裂成两套实现。
`telemetry`、`workflow_monitor` 的正式实现属于 `cogniguard.observability`。
