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

## 多主体放行

几个主体各自只拿到这次放行的单元。合谋检查回答的是：已有回执再加上这次，会不会让不超过 `k` 个主体凑齐某份材料的一个见证集。这条路径记于 2026-11-23，领域算法仍留在原来的目录。

```text
访问登记（组织、授权、策略版本）
    → 领域准备候选
    → ReleaseGate.select_and_reserve（授权、见证、剩余距离定价，只预留选中单元）
    → 交付时 commit；未交付或授权失效则 cancel
    → 回执进入 DisclosureStore，供下一次合谋检查
```

见证集在 `cogniguard/governance/targets.py`。单元是 `(resource_id, unit_id)`。`cogniguard/governance/reconstruction.py` 的 `check_release` 判断会不会凑齐，`residual_distance` 给出还差多少。差得越少，价格越高。

`cogniguard/governance/access_policy.py` 的 `is_authorized` 要求代行组织是该主体加入的组织，并且等于资源所属组织。主体是所有者，或持有同一策略版本、未过期、目的相符的授权。同一组织的成员身份本身不够。

回执类型在 `cogniguard/governance/disclosure.py`，MySQL 日志在 `cogniguard/runtime/disclosure_store.py`。库只存内容哈希。`reserved` 和 `delivered` 都算已经持有，`cancelled` 不算。

闸门是 `cogniguard/runtime/release_gate.py`，不认识教育或代码领域。调用方提交若干候选，每个候选有名字、要透露的单元和效用。`select_and_reserve` 在同一把锁里完成：

1. 丢掉未授权的候选。
2. 丢掉会凑齐见证的候选。
3. 对其余候选按 `效用 − λ × Σ 价值 × exp(−衰减 × 剩余距离)` 打分。分相同则单元更少者优先，再按名字。
4. 只为选中的候选预留回执。没有安全候选则不写回执。

`commit` 在交付前再查一次策略版本和授权。任一单元对不上就取消全部预留。教育在线交付走 `cogniguard/runtime/gateway.py`：整体拦截则取消；提交失败则不把原文交给学生。代码场景不经过 gateway。

### 教育

`cogniguard/workflows/pipeline.py` 只在同时配了目标登记、`coalition_k` 和回执库时才做上面的选择。C²-RAG 先定一种回应方式。闸门比较两个候选：这种方式，以及空的拒绝。方式是否把该单元记为已透露，看 `c2rag.disclosure_rule`；效用看 `c2rag.candidate_utility`。默认除 `refuse` 外都算透露；效用为 quote 1.0、summary 0.8、outline 0.6、variant 0.6、refuse 0.0。这些是待实验校准的默认值，写在 `configs/focused.yaml`。`price_lambda` 和 `price_decay` 默认都是 1.0。选中拒绝时退回这次暴露并按拒绝记账，不写该单元的回执。未启用这三项时，仍按原来的单次预留。`coalition_check` 只记目标数、违规数、放行或拒绝、选中的名字和通过的候选数。

### 代码

`cogniguard/applications/code/` 用标准库把一个 Python 文件拆成顶层函数、类和常量。函数的签名和文档字符串是公开摘要，不算透露单元。`show_function` 的三个候选是完整函数体（效用 1.0）、公开摘要（效用 0.4）和拒绝（效用 0）。`explain_api` 只有公开摘要，不写回执。旁挂 JSON 用单元名列出见证集。`CodeAssistant` 选出候选后直接 `commit`，返回值就是交付。示例是 `examples/code_domain_demo.py`。

`TeacherResource` 的 `owner_principal_id`、`org_id` 只是资源元数据，不能作为授权依据；授权一律以后端构建的 `AssetOwnership` 和 `AccessRegistry` 为准。

MySQL 是可选依赖，用 `pip install -e ".[mysql]"` 安装，连接参数从 `COGNIGUARD_MYSQL_*` 环境变量读取；没有 MySQL 时，披露相关的测试会跳过，所以汇报测试结果时要同时报告跳过的数量。

## 保密模型

本系统保护的是**未公开内容的保密性**，不是著作权：著作权只保护表达，换一种说法就不算侵权；保密保护的是信息本身，换一种说法推出了同一个取值，仍然算泄露。根据公开知识独立推出的内容不算泄露。法律依据中的具体条文和判例待核实。

受保护对象统一为**离散秘密**，教师资产和学生属性用同一套类型、同一个闸门：

| 概念 | 代码位置 | 说明 |
|---|---|---|
| 离散秘密 | `cogniguard/governance/targets.py` 的 `ProtectedTarget` | `kind` 为 `teaching_asset` 或 `student_attribute`；`domain_size` 是候选取值个数；`value_commitment` 是 HMAC-SHA256 承诺（`commit_value`、`verify_commitment`）。真实取值和盐不进入目标对象 |
| 推导集 | 同上，`witness_sets` | 凑齐其中任一个单元集合，就能把秘密推到阈值以上 |
| 计量器 | 接口在 `cogniguard/governance/meter.py`，实现在 `cogniguard/runtime/meters.py` | 把非结构化文本翻译成"透露了哪些单元"。`LexicalMeter` 是词面基线；`CalibratedMeter` 等校准实验完成后再实现。原文只放在 `UnitContentStore`，不写日志，也不进回执 |
| 学生属性 | `protection/student_profile/src/fopd/secret_targets.py` 的 `attribute_target` | 单元是画像记录，推导集是"凑齐就能推出属性"的记录组合 |

计量器只许多算、不许漏算。闸门的候选可以带 `text` 和 `meter_scope`：配置了计量器时，声明的单元与计量器判出的单元取并集；计量在加锁之前完成；计量出错时，`evaluate_and_reserve` 返回 `meter_error`，`select_and_reserve` 跳过该候选。evidence 只记计量方法名和单元数量。

教育流程（`LangGraphProtectionPipeline(meter=...)`）在得到 C²-RAG 的回应后计量一次，用判出的单元取代 `disclosure_rule`，作为显式声明的单元交给闸门（不再让闸门重复计量）。计量失败时，在扣预算和登记 `approved_chunks` 之前就改为拒绝。不配置计量器时，行为和以前完全一致。

`TeacherResource.confidentiality_level` 是 `copyright_level` 的只读别名，新代码用前者。

形式化定义（g-泄露、相对先验的增量泄露、推导集与引理、保证成立所需的四条假设）不在本文件，以随论文发布的定义为准。

## 现行目录

| 层 | 路径 | 可以放什么 |
|---|---|---|
| 主体 | `cogniguard/agents/roles/`、`cogniguard/governance/principals.py` | 诊断、选材、教学、评估、学生侧，以及组织成员。角色只构造请求，不直接读资产库 |
| 守门 | `cogniguard/governance/`、`cogniguard/protection/cg/`、`cogniguard/runtime/gateway.py`、`cogniguard/runtime/release_gate.py` | 许可、预算、见证、距离定价、回执和最终交付。治理原语保持标准库 |
| 编排 | `cogniguard/workflows/pipeline.py`、`cogniguard/applications/education/` | 节点和条件边。启用合谋检查时只向闸门提交候选 |
| 代码场景 | `cogniguard/applications/code/` | 函数体、公开摘要或拒绝。不经过教育 gateway |
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
