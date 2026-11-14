# EVAL-04-F 复核

预注册先于实验提交于 `b866ed1a5a35c9bb503a934952941dbde20aca22`。详见 F_PREREG.md、F_FREEZE.json 和 F_DEV_RESULT.md。此次按覆盖增益上界提前停止。300 篇完整槽位清单、实跑校准、已完成句首子集、历史近失和随机插入可由 per_item.csv 与 figure_counts.json 复核。

下列命令在另一个工作树和新的空运行目录复核。所需原始数据、模型、CPU 桥、KaTeX、版本及哈希见 F_FREEZE.json。历史密钥及本次校准密钥只可从受限本地位置加载。两者均通过承诺校验。

```powershell
$wt = 'D:/pycharm/CogniGuard-worktrees/hsw-st'
$lab = "$wt/experiments/hsw_certinsert_eval04_formula_20261114"
$py = "$wt/var/results/hsw-st/certinsert_eval04_20261113/runtime/Scripts/python.exe"
$env:OMP_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:PYTHONUTF8 = '1'
& $py -B "$lab/measure_formula.py" inventory
& $py -B "$lab/measure_formula.py" calibration
& $py -B "$lab/measure_formula.py" bound
& $py -B "$lab/attacks.py" --random-only
```

`sentence.py` 是句首基线入口。本轮 CPU 执行在第 8 条完整记录后中止，第 9 条未计分。全量分支保留在脚本中。复算本轮报告可用对应本机运行目录保存的 8 条完整日志，使用 `report_stop.py`。发布的 CSV 已包含上述逐条数值的去文本记录。
