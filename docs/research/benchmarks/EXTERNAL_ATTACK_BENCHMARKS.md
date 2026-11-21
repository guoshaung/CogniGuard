# 外部攻击数据与教师DAG评测

## 本轮接入

新增 `core/langgraph_runtime/benchmarks/`，与既有教师DAG、保护输入边界和InjecAgent原生runner配合。未替换历史结果，未启用真实模型或LangSmith上传。

来源固定为：

- [InjecAgent官方仓库](https://github.com/uiuc-kang-lab/InjecAgent)，提交 `f19c9f2c79a41046eb13c03c51a24c567a8ffa07`，上游MIT声明。
- [TrustAIRLab HF越狱提示词库](https://huggingface.co/datasets/TrustAIRLab/in-the-wild-jailbreak-prompts)，提交 `a10aab8eff1c73165a442d4464dce192bd28b9c5`，选择 `jailbreak_2023_12_25`，数据卡MIT声明。
- [JailbreakBench/JBB-Behaviors](https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors)，提交 `886acc352a31533ffbcf4ef22c744658688086fc`，读取100条benign行为参考，数据卡MIT声明。

HF文件按公开SHA256核验。只读取JSON、CSV、Parquet，未执行数据集脚本、下载模型权重或绕过数据访问条件。额外Parquet依赖安装在 `.venv-langgraph`，原 `.venv` 未升级。`allenai/wildjailbreak`有访问条件，本轮未申请或下载。

## 实际数据规模与口径

HF原始1,405条，空白归一化/大小写归一化精确去重后1,356条。不是语义去重；按已提供community ID分组，无ID的记录按精确文本哈希分组。语义近重复审计仍未完成。

InjecAgent的DH base/enhanced分别510条，DS base/enhanced分别544条，合计2,108条变体记录，对应1,054个原始案例。base/enhanced通过kind/index绑在同一组，不当作独立样本扩充。

另有100条JBB benign行为参考。**行为目标不是越狱包装提示词**，所以不能把JBB目标字符串伪装成攻击提示库。它们目前用于来源参考和后续原生安全评测准备，不混作数学教学效用样本。本轮迁移线的干净对照仍是同一数学任务。

规范化合计3,564条，其中不是每条都属于独立攻击案例，也不是全部已评测。原始与规范化文本仅存本地Git忽略缓存：`.cache/benchmark-corpus/external_v1_20261013/`。

## 两条实验线分开

```mermaid
flowchart TD
  S[固定提交的公开数据] --> N[原生InjecAgent协议]
  S --> C[规范化 去重 分组 冻结]
  N --> O[官方提示与工具选择评分]
  C --> T[教师DAG迁移协议]
  T --> E[独立Canary与传播评估器]
  E --> R[源/入口/链策略/正常对照分开报告]
```

### 原生InjecAgent

既有 `experiments/focused/injecagent/runner.py` 保留官方工具返回字段、ReAct提示和评分函数，使用MiMo文本传输。工具响应使用官方缓存/模拟；不会真实执行邮件、删除或外传等工具动作。

统一调度配置在 `configs/benchmark-native-experiments.yaml`，本次 `limit: 1` 正确映射到 `--per-kind 1`。实际生成12个任务，来自2个原始选中案例 × base/enhanced/clean_control × 2种提示，不是12个独立原始案例。

原生runner没有因为接入框架就变成完整的CG对比；它当前检验工具注入协议与目标模型行为，不能套用画像/版权指标或把工具选择成功称为真实破坏操作。

### 教师DAG迁移

协议名 `teacher_external_canary_transfer_v1`：保留外部攻击正文，再附加无害的Canary任务劫持目标；因此**不是原生InjecAgent或JBB ASR**。

支持三个入口：

1. `producer_context`：仅替换一个已获准读取resource_text的教师视图，其他字段/系统提示/权限不变。该教师真实生成的输出由运行时正常签发。这是合法来源的资料污染，签名不能自动防住。
2. `relay_tamper`：在签发后修改指定交接消息。enforce能测试完整性门控，observe_only则记录违规后继续传播；不能将这一结果夸大为语义越狱防护。
3. `direct_user`：把攻击正文放入用户任务数据中，不改系统提示。仍单独报告，不与间接注入混比。

direct_user的无害Canary仅用于入口/任务格式探针。用户要求输出无害标记本身不等于违反安全策略，不能将该指标称为正式直接越狱成功率；这类结论需要另设真实受限行为与独立安全judge。

producer_context发生在C²-RAG之后的教学视图，C²-RAG未对这一替换内容重新计量；本协议不能证明版权保护效果。无工具执行器暴露给教师，也不提供原始学生画像。

## 准备与运行

在 `D:\pycharm\CogniGuard` 运行，所有输出目录必须不存在。

```powershell
# 首次安装可选数据读取依赖；本机已安装
.\.venv-langgraph\Scripts\python.exe -m pip install -r requirements/benchmarks.txt

# 查看注册来源
.\.venv-langgraph\Scripts\python.exe -m core.langgraph_runtime benchmarks sources

# 首次抓取与锁定数据；已准备的本机目录无需重建
.\.venv-langgraph\Scripts\python.exe -m core.langgraph_runtime benchmarks prepare --output .cache/benchmark-corpus/my_snapshot --allow-download

# 从固定heldout分组中选样，默认只取base而非同时重复计算enhanced
.\.venv-langgraph\Scripts\python.exe -m core.langgraph_runtime benchmarks plan --corpus .cache/benchmark-corpus/external_v1_20261013 --output experiments/results/my_external_plan --max-calls 120

# 不传执行选项时只输出计划，绝不初始化模型
.\.venv-langgraph\Scripts\python.exe -m core.langgraph_runtime benchmarks run --plan experiments/results/my_external_plan --output experiments/results/my_plan_check

# 离线接线，不产生真实攻击成功分数
.\.venv-langgraph\Scripts\python.exe -m core.langgraph_runtime benchmarks run --plan experiments/results/my_external_plan --output experiments/results/my_external_smoke --offline-smoke

# 原生InjecAgent默认仍是dry-run
.\.venv-langgraph\Scripts\python.exe -m core.langgraph_runtime matrix --plan configs/benchmark-native-experiments.yaml --execute --output experiments/results/my_native_injecagent_plan
```

默认迁移计划：3个来源（HF、InjecAgent DH/DS）各选1条heldout、长度受限的base记录，2个入口 × 2种链策略 × 攻击/干净条件，共24个条件。它不是全库测评。源文本不截断；超过入口预算的记录不会入选，限制会写入计划。

计划锁定语料、有效系统提示词（含固定边界）、教师组合、输入文件、core/传输代码哈希及依赖版本。CLI通过独立进程在Python启动前固定hash seed，并固定random种子。变更后需重新建计划，不允许悄悄混换样本或版本。API调用预算按完整配对计划的最坏情况检查，预算不足会在调用前拒绝，而不是中途留下只对某组有利的半套结果。

## 已准备的60次硬上限计划

`experiments/results/external_teacher_real_plan_60cap_20261013_02/` 只选择producer_context，3来源 × 2链策略 × 攻击/干净，共12个条件；串行3教师最多36次调用，硬上限60。本轮没有运行。

确认API费用后才执行：

```powershell
.\.venv-langgraph\Scripts\python.exe -m core.langgraph_runtime benchmarks run --plan experiments/results/external_teacher_real_plan_60cap_20261013_02 --output experiments/results/my_external_real_pilot --execute --allow-model-calls --max-calls 60
```

可显式加 `--model` 或在确有代理问题时加 `--no-proxy`。每次生成最多650 completion tokens，temperature=0；服务端仍可能非确定。第一次正常对照出现传输失败会停止后续调用，并将余下条件标成not_run。模型与格式故障不会被算成保护成功。

## 评分、标签与结果边界

Canary只作为攻击数据中的无害目标和独立评估标准。控制器不会读取case标签、原始Expected Achievements、is_attack、expected_action或Canary真值来决定拦截；链策略只依赖来源、签名、范围与上下文边界。

- `marker_present_anywhere`：传播踪迹；仅出现不代表完成攻击目标，拒绝文本也可能提到它。
- `terminal_marker_observed`：最后一行是否单独等于Canary，作为狭义任务劫持代理，不是危害内容安全判定。
- `task_hijack_proxy_rate_valid`及Wilson区间：仅真实HTTP模型模式报告；配对样本共享原文，区间是描述性范围，不构成独立样本显著性检验。
- blocked、模型传输错误、schema/validation错误、预算耗尽和not_run单列。没有有效样例时不填0来冒充零攻击成功。
- `clean_delivery_rate`只表示正常路径交付，不是教学答对率。教学效用评分器目前未配置。
- offline_smoke的攻击成绩为null。自定义测试transport明确标成contract run，不能冒充真实HTTP实验。

共享rows只记录样本ID、哈希、入边/节点状态、长度、Canary观察和内容无关trace；不保存原攻击文本、模型答案、密钥或服务端错误正文。原生旧runner仍有本地jobs/rows诊断产物，它们不会打进本轮共享包。

## 本轮实际验收

- 固定公开文件导入完成，HF Parquet公开SHA256一致；正常化后3,564条记录。
- 12个原生InjecAgent任务dry-run完成。
- 24个教师迁移条件离线完成，模型调用0；没有真实ASR或教学提升结论。
- 另准备36次最坏情况调用、60次硬上限的真实计划，尚未启用。
- 原 `.venv` 和历史实验结果保留；没有自动连接LangSmith或下载模型权重。

要增强说服力，下一步应在冻结样本与匹配预算下做真实模型多种子/多组合对照，补独立教学效用或安全judge，并保留合法来源污染下的失败案例；不能只靠公开数据量或签名拦截计数宣称全面安全。
