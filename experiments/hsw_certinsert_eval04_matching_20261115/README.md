# EVAL-04-M 运行与复核

预注册提交 `643210abd6753e1a3a4be51da2a81c4287b28c7d`。按两个 R 队列及三种嵌入器执行。模型、冻结组件、密钥承诺和抽样定义见 M_FREEZE.json 与 M_PREREG.md。T1–T6 不作为输入。

依赖复用 EVAL-04 的 Python 环境与 EVAL-03 CUDA 运行库。将 ortools==9.11.4210、absl-py==2.1.0、protobuf==5.26.1、immutabledict==4.2.0 安装在本次忽略目录的 deps 下。已有权重、归档输入和密钥按冻结路径在授权的本机恢复。

```powershell
$w = 'D:/pycharm/CogniGuard-worktrees/hsw-st'
$e = "$w/experiments/hsw_certinsert_eval04_matching_20261115"
$py = "$w/var/results/hsw-st/certinsert_eval04_20261113/runtime/Scripts/python.exe"
$env:OMP_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:PYTHONUTF8 = '1'
& $py -B "$e/run_m.py"
& $py -B "$e/check_outputs.py"
& $py -B "$e/report_m.py"
```

run_m.py 保留逐篇检查点。清单、JSONL 和运行汇总位于本次专用的 var/results 目录。正式独立复跑使用新的工作树和空目录。比较表可由 per_item.csv 复核，figure_counts.json 的 embedder_comparison 字段保存汇总。冻结资产与文本分数无法从这份去文本的公开记录恢复。
