# Governance API

框架的领域无关治理实现。公开类型可直接从 `cogniguard` 导入；
完整可运行示例见 [examples/quickstart.py](../../examples/quickstart.py)。

## 处理链路

可信调用方创建 `CapabilityPolicy`，并将结构化的 `EvidenceEnvelope` 交给
`LifecycleGuard.evaluate()`。治理器核对能力授权、上下文边界、领域约束、来源与审计状态，
返回 `LifecycleDecision`，同时更新会话信任和审计记录。

- `capability.py`：调用主体类别、目标和使用目的的授权。
- `evidence.py`：主体、目的、上下文边界与领域证据的数据结构。
- `lifecycle.py`：根据证据协调治理决策；不负责各领域的算法和预算计算。
- `audit.py`：进程内哈希链审计记录。
- `trust.py`：会话信任状态。

## 集成约定

调用方必须从可信会话或配置构建主体及权限；用户文本、检索内容和模型输出不应授予权限。
`audit_valid` 应来自调用方实际的审计验证；治理器不会自动读取外部持久化审计服务。

`sanitize`、`degrade` 等动作表示治理决策。实际内容变换由集成方实现；
`rollback_required` 也需要调用方执行相应回滚。治理器本身不会清理文本、撤销工具副作用，
或代替领域模块计算隐私与版权成本。

教育领域的接入入口见 [integrations/education.py](../integrations/education.py)，
HTTP 入口见 [api/README.md](../api/README.md)。
