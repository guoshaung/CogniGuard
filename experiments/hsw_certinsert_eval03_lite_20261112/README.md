# HSW-CERTINSERT-EVAL-03-LITE

New isolated evaluation. EVAL01/02 and revision09 are read-only.
Read `PROTOCOL.md` and `EVAL_FREEZE.json` before running. Source-selection and
protocol files must be committed before inventory/sampling tests; exact sample
manifests must then be committed before any scoring/generation.

Run output: `var/results/hsw-st/certinsert_eval03_lite_20261112/run01/`.
No paid API, new models, or shared-service changes. Never replace failed samples.

Entry points: `initialize.py` (metadata freeze), `inventory.py` (read-only source
inventory after commit). GPU phases are not yet runnable until the data gate.
