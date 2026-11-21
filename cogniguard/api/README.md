# HTTP API 维护入口

启动使用 `python -m cogniguard.api 8000`，Windows 可用 `serve.cmd 8000`。
模块入口在 `__main__.py`；当前服务使用标准库 HTTPServer，不需要部署 LangGraph Server。

## 代码怎么找

- `http_server.py`：HTTP 传输、CORS、JSON、NDJSON、静态文件和统一 400/404/405/500 响应。
- `routing.py`：`Route`、`Endpoint` 协议、`Router` 注册表和请求 URL 解析。
- `routes/__init__.py`：全部 **29 个**现有 API 的唯一注册入口。
- `routes/dialogue.py`：自由聊天与课堂回合，调用现有 LangGraph 工作流。
- `routes/cases.py`：案例清单、GET/POST 运行、NDJSON 运行事件。
- `routes/dashboard.py`：状态、看板、工作流、画像、资源、通信和比较展示。
- `routes/scenarios.py`：episode 与攻击模板清单。
- `routes/attacks.py`：攻击案例、历史结果、演示攻击与批量记录。
- `routes/watermarks.py`：水印检测、攻击、审计与图像/制品下载。
- `services/case_execution.py`：三种运行接口共享的执行、日志和结果组装。
- `services/history.py`、`services/watermarks.py`：历史指标和水印会话服务。
- `services/attacks.py`：攻击历史读取与原有演示记录逻辑，不启动正式基准。
- `dependencies.py`：绑定现有业务组件，并集中保留可选依赖的导入降级行为。
- `demo_data.py`：原有演示案例，不作为真实安全实验成绩。
- `dashboard_data.py`：现有前端数据投影。
- `legacy/`：未挂载的历史 FastAPI router，字段契约不等同于当前接口。

## 使用的设计方式

HTTP 层采用**注册表 + 函数策略分发**。每个处理函数实现 `Endpoint` 协议，
`Router` 根据 method 和 path 选择它。精确匹配优先，文件下载采用最长前缀匹配，
重复注册在启动时抛错。新增接口时在相应模块定义处理函数，再加入该模块的 `ROUTES`，
不向 `__main__.py` 添加路径分支。

API 处理函数负责解析请求和发送响应；需要复用的执行逻辑放 `services/`。
LangGraph 继续负责流程编排，CG、画像、版权与水印领域模块继续负责业务策略。
正式业务入口位于 `cogniguard.applications.education`，图位于 `cogniguard.workflows`。
`GET /api/runtime/status` 的 `observability` 字段提供 LangSmith 的安全配置状态，
不创建 SDK Client、不回显密钥或 endpoint；`configured` 不代表已经连接或提交。
这次目录整理没有引入新的安全判别算法。

运行案例通过 `runtime.mode.runtime_options` 的 ContextVar 设置当前请求模式，
正常结束、异常和嵌套调用都会恢复设置，不再修改进程级 `os.environ`。
新建原生后台线程时要显式传播 context，不能假定任意第三方线程自动继承请求配置。

## 常用接口

- `GET /api/runtime/status`：当前默认运行模式。
- `POST /api/dialogue/free-chat`：`message`。`history`、`teaching_image_count` 仅保留兼容接收，
  不会覆盖服务器历史或图片预算。
- `POST /api/dialogue/next-round`：`case_index`、`student_message`、`turn_kind` 等业务输入；
  轮次与课堂状态由服务器恢复。客户端 `session_state`、`round_number`、`target_mastery`、
  `cg_ablation` 不可覆盖服务器策略。切换案例会重建该会话的课堂状态，保留已用预算。
- `GET /api/cases`、`GET /api/scenario/episodes`：案例/episode 清单。
- `GET /api/run-case?index=0`、`POST /api/run-case`：运行受保护示例。
- `POST /api/run-case/stream`：相同案例执行，响应为 `application/x-ndjson`。
- `GET /api/watermark/rounds`、`POST /api/watermark/detect`：水印回合和文本检测。
- `POST /api/watermark/image-detect`、`POST /api/watermark/image-attack`：图像服务接口。

运行案例的请求可带 `runtime_mode` 与 `enable_nemo`；GET 使用 `index`，POST 使用
`case_index`。开关接受 JSON boolean 或 true/false、yes/no、on/off、1/0，非法值返回 400。
课堂与自由聊天使用 `.env` 的默认模式，不会继承另一个案例请求的临时模式。
未知 API 返回 JSON 404，已知路径的方法不匹配返回 405，格式错误的 JSON 返回 400。

## 会话与最终交付

三个业务入口统一经过 `runtime/gateway.py`；HTTP 层保留传输职责。五个位置的本地接入为
输入检查、候选资源隔离、服务器会话状态、执行前预算和最终输出校验。它们不执行 NeMo
Colang flows，`enable_nemo=false` 也不能关闭强制会话、领域预算和最终交付检查。
服务端另可设置 `COGNIGUARD_NEMO_NATIVE=on` 启用原生 NeMo IORails 基础输入/输出
检查，独立于客户端参数；配置详见 [NeMo 接入说明](../integrations/nemo/README.md)。
首次交付的执行状态可查看响应中的 `protection.nemo_base_backend`。缓存重放会用当前
原生护栏重新检查，但保留首次交付的原始响应与状态；运行模式查询中的
`nemo_native_configured` 只表示服务端配置，不能证明某次请求已经执行。

- 首次请求创建匿名会话，响应设置 `cgc_session` HttpOnly、SameSite=Lax Cookie，路径为
  `/api`；后续请求携带该 Cookie。程序客户端也可发送 `Authorization: Bearer <token>`。
  Cookie 与 Bearer 不一致、空凭据或未知 token 都被拒绝。公开 `session_id` 不能代替凭据。
- 用 `Idempotency-Key` 标识一次业务请求。相同会话、相同业务参数的已完成请求返回缓存，
  不重复生成图片或扣账；处理中、失败待核实及更改参数复用同 ID 返回冲突。
- 无效凭据返回 401，请求冲突/会话忙返回 409，额度耗尽返回 429。错误响应不包含原始模型
  输出、会话凭据或 Python traceback。公开 JSON 和 NDJSON 移除 `session_token`。
- 答案、消息和嵌套诊断字段都通过输出校验。最终正文经过 HSW-ST 本地语义水印和 HMAC
  来源绑定后再校验、验签；必需水印/来源验证失败不会交付原答案。语义水印不等于 KGW。

匿名会话不是用户认证；更换新会话仍能获得新配额。账号级/全局额度、网络限流及 TLS
部署需要由部署层提供，当前本机 SQLite 账本不冒充这些能力。详细账本语义见
[runtime README](../runtime/README.md)。

回归检查：

```powershell
run.cmd test tests/test_protection_gateway.py tests/test_server_sessions.py tests/test_classroom_protection_context.py cogniguard/tests/test_frontend_api_endpoints.py cogniguard/tests/test_api_routing.py -q
```
