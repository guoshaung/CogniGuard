# DeepTutor 接入检查点

状态：合成案例接线已验证，尚未完成平台受保护接入。DeepTutor 源码单独检出于
`var/tmp/deeptutor-integration`，检查版本 `f7aed0744c36c5afef16a4261c31ebee1208cac2`。
它是第三方 Apache-2.0 项目；依赖和第三方组件许可需另行核验。

## 已确认的边界

- DeepTutor 的 WebSocket、CLI 和 Python SDK 进入共同的 `TurnApplicationService`，
  下层有能力、工具和 Agent 调度。不能假设只修改某个 SDK 会覆盖所有入口。
- DeepTutor 回合事件可持久化并回放，事件还可能包含工具结果和来源；如果仅在最后
  的回答外包一次输出检查，原始流、会话读取或工具数据仍可能绕过检查。
- CogniGuard 的 `run_protected_education` 运行自有教学流程，并非现成的通用外部
  Agent 代理；其会话 token 不是用户身份。身份、工作区和可信策略必须由服务端映射。
- 领域策略由 CogniGuard 负责。DeepTutor 的检索、工具执行和实际交付必须分别接入
  对应可信边界；水印与来源绑定必须作用于最终交付，原始事件不得直接给学生回放。

## 未完成

合成的隔离 SDK 回合已接入 CogniGuard 教育流程，详见
[案例记录](../../experiments/deeptutor_cg_fixture_20261105/README.md)。该案例使用
本机确定性模型替身，不覆盖原生 Web/CLI、工具或原始事件回放。
尚未完成平台端到端连接、真实身份映射、领域策略和各出口覆盖。
尤其不能把第三方源码下载、SDK 导入或单条最终答案检查称为完整接入。
接入后需要验证拒答、重放、流式输出、跨会话状态、检索及工具返回都不能绕过保护。
开发验证只使用合成资料，不自动调用真实模型。

## 未来切换到 SMART RAG

CogniGuard 的领域策略、授权语义和审计规则可复用；平台侧的身份映射、课程和知识库
元数据、Agent/工具调度、流式结果与历史存储适配需要重新实现和验证。SMART RAG 的
部署依赖和非商业许可也需单独核查；不保证更换配置即可切换。
