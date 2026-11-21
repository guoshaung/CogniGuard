# 运行模式与服务端会话

应用用例来自 `cogniguard.applications`，实际图来自 `cogniguard.workflows`。
`gateway.py` 用 `cogniguard.observability` 关联请求、输入检查、领域预算、业务图和最终交付的
安全指标树；子图复用请求 recorder，只在请求结束后统一导出。
返回的 `observability.trace_id` 是随机 UUID，重放仍引用首次交付的追踪，不能代替会话凭据。
监控只记录阶段、耗时、有限数值和通用失败状态；不可上传任何保护对象或异常正文。
配置与明确的远端启用步骤见 [观测 README](../observability/README.md)。

`mode.py` 管理运行模式和请求级配置。`sessions.py` 用标准库 SQLite 与文件锁保存匿名会话、
服务端状态、预算和请求重放结果；默认文件为 `core.paths.RUNTIME_DIR / "sessions.sqlite3"`。

## 实际应用边界

`gateway.py` 包装自由聊天、课堂与案例的公共入口。`protection_context.py` 在请求本地传递
服务器状态、真实私值、原始资源、获准片段与成本证据，不把这些对象写入 LangGraph 通道。
教育 SDK 的在线调用使用 `cogniguard.integrations.education.run_protected_education()`，
可信服务构建 pipeline/profile/`AccessScope` 后进入相同 gateway；会话不能切换获准学生。
可选的画像字段动态同意基础版及其认证、覆盖限制见
[动态授权说明](../../docs/design/PROFILE_CONSENT.md)。
底层 `ProtectionPipeline.run()` 和示例中的纯离线研究调用仍是组合机制，不自动启用 gateway。

执行顺序：

1. 校验服务器签发的会话凭据，原子认领请求 ID，预留请求额度；重放直接取缓存结果。
2. 读取服务器状态并执行通用输入检查，随后进入原有图和 CGC/领域策略。
3. 候选检查先于 C²-RAG 受控释放；画像与版权节点登记实际上下文和成本；图像生成先扣额度。
4. 交付前检查答案及嵌套日志，移除私值、未批准原文与伪造来源。
5. 绑定最终文本水印和来源，再次检查绑定后的正文并验证 HMAC；成功后保存安全状态和结果。

`enable_nemo` 不关闭这条必经边界。这里调用本地确定性适配器，没有创建 `LLMRails` 或执行
Colang flows。设置 `COGNIGUARD_NEMO_NATIVE=on` 并安装 `nemo` 可选依赖后，网关额外
调用真实 NeMo IORails 输入/输出检查；配置或执行失败时停止，不静默退回本地检查。
可另用 `COGNIGUARD_NEMO_COLANG=on` 启用固定 Colang 对话、检索和部分执行前检查；
规则范围与未覆盖路径见 NeMo 说明。默认水印为
HSW-ST 本地语义标记及 HMAC 来源绑定，不宣称 KGW 统计水印。
另可按 [NeMo 说明](../integrations/nemo/README.md) 显式启用仅限本地服务的模型语义
自检；必须同时启用原生 NeMo，服务错误不能退回正则护栏。
签名密钥保存在 `var/secrets/text-provenance.key`，测试注入独立固定测试密钥。

客户端发送的 `history`、`session_state`、计费字段或 ablation 不是授权来源。直接 Python 调用
如需续接会话，显式传回上轮 `session_token`；不带凭据的独立调用不共享隐式全局会话。
HTTP 服务用 HttpOnly Cookie 或 Bearer 凭据续接，凭据不会出现在公开 JSON 日志中。

## 服务端会话

```python
from cogniguard.runtime.sessions import SessionStore

store = SessionStore(limits={"images": 2, "requests": 1000, "privacy": 10, "copyright": 10})
session = store.get_or_create(token_from_request_or_none)
with session.request(request_id, fingerprint=canonical_request_sha256) as request:
    if request.cached:
        result = request.result
    else:
        with session.transaction() as state:
            # Read trusted history/classroom state here, never merge client state.
            reservation = session.reserve("images", image_count, request_id)
            result = execute_once_with_server_state(state)
            state["history"] = trusted_updated_history
        request.complete(result)  # Persist JSON, then attach token to the HTTP response.
```

首次请求不带 token 时创建高熵凭据；`session.token` 仅经响应交给持有者，数据库只保存 token
哈希，`repr` 不包含 token。未知 token 被拒绝，公开 `session_id` 不能恢复或授权会话。
这是匿名会话持有凭据，不是用户身份认证系统；新建会话仍可获得新配额，全局限流、账号额度及
token 的安全传输由部署层负责。token 不应进入日志、持久化 state 或缓存结果。

## 状态与并发

`load_state()` 返回独立副本；`save_state(dict)` 只能接收服务器构建的状态。HTTP 层不得把
客户端 `history`、`classroom_state` 或计费字段直接传入。`transaction()` 在同会话文件锁下
读改写状态，成功时保存，异常时丢弃修改，支持同线程嵌套。`lock()` 可独立使用，支持多个
`SessionStore` 实例、线程和本机进程；SQLite 数据库与锁文件应位于同一主机本地文件系统，
不承诺跨主机网络文件系统锁语义。不要删除仍被进程使用的 `.sqlite3.locks/` 文件。

## 预算与幂等

- `reserve(budget, amount, request_id, key="default")` 在 SQLite 短事务中原子预留；相同
  请求、预算和 key 的相同金额只扣一次。`images`、`requests` 仅接收整数；`privacy`、
  `copyright` 等通用预算使用固定十亿分之一单位，成本向上取整。
- 所有 pending 预留立即占额度并持久化，重启不清零。`commit()` 确认成本；仅服务器确认
  未产生副作用时可调用 `release(no_side_effects=True)`。异常或进程崩溃默认保留成本，不能
  按超时自动返还已可能执行的图片/领域成本。
- 限额在新建会话时写入。构造器 `limits` 可配置新会话；重启、更换 Store 实例或客户端字段
  均不会放大已有会话额度。`budget_snapshot()` / `to_public()` 提供服务器账本证据。
- `claim_request(request_id, fingerprint=...)` 在副作用之前独立提交 pending 标记；已完成请求
  返回缓存 JSON，active、failed、请求指纹不一致均报冲突。`complete_request()` 将结果与
  该请求预留的 commit 一并提交；`fail_request()` 保守计费。请求不自动重试；崩溃后的 pending
  只能由服务器核实副作用后人工处置。
- `request()` 包装上述流程并自动预留一次 requests 成本、串行执行、处理失败。调用者必须
  先检查 `record.cached`；缓存分支不执行业务。手动使用 claim/lock 时须自行预留 requests，
  保存最终 JSON，调用 complete/fail。客户端不能控制服务端预算限额或决定成本值。

这里持久化可 JSON 表达的 CGC/领域状态；不序列化策略对象、模型或 Python 实例。真实
privacy/copyright 成本由 CGC 及领域执行证据决定，账本不根据客户端声明或固定假值推算成本。
