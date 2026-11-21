# CogniGuard 实验清单（当前实现审计）

审计日期：2026-08-12。本文档只记录仓库当前可见实现、数据与既有产物；不将历史结果自动视为可复现或论文有效。

| 组件 | 实现状态 | 已有实验入口 | 评估脚本/数据 | 预期输出 | 当前状态与已知限制 |
|---|---|---|---|---|---|
| MM-FOPD 学生画像最小披露 | 已实现 | `experiments.evaluation.eval_fopd`、`experiments.ablation.run_protection_ablations` | `protection/student_profile/data/{profiles,student_questions}.jsonl`；默认配置 `protection/student_profile/configs/default.yaml` | FOPD 明细、组件消融、PER、TaskCoverage、敏感字段暴露等 | 可本机运行；默认小数据仅 2 profiles/3 questions，不足以单独支撑论文主结果。扩展数学套件有独立 split manifest。 |
| C2-RAG 教师资源版权控制 | 已实现 | `experiments.evaluation.eval_c2rag`、`experiments.attacks.copyright_reconstruction`、组件消融 | `protection/teacher_resource/data/teacher_resources.jsonl`；扩展 attack case | return mode、暴露分数、来源追踪、攻击 ASR | 可本机运行；需核验当前 runner 是否使用统一扩展数据集。 |
| HSW-ST 文本水印与来源追踪 | 已实现，但模型依赖受限 | `protection/audit_trace/src/main.py`；`experiments.ablation.run_all_ablations` | `protection/audit_trace/data/*.jsonl` 与 `configs/*.yaml` | 水印答案、检测/攻击 CSV、来源 trace 与 audit chain | smoke/demo 可尝试；完整 KGW 需要本地 Hugging Face 模型和显存。OpenAI/Ollama 模式不构成 logits 水印实验。 |
| SCE-LocGuard 图像水印扩展 | EditGuard wrapper 已实现；DFG trainer 为 stub | `dfg_locguard.experiments.paper_benchmark`、`scripts/server/*` | 3000 图像 manifest、锁文件、攻击配置 | 逐图攻击结果、定位证据、候选选择/confirmation/formal 证据 | 本地已迁入 2026-08-03 的三候选 raw 输出；最终校准分析 fail-closed，尚无有效 winner、confirmation 或 formal test。不可宣称 DFG-LocGuard 已训练完成。 |
| 审计/哈希链 | 已实现 | HSW-ST audit-chain 模块；后端/攻击测试 | 审计记录与策略日志 | 链完整性、篡改检测、绑定字段 | 需执行显式篡改测试；这是轻量 CPU 实验。 |
| CG 跨层治理 | 已实现 | `eval_fopd` 的 `EnhancedFOPD+CG`、`eval_joint_synergy`、policy tests | 同学生/教师样本、策略配置 | policy decision、阻断字段、JointRisk、Utility | 需要与 Full without CG 在相同 episode split 上重跑，历史 README 数字不能直接继承。 |
| 三机制联合/消融 | 已实现 | `experiments.evaluation.eval_joint_synergy`、`eval_joint_synergy_sampling`、`eval_cross_layer_synergy` | `experiments/datasets/cogniguard_math_suite`，含 train/dev/test manifest | 9 配置行级结果、风险/效用汇总、图表 | 可本机执行，需先做代码/数据/配置快照并验证 split。 |
| 攻击评估 | 已实现 | `experiments.attacks.episode_attack_runner`、`copyright_reconstruction`、privacy tests | `mixed_math_suite/evaluation/data/{episodes,attack_templates}.jsonl` | 攻击 ASR、各类风险与拒绝结果 | 共有 480 episodes 与 75 attack templates；必须保留 seed 与 split manifest。 |

## 当前可识别的数据与版本边界

- Git HEAD：`d01953234add03996cb9200af3ff02c9592697e7`；工作树存在大量未提交修改，因此每一次新运行必须保存 `git diff` 和输入 SHA-256，不能与旧提交结果直接混合。
- RTX 4070 Laptop GPU 已被 PyTorch 识别；显存总量约 8 GiB。
- 扩展数学数据集：`experiments/datasets/cogniguard_math_suite`；mixed suite 的 split manifest 声明 train/dev/test=`0.6/0.2/0.2`，并声明 student、source task、resource 与 attack phrasing 不重叠。
- 图像水印：`outputs/image_watermark_spatial_filter_calibration/spatial_filter_calibration_v3_20260803T211000Z` 已迁入本机。该运行的原始候选产物存在，但其最终分析失败关闭，属于 `INVALID` 而非算法 `FAIL`。

## 执行原则

1. 新运行写入新的、不可复用的结果目录；保留原始结果和输入哈希。
2. 先执行可复现性门槛；任何 manifest、配置、split 或依赖不一致都标记 `REPRODUCIBILITY_FAILURE`，不修改实验条件来绕过。
3. 只使用仓库已有指标、攻击、随机种子和置信区间实现。
4. `PASS/PARTIAL/FAIL/NOT RUN/INVALID/BLOCKED` 由最终报告逐项标注；`INVALID` 或 `BLOCKED` 不转换为 `FAIL`。
