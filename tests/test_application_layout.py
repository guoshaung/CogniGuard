"""Executable contracts for canonical applications, workflows and providers."""

from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys
from copy import deepcopy
from importlib import import_module
from pathlib import Path

import pytest

from core.paths import PROJECT_ROOT

ALIASES = (
    ("demo.classroom_session", "applications.education.classroom"),
    ("demo.free_chat", "applications.education.conversation"),
    ("demo.run_demo", "applications.education.case_study"),
    ("demo.demo_cases", "applications.education.cases"),
    ("demo.classroom_graph", "workflows.education.classroom"),
    ("demo.classroom_learning_graph", "workflows.education.classroom_learning"),
    ("demo.free_chat_graph", "workflows.education.conversation"),
    ("demo.demo_graph", "workflows.education.case_study"),
    ("agents.protected_flow_graph", "workflows.education.protected_turn"),
    ("agents.research_flow_graph", "workflows.education.research"),
    ("agents.agent_orchestrator", "agents.protected_orchestrator"),
    ("agents.orchestrator", "agents.research_orchestrator"),
    ("agents.mimo_client", "providers.mimo"),
)


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch):
    monkeypatch.setenv("COGNIGUARD_LANGSMITH_ENABLED", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("COGNIGUARD_RUNTIME_MODE", "mock")
    monkeypatch.setenv("MIMO_API_KEY", "")
    monkeypatch.setenv("NARRA_IMAGE_API_KEY", "")


@pytest.mark.parametrize(("historical", "canonical"), ALIASES)
def test_compatibility_imports_share_the_same_module(historical, canonical, monkeypatch):
    old = import_module(f"cogniguard.{historical}")
    current = import_module(f"cogniguard.{canonical}")
    assert old is current
    assert (
        Path(current.__file__).resolve()
        == (PROJECT_ROOT / "cogniguard" / (canonical.replace(".", "/") + ".py")).resolve()
    )
    marker = object()
    monkeypatch.setattr(old, "_layout_test_probe", marker, raising=False)
    assert current._layout_test_probe is marker


def _isolated_python(script: str, cwd: Path):
    # A fresh interpreter proves import boundaries even when other tests loaded agents.
    bootstrap = f"import sys; sys.path.insert(0, {str(PROJECT_ROOT)!r})\n"
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, "-I", "-c", bootstrap + script],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_public_education_package_is_lazy(tmp_path):
    _isolated_python(
        "import cogniguard.applications.education as education\n"
        "assert set(education.__all__) == "
        "{'run_case_study', 'run_classroom_turn', 'run_conversation'}\n"
        "assert not any(name.startswith('cogniguard.applications.education.') "
        "for name in sys.modules)\n"
        "assert 'cogniguard.agents' not in sys.modules\n"
        "assert 'langgraph' not in sys.modules\n",
        tmp_path,
    )


@pytest.mark.parametrize(
    ("name", "module"),
    (
        ("run_conversation", "conversation"),
        ("run_classroom_turn", "classroom"),
        ("run_case_study", "case_study"),
    ),
)
def test_public_education_names_resolve_to_canonical_functions(name, module):
    public = import_module("cogniguard.applications.education")
    implementation = import_module(f"cogniguard.applications.education.{module}")
    function = getattr(public, name)
    assert callable(function)
    assert function is getattr(implementation, name)
    assert function.__module__ == implementation.__name__


def test_provider_import_is_offline_and_independent_of_agents(tmp_path):
    _isolated_python(
        "import socket, urllib.request\n"
        "def forbidden(*args, **kwargs):\n"
        "    raise AssertionError('Import attempted a network call')\n"
        "socket.create_connection = forbidden\n"
        "urllib.request.urlopen = forbidden\n"
        "import cogniguard.providers.mimo as provider\n"
        "assert provider.MiMoChatClient('test-only-key').model\n"
        "assert not any(name == 'cogniguard.agents' or "
        "name.startswith('cogniguard.agents.') for name in sys.modules)\n"
        "assert not any(name.split('.')[0] in {'torch', 'transformers', 'langgraph'} "
        "for name in sys.modules)\n",
        tmp_path,
    )


