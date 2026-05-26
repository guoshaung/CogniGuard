# FOPD + C2-RAG MVP

This is a runnable minimum implementation for the first two innovation points:

- FOPD v0: task-aware minimum disclosure of student profile records.
- C2-RAG: copyright-aware retrieval with exposure budget, return policy, variant generation, and source trace.

The project can run with a local Ollama LLM. It still keeps the safety algorithms deterministic: FOPD performs profile minimization, C2-RAG performs copyright and exposure control, and HSW-ST handles watermark/trace binding.

The default local model is `qwen2.5:7b`, which is suitable for Chinese tutoring and fits common 8GB laptop GPUs in Ollama's quantized format.

## Install

```bash
cd fopd_c2rag_mvp
pip install -r requirements.txt
```

The code can run without `scikit-learn` because `src/common/text_utils.py` contains a pure Python TF-IDF fallback. Installing the requirements is still recommended for experiments.

## Run Demo

Start Ollama and make sure the model is installed:

```bash
ollama pull qwen2.5:7b
```

```bash
python -m src.pipeline.run_demo ^
  --profiles data/profiles.jsonl ^
  --questions data/student_questions.jsonl ^
  --resources data/teacher_resources.jsonl ^
  --config configs/default.yaml ^
  --out outputs/demo_results.jsonl
```

On macOS/Linux:

```bash
python -m src.pipeline.run_demo \
  --profiles data/profiles.jsonl \
  --questions data/student_questions.jsonl \
  --resources data/teacher_resources.jsonl \
  --config configs/default.yaml \
  --out outputs/demo_results.jsonl
```

Outputs:

- `outputs/demo_results.jsonl`
- `outputs/metrics_summary.json`
- `outputs/report.md`
- `outputs/watermark_logs.jsonl`
- `outputs/source_trace_logs.jsonl`
- `outputs/unified_trace_logs.jsonl`
- `outputs/hsw_st_input.jsonl`

`watermark_logs.jsonl` uses a pre-bound `watermark_id` so the C2-RAG answer can later be passed through HSW-ST. `source_trace_logs.jsonl` and `unified_trace_logs.jsonl` carry the same `answer_id`, `watermark_id`, and `trace_binding_id`, plus the C2-RAG `resource_id/chunk_id/return_mode/exposure` fields.

`hsw_st_input.jsonl` converts the C2-RAG final answers into the dataset shape used by `../hsw_st_minimal`: `sample_id/question/draft_answer/source_trace/protected_*`. Point HSW-ST's `data.dataset_path` at this file to watermark the C2-RAG answers while preserving the same source trace.

Each demo row also contains `agent_logs`:

- `AG1`: learner/task modeling agent, connected to FOPD.
- `AG2_request`: tutor planner, turns FOPD `context_card` into a C2-RAG request.
- `AG2_answer`: tutor answer agent, only sees C2-RAG controlled output.
- `AG3`: copyright resource agent, explains C2-RAG return policy.
- `AG4`: watermark/trace agent, explains HSW-ST binding.

Set `COGNIGUARD_DISABLE_LLM=1` to run the deterministic fallback without Ollama.

## Run Evaluations

```bash
python -m src.experiments.eval_fopd --config configs/default.yaml
python -m src.experiments.eval_c2rag --config configs/default.yaml
python -m src.experiments.eval_unified --config configs/default.yaml
python -m src.experiments.simulate_attacks --config configs/default.yaml
```

## Run Tests

```bash
pytest
```

## Boundary With HSW-ST

This directory is independent from `../hsw_st_minimal`. It does not modify or import the watermark implementation, so it can be developed while another agent works on HSW-ST.
