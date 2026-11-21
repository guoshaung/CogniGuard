"""Synthetic engineering controls; never counted as model/GPU experiments."""

from __future__ import annotations

import ast
import hashlib
import json
import struct
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from protection.audit_trace.remote_worker.benchmark import compare_results, throughput_plan
from protection.audit_trace.remote_worker.controller import Controller, make_task
from protection.audit_trace.remote_worker.engine import verify_model_files
from protection.audit_trace.remote_worker.kgw import Greenlist, detect_ids
from protection.audit_trace.remote_worker.preflight import fingerprint, inventory_commands
from protection.audit_trace.remote_worker.protocol import ModelIdentity, Task, canonical, digest
from protection.audit_trace.remote_worker.source_api import generate_original
from protection.audit_trace.remote_worker.store import JobStore
from protection.audit_trace.remote_worker.transport import RemoteConfig, SSHTransport
from protection.audit_trace.remote_worker.worker import run_task

KEY = "SYNTHETIC_CONTROL_KEY_NOT_USED_IN_RESEARCH"
ORIGINAL = "TEST ONLY: Q=CV，给定C和V求电荷。"
CONTRACT = {"status": "SYNTHETIC_ENGINEERING_CONTROL_NOT_RESEARCH", "required": ["Q=CV"]}
REVIEW = {"overall": "PASS", "public_text_sha256": digest(ORIGINAL.encode())}
MODEL = ModelIdentity("Qwen/Qwen2.5-7B-Instruct", "control-revision", "fp16", "a" * 64, "b" * 64)


def task(method="clean"):
    return make_task(ORIGINAL, CONTRACT, REVIEW, MODEL, method, digest(KEY.encode()))


def fake_result(t):
    """No inference: only a transport/lifecycle fixture."""
    return {
        "status": "COMPLETED",
        "method": t.method,
        "input_sha256": t.input_sha256,
        "messages_sha256": t.messages_sha256,
        "model": t.to_dict()["model"],
        "algorithm": {
            "gamma": 0.25,
            "delta": 2.0,
            "window": 4,
            "prf": t.prf,
            "key_sha256": t.key_sha256,
        },
        "generation": {
            "mode": "greedy",
            "seed": 0,
            "max_new_tokens": 32,
            "num_beams": 1,
            "repetition_penalty": 1.0,
            "backend": "transformers-torch_musa-internal",
        },
        "text": "fixture",
        "text_sha256": digest(b"fixture"),
        "prompt_ids": [1, 2, 3, 4],
        "prompt_tokens": 4,
        "generated_ids": [20, 21],
        "returned_ids": [20, 21, 151645],
        "output_tokens": 2,
        "stop_reason": "eos",
        "callback_calls": 0,
        "callback_context4": [],
        "callback_green_sha256": [],
    }


def test_task_roundtrip_and_source_required():
    t = task()
    assert Task.from_dict(json.loads(canonical(t.to_dict()))) == t
    assert ORIGINAL in t.messages[1]["content"]
    assert KEY not in canonical(t.to_dict()).decode()
    with pytest.raises(ValueError):
        make_task(
            ORIGINAL, CONTRACT, {**REVIEW, "overall": "UNKNOWN"}, MODEL, "kgw", digest(KEY.encode())
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_text", "changed"),
        ("delta", 1),
        ("gamma", 0.5),
        ("window", 3),
        ("threshold", 2.9),
        ("output_relpath", "../../escape.json"),
        ("max_new_tokens", 1025),
        ("method", "selective"),
        ("seed", True),
    ],
)
def test_frozen_parameters_reject_mutation(field, value):
    with pytest.raises(ValueError):
        replace(task(), **{field: value}).validate()


def test_exact_original_prf_and_bounded_cache():
    source = Path(__file__).parents[2] / "src/watermark_logits_processor.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in {"_context_hash", "greenlist_for_prefix"}
    ]
    scope = {"hashlib": hashlib, "struct": struct, "np": np}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), scope)
    prf = Greenlist(KEY, cache_size=2)
    for ids in [[], [1], [1, 2], [1, 2, 3, 4], [99, 1, 2, 3, 4], [151643, 120, 301, 900]]:
        actual = prf.indices(ids)
        expected = scope["greenlist_for_prefix"](ids, 151643, 0.25, KEY, 4)
        assert actual.tolist() == sorted(expected)
        assert len(prf._cache) <= 2
    assert np.array_equal(prf.indices([1, 2, 3, 4]), prf.indices([99, 1, 2, 3, 4]))


