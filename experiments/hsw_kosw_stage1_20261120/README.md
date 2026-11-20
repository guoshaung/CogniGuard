# KOSW stage 1

Windows/CUDA geometry feasibility only; no watermark embedding.
Read TASK_AUTHORITY.md and K1_PREREG.md. R-only inputs; never open T1-T7.
Conda environment kosw (Python3.11) is installed under the local result directory.
Run run_kosw.cmd after K1_FREEZE.json is committed and pushed. This entry uses only
the fixed MPNet snapshot and Ollama qwen2.5:7b-instruct, unloading one before the other.
Results and diagnostic keys remain local under var/results/hsw-st/kosw_stage1_20261120.
Public reports and code are in this directory. Phase2 is not executed.
