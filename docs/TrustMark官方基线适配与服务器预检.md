# TrustMark 官方基线适配与服务器预检

## 结论与边界

本适配只调用 Adobe 官方 TrustMark Python 实现，不复制、替换或修改模型算法。它采用独立 runner，而不强行套入 CogniGuard 的生产水印 API，原因是两者的原生语义不同：

| 项目 | TrustMark 官方基线（本适配固定值） | CogniGuard 当前协议 |
|---|---:|---:|
| 原生神经网络通道 | 100 bit | 不是此含义 |
| 有效载荷 | 61 bit（`BCH_5`） | 64-bit HMAC source capsule |
| ECC | 官方 `BCH_5`，开启 | registry 半径纠错是另一层语义 |
| 模型与强度 | `Q`，`WM_STRENGTH=1.0` | EditGuard wrapper 自身配置 |
| source registry | 无 | 有 |
| 篡改定位 | 本基线不支持、不报告 | EditGuard wrapper 支持 |

因此不能把 TrustMark 的 100-bit 原始通道、61-bit ECC 后载荷或 `watermark_present` 写成 CogniGuard 的 64-bit capsule、HMAC 认证、exact registry match 或 corrected registry match。本 runner 不产生这些 registry 字段，也不报告篡改定位 mask IoU/Dice；它只在未嵌入的原图负控上报告 TrustMark 原生 `observed`/ECC 解码 FPR。

官方依据：

