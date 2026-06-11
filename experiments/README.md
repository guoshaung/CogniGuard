# CogniGuard Experiments

This directory contains research evaluation code rather than protection-layer
runtime logic.

## Layout

- `attacks/`: privacy, copyright reconstruction, permission bypass, profile
  pollution, and watermark robustness attacks.
- `attacks/data/`: prompts and fixtures used only by attack experiments.
- `attacks/tests/`: deterministic pytest regressions for known attack vectors.
- `ablation/`: batch runners for component-removal and configuration studies.
- `evaluation/`: FOPD, C2-RAG, and unified metric entry points.
- `results/`: generated experiment artifacts. This directory is git-ignored.

## Attack Regression Tests

```bash
pytest experiments/attacks/tests
```

## Copyright Reconstruction Experiment

```bash
python -m experiments.attacks.copyright_reconstruction
```

## Layer Evaluations

```bash
python -m experiments.evaluation.eval_fopd
python -m experiments.evaluation.eval_c2rag
python -m experiments.evaluation.eval_unified
```

## HSW-ST Ablations

Preview the four generated runs without loading a model:

```bash
python -m experiments.ablation.run_all_ablations --dry-run
```

Run the full suite:

```bash
python -m experiments.ablation.run_all_ablations --mode experiment
```
