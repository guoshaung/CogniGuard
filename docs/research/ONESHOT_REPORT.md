# 一次性任务报告：进化治理层

日期：2026-11-28。分支 `paper/eswa-evolving`，从 `origin/main` 的 `5827e4e` 拉出。工作目录是新的 git worktree：`/Users/MBP/Exp/CogniGuard/paper-eswa-evolving`。原来的 `CogniGuard` 检出仍停在 `dev/source-evidence`，没有被切走。

没有调用付费 API，没有下载模型。新代码只用 Python 标准库。没有修改、删除本轮开始前已经存在的文件。

测试命令按任务书执行。本机 `python` 是 3.9.6，工程要求 `>=3.12`，所以实际解释器是 `/usr/local/bin/python3.14`。为了让既有测试能被收集，给这个解释器装了 pytest、PyYAML、langgraph、pymysql、numpy、Pillow。torch、transformers、scikit-learn 没有装。

留存的整套测试最后一行：

- 代码落地后的两次（37.03s、36.85s）：`3 failed, 379 passed, 9 skipped, 14 warnings, 18 subtests passed`
- 本报告提交前再跑一次（37.19s）：`3 failed, 379 passed, 9 skipped, 13 warnings, 18 subtests passed`

三次失败的都是任务书点名的那 3 个：`test_paths` 1 个、`test_supplychain` 2 个，见 `docs/research/FAILING_TESTS_DIAGNOSIS.md`。警告数少了 1，失败数没有超过 3。中间各步没有各自留一份完整日志，上面是留存的整套结果。

## 提交

| 步 | 提交 | 摘要 |
|---|---|---|
| 1 | `513e6e8` Diagnose the three known failing tests | 1 个文件，+59。`docs/research/FAILING_TESTS_DIAGNOSIS.md` |
| 2 | `2a27964` Add evolution events, ledger and commit gate (M1 core) | 5 个文件，+450。`events.py`、`ledger.py`、`gate.py`、`__init__.py`、`test_evolution_gate.py` |
| 3 | `bf4934f` Add deterministic evolution checkers (M2, M3, M4, M6) | 3 个文件，+303。`checkers.py`、`__init__.py`、`test_evolution_checkers.py` |
| 4 | `f0a76b5` Add evolving agent state with gated evolution hooks | 4 个文件，+325。`agent_state.py`、`__init__.py`、`examples/evolving_agents_demo.py`、`test_evolving_agent_state.py` |
| 5 | `f32e3a4` Add MLAS cell attack unit tests for the evolution layer | 1 个文件，+191。`test_mlas_cells.py` |
| 6 | `7ec7b9d` Add evolution-layer persistence pilot (not preregistered) | 3 个文件，+285。`run.py`、`README.md`、`results/pilot.json` |
| 7 | `1275006` List candidate benchmarks for A-tier MLAS cells | 1 个文件，+95。`docs/research/BENCHMARKS.md` |

## 第 6 步试验数字

种子 20261129。5 个智能体，20 代，每代每人 3 个正常动作，第 3 代注入 40 个载荷。有防护的一组在第 10 代隔离注入来源。

| | 无防护 | 有防护 |
|---|---|---|
| 仍然生效的污染版本 | 40 | 0 |
| 持久化率 | 1.0 | 0.0 |
| 被影响到的智能体 | 6（a0–a4 和 outsider） | 0 |
| 正常动作误拒 | 0 / 300 | 0 / 300 |
| propose 平均耗时 | 2.57e-6 秒 | 6.02e-6 秒 |

有防护时 40 个载荷都在 `propose` 时被拒绝，所以第 10 代的隔离没有可回滚的提交版本。这是试验数字，README 里写了不能当论文结论。

## 和任务书不一致的地方

这些是实现时任务书没有写出具体字符串或目标名，不改规则的含义：

- 技能、提示、记忆的 target 分别是 `{agent}:skill:{name}`、`{agent}:prompt:{fragment}`、`{agent}:memory:{key}`。任务书写了记忆和共享副本的 target，没有写技能和提示的 target。
- `share` 对每个接收方各走一次 propose 和 commit，成功时返回最后一条决定，失败时返回第一条拒绝。任务书的返回类型是一条 `GateDecision`。
- 账本增加了只读方法 `source_trusted`、`is_quarantined`、`targets`。任务书允许为隔离检查增加 `is_quarantined`。另外两个是检查器和 `skills()` 读取当前状态所需要的。
- 任务书没有给名字的拒绝原因用了 `invalid_skill_spec`、`url_not_allowed`、`payload_too_long`。URL 白名单按主机名精确匹配。
- `QuarantinedLineageChecker` 除了 provenance，也拒绝 parent 已经在隔离谱系里的提案。
- 闸门把原因拼成 `检查器名:原因`。检查器自己的原因已经是 `untrusted_instruction` 这种词，所以审计里会看到 `untrusted_instruction:untrusted_instruction`。这是按任务书的拼接格式来的。
- 示范和试验放在新 worktree，而不是切走用户正在用的检出。分支名仍是 `paper/eswa-evolving`。
- 测试解释器是 Python 3.14，不是名为 `python` 的 3.9。

## 没有完成的部分

- 三个已知失败没有修。任务书要求只诊断。
- #5、#10、#14、#17、#19 没有足够确认的第二份基准，或者格子本身对不上一份公开基准。`BENCHMARKS.md` 里写了待核实，没有编造许可证和规模。
- #5、#10、#25 的格子名字是按论文摘要里的模块顺序和任务书已点名的格子推的，没有对照论文里的正式编号表。
- 推送结果写在本文件末尾。若下面还没有成功记录，就是推送当时还没做完。

## 推送

见随后的提交说明。本提交写报告时推送尚未执行。
