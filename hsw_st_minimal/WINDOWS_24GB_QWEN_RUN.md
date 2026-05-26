# Windows 24GB 显存运行强模型 KGW 水印说明

这份文档给同学在 Windows + NVIDIA 24GB 显存机器上复现实验用。重点是：本项目的 KGW 水印必须在 Hugging Face `transformers` 生成过程中插入 `LogitsProcessor`，所以请使用 HF/Transformers 模型，不要换成 Ollama、GGUF 或纯 API 模型。

## 推荐模型

优先推荐：

| 用途 | 模型 | 配置文件 | 下载体积 | 建议 |
|---|---|---|---:|---|
| 稳妥强模型 | `unsloth/Qwen3-14B-unsloth-bnb-4bit` | `configs/config.qwen3_14b_bnb4.yaml` | 约 10.4GB | 24GB 显存优先用这个 |
| 更强但更吃显存 | `unsloth/Qwen3-32B-bnb-4bit` | `configs/config.qwen3_32b_bnb4_24g.yaml` | 约 17.9GB | 24GB 可尝试，先跑 demo |

为什么不用官方 AWQ/GPTQ 作为主线：当前 Windows 环境下，`transformers` 加载 AWQ/GPTQ 往往需要 `gptqmodel`，可能触发 Visual Studio Build Tools 编译依赖。BNB 4bit 已有 Windows wheel，安装最省心。

## 1. 准备环境

在项目根目录 `CogniGuard` 下执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

先安装 CUDA 版 PyTorch。下面是 CUDA 12.1 wheel 的常用命令；如果同学机器 CUDA/PyTorch 版本不同，可以按 PyTorch 官网命令替换。

```powershell
.\.venv\Scripts\python.exe -m pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
```

再安装项目依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

检查 GPU 是否可用：

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO CUDA')"
nvidia-smi
```

如果 `torch.cuda.is_available()` 是 `False`，不要继续跑大模型，先重装 CUDA 版 PyTorch。

## 2. 下载模型

进入 HSW-ST 子项目：

```powershell
cd hsw_st_minimal
$env:HF_HUB_ENABLE_HF_TRANSFER = "1"
```

下载推荐的 14B 4bit 模型：

```powershell
..\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('unsloth/Qwen3-14B-unsloth-bnb-4bit', allow_patterns=['*.json','*.safetensors','*.txt','*.model'])"
```

确认虚拟环境 Python 路径应该是：

```powershell
..\.venv\Scripts\python.exe
```

如果要挑战 32B 4bit：

```powershell
..\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('unsloth/Qwen3-32B-bnb-4bit', allow_patterns=['*.json','*.safetensors','*.txt','*.model'])"
```

如果下载慢，保持 `HF_HUB_ENABLE_HF_TRANSFER=1`。模型缓存默认在：

```text
%USERPROFILE%\.cache\huggingface\hub
```

## 3. 跑一轮 demo

推荐先跑 14B demo：

```powershell
..\.venv\Scripts\python.exe src\main.py --config configs\config.qwen3_14b_bnb4.yaml --mode demo
```

如果 14B 正常，再试 32B：

```powershell
..\.venv\Scripts\python.exe src\main.py --config configs\config.qwen3_32b_bnb4_24g.yaml --mode demo
```

运行时会打印：

```text
[HSW-ST] model.device=cuda dtype=float16
[HSW-ST] output_run=...\outputs\run_YYYYMMDD_HHMMSS_xxxxxx
```

结果文件都在这个最新的 `outputs\run_...` 目录里。

## 4. 查看结果

查看最新输出目录：

```powershell
Get-ChildItem .\outputs -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

查看汇总指标，把 `<RUN_DIR>` 换成最新目录名：

```powershell
Get-Content .\outputs\<RUN_DIR>\metrics_summary.csv
```

重点看：

| 指标 | 含义 |
|---|---|
| `WDR` | 水印文本被检测出来的比例，越高越好 |
| `FPR` | 干净文本误判为水印的比例，越低越好 |
| `ADR` | 攻击后仍检测出的比例，越高越好 |
| `AvgZ_mean` | 平均 Z-score，越高越容易过阈值 |
| `PlaceholderPass_mean` | 公式、数字、术语保护是否通过 |
| `TraceBindRate_mean` | 水印日志和来源日志是否绑定成功 |

## 5. 参数调节建议

更大的模型通常会让改写质量更好，但 KGW 检测率不保证自动变高。水印强度主要看 `watermark.delta` 和 `watermark.z_threshold`。

如果 `WDR` 低、`AvgZ_mean` 低：

```yaml
watermark:
  delta: 2.5
  z_threshold: 2.85
```

如果还是低，可以继续试 `delta: 3.0`。但如果文本开始胡编、公式乱掉，就把 `delta` 降回去。

如果 `PlaceholderPass_mean` 低：

```yaml
model:
  rewrite_temperature: 0.20
  rewrite_max_new_tokens: 120
```

如果只是想确认 KGW 是否能打上，不想受占位符保护影响，可以临时改：

```yaml
experiment:
  ablation: "kgw_only"
```

如果 `CUDA out of memory`：

1. 先关掉浏览器、游戏、Ollama、其他 Python 进程。
2. 用 `nvidia-smi` 确认至少有 20GB 以上空闲显存再跑 32B。
3. 32B 不稳就改跑 14B。
4. 把 `rewrite_max_new_tokens` 降到 `96` 或 `80`。

## 6. 正式实验

demo 只跑 8 条样本。确认模型能跑之后，再跑完整实验：

```powershell
..\.venv\Scripts\python.exe src\main.py --config configs\config.qwen3_14b_bnb4.yaml --mode experiment
```

32B 完整实验耗时会比较久，建议先只用 demo 确认输出质量和显存稳定性。

## 7. 常见坑

- 不要用 Ollama 跑 KGW。Ollama 不能在生成时注入本项目的绿色 token logits bias。
- 不要优先装 GPTQ/AWQ 后端。Windows 上可能需要 VS Build Tools，BNB 4bit 更省事。
- 第一次下载模型会很久，`hf_transfer` 能明显加速。
- 如果 Hugging Face 下载中断，直接重跑下载命令即可，缓存会尽量续传。
- 如果输出里出现 `<think>` 或长推理内容，确认代码已包含 `enable_thinking=False` 的兼容改动。
