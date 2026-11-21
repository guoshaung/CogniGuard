# 仓库职责与目录

现行结构见 [架构](ARCHITECTURE.md)。下面的树包含仍留在原地的历史目录。
首次使用看 [快速开始](getting-started.md)，定位代码看 [源码地图](code-map.md)。
公开治理接口为 `cogniguard`，教育接入为 `cogniguard.integrations.education`。
新代码的入口是 `run_protected_education()`，资产算法只扩展 `protection/student_profile/`、`protection/teacher_resource/`、`protection/audit_trace/`。

## 源码按职责存放

```text
CogniGuard/
├─ cogniguard/
│  ├─ governance/            标准库治理原语
│  ├─ integrations/          公开场景接入
│  ├─ applications/education/ 课堂、对话、案例等应用逻辑
│  ├─ agents/                Agent 角色与两类显式 orchestrator
│  ├─ providers/             模型供应方适配
│  ├─ workflows/             业务图、教师 DAG、实验与工具调度图
│  ├─ observability/          请求/图观测、安全遥测与可选 LangSmith
│  ├─ runtime/               服务器会话、预算和最终交付边界
│  ├─ api/                   HTTP 传输、路由与研究服务
│  └─ demo/                  历史应用导入兼容
├─ core/                    真实教育领域服务及历史导入兼容
├─ protection/              画像、版权、文本/图像水印算法
├─ third_party/             外部算法与明确来源的本地扩展
├─ examples/                合成最小示例
└─ tests/                   公开接口、交付边界与目录契约
```

应用决定调用方式，workflows 明确节点与路由，领域算法决定实际释放和成本，治理层消费证据。
观测实现单独维护；HTTP 和算法函数不因目录迁移变成图。准确图覆盖见 [源码地图](code-map.md)。
`core/access.py`、`domain.py`、`teaching.py`、`inputs.py` 仍有真实领域实现；
旧 `core/langgraph_runtime/` 与应用旧模块保留兼容导入，不能据目录名字断言其中所有文件都仅是空壳。

## 文档、研究和工具

```text
docs/
├─ getting-started.md       使用入口
├─ code-map.md              源码与执行覆盖
├─ REPOSITORY_LAYOUT.md     目录职责
├─ design/                 当前接入约定与设计说明
├─ research/
│  ├─ cgc/                  治理规范、基线、开发试验与判别器记录
│  ├─ profile/              画像指标与补充实验
│  ├─ retrieval/            检索数据、基线与开发记录
│  └─ benchmarks/           基准和数据适配记录
├─ maintenance/            阶段性迁移、同步与维护记录
├─ experiments/            既有专题实验说明
├─ reports/                独立书面报告
└─ archive/                旧阶段归档
```

水印专题与含水印结果的综合报告本轮保持原位，以免影响独立进行的水印任务。
研究文档的版本、结论和冻结记录未因归档重算；索引见 [文档首页](README.md)。

- `experiments/`：实验协议、评估、数据准备和版本化结果。
- `configs/`、`data/`：配置与输入数据；`requirements/`：运行、版本锁、研究与基准依赖。
- `visualization/`：可选研究界面；`scripts/`、`deploy/`：运行与部署。
- `tools/`：独立开发工程和编辑器工作区；`artifacts/`：交付包、媒体与文档预览。

## 本地运行与资产

- `var/logs/`、`var/outputs/`、`var/results/`：应用日志与通用产物。
- `var/cache/`、`var/tmp/`：缓存和临时文件；`.tmp/`：本地维护工作文件。
- `assets/models/`、`assets/checkpoints/`：模型资产，独立于源码维护。

路径常量及历史路径转换由 `core/paths.py` 提供。历史实验自己的结果和冻结清单按原结构保留。
此前迁移过程见 [维护记录](maintenance/REPOSITORY_MIGRATIONS.md)。
