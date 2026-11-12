# figure_counts.json 格式说明（EVAL-03-LITE 交付物）

本文件**替代**任务书中"与 figures/make_figures.py 一一对应"的要求。Codex 不需要那个脚本，按下面的格式输出即可，论文作图端会改为直接读取这个 JSON。

## 通用规则
- 每个计数一律写成 `{"k": 命中数, "n": 分母}`。分母必须是该格**实际评估过的样本数**，不能缺省，也不能把缺失样本当成失败。
- 没有跑的格写成 `null`，**不要写 0**。
- 每个数都必须能从 `per_item.csv` 重新算出来。在 `SUMMARY_RECOMPUTATION.json` 中写明每个字段的计算方式。
- 系统名固定为：`CertInsert`、`RC`、`KGW`、`Unigram`、`Fingerprint`。
- 攻击名固定为：`none`、`ocr`、`crop_first100`、`crop_middle100`、`compress70`。
- 数据集名固定为：`T4`、`T5`、`T4_paired100`。
- 区间用按源文本做的 cluster bootstrap 95% 区间，格式为 `{"lo": 0.12, "hi": 0.34}`，可选。

## 结构

```json
{
  "meta": {
    "run_id": "EVAL-03-LITE",
    "commit": "<归档 commit 号>",
    "freeze_sha256": "<EVAL_FREEZE.json 的 sha256>",
    "calibration": "in-domain (same as EVAL-02)"
  },

  "coverage": {
    "T4": {"CertInsert": {"k": 0, "n": 400}, "RC": {"k": 0, "n": 400}},
    "T5": {"CertInsert": {"k": 0, "n": 200}, "RC": {"k": 0, "n": 200}}
  },

  "coverage_by_length": {
    "T4": {"<100": {"k": 0, "n": 0}, "100-200": {"k": 0, "n": 0}, "200-400": {"k": 0, "n": 0}, ">400": {"k": 0, "n": 0}},
    "T5": {"<100": {"k": 0, "n": 0}, "100-200": {"k": 0, "n": 0}, "200-400": {"k": 0, "n": 0}, ">400": {"k": 0, "n": 0}}
  },

  "detection": {
    "T4": {
      "CertInsert": {"none": {"k": 0, "n": 0}, "ocr": {"k": 0, "n": 0}, "crop_first100": {"k": 0, "n": 0}, "crop_middle100": {"k": 0, "n": 0}},
      "RC":         {"none": {"k": 0, "n": 0}, "ocr": {"k": 0, "n": 0}, "crop_first100": {"k": 0, "n": 0}, "crop_middle100": {"k": 0, "n": 0}},
      "Fingerprint":{"none": {"k": 0, "n": 0}, "ocr": {"k": 0, "n": 0}, "crop_first100": {"k": 0, "n": 0}, "crop_middle100": {"k": 0, "n": 0}}
    },
    "T5": { "...": "同 T4 结构" },
    "T4_paired100": {
      "CertInsert": {"none": {"k": 0, "n": 0}, "ocr": {"k": 0, "n": 0}, "crop_first100": {"k": 0, "n": 0}, "crop_middle100": {"k": 0, "n": 0}, "compress70": {"k": 0, "n": 0}},
      "RC":         {"...": "同上"},
      "KGW":        {"...": "同上"},
      "Unigram":    {"...": "同上"},
      "Fingerprint":{"...": "同上"}
    }
  },
  "detection_note": "CertInsert/RC 的 n = 成功加水印的源数（条件率）；无条件率由 coverage 推出。Fingerprint 的 k = source top-1 正确数。",

  "numbers_formulas_intact": {
    "T4_paired100": {"CertInsert": {"k": 0, "n": 0}, "RC": {"k": 0, "n": 0}, "KGW": {"k": 0, "n": 0}, "Unigram": {"k": 0, "n": 0}}
  },

  "compression_detail": {
    "T4_paired100": {
      "CertInsert": {"reached_target": {"k": 0, "n": 0}, "reached_and_intact": {"k": 0, "n": 0}, "detected_given_reached_and_intact": {"k": 0, "n": 0}},
      "KGW":        {"...": "同上"},
      "Unigram":    {"...": "同上"},
      "RC":         {"...": "同上"},
      "Fingerprint":{"reached_target": {"k": 0, "n": 0}, "reached_and_intact": {"k": 0, "n": 0}, "identified_given_reached_and_intact": {"k": 0, "n": 0}}
    }
  },

  "false_positives": {
    "in_domain_1000": {"CertInsert": {"k": 0, "n": 1000}, "RC": {"k": 0, "n": 1000}, "KGW": {"k": 0, "n": 1000}, "Unigram": {"k": 0, "n": 1000}},
    "general_300":    {"CertInsert": {"k": 0, "n": 300},  "RC": {"k": 0, "n": 300},  "KGW": {"k": 0, "n": 300},  "Unigram": {"k": 0, "n": 300}}
  },

  "pvalue_calibration": {
    "keys": 1000,
    "passages": 1000,
    "empirical_rate": {"0.001": 0.0, "0.01": 0.0, "0.05": 0.0}
  },

  "certificate": {
    "T4": {"restore_pass": {"k": 0, "n": 0}, "anchor_invariant_pass": {"k": 0, "n": 0}},
    "T5": {"restore_pass": {"k": 0, "n": 0}, "anchor_invariant_pass": {"k": 0, "n": 0}}
  }
}
```

## 校验（交付前自检）
- 所有 `k <= n`。
- `coverage.*.CertInsert.k` 等于 `detection.*.CertInsert.none.n`。
- 配对 100 篇中，五个系统使用同一批源 ID；源 ID 清单另存为 `PAIRED_IDS.json`。
- 不存在任何从 `per_item.csv` 推不出来的数字。