def test_public_scoring_counts_repeats_and_initial_four():
    assert detect_ids([1, 2, 3, 4], KEY)["status"] == "INSUFFICIENT"
    ids = [10, 20, 30, 40, 50] * 7
    result = detect_ids(ids, KEY)
    reference = Greenlist(KEY, 0)
    expected_g = sum(ids[j] in reference.indices(ids[j - 4 : j]) for j in range(4, len(ids)))
    assert result["T"] == len(ids) - 4 and result["G"] == expected_g
    assert result["repeated_positions"] > 0
    assert result["detected"] == (result["z"] > 3)


def test_worker_at_most_once_concurrent_claims(tmp_path):
    t = task()
    calls = []

    class FixtureEngine:
        def generate(self, t, key):
            calls.append(t.task_id)
            return fake_result(t)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: run_task(t, tmp_path, FixtureEngine, None), range(8)))
    assert calls == [t.task_id]
    assert all(r["status"] in {"COMPLETED", "RUNNING_OR_UNKNOWN"} for r in results)
    assert run_task(t, tmp_path, FixtureEngine, None)["status"] == "COMPLETED"
    assert len(calls) == 1


def test_worker_failed_and_stale_jobs_do_not_retry(tmp_path):
    t = task()
    calls = []

    def failing():
        calls.append(1)
        raise RuntimeError("fixture failure")

    assert run_task(t, tmp_path, failing, None)["status"] == "FAILED"
    assert run_task(t, tmp_path, failing, None)["status"] == "FAILED"
    assert len(calls) == 1
    other = task()
    assert JobStore(tmp_path).claim(other)[0]
    assert run_task(other, tmp_path, failing, None)["status"] == "RUNNING_OR_UNKNOWN"
    assert len(calls) == 1
    with pytest.raises(ValueError):
        JobStore(tmp_path).claim(replace(other, seed=123))
    partial = task()
    folder = tmp_path / partial.task_id
    folder.mkdir()
    (folder / "claim.json").write_bytes(b'{"partial":')
    assert run_task(partial, tmp_path, failing, None)["status"] == "RUNNING_OR_UNKNOWN"
    assert len(calls) == 1


def test_controller_acceptance_recovery_and_no_double_count(tmp_path):
    c = Controller(tmp_path / "controller")
    c.freeze_source(ORIGINAL, CONTRACT, REVIEW)
    t = task()
    c.register(t)
    c.register(t)
    c.mark_submitted(t)
    with pytest.raises(ValueError):
        c.mark_submitted(t)
    result = run_task(
        t,
        tmp_path / "worker",
        lambda: type("Fixture", (), {"generate": lambda s, t, k: fake_result(t)})(),
        None,
    )
    raw = canonical(result)
    c.accept(t, raw, digest(raw))
    c.accept(t, raw, digest(raw))
    assert c.completed_count() == 1
    assert (c.root / t.output_relpath).read_bytes() == raw
    with pytest.raises(ValueError):
        c.accept(t, raw, "0" * 64)
    bad = {**result, "input_sha256": "0" * 64}
    with pytest.raises(ValueError):
        c.accept(t, canonical(bad), digest(canonical(bad)))
    bad = {**result, "generated_ids": [20]}
    with pytest.raises(ValueError):
        c.accept(t, canonical(bad), digest(canonical(bad)))


def test_existing_source_review_not_replaced(tmp_path):
    c = Controller(tmp_path)
    c.freeze_source(ORIGINAL, CONTRACT, REVIEW)
    with pytest.raises(ValueError):
        c.freeze_source(ORIGINAL, {"changed": True}, REVIEW)


