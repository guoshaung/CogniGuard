# CogniGuard Research Visualization

CogniGuard 安全保护框架的研究可视化工具，使用 React 和 Vite 展示实验结果、
LangGraph 工作流、画像与资源保护、攻击案例，以及文本和图像水印防护。
看板中的演示数据与案例用于观察保护过程；正式实验定义和历史结果由仓库中的
[`experiments/`](../experiments/) 管理。

## 本地开发

先在仓库根目录启动 Python API：

```powershell
.\serve.cmd 8000
```

另开终端进入本目录：

```powershell
cd visualization
npm.cmd ci
npm.cmd run dev
```

打开 Vite 输出的本地地址。开发服务器将 `/api` 请求代理到
`http://localhost:8000`，代理配置位于 `vite.config.js`。

## 构建与展示

在本目录执行：

```powershell
npm.cmd run build
```

构建产物写入已忽略的 `visualization/dist/`。随后在仓库根目录运行
`.\serve.cmd 8000`，访问 `http://localhost:8000/`；Python 服务优先读取
`visualization/dist/`，并同时提供 API。更新界面后需要重新构建。

`npm.cmd run preview` 可单独预览构建产物；需要调用 API 时，使用上述
`serve.cmd` 同源展示方式。

## 会话与水印显示

业务请求与真实水印查询使用同源 HttpOnly 会话 Cookie。真实水印页只读取结果顶层
`session_id` / `protection.session_id`，不会使用历史 `audit_record.session_id` 授权查询。
没有最终交付记录时，预览显式使用 `scope=demo` 并标记为合成示例。

真实验证状态取自 `text_watermark` 与 `protection.watermark_verification`；没有测量值时
显示未测量，不把旧示例置信度、默认 `true` 或演示图片预览显示为已验证。
当前默认文本方案显示为本地语义标记与 HMAC 来源绑定，不冒充 KGW 统计检测。

## 代码入口

- `src/App.jsx`：研究看板与页面组织。
- `src/components/`：实验、防护、对话和水印等可视化组件。
- [`cogniguard/api/README.md`](../cogniguard/api/README.md)：Python API 契约与维护入口。
- [`cogniguard/api/routes/__init__.py`](../cogniguard/api/routes/__init__.py)：HTTP 路由注册。
- [`cogniguard/api/http_server.py`](../cogniguard/api/http_server.py)：API 传输和静态构建读取。
- [`CONTRIBUTING.md`](../CONTRIBUTING.md)：仓库目录与维护约定。
