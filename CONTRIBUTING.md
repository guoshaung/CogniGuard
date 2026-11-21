# 仓库维护约定

先看 [快速开始](docs/getting-started.md) 选择治理库、教育场景或研究服务，查看 HTTP 接口时直接进入
[cogniguard/api/README.md](cogniguard/api/README.md)。

## 公共接口与依赖边界

- 公共治理类型从 `cogniguard` 导入；实现集中在 `cogniguard/governance/`，保持不依赖模型、LangGraph 与领域数据。
- 教育场景从 `cogniguard.integrations.education` 导入；LangGraph 与 YAML 等依赖属于 `runtime` 可选依赖组。
- 新治理示例放 `examples/quickstart.py`，教育参考流程示例放 `examples/education.py`；二者默认均不调用真实模型。
- `cogniguard/api/` 是研究 HTTP 服务，`create_router()` 是内部路由组合点，不作为保护库的公共调用示例。
- `core/governance/` 与 `core.pipeline` 保留显式兼容导出；新增调用使用公开包路径，避免继续扩大旧入口。
- 支持源码 checkout 的 `python -m pip install -e .`；教育流程使用 `python -m pip install -e ".[runtime]"`。
  完整研究依赖按 `requirements.txt` 及模块说明安装，不将全部实验工具承诺为独立 wheel 能力。

## 新文件放哪里

生成代码前先读 [现行架构](docs/ARCHITECTURE.md)。新保护逻辑只进入该页的现行列。
`protection/Layer*`、`cogniguard/demo/`、`core/pipeline.py` 是历史入口。

Rails 与三层保护的接入、冲突处理和当前覆盖范围见
[接入约定](docs/design/RAIL_INTEGRATION.md)。重合的第三方内置策略由 CogniGuard 领域实现替换，
非重合的通用检查独立配置；不得把领域 `allow` 当作跳过所有其他检查的通行证。

- `cogniguard/`：安全保护框架 Python 包；模块使用 `cogniguard.*` 导入。
- `cogniguard/governance/`：中立治理原语；`cogniguard/integrations/`：领域参考接入。
- `examples/`：可从源码安装运行的最小示例。
- `visualization/`：研究可视化工具，包含 React 看板与实验展示。
- `cogniguard/api/`：HTTP 路由、参数解析与应用服务。
- `cogniguard/applications/`：场景用例、可信业务输入与结果组装。
- `cogniguard/workflows/`：实际 LangGraph 节点、条件边、教师 DAG 和研究任务调度。
- `cogniguard/agents/`：代理角色、受保护协调器与 CGC；不再放图实现或模型 HTTP 客户端。
- `cogniguard/providers/`：外部模型客户端。
- `cogniguard/observability/`：本地阶段计量与显式启用的安全 LangSmith 导出。
- `core/langgraph_runtime/`、`cogniguard/demo/`：旧导入兼容，新增实现使用上面的正式路径。
- `protection/`：画像、资源版权、水印的领域算法。
- `configs/`：第一方运行配置。
- `requirements/`：`runtime.txt`、`runtime-lock.txt`、`research.txt`、`benchmarks.txt` 等依赖清单；根 `requirements.txt` 保留为常用安装入口。
- `experiments/`：实验定义、数据构建、评估与版本化历史结果。
- `scripts/`：数据准备和服务运行脚本；`deploy/` 放对应部署资料。
- `tools/`：独立开发工具和演示工程，例如 `tools/video/`。
- `artifacts/`：交付包、校验报告、文档预览、动画素材等非源码产物。
- `docs/reports/`：独立书面报告；`docs/` 放接口、架构和实验说明。
- `docs/maintenance/`：阶段性项目同步与维护记录，不充当快速开始。
- `docs/getting-started.md`、`docs/code-map.md`：快速开始与源码导航；编辑器工作区放 `tools/editor/`。
- `var/logs/`、`var/outputs/`、`var/results/`：运行日志、服务输出和旧通用结果。
- `var/cache/`、`var/tmp/`：Python、pytest、Ruff 缓存和测试临时文件。
- `assets/models/`、`assets/checkpoints/`：不进入 Git 的模型权重、下载缓存和 checkpoint。
- `third_party/editguard/`：EditGuard 图像水印源码及已有本地扩展。
- `protection/supporting/image_watermark/`：原 DFG/SCE-LocGuard 的图像水印服务和评估集成。
- `data/benchmarks/`：独立 benchmark 数据快照；`.tmp/` 仅保留本地维护工作文件。

路径统一由 `core/paths.py` 定义。新增第一方代码应导入相应目录常量，避免自行拼接根目录下的
`logs`、`outputs`、`models` 等旧名称。历史报告中的旧项目路径在服务读取边界转换，
不建立根目录兼容软链接。迁移对照见 [目录布局](docs/REPOSITORY_LAYOUT.md)。

## 维护方式

1. 根目录保留项目主页、许可、维护约定、`pyproject.toml`、常用依赖入口和 Windows 启动器。
   Python CLI 与 HTTP 入口随包维护，通过 `python -m cogniguard`、`python -m cogniguard.api` 运行；详细指南、依赖清单和编辑器文件放各自目录。
2. API 采用注册表和可替换处理函数；HTTP 层不复制 CG 策略，也不编排教学节点。
3. 相同业务被多个接口调用时，抽到 `api/services/`；请求选项通过上下文传递，不修改全局环境。
4. 新增共享抽象需要真实的复用点；避免为每个接口建立只有一个方法的类。
5. 移动文件时同步修改实际导入、脚本路径、README 和 workspace 配置；历史结果及冻结清单保留原记录。
6. 沿用 `run.cmd` / `serve.cmd` 和 `.venv-langgraph`。使用 `run.cmd test <测试路径> -q` 验证受影响接口和图；启动器统一设置 Python 缓存位置。
7. 变更公共接口前核对 `visualization/` 中的调用；保留兼容入口时要写明正式实现在哪里。
8. 模块名使用 `snake_case`，按职责命名；应用用例、图、模型客户端与观测分别放在对应包。
   不在新模块使用 `demo`、`upgrade`、`v2` 区分同一职责的活动实现；版本研究放 `experiments/`。
   旧路径兼容必须指向同一模块/对象，不能复制一份代码继续维护。
9. LangSmith 只导出白名单数值指标和随机追踪 ID。关闭原生输入输出自动采集，禁止把画像、
   题库、提示词、模型正文、会话 token/API key 或异常正文放进追踪；远端观测故障不能改写保护结果。

历史未挂载 API 归入 `cogniguard/api/legacy/`，不从正式路由注册表导入。
第三方依赖目录、构建目录、模型权重和本地密钥不进入 Git。

代码格式与基础静态检查由 `pyproject.toml` 中的 Ruff 配置统一，使用 Python 3.12、
100 字符行宽和导入排序。当前优先维护本次整理的 API 层：

```powershell
ruff check cogniguard/api/routes cogniguard/api/services cogniguard/api/routing.py cogniguard/api/http_server.py cogniguard/api/dependencies.py cogniguard/api/demo_data.py cogniguard/tests/test_api_routing.py cogniguard/api/__main__.py cogniguard/cli.py
ruff format --check cogniguard/api/routes cogniguard/api/services cogniguard/api/routing.py cogniguard/api/http_server.py cogniguard/api/dependencies.py cogniguard/api/demo_data.py cogniguard/tests/test_api_routing.py cogniguard/api/__main__.py cogniguard/cli.py
```

旧研究代码尚未统一 lint；维护时按改动范围逐步收敛，不为通过全仓 lint 改写冻结实验源码。