def test_model_manifest_and_gguf_branch(tmp_path):
    files = {
        "config.json": b"{}",
        "tokenizer.json": b"{}",
        "tokenizer_config.json": b"{}",
        "model.safetensors": b"NOT_REAL_WEIGHTS_FILE_HASH_CONTROL_ONLY",
    }
    for name, raw in files.items():
        (tmp_path / name).write_bytes(raw)
    manifest = {"files": {n: digest(b) for n, b in files.items()}}
    identity = replace(
        MODEL, manifest_sha256=digest(canonical(manifest)), tokenizer_sha256=digest(b"{}")
    )
    verify_model_files(tmp_path, manifest, identity)
    (tmp_path / "unfrozen.safetensors").write_bytes(b"unexpected weights")
    with pytest.raises(ValueError, match="Unfrozen loadable"):
        verify_model_files(tmp_path, manifest, identity)
    (tmp_path / "unfrozen.safetensors").unlink()
    (tmp_path / "model.safetensors").write_bytes(b"changed")
    with pytest.raises(ValueError):
        verify_model_files(tmp_path, manifest, identity)
    a = {
        "model": MODEL.__dict__,
        "input_sha256": "x",
        "algorithm": {"delta": 2},
        "generated_ids": [1],
    }
    b = {**a, "model": replace(MODEL, precision="gguf-q4_k_m").__dict__}
    assert compare_results(a, b)["status"] == "NOT_STRICTLY_COMPARABLE"
    assert compare_results(a, a)["status"] == "NOT_STRICTLY_COMPARABLE"


def test_benchmark_gates_do_not_launch_models():
    with pytest.raises(ValueError):
        throughput_plan({"1": "PASS"}, 2, MODEL)
    p = throughput_plan({str(i): "PASS" for i in range(1, 6)}, 8, MODEL)
    assert p["status"] == "PLAN_ONLY_NOT_RUN" and p["tasks"] == 8


def test_ssh_plan_quotes_paths_and_requires_pinned_fingerprint():
    class Key:
        def asbytes(self):
            return b"synthetic-host-key"

    class Transport:
        def get_remote_server_key(self):
            return Key()

    class Client:
        def get_transport(self):
            return Transport()

    config = RemoteConfig(
        "fixture.invalid",
        22,
        "test",
        fingerprint(Key()),
        "/usr/bin/python3",
        "/tmp/hsw space",
        "/tmp/model;not-a-command",
        "/tmp/model-manifest.json",
    )
    sender = SSHTransport(config, Client())
    assert sender.submit(task())["status"] == "PLAN_ONLY"
    assert "'/tmp/model;not-a-command'" in sender.command(task())
    with pytest.raises(ValueError):
        SSHTransport(replace(config, host_fingerprint="SHA256:wrong"), Client())
    assert all("sudo " not in x and "pip install" not in x for x in inventory_commands().values())


def test_source_api_single_attempt_and_no_credential_in_result():
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, n):
            return json.dumps(
                {
                    "model": "fixture",
                    "choices": [
                        {"message": {"content": "fixture source"}, "finish_reason": "stop"}
                    ],
                    "usage": {"total_tokens": 5},
                }
            ).encode()

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            return Response()

    result = generate_original(
        "https://fixture.invalid/v1", "fixture", [], "TEST_ONLY_CREDENTIAL", opener=Opener()
    )
    assert len(calls) == 1 and "TEST_ONLY_CREDENTIAL" not in json.dumps(result)

    class Failure:
        def open(self, *args, **kwargs):
            calls.append(1)
            raise RuntimeError("fixture")

    with pytest.raises(RuntimeError):
        generate_original(
            "https://fixture.invalid/v1", "fixture", [], "TEST_ONLY_CREDENTIAL", opener=Failure()
        )
    assert len(calls) == 2


def test_internal_tensor_callback_matches_original_bias_and_request_isolation():
    torch = pytest.importorskip("torch")
    from protection.audit_trace.remote_worker.kgw import InternalKGW

    first, second = InternalKGW(KEY), InternalKGW(KEY)
    histories = [[1, 2, 3, 4], [4, 3, 2, 1], [1, 2, 3, 4, 5]]
    for processor, ids in [(first, histories[0]), (second, histories[1]), (first, histories[2])]:
        scores = torch.zeros((1, 151936))
        out = processor(torch.tensor([ids]), scores)
        expected = Greenlist(KEY).indices(ids).tolist()
        assert torch.nonzero(out[0], as_tuple=False).flatten().tolist() == expected
        assert torch.all(out[0, expected] == 2)
        assert torch.all(out[0, 151643:] == 0)
    assert first.calls == 2 and second.calls == 1
    assert first.contexts == [histories[0], histories[2][-4:]]
    with pytest.raises(ValueError):
        first(torch.tensor([[1, 2], [3, 4]]), torch.zeros((2, 151643)))
