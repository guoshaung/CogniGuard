from __future__ import annotations

import json
from dataclasses import replace

from experiments.c2rag_v3.core import (
    C2RAGConfig,
    C2RAGV3,
    ResourceDocument,
    StructureAwareChunker,
)
from experiments.c2rag_v3.evaluator import HiddenCase, OfflineEvaluator, SemanticEvaluator
from experiments.c2rag_v3.dataset import build_isolated_development_fixture, load_isolated_dev_sessions


def document(text: str, *, allowed_use: tuple[str, ...] = ("tutoring",), document_id: str = "doc-1") -> ResourceDocument:
    return ResourceDocument(
        document_id=document_id,
        parent_id=f"parent-{document_id}",
        section_id=f"section-{document_id}",
        text=text,
        title="algebra",
        owner="owner-1",
        license="restricted",
        copyright_level=0.9,
        allowed_roles=("student", "teacher", "copyright_agent", "auditor"),
        allowed_use=allowed_use,
        source_hash="source-hash",
        source_family="family-1",
        semantic_topic="algebra",
        knowledge_units=("algebra", "answer"),
    )


def test_structure_aware_chunking_preserves_metadata() -> None:
    chunks = StructureAwareChunker(max_tokens=20, overlap=2).chunk(document("Title: Linear algebra. Question: Solve x + 1 = 2. Answer: x = 1."))
    assert {chunk.section_type for chunk in chunks} == {"title", "question", "answer"}
    assert all(chunk.source_hash == "source-hash" for chunk in chunks)
    assert all(chunk.parent_id == "parent-doc-1" for chunk in chunks)


def test_full_v3_has_bm25_dense_rrf_and_reranker() -> None:
    engine = C2RAGV3([document("Question: Solve algebra equation. Answer: x equals one.")])
    result = engine.run_round(session_id="s1", round_id=1, identity="teacher", query="algebra equation", method="full_c2rag_v3")
    assert engine.mechanism_snapshot("full_c2rag_v3")["bm25_enabled"]
    assert engine.mechanism_snapshot("full_c2rag_v3")["dense_embedding_enabled"]
    assert engine.mechanism_snapshot("full_c2rag_v3")["rrf_enabled"]
    assert result.selected_chunks
    assert result.committed_cost == result.actual_cost


def test_metadata_authorization_happens_before_retrieval() -> None:
    restricted = document("Question: restricted algebra source.", allowed_use=("research",), document_id="restricted")
    allowed = document("Question: restricted algebra teaching source.", document_id="allowed")
    engine = C2RAGV3([restricted, allowed])
    result = engine.run_round(session_id="s1", round_id=1, identity="student", query="restricted algebra", role="student", purpose="tutoring", method="full_c2rag_v3")
    assert not result.refusal
    assert result.selected_chunks
    assert all(item["document_id"] != "restricted" for item in result.selected_chunks)


def test_actual_cost_not_planned_cost() -> None:
    engine = C2RAGV3([document("Question: algebra. Answer: x equals one.")], C2RAGConfig(max_quote_tokens=2))
    result = engine.run_round(session_id="s1", round_id=1, identity="teacher", query="algebra", method="advanced_rag_no_defense")
    assert result.actual_cost >= 0.0
    assert result.committed_cost == result.actual_cost
    assert result.committed_cost != result.estimated_cost or result.estimated_cost == 0.0


def test_baseline_snapshots_do_not_inherit_full_state() -> None:
    engine = C2RAGV3([document("Question: algebra. Answer: x equals one.")])
    no_budget = engine.mechanism_snapshot("c2rag_without_cumulative_budget")
    no_history = engine.mechanism_snapshot("c2rag_without_reconstruction_history")
    full = engine.mechanism_snapshot("full_c2rag_v3")
    assert not no_budget["cumulative_budget_enabled"]
    assert not no_history["reconstruction_history_enabled"]
    assert full["cumulative_budget_enabled"] and full["reconstruction_history_enabled"]


