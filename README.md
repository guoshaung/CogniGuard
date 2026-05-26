# CogniGuard

CogniGuard is a minimum runnable demo for a multi-agent personalized education protection system. The current system focuses on lifecycle protection around personalized tutoring rather than full-scale federated training.

## Protection Layers

- User side: FOPD performs task-aware minimum disclosure of student profile records and builds a small context card for the tutor agent.
- Teaching side: C2-RAG controls retrieval, copyright exposure budgets, return modes, variants, and source tracing for teaching resources.
- Model output side: HSW-ST applies watermarking, source binding, trace logs, and detection/evaluation for generated answers.

## Project Layout

- `fopd_c2rag_mvp/`: minimum demo for profile minimization, copyright-aware retrieval, multi-agent orchestration, metrics, and tests.
- `hsw_st_minimal/`: minimum implementation of hybrid semantic-aware watermarking and source tracing.
- `requirements.txt`: root convenience requirements file that points to the HSW-ST dependencies.

## Quick Start

Run the FOPD + C2-RAG demo:

```bash
cd fopd_c2rag_mvp
pip install -r requirements.txt
python -m src.pipeline.run_demo --profiles data/profiles.jsonl --questions data/student_questions.jsonl --resources data/teacher_resources.jsonl --config configs/default.yaml --out outputs/demo_results.jsonl
```

Run tests:

```bash
cd fopd_c2rag_mvp
pytest
```

Run the HSW-ST watermark demo:

```bash
cd hsw_st_minimal
pip install -r requirements.txt
python -m src.main --config configs/config.yaml
```

See the README files inside each module for detailed configuration notes.
