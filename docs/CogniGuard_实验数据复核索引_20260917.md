# CogniGuard 实验数据复核索引

> 本文件供本人答疑和现场复核使用，不属于组会展示正文。所有路径均相对于项目根目录 `D:\pycharm\CogniGuard`。

## 1. 最快打开的六组结果

| 实验 | 先看汇总 | 再看逐样本数据 |
|---|---|---|
| MM-FOPD | `experiments/results/mmfopd_v3_development_compressed_card/summary.csv` | `experiments/results/mmfopd_v3_development_compressed_card/rows.csv` |
| C²-RAG | `experiments/cａｕｃ2rag_v3/results/paired_differentiated_budget040/final_development_table.csv` | `experiments/c2rag_v3/results/paired_differentiated_budget040/raw_results.jsonl` |
| HSW-ST | `experiments/results/text_watermark_selective12/run_20260906_221459_352036/metrics_summary.csv` | 同目录下的 `metrics_per_sample.csv` 和 `attack_results.csv` |
| JailbreakBench | `experiments/results/cg_jailbreakbench/summary.json` | `experiments/results/cg_jailbreakbench/summary.csv` |
| BIPIA | `experiments/results/cg_bipia/summary.json` | 同一 JSON 的 `rows` 数组 |
| XSTest | `experiments/results/cg_xstest/summary.json` | 同一 JSON 的 `rows` 数组 |

## 2. MM-FOPD 数据

### 输入数据

- 扩充后的 270 个合成学生画像：`experiments/datasets/mmfopd_v3_suite/mixed_math_suite/student_profile/data_expanded/profiles.jsonl`
- 720 个任务及划分：`experiments/datasets/mmfopd_v3_suite/mixed_math_suite/student_profile/data_expanded/student_questions.jsonl`
- 纵向学习事件：`experiments/datasets/mmfopd_v3_suite/mixed_math_suite/student_profile/data_expanded/learning_events.jsonl`
- 原始未扩充画像：`experiments/datasets/mmfopd_v3_suite/mixed_math_suite/student_profile/data/profiles.jsonl`
- 画像扩充程序：`experiments/mmfopd_v3/expand_profiles.py`

数据规模已经核验：270 个画像，每个 50 条记录，共 13,500 条；任务共 720 个，其中 train/dev/test 为 432/144/144。本轮结果使用 dev 的 144 个任务。

### 结果含义

- `rows.csv`：每个任务、每种方法一行，包含选择记录、敏感暴露、成本、必要单元召回和 F1。
- `summary.csv`：按方法宏平均后的主结果。
- `manifest.json`：方法列表、划分和实验边界。

### 复现命令

```powershell
.\.venv\Scripts\python.exe -m experiments.mmfopd_v3.runner `
  --data-root experiments/datasets/mmfopd_v3_suite/mixed_math_suite/student_profile/data_expanded `
  --output experiments/results/mmfopd_v3_development_compressed_card `
  --split dev
```

## 3. C²-RAG 数据

### 输入与冻结条件

- 正常—攻击配对会话：`experiments/c2rag_v3/results/paired_differentiated_budget040/runtime_fixture/public_sessions.jsonl`
- 隐藏评价样本：`experiments/c2rag_v3/results/paired_differentiated_budget040/runtime_fixture/hidden_cases.jsonl`
- 数据与配置校验：同目录下的 `fixture_manifest.json`、`run_manifest.json` 和 `freeze_manifest.json`

表中的“120 对正常—攻击请求”对应 240 个会话；每个会话 4 轮。11 种方法共生成 10,560 条逐轮记录。

### 结果含义

- `raw_results.jsonl`：全部逐轮真实释放内容和决策。
- `session_metrics.jsonl`：按会话计算 ASR、最终暴露和累计重构面积（Reconstruction AUC）。
- `paired_attack_utility.csv`：正常—攻击配对后的安全与效用结果。
- `attack_family_metrics.csv`：六类攻击的分组结果。
- `budget_ledger_trace.jsonl`：逐轮版权成本与剩余预算。
- `cumulative_reconstruction_curves.jsonl`：累计重构曲线。
- `attack_method_ranking.csv`：攻击场景平均版权成本。
- `final_development_table.csv`：展示稿使用的综合结果表。

“平衡安全效用”是本文定义的内部综合指标：`clean_utility × turn_availability × (1 − attack_exposure_severity)`，原始字段名为 `balanced_safe_utility`。它不是通用标准指标，正式汇报必须与三个组成项同时展示。

### 复现入口

主入口为 `experiments/c2rag_v3/runner.py`。当前结果目录的固定参数记录在 `run_manifest.json`，复跑时应以该文件中的 seed、预算、模型版本和 paired fixture 为准，不应临时修改参数。

## 4. HSW-ST 数据

### 输入数据与配置

- 12 条长教育文本：`protection/audit_trace/data/expanded_edu_dataset.jsonl`
- 20 条干净对照：`protection/audit_trace/data/expanded_clean_baseline.jsonl`
- 受保护数学术语：`protection/audit_trace/data/protected_terms_math.txt`
- Selective HSW-ST 配置：`experiments/text_watermark/config.local_qwen05b_selective12.yaml`

每条水印文本接受 5 类攻击，因此共有 60 条攻击结果。

### 结果含义

- `metrics_summary.csv`：WDR、FPR、ADR、TKR、FKR、NKR 和 Placeholder Pass 汇总。
- `metrics_per_sample.csv`：12 条文本的逐样本保真与检测数据。
- `attack_results.csv`：60 条攻击后的水印检测数据。
- `watermarked_answers.jsonl`：最终水印文本。
- `source_trace_logs.jsonl`：来源绑定记录。

### 复现命令

```powershell
Set-Location protection/audit_trace
..\..\.venv\Scripts\python.exe src/main.py `
  --config ../../experiments/text_watermark/config.local_qwen05b_selective12.yaml `
  --mode experiment
