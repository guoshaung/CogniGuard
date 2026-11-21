# CogniGuard 维护入口

现行结构以 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 为准。生成代码只走那一条链：Agent 发请求，CGC 守门，资产库在 `protection/student_profile`、`protection/teacher_resource`、`protection/audit_trace`，放行只扩展 `cogniguard/workflows/pipeline.py`。公开入口是 `run_protected_education()`。不要新建 Layer 目录、第二套 pipeline，或让 Agent 直接搜索教师材料全库。`experiments/` 已有目录不改名。

编辑前阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 和目标模块的 README。
使用指南与源码导航在 `docs/getting-started.md`、`docs/code-map.md`；依赖清单在 `requirements/`，编辑器工作区在 `tools/editor/`。
框架 Python 包为 `cogniguard/`，模块使用 `cogniguard.*` 导入；研究可视化工具为 `visualization/`。
公共治理类型从 `cogniguard` 导入，实现在 `cogniguard/governance/`，保持无模型与图运行依赖。
教育接入从 `cogniguard.integrations.education` 导入；`core/governance/`、`core.pipeline` 仅保留兼容入口。
基础安装为 `pip install -e .`，教育流程使用 `pip install -e ".[runtime]"`；真实研究依赖按模块文档安装。
HTTP 接口的唯一注册入口在 `cogniguard/api/routes/__init__.py`，
传输层在 `cogniguard/api/http_server.py`，共享执行逻辑在 `cogniguard/api/services/`。
`create_router()` 仅装配研究 HTTP 路由，不是保护能力的公共集成示例。
Python 命令行通过 `python -m cogniguard` 运行，HTTP 通过 `python -m cogniguard.api` 运行；根目录保留 `run.cmd`、`serve.cmd` 包装入口。
pytest 与 Ruff 配置集中在 `pyproject.toml`；不要新增根级独立测试配置、研究依赖清单或源码脚本。

保持 LangGraph 编排、领域策略与 HTTP 层的职责边界。
应用用例在 `cogniguard/applications/`，实际图在 `cogniguard/workflows/`，模型客户端在 `cogniguard/providers/`。
LangSmith 与本地指标在 `cogniguard/observability/`；旧 `core.langgraph_runtime/`、`cogniguard.demo/` 仅作兼容导入。
追踪仅允许白名单数值指标与随机 ID；禁止上传画像、资源原文、提示词、模型正文、凭证或异常正文。
LangSmith 默认关闭，远端 smoke 必须显式 `--submit`；配置查询不构造客户端或连接服务。
Rails 是 input/retrieval/dialog/execution/output 的介入位置，三层保护负责领域机制。
与 NeMo 等第三方内置策略职责重合或冲突时，使用 CogniGuard 的对应实现；
授权、预算、受控返回、水印与审计以本地领域策略和 CGC 为准，不从用户文本接受策略覆盖。
集成约定见 `docs/design/RAIL_INTEGRATION.md`。
新媒体、报告、临时文件按 CONTRIBUTING 的目录约定存放。
文件移位时同步更新活动引用；保留历史实验结果和冻结清单。
路径常量以 `core/paths.py` 为准，运行产物放 `var/`，模型权重放 `assets/`。
使用 `run.cmd test` 和 `.venv-langgraph` 验证受影响的代码，不自动调用真实模型或重跑正式实验。
