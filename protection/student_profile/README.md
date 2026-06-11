# Student Profile Protection

This package contains the MM-FOPD student profile layer and the minimum
cross-layer integration pipeline.

- `src/fopd/`: task-aware profile selection and minimum context cards.
- `src/pipeline/`: integration pipeline that calls PB-C2-RAG through
  `protection.teacher_resource`.
- `data/`: student profile and question fixtures used by the minimum runnable
  demo.

Run commands from the CogniGuard repository root so the `protection` package is
resolved consistently.

Cross-layer schemas and utilities are provided by `protection.common`.

## Install

```bash
pip install -r protection/student_profile/requirements.txt
```

## Run Demo

```bash
python -m protection.student_profile.src.pipeline.run_demo \
  --profiles protection/student_profile/data/profiles.jsonl \
  --questions protection/student_profile/data/student_questions.jsonl \
  --resources protection/teacher_resource/data/teacher_resources.jsonl \
  --config protection/student_profile/configs/default.yaml \
  --out protection/student_profile/outputs/demo_results.jsonl
```

Set `COGNIGUARD_DISABLE_LLM=1` to use the deterministic fallback without
Ollama.

## Run Tests

```bash
pytest protection/student_profile/tests protection/teacher_resource/tests
```

Research evaluations and attacks live under the repository-level
`experiments/` package.

The pipeline exports `hsw_st_input.jsonl` for the Audit & Trace layer under
`protection/audit_trace`.
