# EVAL-04-B2 本地复核

预注册提交为 `28fc4a8a87c0f87dbb2be6e753f7179c44a0e9b0`。路径和输入字节哈希见 B2_PREREG.md 和 B2_FREEZE.json。使用冻结的 R、旧 EVAL-03 代码、CUDA 打分库与 3B 权重。本轮不读取 T1–T6 原文。

可公开复核的证据在 B2_DEV_RESULT.md、figure_counts.json、calibration_by_doc.csv 和 per_item.csv。逐项数值含分母。编译和运行只需访问本地资产。公开仓库可重算计数。复跑同一随机密钥实验需拥有本地忽略目录内的密钥文件，并通过冻结承诺检查。

在独立工作树上恢复冻结路径和已有本地密钥后，依次运行下列命令。生成脚本以独占方式新建结果。复跑时保留归档，使用隔离工作副本和空输出目录。

```powershell
$root = 'D:/pycharm/CogniGuard-worktrees/hsw-st'
$experiment = "$root/experiments/hsw_certinsert_eval04_b2_20261114"
$python = "$root/var/results/hsw-st/certinsert_eval04_20261113/runtime/Scripts/python.exe"
$pdfPython = "$env:USERPROFILE/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:OMP_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
& $pdfPython -B "$experiment/prepare_pdtb.py"
& $python -B "$experiment/run_b2.py" calibration
& $python -B "$experiment/run_b2.py" embed
& $python -B "$experiment/evaluate_b2.py"
& $python -B "$experiment/verify_b2.py"
```
