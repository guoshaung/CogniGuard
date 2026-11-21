# 应用用例

`education/` 组织业务输入、领域服务和结果组装，所有在线生成入口经过
`cogniguard.runtime.gateway.ProtectionGateway`。

- `classroom.py`：课堂回合和服务端学习状态。
- `conversation.py`：不读取课堂画像的自由问答。
- `case_study.py`：受保护案例执行与研究展示。
- `cases.py`：合成案例和 episode 加载。

图节点、条件路由和编译位于 `cogniguard/workflows/education/`；模型客户端位于
`cogniguard/providers/`。HTTP 参数和传输位于 `cogniguard/api/`。
三层保护与 CGC 的算法不在应用层重新实现。

新调用使用 `from cogniguard.applications.education import run_conversation,
run_classroom_turn, run_case_study`。原 `cogniguard.demo.*` 只保留旧导入兼容。
`classroom.py` 的领域步骤仍由课堂图逐阶段推进；物理目录整理不代表改写算法。
