# EVAL-03-LITE adjusted Batch02

Authority: `TASK_AUTHORITY.md`, replacing the previous 60-pair plan. Frozen
method hash: `a50f08df466c35a1c07177e14f05305389299bea3288158fb62c31ed0180c001`.
This folder contains isolated research scripts; no production changes.

Run state is under
`var/results/hsw-st/certinsert_eval03_lite_20261112/run01/batch02_adjusted/`.
Read its `NEXT_ACTION.md`, raw records and stage receipts before resuming.
Most entry points are write-once. Never restart a completed generation stage.

## Stage order

1. Frozen public data and inputs; P1 T4-only N10, P2 protected regions and P6
   background calibration are already archived separately.
2. `generate_t5.py` and `prepare_t5.py`: 200 bounded source generations, no
   retry, frozen Markdown interface. Outputs are not human knowledge gold.
3. `continue_pipeline.py`: wait existing jobs, commit actual source manifests,
   score insertion with the frozen model, run OCR and public evaluation, freeze
   expanded public observations and attack strings, then score attacks and
   create the two independent human forms.
4. `archive_remaining.py`: wait existing pipeline, validate serialized counts,
   publish separate stage packages with secret scans and remote readback.

P4 human labels remain blank until two reviewers submit them. Its private
method mapping is never included in reviewer or public packages. P5 is an
optional, separate unstarted baseline expansion; it is not implied complete by
these entry points. The superseded baseline queue retains all 26 attempts.

## Recompute reports only (no new model execution)

Use the existing base Python environment to run `report_t5.py` or
`report_expanded.py` only when their required completed records are present.
Both create new delivery directories and refuse to overwrite them. Raw score
records and serialized CSV are independently cross-checked. Reproduction of
secret-key detection requires controlled local key access; public hashes alone
do not provide full independent keyed detection reproduction.

No paid API, new model download, threshold adjustment or failure replacement.
An unavailable observation count is null, never reported as zero or replaced by
a smaller count with the same label.
