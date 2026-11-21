# 现行架构

日期：2026-11-15。这一页是收缩后的唯一结构。生成或修改代码前先读它。
历史目录仍留在原地，供已有导入和冻结实验使用。新代码不得把它们当成入口，也不得再平行建一套。

硕士主线是多智能体保护：几个主体各自合法拿到一点，拼起来能知道多少。
检索是教师材料库内部的读取方式，不是顶层模块。

## 一条调用链

```text
四个 Agent 只发请求
    → CGC 守门（许可、预算、合谋）
    → 资产库（画像 / 教师材料 / 已发出的文本）
    → 放行（最小字段、受控片段、带水印的讲解，附收据）
    → 核对（多个主体把合法结果拼起来）
```

公开入口是 `cogniguard.integrations.education.run_protected_education()`。
实现在 `cogniguard/applications/education/protected_access.py`。
业务图只扩展 `cogniguard/workflows/pipeline.py`。不要新增第二套 pipeline、orchestrator 或 Layer 目录。

## 现行目录

| 层 | 路径 | 可以放什么 |
|---|---|---|
| 主体 | `cogniguard/agents/roles/` | 诊断、选材、教学、评估、学生侧。只构造请求，不直接读资产库 |
| 守门 | `cogniguard/governance/`、`cogniguard/protection/cg/`、`cogniguard/runtime/gateway.py` | 许可、预算、审计、最终交付。治理原语保持标准库 |
| 编排 | `cogniguard/workflows/pipeline.py`、`cogniguard/applications/education/` | 节点和条件边。领域计算仍是普通 Python |
| 画像 | `protection/student_profile/` | MM-FOPD |
| 教师材料 | `protection/teacher_resource/` | 授权之后的查找、受控返回、暴露记账。BM25、精确单元或现有 TF-IDF 都留在这里 |
| 水印 | `protection/audit_trace/` | 文本水印。12 月的 T6 仍在 `codex/hsw-st` 工作区，不在主检出里改方法 |
| 示例 | `examples/` | 不调用真实模型的最小调用 |
| 冻结结果 | `experiments/` | 只追加新的预注册目录。已有目录不改名、不搬移 |

模型客户端只放 `cogniguard/providers/`。HTTP 只在 `cogniguard/api/` 装配，不在路由里写保护策略。

## 历史目录

这些路径继续能被旧导入找到。新功能不要写进去，也不要从这里复制出新模块。

- `protection/legacy/layers/`：原来的 `Layer1_fopd_c2rag`、`Layer2_c2rag`、`Layer2_hsw_st_minimal`。旧导入名仍可用
- `protection/supporting/`：图像水印和 NeMo 配置，不是文本水印主线
- `cogniguard/supporting/`：合成数据和闭环对照
- `cogniguard/demo/`：旧导入，实现在 `applications/` 和 `workflows/`
- `core/pipeline.py`、`core/langgraph_runtime/`、`core/governance/`。`core/access.py`、`domain.py`、`teaching.py`、`inputs.py`、`paths.py` 仍有在用的领域代码和路径常量，改动前先搜引用
- 仓库根目录里的 `DISK_INVENTORY.md`、`MIGRATION_PLAN.md`、`BACKUP_AND_RECOVERY_CHECK.md` 以及 `ADMIN_READONLY_*.txt`、`BITLOCKER_*.txt`、`D_AUTOUNLOCK_CHECK.txt`、`USER_APPROVAL_REQUIRED.md`：磁盘维护笔记，不是系统架构
- 嵌在本仓库里的 `research-sync/`：重复副本。正式早期实验在 `D:\pycharm\research-sync`

`experiments/` 里已有的 79 个目录保持原路径。预注册和论文按这些路径核对，收缩不包含改名。

## 生成代码时

1. 先决定改的是主体、守门、资产库还是放行，再选上表里的一个目录。
2. Agent 不打开教师材料全库，不自己 grep 资源原文。查找函数放在 `protection/teacher_resource/`，由守门调用。
3. 不新建 `Layer*`、`*_v2` 包、第二份 RAG 模块或第二份编排图。
4. 不把实验脚本放进 `cogniguard/`。新实验用新的 `experiments/<预注册名>/`，并先写预注册。
5. 不移动、不重命名已有 `experiments/` 目录，不改水印检测器和阈值。
6. 文件移位时同步更新仍在使用的导入。冻结结果目录除外，那些保持不动。
