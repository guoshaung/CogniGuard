# Official Watermark Anything adapter

This directory contains an optional, independent adapter for
`facebookresearch/watermark-anything`. It is not enabled in CogniGuard's
production service or paper benchmark configuration.

Pinned release contract:

- Repository: `https://github.com/facebookresearch/watermark-anything.git`
- Commit: `2c08af04d037d5667c02f6ddebbda9ff04581c3e`
- Checkpoint variant: MIT checkpoint trained on a subset of SA-1B
- Checkpoint bytes: `377825938`
- Checkpoint SHA256:
  `90ef232384e023bd63245eb0c131abd69d2afc7b8f17a71ccedceb542bf009e2`
- `checkpoints/params.json` SHA256:
  `d133a504d126b56b3e980add9fc014d718e3635a0f5740d8d6dc3190007fb476`
- Native message: 32 bits
- Native detector: 1 watermark-presence channel + 32 per-pixel message channels
- Frozen strength: `scaling_w=2.0`, `scaling_i=1.0`

The adapter never converts WAM into a 64-bit method. It performs no HMAC
capsule construction, registry lookup, Hamming-radius correction, or source
identity match. Native 32-bit raw bit accuracy/exact recovery and watermark
detection are reported in a WAM-specific section. PSNR, SSIM, an optional
shared LPIPS evaluator, and latency form the common comparison table.
Localization belongs in a separate table and is emitted only when an aligned
spatial attack ground-truth mask is supplied. With full-frame embedding, the
embedding mask is an explicit all-ones mask; derived tamper localization is
watermark absence inside that known support.

WAM exposes a per-pixel presence logit, not a pinned image-level yes/no
threshold. The adapter therefore reports the sigmoid presence-score
distribution and the pixel area above the official logit-zero boundary. It
does not turn “any positive pixel” into an invented image decision or FPR.
Original, unwatermarked inputs are always evaluated as negative controls.

Install source/dependencies in a dedicated environment (the script does not
download weights):

```bash
VENV=/opt/venvs/cogniguard-wam \
PYTHON=/opt/venvs/cogniguard-wam/bin/python \
bash dfg_locguard/official_baselines/wam_official_install.sh \
  /opt/watermark-anything
```

The installer rejects the main `.venv-server`, installs
`torch==2.5.1`/`torchvision==0.20.1` from the official PyTorch cu121 index,
and pins the shared attack runtime to `numpy==1.26.4` and `Pillow==10.4.0`.
For a previously cloned, exact clean checkout, additionally set
`WAM_REUSE_PINNED_REPO=1`.

Audit the checkout, dependencies, params, license, weight byte count, and
weight SHA256 before any pickle deserialization:

```bash
/opt/venvs/cogniguard-wam/bin/python -m \
  dfg_locguard.official_baselines.wam_official_preflight \
  --repo-root /opt/watermark-anything \
  --checkpoint /secure/checkpoints/wam_mit.pth \
  --device cuda \
  --output-json outputs/wam/preflight.json
```

Run one auditable native case (the 32 bits are required rather than generated
implicitly):

```bash
/opt/venvs/cogniguard-wam/bin/python -m \
  dfg_locguard.official_baselines.wam_official_cli \
  --repo-root /opt/watermark-anything \
  --checkpoint /secure/checkpoints/wam_mit.pth \
  --input data/example.png \
  --message-bits 01010101010101010101010101010101 \
  --output-dir outputs/wam/example
```

Run a one-image/clean smoke on the exact manifest selected by the existing
benchmark YAML, without editing that YAML:

```bash
/opt/venvs/cogniguard-wam/bin/python -m \
  dfg_locguard.official_baselines.wam_official_manifest_runner \
  --mode smoke \
  --repo-root /opt/watermark-anything \
  --checkpoint /secure/checkpoints/wam_mit.pth \
  --benchmark-config dfg_locguard/configs/paper_benchmark.yaml \
  --device cuda \
  --limit 1 \
  --seed 20260802 \
  --attack clean \
  --skip-lpips \
  --output-dir outputs/wam/smoke
```

