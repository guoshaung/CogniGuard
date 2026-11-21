# 教学画像字段动态授权：基础版

教育 SDK 可选使用 `ProfileConsentPolicy`：可信服务端按画像记录的 `type` 指定
`automatic`（已有可信规则允许的自动处理）、`ask`（需明确同意）或 `deny`。
未列明类型拒绝。策略还需指定版本、请求 Agent 与教学用途；它们是服务端提供的声明，
不从用户文字、模型输出或检索材料取得权限。`automatic` 不代表用户已经同意，也不
自动建立处理的法律依据。

`run_protected_education(..., consent_policy=policy)` 在画像选择与教学生成前筛选记录：
需要同意的类型未获准时不进入教学管线，其他允许记录仍可使用。返回的
`profile_consent_requests` 只含字段类型、请求 Agent、用途、策略版本和随机请求 ID，
不含画像值。类型可能包含多条记录，本版按类型整体授权，不能单独授权一条记录。

确认 UI 应展示字段及用途，由**已认证**的学生作决定后，可信后端调用
`resolve_profile_consent(session, request_id, verified_student_id=..., approve=True/False)`。
它校验会话绑定的教育对象；调用方必须自行完成身份认证。本仓库的匿名 session token
只是持有凭据，不是身份验证。不得把聊天文本或未认证请求直接变成此调用。
`revoke_profile_consent` 可撤销明确同意，并让旧的待审批请求失效；已交付内容无法收回。

同一宿主机上，决策、当前教育调用及同意版本使用会话锁串行化。授权状态变化后，旧
request ID 的缓存结果不能重新交付，调用方需使用新的 request ID。授权仅限该匿名
会话、策略版本、Agent 标签和用途；策略内容改变需更新版本。策略的 Agent 标签不会
自行验证真实模型或路由身份，必须由可信应用确保请求实际送达相应 Agent。没有提供
跨设备账号同步、有效期、按单条记录授权、家长授权、已读取内容的远程撤回或分布式
一致性。教育 SDK 以外的课堂或离线直接调用不受此
基础版约束；未传策略时保留旧行为，不能宣称所有画像已受动态同意控制。

## 仅合成数据的本机界面

已提供默认关闭的演示组件和两条本机限定路由：

```powershell
$env:COGNIGUARD_PROFILE_CONSENT_DEMO='on'
.\serve.cmd 8000
```

打开本机界面的“闭环案例演示”，可针对固定合成画像提问、同意、拒绝与撤销。
此路由不接收学生 ID 或真实画像，也不提供真实身份认证；它仅模拟学生点击后的
服务端流程。当前教师回答由离线规则生成，既有课堂对话不自动继承此演示授权。
如果 Python 服务已启动，需重启才能加载代码和开关。生产环境保持关闭。

同一开关还启用独立的模拟学生登录，账号 `student-demo`、公开演示密码
`demo-only-2026`；仅允许 loopback 请求。登录发放独立 HttpOnly、SameSite=Strict 的
短期会话，退出会清除服务端登录状态。演示账号和密码是公开固定值，不构成真实身份
验证，也没有安全的账号生命周期或生产登录防护。该会话当前**没有**与上方画像授权
演示或真实课堂相连；不得用它来授权真实资料，后续应接可信身份提供方。

示例（`session` 由可信服务端从返回的会话凭据恢复；身份认证步骤由应用完成）：

```python
from cogniguard.integrations.education import ProfileConsentPolicy, resolve_profile_consent

policy = ProfileConsentPolicy(
    version="school-policy-1",
    agent="teaching-agent",
    purpose="personalized_tutoring",
    fields={"mastery": "automatic", "preference": "ask"},
)
# result = run_protected_education(..., consent_policy=policy)
# 经已认证的学生通过 UI 确认后：
# resolve_profile_consent(session, result["profile_consent_requests"][0]["request_id"],
#                         verified_student_id=student_id, approve=True)
```