- [Adobe TrustMark 官方仓库](https://github.com/adobe/trustmark)
- [固定源码 commit](https://github.com/adobe/trustmark/tree/0ed40cbe8188f664fd9cbbeacd969807de27440a)
- [官方配置说明](https://github.com/adobe/trustmark/blob/0ed40cbe8188f664fd9cbbeacd969807de27440a/python/CONFIG.md)
- [官方 TrustMark Python 源码](https://github.com/adobe/trustmark/blob/0ed40cbe8188f664fd9cbbeacd969807de27440a/python/trustmark/trustmark.py)

## 指标口径

每个样本与实验 seed 的组合由 `sample_id + seed` 通过 SHAKE-256 域分离规则确定性生成 61-bit 方法原生载荷，不使用标签选择视图或结果。

- `raw_channel_bit_accuracy`：官方 ECC 编码器形成的 100-bit codeword，与同一个官方 decoder 在官方预处理和 `>0` 阈值下输出的 100-bit 原始通道结果比较。它是 pre-ECC 指标。
- `effective_payload_bit_accuracy`：官方 `decode(..., MODE="binary")` 返回的 BCH 后 61-bit 有效载荷与期望载荷比较。它是 post-ECC 指标。
- `exact_payload_match`：上述 61 bit 全部一致。
- `watermark_present`：直接采用官方 decoder/ECC 返回值。
- `watermark_psnr`、`watermark_ssim`、`watermark_lpips`：与其他方法共用项目现有指标实现。
- `watermark_observed`、`ecc_decode_success`、`verified_exact_payload_match`：分别表示官方检测、有效 ECC 解码和与期望载荷严格一致；missing 或单图推理异常的严格指标按 0 计，并独立保留异常字段。
- `embed_latency_seconds`、`decode_latency_seconds`：后者只计官方公共 `decode`；第二次 100-bit raw-channel diagnostic 的耗时单列为 `raw_channel_diagnostic_latency_seconds`。

输出同时记录 package version、源码 commit、模型 variant、strength、ECC schema、实际有效嵌入位数、原始通道位数和模型文件 SHA-256/官方 MD5。所有结果都标记 `cogniguard_64_bit_capsule=false`、`cogniguard_hmac_registry_used=false`、`tamper_localization_supported=false`。

## 隔离安装与资产预检

TrustMark 依赖 `numpy<2`，应使用专用环境，避免改变项目服务器正式环境。准备脚本默认只安装固定 commit；官方模型资产下载必须显式开启：

```bash
cd /root/autodl-tmp/CogniGuard
TRUSTMARK_STAGE_OFFICIAL_ASSETS=1 \
  bash scripts/server/prepare_trustmark_official_env.sh
```

若服务器基础环境只有 Python 3.12，可绕过损坏的用户级 Conda channel 配置并创建隔离的 Python 3.10 环境：

```bash
TRUSTMARK_BOOTSTRAP_CONDA=1 \
TRUSTMARK_PYTHON_VERSION=3.10 \
TRUSTMARK_STAGE_OFFICIAL_ASSETS=1 \
  bash scripts/server/prepare_trustmark_official_env.sh
```

脚本在两种模式下都拒绝 Python 3.12，只接受 3.10/3.11；Conda bootstrap 固定使用 `--override-channels -c https://repo.anaconda.com/pkgs/main`。若服务器已有合适解释器，也可显式传入 `PYTHON_BIN=/absolute/path/to/python`。

该阶段允许官方包按其原始逻辑下载 Q 模型的 config、encoder 和 decoder。下载后，项目预检会校验：

1. `trustmark==0.9.0`；
2. PEP 610 `direct_url.json` 指向 Adobe 官方仓库和固定完整 commit；
3. 实际导入模块的 `__file__` 位于该 PEP 610 distribution 内；
4. `RECORD` 中关键源码的 hash/size 与安装文件一致，并再次匹配审计 commit 的源码 SHA-256；
5. Q 模型三个必需文件存在，且 MD5 与固定官方源码一致；
6. encoder/decoder 能加载；
7. remover 和 bbox detector 未加载。

若服务器已有预检通过的隔离环境，不要重新执行会拒绝覆盖的安装脚本。正式运行前应对新冻结的 TrustMark 配置在不允许资产下载的环境再次执行预检：

```bash
cd /root/autodl-tmp/CogniGuard
TAG="$(date -u +%Y%m%dT%H%M%SZ)"
TRUSTMARK_SELECTED="/absolute/path/to/frozen_trustmark_selected.yaml"
/root/autodl-tmp/venvs/trustmark-official/bin/python \
  scripts/server/preflight_trustmark_official.py \
  --config "$TRUSTMARK_SELECTED" \
  --load-model \
  --output "outputs/trustmark_official_preflight_${TAG}.json"
```

只要包、commit、模型资产或 checksum 不匹配，预检和 runner 都以非零状态终止；不会回退到本项目近似实现，也不会输出可被误当作实验结果的 summary。

## 运行方式

独立 runner 只允许绑定已通过“阈值校准→2-of-3 通道确认”完整证据链的最终冻结 YAML，并在执行时重放该冻结验证。不能直接把未选择的 `paper_benchmark.yaml` 用于正式基线。在最终选定配置产生后，使用以下命令（所有输出路径必须尚不存在）：

```bash
cd /root/autodl-tmp/CogniGuard
TAG="$(date -u +%Y%m%dT%H%M%SZ)"
SELECTED="/absolute/path/to/paper_channel_vote_selected.yaml"
TRUSTMARK_SELECTED="outputs/trustmark_selected_configs/trustmark_${TAG}.yaml"

.venv-server/bin/python scripts/server/freeze_trustmark_selected_config.py \
  --baseline-config dfg_locguard/configs/trustmark_official_baseline.yaml \
  --selected-benchmark-config "$SELECTED" \
  --output-config "$TRUSTMARK_SELECTED"

PYTHONPATH="$PWD" \
  /root/autodl-tmp/venvs/trustmark-official/bin/python \
  scripts/server/preflight_trustmark_official.py \
  --config "$TRUSTMARK_SELECTED" \
  --load-model \
  --output "outputs/trustmark_official_preflight_${TAG}.json"

CUDA_VISIBLE_DEVICES=0 PYTHONPATH="$PWD" \
  /root/autodl-tmp/venvs/trustmark-official/bin/python -m \
  dfg_locguard.experiments.trustmark_official_baseline \
  --config "$TRUSTMARK_SELECTED"
```

`formal` 模式拒绝 `--output-dir`、样本上限、split、seed 和攻击网格覆盖；输出位置由冻结配置的 `output_root/run_id` 决定。需要小规模连通性检查时应复制配置并显式设置 `mode: smoke`，其汇总固定标记 `paper_eligible=false`。

主要产物：

- `environment.json`：输入哈希、固定实现与资产 provenance、容量/ECC 语义；
- `embeddings.jsonl`：逐样本/seed 的水印 PNG SHA-256/字节数、原生 payload/codeword、质量与嵌入时延；
- `raw_results.jsonl`：逐样本/seed/攻击的 native recovery、watermark-present 和解码时延；
- `negative_controls.jsonl`：同一 test split 原图的原生检测/ECC 误报与异常记录；
- `summary.json`：overall、按攻击、按领域、按攻击×领域汇总。

runner 先在同级临时目录完成全部笛卡尔积、负控和汇总校验，再原子发布最终目录；任何已存在的目标（包括空目录）都拒绝覆盖。正式运行共产生 `558×3×35=58,590` 条传统攻击结果、`1,674` 条嵌入记录和 `558` 条原图负控。每张水印 PNG 只在其 35 个攻击全部完成前临时存在；正式产物保留 PNG SHA-256/字节数后删除图像，避免运行结果耗尽数据盘。单图 encode/decode 异常保留为 `status=failed` 行并将原生严格指标计 0，系统性 provenance、manifest、攻击协议或输出完整性错误则立即回滚。正式汇总只有在失败率不超过冻结阈值时才可标记为 paper eligible。

当前独立 runner 只继承传统攻击。源配置中的 AIGC 局部编辑不会被静默冒充为已测试：summary 明确写入 `aigc_results_claimed=false`。因此 TrustMark 只能进入“同一 test 样本×同一 3 seeds×同一 35 传统攻击”的公平比较表，不能进入 AIGC 攻击对比表。后续如需与同一 AIGC 攻击比较，应先冻结共享的已编辑图像 artifact manifest 及对齐的 GT mask，再让所有方法解码同一批 artifact。