def test_hidden_labels_are_posthoc_only() -> None:
    engine = C2RAGV3([document("Question: algebra. Answer: x equals one.")])
    result = engine.run_round(session_id="s1", round_id=1, identity="teacher", query="algebra", method="full_c2rag_v3")
    runtime_record = result.to_dict()
    assert "attack_family" not in runtime_record
    assert "is_attack" not in runtime_record
    hidden = HiddenCase("case-1", "s1", document("Question: algebra.").text, "family-1", ("algebra",), True, "copyright_extraction", False)
    evaluated = OfflineEvaluator().evaluate_session(hidden, [result])
    assert evaluated["attack_family"] == "copyright_extraction"


def test_isolated_fixture_keeps_security_labels_out_of_public_runtime(tmp_path) -> None:
    source_root = tmp_path / "source"
    evaluation = source_root / "evaluation" / "data"
    resources = source_root / "teacher_resource" / "data"
    evaluation.mkdir(parents=True)
    resources.mkdir(parents=True)
    episode = {
        "episode_id": "case-1",
        "condition": "attack",
        "attack_family": "copyright_extraction",
        "user_request": "request",
        "resource_id": "resource-1",
        "seed": 7,
    }
    resource = {
        "resource_id": "resource-1",
        "chunk_id": "chunk-1",
        "content": "Question: algebra. Answer: x equals one.",
        "knowledge": "algebra",
        "difficulty": "basic",
        "resource_family_id": "family-1",
        "rights_metadata": {"rights_status": "open_license"},
        "access_policy": {"allowed_roles": ["teacher"], "allowed_purposes": ["security_evaluation"]},
        "provenance": {"source_hash": "hash-1"},
    }
    (evaluation / "episodes.jsonl").write_text(json.dumps(episode) + "\n", encoding="utf-8")
    (resources / "teacher_resources.jsonl").write_text(json.dumps(resource) + "\n", encoding="utf-8")
    fixture = tmp_path / "fixture"
    build_isolated_development_fixture(source_root, fixture)
    public = json.loads((fixture / "public_sessions.jsonl").read_text(encoding="utf-8").splitlines()[0])
    hidden = json.loads((fixture / "hidden_cases.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert not {"attack_family", "is_attack", "source_text"}.intersection(public)
    assert {"attack_family", "is_attack", "source_text"}.issubset(hidden)
    sessions = load_isolated_dev_sessions(source_root, fixture)
    assert sessions[0].public_queries


def test_target_resource_is_not_replaced_by_another_document() -> None:
    first = document("Question: unrelated geometry. Answer: area.", document_id="wrong")
    target = document("Question: algebra. Answer: x equals one.", document_id="target")
    engine = C2RAGV3([first, target])
    result = engine.run_round(session_id="s1", round_id=1, identity="teacher", query="algebra", target_resource_id="target")
    assert result.selected_chunks
    assert all(item["document_id"] == "target" for item in result.selected_chunks)


def test_independent_session_order_is_invariant() -> None:
    sessions = [("s-a", "principal-a", "algebra"), ("s-b", "principal-b", "geometry")]

    def run(order):
        engine = C2RAGV3([document("Question: algebra. Answer: x equals one.", document_id="a"), document("Question: geometry. Answer: area.", document_id="b")])
        results = {}
        for session_id, principal, query in order:
            result = engine.run_round(session_id=session_id, round_id=1, identity=principal, principal_id=principal, query=query, target_resource_id="a" if principal.endswith("a") else "b")
            results[session_id] = (result.released_answer, result.actual_cost, result.session_cost_after, result.cross_session_cost_after)
        return results

    assert run(sessions) == run(list(reversed(sessions)))


def test_linked_budget_has_no_double_counting() -> None:
    engine = C2RAGV3([document("Question: algebra. Answer: x equals one.", document_id="a")])
    first = engine.run_round(session_id="s-a", round_id=1, identity="p", principal_id="p", cross_session_linked=True, query="algebra", target_resource_id="a")
    second = engine.run_round(session_id="s-b", round_id=1, identity="p", principal_id="p", cross_session_linked=True, query="algebra", target_resource_id="a")
    assert first.cross_session_cost_after == first.actual_cost
    assert second.cross_session_cost_before == first.cross_session_cost_after
    assert second.cross_session_cost_after == first.actual_cost + second.actual_cost


def test_each_ablation_removes_one_component_only() -> None:
    engine = C2RAGV3([document("Question: algebra. Answer: x equals one.")])
    full = engine.mechanism_snapshot("full_c2rag_v3")
    for method, component in [("c2rag_without_provenance", "provenance_enabled"), ("c2rag_without_cumulative_budget", "cumulative_budget_enabled"), ("c2rag_without_reconstruction_history", "reconstruction_history_enabled")]:
        snapshot = engine.mechanism_snapshot(method)
        assert [key for key in full if full[key] != snapshot[key]] == [component]


def test_reranking_and_static_excerpt_use_distinct_paths() -> None:
    engine = C2RAGV3([document("Question: algebra. Answer: x equals one.")])
    static = engine.run_round(session_id="s1", round_id=1, identity="teacher", query="algebra", method="static_excerpt")
    rerank = engine.run_round(session_id="s2", round_id=1, identity="teacher", query="algebra", method="reranking_protection")
    assert static.planned_action["action"] == "minimal_excerpt"
    assert rerank.planned_action["action"] == "controlled_quote"


def test_runtime_invokes_shared_generator() -> None:
    class SpyGenerator:
        def __init__(self):
            self.calls = 0

        def generate(self, query, evidence, action, topic):
            from experiments.c2rag_v3.generator import GenerationOutput
            self.calls += 1
            return GenerationOutput("generated", 1, 2, 1, 0.1)

    engine = C2RAGV3([document("Question: algebra. Answer: x equals one.")])
    spy = SpyGenerator()
    engine.generator = spy
    engine.run_round(session_id="s1", round_id=1, identity="teacher", query="algebra")
    assert spy.calls == 1


def test_semantic_evaluator_is_separate_from_lexical_cosine() -> None:
    evaluator = OfflineEvaluator(SemanticEvaluator(backend="lexical"))
    source = "A linear equation is solved by isolating the unknown on one side."
    assert evaluator.semantic.similarity("Isolate the variable to solve the equation.", source) >= 0.0
    assert evaluator.semantic.manifest()["backend"] == "lexical"


def test_ndcg_uses_log_discount_not_reciprocal_rank() -> None:
    engine = C2RAGV3([document("Question: algebra. Answer: x equals one.", document_id="target")])
    result = engine.run_round(session_id="s1", round_id=1, identity="teacher", query="algebra", target_resource_id="target")
    result = replace(result, selected_chunks=[{"document_id": "wrong", "source_family": "other"}, {"document_id": "target", "source_family": "family-1"}])
    case = HiddenCase("case", "s1", document("Question: algebra. Answer: x equals one.", document_id="target").text, "family-1", ("algebra",), True, "attack", False, "target")
    metric = OfflineEvaluator(SemanticEvaluator(backend="lexical")).evaluate_session(case, [result])
    assert 0.0 < metric["ndcg_at_3"] < 1.0
    assert metric["mrr"] == 0.5


def test_clean_over_refusal_requires_complete_session_availability() -> None:
    engine = C2RAGV3([document("Question: algebra. Answer: x equals one.")])
    first = engine.run_round(session_id="s1", round_id=1, identity="teacher", query="algebra")
    second = replace(first, round_id=2, refusal=True, released_answer="当前资源不在允许的披露范围内。", executed_action="refuse")
    case = HiddenCase("clean", "s1", document("Question: algebra. Answer: x equals one.").text, "family-1", ("algebra",), False, "none", True)
    metric = OfflineEvaluator(SemanticEvaluator(backend="lexical")).evaluate_session(case, [first, second])
    assert metric["normal_available"] == 0
    assert metric["over_refusal"] == 1
