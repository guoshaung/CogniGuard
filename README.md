# CogniGuard

面向多 Agent 系统的安全治理研究框架，附带教育场景参考实现、评估代码与可视化工具。

## 项目结构

```text
cogniguard/
  governance/       公共治理原语，无模型和图运行依赖
  applications/     场景用例、输入和结果组装
  workflows/        LangGraph 节点、路由与研究任务调度
  agents/           代理角色与 CGC 协调器
  providers/        外部模型客户端
  runtime/          会话、预算、统一保护入口
  observability/    安全指标与 LangSmith 追踪
  api/              HTTP 传输、路由与应用服务
  integrations/     对外场景接入和第三方桥接
protection/         三层保护的研究算法实现
experiments/        研究协议、评估代码和历史结果
visualization/      研究可视化
docs/               指南、设计与按主题归档的研究文档
```

新业务使用 `cogniguard.applications.education`；图统一从 `cogniguard.workflows` 查找。
旧 `core.langgraph_runtime`、`cogniguard.demo` 及旧代理路径保留薄兼容导入，实际实现只有一份。
算法函数、HTTP 与存储保持各自职责；使用 LangGraph 不表示把所有 Python 函数变成图节点。

## 从哪里开始

- **复用治理能力**：Python 包 `cogniguard` 提供证据封装、能力授权、上下文边界、信任、审计与生命周期决策。
- **体验教育场景**：组合学生画像最小披露（MM-FOPD）、教师资源版权控制（C²-RAG）与水印/审计（HSW-ST）。这是领域参考实现。
- **运行研究实验**：[实验导航](experiments/README.md) 按研究问题查找协议、入口与结果；历史结果保留各自评价口径。

## 安装与第一个示例

需要 Python 3.12，在仓库根目录安装。治理原语没有额外运行依赖：

```sh
python -m pip install -e .
python examples/quickstart.py
```

Windows 也可使用项目专用虚拟环境：

```powershell
py -3.12 -m venv .venv-langgraph
.\.venv-langgraph\Scripts\python.exe -m pip install -e .
.\.venv-langgraph\Scripts\python.exe examples/quickstart.py
```

公共导入从包根开始，例如 `from cogniguard import LifecycleGuard, EvidenceEnvelope`。
[治理示例](examples/quickstart.py) 在本地构造证据并评估决策，不调用模型或网络。

教育流程需要额外运行依赖：

```sh
python -m pip install -e ".[runtime]"
python examples/education.py
```

Windows 使用 `.\.venv-langgraph\Scripts\python.exe` 替代上述 `python`。
详细配置、HTTP 服务和可视化启动见 [快速开始](docs/getting-started.md)。
当前支持从源码 checkout 进行 editable 安装；完整研究工具链不作为独立 wheel 的交付承诺。

包内 CLI 使用 `python -m cogniguard`，研究 HTTP 服务使用 `python -m cogniguard.api 8000`；
Windows 的 `run.cmd`、`serve.cmd` 使用项目虚拟环境调用对应入口。

## 能力与边界

`LifecycleGuard` 根据调用方提供的领域证据、能力授权和上下文边界作出决策，记录审计与信任变化。
它不自行完成身份认证、不计算领域隐私/版权预算，也不替代模型内容检测或操作系统沙箱。

教育流程通过 `cogniguard.integrations.education` 接入 LangGraph 编排与领域算法。
`run_protected_education()` 接入服务器会话、领域预算、输出验证和强制水印验签；
底层 `ProtectionPipeline.run()` 是离线研究组合点，默认规则回答，额外接点由可信代码提供。
研究看板、可选模型/图像服务与各实验的启用条件各自独立，界面中的 demo 数据不代表实测效果。

## LangSmith 观测

LangSmith 用于查看请求和节点执行树、耗时、调用次数及失败阶段。实现位于
[observability](cogniguard/observability/README.md)，图编排与保护决策保持独立。
本项目只导出白名单数值指标和随机追踪 ID；不导出画像、题库原文、提示词或模型回答。
Token 数仅在模型提供方实际返回 usage 时记录。

```bat
run.cmd langsmith status
run.cmd langsmith smoke
```

上述命令不提交远端追踪。需要接入个人 LangSmith 项目时，按 `.env.example` 配置本地
`LANGSMITH_API_KEY`、`COGNIGUARD_LANGSMITH_PROJECT` 和显式启用开关；也可使用
`scripts/launch_langsmith.ps1 -Mode serve -Submit`，密钥通过隐藏输入提供。
配置存在与连接验证是不同状态；本次维护不会自动上传研究数据。

## 仓库导航

- [快速开始](docs/getting-started.md)：治理示例、教育示例、服务和可视化。
- [源码地图](docs/code-map.md)：公共库、领域实现、场景接入、研究工具的职责。
- [文档导航](docs/README.md)：使用指南、设计说明、研究协议和维护记录。
- [贡献与维护](CONTRIBUTING.md)：目录、接口、运行产物与验证约定。
