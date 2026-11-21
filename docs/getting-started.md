# 快速开始

先选择目标：复用治理原语只需基础安装；教育流程与研究服务需要额外依赖。
以下命令均在仓库根目录执行，Python 版本为 3.12。

## 1. 本地治理示例

使用当前 Python 环境：

```sh
python -m pip install -e .
python examples/quickstart.py
```

Windows 项目虚拟环境：

```powershell
py -3.12 -m venv .venv-langgraph
.\.venv-langgraph\Scripts\python.exe -m pip install -e .
.\.venv-langgraph\Scripts\python.exe examples/quickstart.py
```

已有 `.venv-langgraph` 时直接使用，无需重新创建。
示例只使用本地治理原语，不下载权重、不调用模型或网络。
公共类型从 `cogniguard` 导入；实现位于 `cogniguard/governance/`。

## 2. 教育场景参考流程

安装 LangGraph 与 YAML 等运行依赖，再运行离线教育示例：

```sh
python -m pip install -e ".[runtime]"
python examples/education.py
```

Windows 对应命令：

```powershell
.\.venv-langgraph\Scripts\python.exe -m pip install -e ".[runtime]"
.\.venv-langgraph\Scripts\python.exe examples/education.py
```

教育接入入口为 `cogniguard.integrations.education`。示例在内存中构造合成画像、问题与资源，
执行授权、画像选择、受控检索、预算与规则回答。它不是通用聊天模型 API。
默认流程保持领域算法行为，附加治理与水印通过可信调用方传入的接点启用。

需要服务器会话、幂等账本和强制最终交付校验时，调用
`cogniguard.integrations.education.run_protected_education()`，由可信服务构建
pipeline、profile 与 `AccessScope`。底层 `ProtectionPipeline.run()` 和上述合成示例
保留离线组合能力，不自动代表已经进入服务器交付边界。

应用实现在 `cogniguard/applications/education/`，图定义集中于 `cogniguard/workflows/`，
请求与图观测位于 `cogniguard/observability/`。旧 demo/core 模块继续兼容导入；
具体图覆盖和任务调度边界见 [源码地图](code-map.md)。

也可通过包内 CLI 运行教育演示：

```sh
python -m cogniguard demo --json
```

Windows 包装命令继续可用：

```bat
run.cmd demo --json
run.cmd graph
```

## 3. HTTP 服务与研究可视化

研究服务使用项目完整依赖清单：

```sh
python -m pip install -r requirements.txt
python -m cogniguard.api 8000
```

Windows 固定使用 `.venv-langgraph`：

```powershell
.\.venv-langgraph\Scripts\python.exe -m pip install -r requirements.txt
.\serve.cmd 8000
```

服务监听 `http://localhost:8000`。现有业务接口见 [HTTP API](../cogniguard/api/README.md)；
它们服务于研究场景，路由工厂不是治理库的公共集成接口。
不需要额外部署 LangGraph Server。

在另一终端启动研究可视化工具：

```sh
cd visualization
npm install
npm run dev
```

浏览器地址以 Vite 的终端输出为准；开发代理将 `/api` 转发到本地 8000 端口。
看板同时包含真实执行结果和明确的演示数据，不应将展示直接作为实验结论。
真实模型、图像服务和重模型水印的配置见各模块文档，不是离线快速开始的必要条件。

## 4. 查找实验与验证改动

```bat
run.cmd experiments list
run.cmd experiments show --name teacher-security-offline
run.cmd test tests/test_public_api.py tests/test_protection_gateway.py cogniguard/tests/test_api_routing.py -q
```

`list` / `show` 只读取实验元信息；具体执行、数据与模型条件见 [实验导航](../experiments/README.md)。
真实模型实验需各入口显式允许，不会由上述浏览命令启动。
源文件定位见 [源码地图](code-map.md)，维护约定见 [CONTRIBUTING.md](../CONTRIBUTING.md)。
