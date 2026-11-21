# MMFOPD-A Gate 0: OULAD request-only cumulative inference

Only Gate 0. No defense design, API calls, GPU, production edits or historical reruns.
Data: Kuzilek, Hlosta & Zdrahal (2017), OULAD, CC BY 4.0,
https://doi.org/10.1038/sdata.2017.171 ; archive
https://doi.org/10.6084/m9.figshare.5081998.v1 .

Run from repository root with the existing scientific environment:
` .venv/Scripts/python.exe -B experiments/mmfopda_gate0_oulad_20261113/run_gate0.py audit `
then commit FIELD_TABLE.md separately, then `freeze`, commit frozen protocol,
then `run`, and `report`. Each phase checks the preceding artifacts.
After report, run ` .venv/Scripts/python.exe -B experiments/mmfopda_gate0_oulad_20261113/finalize_evidence.py `
to verify serialized request/feature equality and recompute every reported point metric
from the local per-student predictions. This post-run script does not fit models or change rules.
The .venv-langgraph environment lacks pandas; existing .venv is reused without installs.

Aggregate evidence and code are versioned here. Individual records, splits, labels,
requests and predictions stay in `var/results/mmfopda_gate0_oulad_20261113/`.
`per_student.csv` is a local deliverable, never an external receiver payload.
The receiver sees only service request names; it can link requests to a stable
pseudonymous student. Neither ID, cohort, week, registration nor labels are attack features.
This is offline simulated request generation over real behavioral records, not live agents.
