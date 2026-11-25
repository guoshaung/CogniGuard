# Paired R0 inheritance diagnostic

This diagnostic uses the historical R0 registration frozen at commit 06d9259. Three families contribute two source IDs each and two training questions per source. A clean answer and its matching marked answer share each prompt. The 12 same-source evaluation prompts retain the registry label for routing and use new wording. The 6 unseen-source cases use three other families and prompts without registry labels. The same-source split measures transfer across questions within a registered source. Topic and answer reuse are intentional for that split.

Use `generate.jsonl` as the generation input. It exposes only `id` and `prompt`. Each arm supplies the resulting `id` and `text` in its own JSONL file. Pass `evaluate.jsonl` to the scorer. Its labels are used for comparison after the frozen decoder reads the output text. Report per-stratum expected and completed rows alongside all scores.

A complete source recovery requires the frozen R0 decoder to return exactly the expected source. False attribution counts outputs naming any other decoded source. Abstention means the source set was empty. Explicit source label reprints have a separate count. Known-answer checks count an answer pattern and an explanation pattern separately. The pattern checks were confirmed on all 18 reference answers, and their output requires individual review if wording varies or contradictory statements are present.

The CPU integrity check recovered all 12 historical marked references, abstained on all 6 clean references, and found both factual patterns in each of the 18 references. These checks concern the existing targets.

```powershell
python experiments/rkw_official_multibit/training/paired_r0/prepare.py D:/pycharm/CogniGuard-worktrees/rkw-risk-aware/experiments/rkw_risk_aware var/paired-r0
python experiments/rkw_official_multibit/training/paired_r0/score.py D:/pycharm/CogniGuard-worktrees/rkw-risk-aware/experiments/rkw_risk_aware var/paired-r0/evaluate.jsonl var/generated.jsonl var/paired-r0-scores
```