Set-Location ../..
```

## 5. CGC 公开安全基准

### JailbreakBench

- 本地冻结数据：`experiments/external_data/jailbreakbench/harmful-behaviors-886acc352a31.csv` 和 `benign-behaviors-886acc352a31.csv`
- 数据版本：JailbreakBench/JBB-Behaviors commit `886acc352a31533ffbcf4ef22c744658688086fc`
- 运行脚本：`experiments/evaluation/run_cg_jailbreakbench.py`
- 结果：`experiments/results/cg_jailbreakbench/summary.json` 和 `summary.csv`

```powershell
.\.venv\Scripts\python.exe -m experiments.evaluation.run_cg_jailbreakbench `
  --max-harmful 30 --max-benign 30
```

### BIPIA

- 上游数据：Microsoft BIPIA commit `a004b69ec0dd446e0afd461d98cb5e96e120a5d0`
- 使用部分：EmailQA 测试邮件和 `text_attack_test.json` 的 75 条间接注入
- 运行脚本：`experiments/evaluation/run_cg_bipia.py`
- 结果：`experiments/results/cg_bipia/summary.json`

BIPIA 原文由运行脚本从固定提交读取；结果文件只保留上下文/攻击哈希、攻击家族和决策，避免复制传播邮件内容。

```powershell
.\.venv\Scripts\python.exe -m experiments.evaluation.run_cg_bipia --cases 75
```

### XSTest

- 上游数据：XSTest commit `d7bb5bd738c1fcbc36edd83d5e7d1b71a3e2d84d`
- 运行脚本：`experiments/evaluation/run_cg_xstest.py`
- 结果：`experiments/results/cg_xstest/summary.json`

官方文件共有 450 条、18 个类型（250 条 safe、200 条 unsafe）。本轮 25+25 只覆盖 `homonyms` 与 `contrast_homonyms`，属于过度拒答的窄范围 smoke slice，不能表述为完整 XSTest 成绩。

XSTest 原文由运行脚本从固定提交读取；结果保存样本 ID、类型、提示词哈希和决策。

```powershell
.\.venv\Scripts\python.exe -m experiments.evaluation.run_cg_xstest --per-label 25
```

## 6. 老师现场追问时的回答

**“这些是不是随手编的数据？”**

MM-FOPD 和领域攻击会话属于固定种子生成的合成教育实验数据，用于控制变量，不是真实学生数据；JailbreakBench、BIPIA 和 XSTest 是固定公开版本。所有结果保留逐样本记录和运行清单，可以从汇总值追溯到单个样本。

**“表里的数能否回查？”**

可以。先打开对应 `summary.csv/json`，再用 `rows.csv`、`raw_results.jsonl`、`metrics_per_sample.csv` 或结果 JSON 的 `rows` 回查分子、分母和单个决策。

**“为什么公开安全结果里没有保存提示词原文？”**

结果保存公开样本 ID、类别和 SHA-256 哈希，用固定版本数据可重新定位原文；这样既能复现，也避免在实验产物中重复传播有害提示词和邮件内容。
