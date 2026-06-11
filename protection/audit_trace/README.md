# HSW-ST 最低实现版（混合语义感知水印 + 来源追踪）

验证流程：**教学草稿 → 术语/公式/数字占位符保护 → 本地模型 KGW 类 logits 水印改写 → 检测与攻击实验 → 指标 CSV**。来源追踪通过 `answer_id` 将 `watermark_log` 与 `source_trace_log` 绑定（不把 `resource_id` 写进正文）。

## 环境

- Python 3.10+
- **默认 `device: auto`**：检测到 CUDA 则用 GPU，否则 CPU；启动时会打印 `[HSW-ST] model.device=...`。强制无 GPU 时在 `configs/config.yaml` 写 `device: cpu`；强制 GPU 可写 `device: cuda` 或使用 `configs/config.gpu.yaml`
- 安装依赖（任选其一）：
  - 在仓库根目录 `CogniGuard/`：`pip install -r requirements.txt`（会引用本目录的 `requirements.txt`）
  - 在本目录：`pip install -r requirements.txt`

可选语义相似度：额外执行 `pip install sentence-transformers`，并在配置中设置 `experiment.use_sentence_embedding: true`。

## 配置模型

### 1）Hugging Face（推荐，完整 KGW）

```yaml
model:
  provider: "huggingface"
  local_model_name: "Qwen/Qwen2.5-3B-Instruct"  # 可改 7B（需更多显存/量化）或本地路径；0.5B 仅建议调试
  device: "cuda"
  dtype: "float16"
```

首次运行会从 Hugging Face 下载权重。

### 2）DeepSeek 等 OpenAI 兼容 API（无 logits，检测 Z-score 通常不可靠）

用于**仅演示改写 + 日志绑定**，论文级 KGW 实验请用 `huggingface`。

```yaml
model:
  provider: "openai"
  openai_base_url: "https://api.deepseek.com"
  openai_api_key: ""   # 或使用环境变量 DEEPSEEK_API_KEY / OPENAI_API_KEY
  openai_model: "deepseek-chat"
```

### 3）Ollama

Ollama 接口无法在生成时注入自定义 logits bias，**不能实现文档中的 KGW 水印**。若仍希望用本地 Ollama 做「无水印改写演示」，可将 Ollama 的 OpenAI 兼容地址填入 `openai_base_url`（例如 `http://localhost:11434/v1`），`provider: openai`，模型名填 Ollama 中的名称。

## 流畅度 vs 检测强度（Z-score）

KGW 在每一步对 **绿表** 加 `delta` 的 logits 偏置：**`delta` 越大，平均 Z 往往越高、越容易判「有水印」**，但分布被拉离自然语言，教学改写就越容易「不像人写的」——这是方法本身的取舍，不是单纯调提示能完全消除的。

- **默认 `config.yaml`**：按「**最小改动润色 + 可检出**」设 **`delta≈1.75`**、**`z_threshold≈2.85`**、`rewrite_temperature≈0.26`；若出现 **WDR≈0**，多半是 `delta` 太小或 `z_threshold` 太高，二者需一起调。
- **要拉满检出、接受文本更硬**：用 **`configs/config.high_detection.yaml`**（`delta: 2.0`、`z_threshold: 4.0`）。
- **微调**：改变 `delta` 后应用验证集 **重标一条 Z–阈值曲线**，避免「偏置弱却还用过高速率阈值」。

若要「正文几乎无损 + 仍声称极高鲁棒检测」，需要 **论文级扩展**（例如弱水印强度、分段水印、或语义感知加权），超出本仓库最低实现版范围。

## 运行

在项目根目录 `protection/audit_trace/` 下：

```bash
# 快速演示（约 8 条样本）
python src/main.py --config configs/config.yaml --mode demo

# 完整实验（按 config 中 data.num_samples）
python src/main.py --config configs/config.yaml --mode experiment
```

Windows 也可双击或运行 `scripts\run_demo.bat`。

## 消融实验

消融调度代码位于仓库根目录 `experiments/ablation/`。单次运行仍可在
`configs/config.yaml` 中设置 `experiment.ablation`：

- `full`：占位符保护 + KGW
- `kgw_only`：仅 KGW，不做占位符保护
- `protect_only`：占位符保护 + 无 logits 偏置（对照「有水印」）
- `no_watermark`：与 `protect_only` 相同实现（占位符保护 + 无偏置），用于与 `full` / `kgw_only` 对照 WDR/FPR

批量运行四种模式：

```bash
cd ../..
python -m experiments.ablation.run_all_ablations --mode experiment
```

## 输出

| 文件 | 说明 |
|------|------|
| `outputs/run_<时间戳>/` | 默认每次运行单独子目录（`paths.output_run_subdir: true`）；`false` 时文件仍在 `outputs/` 根目录 |
| `.../watermarked_answers.jsonl` | 水印化回答与自检 Z-score |
| `.../watermark_logs.jsonl` | 水印参数与 `watermark_id` |
| `.../source_trace_logs.jsonl` | `resource_id` / `chunk_id` 绑定 |
| `.../metrics_summary.csv` | 汇总：WDR、FPR、ADR 等 |
| `.../metrics_per_sample.csv` | 每条样本明细 |
| `.../attack_results.csv` | 各攻击后检测结果 |

## 指标简述

- **WDR**：水印文本被检出的比例
- **FPR**：干净基线被误判为有水印的比例
- **ADR**：攻击后仍检出的比例
- **TKR / FKR / NKR**：术语 / 公式 / 数字在改写后是否仍存在
- **TraceBindRate**：水印日志与来源日志是否成对写出

## 常见问题

1. **改写质量 / 「当然可以」套话**：默认已用 **3B**，并在后处理里剥客服句、检测到垃圾输出时 **自动贪心重试一轮**。若仍差：试 **Qwen2.5-7B**（显存够或 4bit）、略降 `watermark.delta`（水印略弱）、或 `rewrite_temperature: 0.28`。

2. **无 GPU**：`device: cpu` 可跑 3B（较慢），建议减小 `data.num_samples` 或改用 0.5B 仅作冒烟。
3. **占位符丢失**：实现会自动重试 1 次；仍失败会在 JSONL 中标记 `failed_placeholder_check`。
4. **Z-score 过低**：增大 `watermark.delta` 或 `gamma`，或检查生成与检测是否共用同一 `tokenizer`、`key`、`window_size`。
5. **API 路径错误**：`openai_base_url` 不要重复 `/v1`；代码支持 `https://host` 或 `https://host/v1` 两种写法。

## 项目结构

与任务书一致：`configs/config.yaml`、`data/`、`src/*.py`、`scripts/`、`outputs/`。