Formal mode accepts only the final YAML whose threshold-calibration and
2-of-3-channel confirmation chain can be replayed by
`validate_frozen_channel_vote_formal_config`. The unselected
`paper_benchmark.yaml` is not a formal baseline input. On the current server,
run the same selected manifest, split, seeds, shared LPIPS evaluator, and
complete traditional attack grid as follows:

```bash
cd /root/autodl-tmp/CogniGuard
TAG="$(date -u +%Y%m%dT%H%M%SZ)"
SELECTED="/absolute/path/to/paper_channel_vote_selected.yaml"

PYTHONPATH="$PWD" /root/autodl-tmp/venvs/wam-official/bin/python -m \
  dfg_locguard.official_baselines.wam_official_preflight \
  --repo-root /root/autodl-tmp/vendor/watermark-anything-2c08af0 \
  --checkpoint /root/autodl-tmp/checkpoints/wam/wam_mit.pth \
  --device cuda \
  --output-json "outputs/wam_official_preflight_${TAG}.json"

CUDA_VISIBLE_DEVICES=0 PYTHONPATH="$PWD" \
  /root/autodl-tmp/venvs/wam-official/bin/python -m \
  dfg_locguard.official_baselines.wam_official_manifest_runner \
  --mode formal \
  --repo-root /root/autodl-tmp/vendor/watermark-anything-2c08af0 \
  --checkpoint /root/autodl-tmp/checkpoints/wam/wam_mit.pth \
  --benchmark-config "$SELECTED" \
  --device cuda \
  --output-dir "outputs/wam/formal_channel_vote_${TAG}"
```

Formal mode rejects every manifest/split/seed/attack/limit override. It audits
the global 3,000-row manifest, exact four-source quotas
`1200/600/400/800`, unique IDs/content hashes, the frozen test sample-ID set,
all three seeds, and all 35 traditional attacks. Smoke mode requires an
explicit positive limit and is always `paper_eligible=false`. The formal grid
contains `558 x 3 x 35 = 58,590` rows plus 558 original-image negative controls.

The manifest runner writes `environment.json` (preflight/runtime provenance,
config, manifest, local adapter, and `attacks.py` hashes),
`selected_test_samples.jsonl`, `original_negative_controls.jsonl`,
`raw_results.jsonl`, and `summary.json`. Formal clean watermarked PNGs are
temporary: after all 35 attacks for one sample/seed complete, the runner keeps
their PNG SHA256/byte count and deletes the image. Formal non-clean attacked
PNGs likewise use `hash_only` retention: each is saved, hashed, verified, and
deleted after success; up to 50 non-clean failed inference artifacts are
retained for diagnosis and further failures remain hash-only.
Every result row records the attacked-pixel SHA256 and exact
NumPy/Pillow versions. It intentionally excludes AIGC
rows until every method can consume the same pre-generated attacked image and
aligned attack GT; `summary.json` therefore marks the full public attack suite
incomplete. WAM belongs only in the common 558-sample/3-seed/35-traditional-
attack table, not in the current AIGC comparison table.

Per-sample/per-attack inference failures become explicit Cartesian-grid rows
with `pipeline_success=false`, strict native metrics set to zero, and an error
record. Protocol, manifest, provenance, preflight, quota, or attack-generation
errors still abort atomically. The formal paper claim becomes invalid when the
observed row or negative-control failure rate exceeds the frozen formal
`experiment.max_pipeline_failure_rate=0.0` boundary. Existing output paths
are never overwritten; a complete run is published by one directory rename.

No empirical WAM result is included in this repository. A missing dependency,
dirty/wrong checkout, altered params, missing/wrong checkpoint, unexpected
channel count, empty detector support, or non-finite output is recorded or
rejected rather than replaced with fabricated values.
