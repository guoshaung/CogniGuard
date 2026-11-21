# 教育流程图

本目录只定义 LangGraph 状态、节点、边、调用上下文与编译入口。

- `conversation.py`：输入检查、后端选择、生成和输出检查的条件分支。
- `classroom.py`：课堂初始化、学习/攻击回合分支。
- `classroom_learning.py`：学习回合内部阶段推进。
- `case_study.py`：案例加载、受保护代理、来源绑定和结果组装。
- `protected_turn.py`：诊断、检索、教学、评估、审计的多代理回合。
- `research.py`：离线三层机制研究回合。

业务服务来自 `cogniguard.applications.education` 和 `cogniguard.agents`，
观测适配来自 `cogniguard.observability.graphs`。图通道只放阶段与计量标记；
画像、资源原文、模型提示和运行对象留在 call-local context。
原生 LangSmith 图内容自动采集保持关闭，只有白名单指标进入观测出口。