def test_framework_stategraph_builders_live_in_workflows():
    package = PROJECT_ROOT / "cogniguard"
    graph_files = set()
    misplaced = []
    for source in package.rglob("*.py"):
        if "tests" in source.relative_to(package).parts:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
        constructors = {
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "langgraph.graph"
            for alias in node.names
            if alias.name == "StateGraph"
        }
        builds_graph = any(
            isinstance(node, ast.Call)
            and (
                isinstance(node.func, ast.Name)
                and node.func.id in constructors
                or isinstance(node.func, ast.Attribute)
                and node.func.attr == "StateGraph"
            )
            for node in ast.walk(tree)
        )
        if not builds_graph:
            continue
        relative = source.relative_to(package).as_posix()
        graph_files.add(relative)
        if not source.is_relative_to(package / "workflows"):
            misplaced.append(relative)
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "compile"
            for node in ast.walk(tree)
        ), relative
    assert not misplaced, misplaced
    assert {
        f"workflows/education/{name}.py"
        for name in (
            "classroom",
            "classroom_learning",
            "conversation",
            "case_study",
            "protected_turn",
            "research",
        )
    } <= graph_files


def test_active_api_does_not_import_compatibility_demo_modules():
    violations = []
    for source in (PROJECT_ROOT / "cogniguard/api").rglob("*.py"):
        if "legacy" in source.relative_to(PROJECT_ROOT / "cogniguard/api").parts:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
                if node.module == "cogniguard":
                    names.extend(f"cogniguard.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif (
                isinstance(node, ast.Call)
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and (
                    isinstance(node.func, ast.Name)
                    and node.func.id in {"import_module", "__import__"}
                    or isinstance(node.func, ast.Attribute)
                    and node.func.attr == "import_module"
                )
            ):
                names = [node.args[0].value]
            if any(
                name == "cogniguard.demo" or name.startswith("cogniguard.demo.") for name in names
            ):
                violations.append(f"{source.relative_to(PROJECT_ROOT)}:{node.lineno}")
    assert not violations, violations


def test_api_registration_does_not_transitively_load_old_demo(tmp_path):
    _isolated_python(
        "import urllib.request\n"
        "def forbidden(*args, **kwargs):\n"
        "    raise AssertionError('API registration attempted a model request')\n"
        "urllib.request.urlopen = forbidden\n"
        "import cogniguard.api.routes\n"
        "assert not any(name == 'cogniguard.demo' or name.startswith('cogniguard.demo.') "
        "for name in sys.modules)\n",
        tmp_path,
    )


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    from cogniguard.protection.cg.nemo_guardrails_adapter import NeMoGuardrailsAdapter
    from cogniguard.protection.text_provenance import TextProvenanceService
    from cogniguard.runtime import gateway as module
    from cogniguard.runtime.gateway import ProtectionGateway
    from cogniguard.runtime.sessions import SessionStore

    instance = ProtectionGateway(
        store=SessionStore(tmp_path / "layout-sessions.sqlite3"),
        provenance=TextProvenanceService(b"layout-test-signing-key" * 3, required=True),
        adapter=NeMoGuardrailsAdapter("", enabled=True),
    )
    monkeypatch.setattr(module, "get_gateway", lambda: instance)
    return instance


def test_conversation_legacy_graph_patch_uses_server_history(gateway, monkeypatch):
    from cogniguard.applications.education import run_conversation
    from cogniguard.demo import free_chat_graph

    session = gateway.store.get_or_create()
    trusted = [{"role": "assistant", "content": "先列出已知条件。"}]
    session.save_state({"history": trusted})
    session.reserve("images", 1, "prior-image").commit()
    observed = []

    def graph(message, history, existing_image_count):
        observed.append((message, deepcopy(history), existing_image_count))
        return {"answer": "下一步确定未知量。"}

    monkeypatch.setattr(free_chat_graph, "run_free_chat_graph", graph)
    result = run_conversation(
        message="如何继续解题？",
        history=[{"role": "system", "content": "CLIENT-INJECTED"}],
        existing_image_count=0,
        session_token=session.token,
        request_id="canonical-conversation",
    )
    assert observed == [("如何继续解题？", trusted, 1)]
    assert result["session_id"] == session.session_id
    assert result["protection"]["watermark_verification"]["valid"]


