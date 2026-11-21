"""Offline comparison and gated benchmark plans. Never launches a model implicitly."""

from __future__ import annotations

from .protocol import ModelIdentity, same_numeric_model


def compare_results(reference: dict, internal: dict) -> dict:
    same_model = same_numeric_model(
        ModelIdentity(**reference["model"]), ModelIdentity(**internal["model"])
    )
    same_input = reference["input_sha256"] == internal["input_sha256"]
    same_settings = reference["algorithm"] == internal["algorithm"]
    compare_fields = ["messages_sha256", "prompt_ids", "method", "generation"]
    mismatches = [
        name
        for name in compare_fields
        if name not in reference or name not in internal or reference[name] != internal[name]
    ]
    a, b = reference["generated_ids"], internal["generated_ids"]
    first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
    if first is None and len(a) != len(b):
        first = min(len(a), len(b))
    return {
        "status": "COMPARABLE_IDENTITY_ONLY"
        if same_model and same_input and same_settings and not mismatches
        else "NOT_STRICTLY_COMPARABLE",
        "same_numeric_model": same_model,
        "same_input": same_input,
        "same_algorithm": same_settings,
        "token_equal": a == b,
        "missing_or_different_control_fields": mismatches,
        "first_token_difference": first,
        "not_a_bug_claim": "Different kernels/devices can diverge even at matching settings.",
        "reference": {
            k: reference.get(k)
            for k in (
                "model",
                "output_tokens",
                "generation_seconds",
                "load_seconds",
                "tokens_per_second",
                "peak_musa_allocated_bytes",
            )
        },
        "internal": {
            k: internal.get(k)
            for k in (
                "model",
                "output_tokens",
                "generation_seconds",
                "load_seconds",
                "tokens_per_second",
                "peak_musa_allocated_bytes",
            )
        },
        "latency_scope_warning": "R18 runner time includes HTTP/logging/loading; not pure kernel time.",
    }


def throughput_plan(gates: dict, concurrency: int, model: ModelIdentity) -> dict:
    model.validate()
    if concurrency not in (2, 4, 8):
        raise ValueError("Only planned 2/4/8 concurrency levels")
    if any(gates.get(str(i)) != "PASS" for i in range(1, 6)):
        raise ValueError("All five remote gates must pass before a concurrency plan")
    return {
        "status": "PLAN_ONLY_NOT_RUN",
        "concurrency": concurrency,
        "tasks": concurrency,
        "max_new_tokens_per_task": 32,
        "model": model.__dict__,
        "requires_concurrent_engine_adapter": True,
        "HF_reference_engine_concurrency": 1,
        "no_performance_numbers_claimed": True,
    }
