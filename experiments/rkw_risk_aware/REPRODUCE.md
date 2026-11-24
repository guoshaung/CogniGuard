# 复现 R0 与 R1

预注册在 `e2b1713`，输入、阈值、代码和作业上限见同目录的 SHA-256 清单。CA-PD 来自独立的 Claude `b23c42c` 检出。仓库根目录运行以下命令，选择一个新输出目录。

```sh
python experiments/rkw_risk_aware/pilot.py r0 --out var/rkw-reproduction
python experiments/rkw_risk_aware/risk_check.py --contract ../pe10-b23c42c --out var/rkw-reproduction
python experiments/rkw_risk_aware/pilot.py r1 --out var/rkw-reproduction
python experiments/rkw_risk_aware/score.py --out var/rkw-reproduction
```

R1 使用本机 11434 的 Ollama 和配置指定摘要的 `qwen2.5:7b-instruct`。已发布的原始输出足以离线复核结论，复制到新目录后直接运行 `score.py`。

```powershell
New-Item -ItemType Directory -Force var/rkw-score-replay
Copy-Item experiments/rkw_risk_aware/results/propagation_outputs.jsonl var/rkw-score-replay
python experiments/rkw_risk_aware/score.py --out var/rkw-score-replay
```

预注册摘要用于检查原始文件。评分结果的写入使用独占创建，重放请选择新目录。
