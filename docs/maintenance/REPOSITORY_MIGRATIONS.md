# 历史目录迁移与验证记录

本文保留前两轮目录整理时的说明与验证范围，是维护快照。
当前公开 API 和职责划分以 [现行目录规范](../REPOSITORY_LAYOUT.md) 为准；
治理实现现已位于 `cogniguard/governance/`，旧 `core/governance/` 仅作兼容导出。

## 公开入口整理

治理实现迁入公开包，包根导出中立治理类型，教育流程增加显式集成入口；
增加两个合成数据示例、公共契约检查和 editable 安装元数据。
主页、快速开始、源码与实验导航同步重写，项目同步记录迁入维护目录。

本轮 179 项定向回归通过；格式整理后公共入口与教育图的 18 项复查通过。
独立临时环境安装成功；清空 `PYTHONPATH` 并从仓库外使用隔离模式运行治理示例，
得到预期的 allow/refuse/quarantine 决策。主虚拟环境依赖未修改，未进行真实模型推理。
公开包、示例与兼容导出的 Ruff 检查和格式检查通过。

## 以下为此前目录整理快照

根目录按源码、数据、资产、运行文件和工具划分。应用入口仍为 `run.cmd`、`serve.cmd`，
测试入口为 `run.cmd test`。统一路径定义在 `core/paths.py`。

```text
CogniGuard/
├─ cogniguard/               安全保护框架 Python 包：Agent、治理适配、工作流与 API
├─ visualization/            研究可视化工具：React 看板与实验展示
├─ core/                     共享治理与 LangGraph 执行框架
├─ protection/               画像、版权、文本/图像水印
│  └─ image_watermark/       原 DFG/SCE-LocGuard 服务与评估
├─ third_party/editguard/    原 code/，有名称的图像水印实现
├─ configs/                  第一方配置
├─ data/                     输入数据与 benchmark 快照
│  └─ benchmarks/            原根级 datasets/
├─ assets/                   本地模型与 checkpoint，不进入 Git
│  ├─ models/
│  └─ checkpoints/
├─ var/                      本地运行数据，不进入 Git
│  ├─ logs/
│  ├─ outputs/
│  ├─ results/
│  ├─ cache/
│  └─ tmp/
├─ experiments/              实验定义、评估与版本化结果
├─ deploy/                   部署说明、环境示例与资产清单
├─ scripts/                  启动、数据准备与维护脚本
├─ tools/                    独立开发及视频工程
├─ artifacts/                交付、报告预览、动画素材
└─ docs/                     项目文档与报告
```

## 路径迁移与兼容

- 原应用实现提升为 `cogniguard/` Python 包，导入统一使用 `cogniguard.*`。
- 原前端目录改为 `visualization/`，沿用 Vite/React 构建与运行命令。
- `code/` → `third_party/editguard/`。
- `dfg_locguard/` → `protection/supporting/image_watermark/`；Python 模块名改为 `protection.supporting.image_watermark.*`。
- 根级 `logs/`、`outputs/`、`results/` → `var/` 下的同名目录。
- 根级 `models/`、`checkpoints/` → `assets/` 下的同名目录。
- 根级 `datasets/` → `data/benchmarks/`。
- 水印模块的旧 `api_jobs/` → `var/outputs/sce_locguard_api_jobs/`。
- 原根级 pytest、Ruff 和 Python 缓存迁入 `var/cache/`；后续由启动器/配置统一定位。

目录为实际迁移，根目录不保留旧文件夹或兼容链接。
`experiments/results/` 属于实验内部的版本化结果目录，保持其内部结构。
历史报告、结果与冻结快照保留原记录，通过 `resolve_project_path` 在服务读取边界转换旧路径。
统一实验调度器也接受历史 `dfg_locguard.*`、`code.*` 名称，并转向新模块。

迁移会改变源码路径与指纹。新的正式实验应生成新的源码/配置冻结记录，
不能修改已发表结果的原始锁定清单来消除路径差异。

## Python 模块边界

从仓库根目录运行时，框架 API 可使用 `from cogniguard.api.routes import create_router`，
Agent 模块使用 `cogniguard.agents.*`，课堂工作流使用 `cogniguard.demo.*`。
共享图运行时仍为 `core.langgraph_runtime.*`，领域算法仍为 `protection.*`。
这次调整命名和存放位置，算法、模型能力及历史评估口径保持原有定义。

## 运行与维护

```bat
run.cmd demo --json
run.cmd experiments list
run.cmd test cogniguard/tests/test_api_routing.py core/tests/test_paths.py -q
serve.cmd 8000
```

水印 API 的启动模块为 `protection.supporting.image_watermark.api.server:app`，
服务脚本和部署配置已同步修改。已有进程需要重新启动后使用新路径。
若手动调用 Python，应设置 `PYTHONPYCACHEPREFIX=<仓库>/var/cache/python`。

## 框架命名迁移验证

`cogniguard/` 包、路径兼容、API、治理、工作流、实验目录与工具调度的 170 项定向检查通过。
CG 策略与历史工具名称另行复查 19 项通过；`visualization/` 的生产构建成功。
历史模块名 `backend.app.*` 仅在工具调度器中转换为 `cogniguard.*`，不建立旧 Python 包。

## 首轮目录整理验证范围（框架包更名前）

- HTTP、请求上下文及课堂工作流：49 项检查通过。
- 路径兼容、工具调度、水印服务和 benchmark：177 项检查通过；后续配置与 TrustMark runner 复查 130 项通过。
- 部署与启动路径定向复查通过；12 个 Linux 启动脚本通过 Bash 语法检查。
- 134 个迁移 Python 文件通过语法解析；3 个 checkpoint 的大小与 SHA-256 均匹配原资产清单。
- `run.cmd demo --json`、`run.cmd experiments list` 启动成功；新路径与 API 层 Ruff 检查通过。

以上为定向回归，未执行训练、模型下载或真实模型推理。主虚拟环境未安装 Torch，
其 FP16 测试未运行；额外的全量校准检查因耗时停止，不计入通过结果。