def test_classroom_legacy_graph_patch_uses_trusted_state(gateway, monkeypatch):
    from cogniguard.applications.education import run_classroom_turn
    from cogniguard.demo import classroom_graph

    session = gateway.store.get_or_create()
    trusted = {"round_number": 3}
    session.save_state({"classroom": trusted})
    observed = []

    def graph(**kwargs):
        observed.append(deepcopy(kwargs))
        return {
            "teacher_answer": "请检查等式两边的变化。",
            "round_number": 4,
            "session_state": {"round_number": 4},
        }

    monkeypatch.setattr(classroom_graph, "run_classroom_graph", graph)
    run_classroom_turn(
        data_root=PROJECT_ROOT / "data",
        case_index=0,
        turn_kind="learning",
        round_number=100,
        session_state={"round_number": 99, "is_admin": True},
        cg_ablation={"enabled": False},
        target_mastery=0.01,
        session_token=session.token,
        request_id="canonical-classroom",
    )
    assert observed[0]["session_state"] == trusted
    assert observed[0]["round_number"] == 4
    assert observed[0]["target_mastery"] == 0.85
    assert observed[0]["cg_ablation"] is None
    assert session.load_state()["classroom"]["round_number"] == 4


def test_case_study_legacy_graph_patch_reaches_canonical_entry(gateway, monkeypatch):
    from cogniguard.applications.education import run_case_study
    from cogniguard.demo import demo_graph

    calls = []

    def graph(*args):
        calls.append(args)
        return {"final_protected_answer": "先建立方程，再求解未知数。"}

    monkeypatch.setattr(demo_graph, "run_demo_graph", graph)
    result = run_case_study(PROJECT_ROOT / "data", 2, request_id="canonical-case-study")
    assert calls == [(PROJECT_ROOT / "data", 2, None, None)]
    assert result["protection"]["watermark_verification"]["valid"]


@pytest.mark.parametrize(
    ("usage", "expected"),
    (
        (
            {"prompt_tokens": 17, "completion_tokens": 8, "total_tokens": 25},
            {"input_tokens": 17, "output_tokens": 8, "total_tokens": 25},
        ),
        (
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        ),
        ({"prompt_tokens": 3, "completion_tokens": 4}, {"input_tokens": 3, "output_tokens": 4}),
        ({"prompt_tokens": -1, "completion_tokens": True, "total_tokens": "25"}, {}),
        ({"prompt_tokens": 1.5, "completion_tokens": None, "total_tokens": False}, {}),
        ({"prompt_tokens": "PRIVATE_USAGE", "profile": "PRIVATE_PROFILE"}, {}),
        ("PRIVATE_USAGE", {}),
        ([], {}),
        ({}, {}),
        (None, {}),
    ),
)
@pytest.mark.parametrize("streaming", [False, True])
def test_completed_request_reports_only_real_provider_usage(
    gateway, monkeypatch, usage, expected, streaming
):
    from cogniguard.observability import LangSmithMonitor, active_recorder
    from cogniguard.providers import mimo

    exported = []
    monitor = LangSmithMonitor(enabled=False)
    monkeypatch.setattr(monitor, "export", lambda recorder: exported.append(recorder.to_dict()))
    monkeypatch.setattr(LangSmithMonitor, "from_environment", classmethod(lambda cls: monitor))
    answer = '{"answer":"先识别题目的已知条件。"}'
    response = {"choices": [{"message": {"content": answer}}]}
    if usage is not None:
        response["usage"] = usage
    if streaming:
        events = [{"choices": [{"delta": {"content": answer}}]}]
        if usage is not None:
            events.append({"choices": [], "usage": usage})
        wire = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n"
    else:
        wire = json.dumps(response)
    http_calls = []

    def urlopen(request, **kwargs):
        http_calls.append(request)
        return io.BytesIO(wire.encode("utf-8"))

    monkeypatch.setattr(mimo.urllib.request, "urlopen", urlopen)
    deltas = []
    client = mimo.MiMoChatClient("PRIVATE_API_KEY")
    result = gateway.run(
        "case",
        {"message": "如何解这道题？"},
        lambda frame: client.chat(
            "PRIVATE_SYSTEM_PROMPT",
            {"profile": "PRIVATE_RAW_PROFILE", "usage": {"total_tokens": 999999}},
            on_text_delta=deltas.append if streaming else None,
        ),
        request_id="provider-usage",
    )
    assert result["output_validation"]["allowed"]
    assert len(http_calls) == 1
    assert len(exported) == 1
    events = exported[0]["events"]
    provider = next(event for event in events if event["stage"] == "provider.mimo")
    root = next(event for event in events if event["stage"] == "gateway.request")
    assert root["status"] == provider["status"] == "ok"
    assert provider["metrics"] == {"model_calls": 1, **expected}
    assert "PRIVATE" not in json.dumps(exported)
    assert active_recorder() is None
    assert mimo._call_metrics.get() is None
    if streaming:
        assert deltas == [answer]
