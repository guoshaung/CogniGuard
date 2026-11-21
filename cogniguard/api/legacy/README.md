# 历史 FastAPI 路由

这两份 router 来自旧实现，当前 `serve.cmd` / `python -m cogniguard.api` 不会挂载它们。
它们的请求字段、会话状态与主线存在差异，移动到本目录保留现有修改和历史实现。

维护当前接口请修改 `../routes/`；统一注册入口是 `../routes/__init__.py`。
不要同时挂载这两份旧 router 和当前 HTTP 路由，也不要把这里的响应契约当成前端契约。
