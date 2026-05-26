# CogniGuard

CogniGuard is a minimum runnable demo for a multi-agent personalized education protection system. The current system focuses on lifecycle protection around personalized tutoring rather than full-scale federated training.

## Protection Layers

- User side: FOPD performs task-aware minimum disclosure of student profile records and builds a small context card for the tutor agent.
- Teaching side: C2-RAG controls retrieval, copyright exposure budgets, return modes, variants, and source tracing for teaching resources.
- Model output side: HSW-ST applies watermarking, source binding, trace logs, and detection/evaluation for generated answers.

## Project Layout

- `backend/app/agents/`: protected LLM tutoring agent layer with TPCS-mediated communication.
- `fopd_c2rag_mvp/`: minimum demo for profile minimization, copyright-aware retrieval, multi-agent orchestration, metrics, and tests.
- `hsw_st_minimal/`: minimum implementation of hybrid semantic-aware watermarking and source tracing.
- `requirements.txt`: root convenience requirements file that points to the HSW-ST dependencies.

## LLM Agent Configuration

The backend agent layer can use MiniMax through its OpenAI-compatible chat API. Keep real keys out of git and configure them through environment variables or a local `.env` file:

```bash
MINIMAX_API_KEY=your_minimax_api_key_here
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_MODEL=MiniMax-M2.7
```

If no `MINIMAX_API_KEY` is present, the agents run with deterministic fallback outputs for local demos and tests.

## Quick Start

Generate synthetic multimodal student data:

```bash
python scripts/generate_synthetic_multimodal_data.py --student-count 30
```

The generator writes raw multimodal artifacts to `data/raw/` and MM-FOPD-safe context cards to `data/processed/profile_cards/`. Agent code should only consume the profile cards.

Run the protected tutoring pipeline demo:

```bash
python -m backend.app.demo.run_demo --case-index 0
```

The demo keeps the top-level architecture as three protection layers plus horizontal TPCS governance; the four LLM agents run only as controlled tutoring nodes.

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
