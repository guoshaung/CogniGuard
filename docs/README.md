# 文档导航

先读 [快速开始](getting-started.md)，找实现时使用 [源码地图](code-map.md)。
当前入口与版本化研究报告分开维护；旧结果不能代表新入口的默认行为。

## 使用与接入

- [治理最小示例](../examples/quickstart.py)：无需模型与网络的治理原语。
- [教育接入](../cogniguard/integrations/education.py)：可信服务构建访问范围后调用公开教育入口。
- [HTTP API](../cogniguard/api/README.md)：研究接口、服务端会话与请求字段。
- [研究可视化](../visualization/README.md)：真实交付、合成预览与水印证据的显示约定。
- [实验导航](../experiments/README.md)：实验协议、执行条件和历史版本。

## 架构与执行

- [现行架构](ARCHITECTURE.md)：收缩后的唯一调用链，以及生成代码时允许写入的目录。
- [目录职责](REPOSITORY_LAYOUT.md)：应用、工作流、领域算法和运行产物的位置。
- [源码地图与 LangGraph 覆盖](code-map.md)：真实业务图、任务调度图及非图代码的边界。
- [Rails 与三层保护](design/RAIL_INTEGRATION.md)：接入位置、策略所有权和交付检查。
- [领域职责](design/COGNIGUARD_CORE_RESPONSIBILITY_SPLIT.md)：既有治理与领域机制的拆分记录。
- [教师 DAG](design/TEACHER_DAG.md)：教师组合和交接约束。
- [输入边界](design/INJECTION_BOUNDARIES.md)：访问范围和不可信文本的约束。
- [实验目录与调度等级](design/EXPERIMENT_CATALOG.md)：发现范围、风险门与产物约定。

## 研究资料

- [研究索引](research/README.md)：按 CGC、画像、检索和基准查找版本化记录。
- [CGC 与安全治理](research/cgc/)：算法规范、基线、试验和判别器记录。
- [画像保护](research/profile/)：MM-FOPD 指标口径与补充实验。
- [受控检索](research/retrieval/)：C²-RAG 数据、基线、开发试验及审查。
- [基准与数据](research/benchmarks/)：外部攻击、数据适配与领域基准记录。
- [专题实验说明](experiments/)；[独立报告](reports/)；[旧归档](archive/)。

水印专题与包含水印结果的综合报告本轮保持原位，避免打断独立水印研究任务。
相关入口包括 [水印集成说明](水印集成说明.md)、
[图像水印接入说明](图像水印论文代码接入说明.md) 和
[TrustMark 预检](TrustMark官方基线适配与服务器预检.md)。
查验研究结论仍需同时核对数据、源码版本、配置、评分协议与冻结清单。

## 维护记录

- [贡献与维护](../CONTRIBUTING.md)：维护规则、接口边界与验证方式。
- [目录迁移记录](maintenance/REPOSITORY_MIGRATIONS.md)：此前目录调整与定向验证。
- [项目同步记录](maintenance/PROJECT_SYNC.md)：阶段性项目检查。
- [LangGraph 迁移状态](maintenance/LANGGRAPH_MIGRATION_STATUS.md)：历史验收范围与限制。
- [LangGraph 重构记录](maintenance/LANGGRAPH_REFACTOR.md)：此前的执行框架设计。
