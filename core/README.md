# 教育参考流程与研究执行

公共治理实现位于 [cogniguard/governance](../cogniguard/governance/README.md)，
教育流程的公开集成入口为 `cogniguard.integrations.education`。
本目录保留教育领域服务、统一路径常量和历史兼容导入。

`core/pipeline.py` 只提供兼容导入；实际节点与条件路由在
`cogniguard/workflows/pipeline.py`。`langgraph_runtime/` 也是同对象兼容层。
`domain.py` 初始化选择器、预算账本和结果结构，不独立执行顺序主线。

```text
可信调用方（离线 CLI / 数据集评估）
  ├─ inputs.py       加载配置、画像、题目和资源
  └─ cogniguard/workflows/pipeline.py 编译图协调一轮执行
       ├─ access.py  授权 + 画像字段硬筛选
       ├─ protection/student_profile    相关性选择 + 最小卡片
       ├─ protection/teacher_resource  检索 + 版权与暴露预算
       └─ teaching.py 纯文本教学输入 + 离线规则回答
```

`AccessScope` 必须由可信调用方构建；在线服务应取自已验证的登录会话。
它是进程内的权限对象，不是登录认证服务或操作系统沙箱。
`TeachingInput` 不含原始画像、原始资源对象或可执行工具。
内部 `ProtectionResult` 仍保留诊断信息，不能直接送给模型。

`governance/` 仅重新导出 `cogniguard.governance` 的同一组类型。
基础离线图默认不启用额外治理；可显式配置输入/输出治理接点。
`tests/` 中 `test_access.py` 检查访问范围与数据边界，
`test_injection_boundaries.py` 检查恶意文本输入，`test_focused.py` 检查默认入口。
`test_governance_split.py` 是 pytest 风格的扩展治理测试，不在 unittest 发现范围内。
