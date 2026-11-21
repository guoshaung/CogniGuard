from types import SimpleNamespace
import pytest
from core.langgraph_runtime.adapters import JsonTeachingAdapter, SelectiveHSWSTAdapter
from core.teaching import TeachingInput


def test_json_adapter_never_executes_model_tool_requests():
    class Model:
        def call(self, system, payload):
            assert set(payload) == {"question", "knowledge", "difficulty", "context_card", "resource_mode", "resource_text"}
            return {"output": {"answer": "test answer", "action": {"tool": "forbidden"}}}
    adapter = JsonTeachingAdapter(Model())
    assert adapter(TeachingInput("q", "k", "d", "card", "none", "")) == "test answer"


def test_hswst_calls_real_contract_but_tests_use_no_model():
    def rewrite(answer, terms, formulas, numbers, config, ablation, question):
        assert ablation == "full"
        return {"watermarked_answer": answer, "use_kgw": True, "use_protect": True,
                "repaired_placeholder_count": 2, "tokenizer": "TEST_TOKENIZER"}
    adapter = SelectiveHSWSTAdapter(rewrite_sample=rewrite,
        detect=lambda text, tok: {"detected": True, "z_score": 4.1},
        critical_spans=lambda answer, task: {"terms": [], "formulas": [], "numbers": []},
        config={"model": {"provider": "huggingface"}})
    result = adapter("answer", SimpleNamespace(question="q"), {})
    assert result.evidence["detected"]
    assert result.evidence["repaired_placeholder_count"] == 2


def test_hswst_does_not_label_api_rewriting_as_kgw():
    with pytest.raises(ValueError):
        SelectiveHSWSTAdapter(rewrite_sample=None, detect=None, critical_spans=None,
                             config={"model": {"provider": "openai"}})


@pytest.mark.parametrize("flag", ["used_draft_fallback", "failed_placeholder_check", "fidelity_violations"])
def test_hswst_fails_closed_on_fallback_or_fidelity_errors(flag):
    def rewrite(*args, **kwargs):
        return {"watermarked_answer": "answer", "use_kgw": True, "use_protect": True, flag: True}
    adapter = SelectiveHSWSTAdapter(rewrite_sample=rewrite, detect=lambda *args: None,
        critical_spans=lambda *args: {"terms": [], "formulas": [], "numbers": []}, config={})
    with pytest.raises(ValueError):adapter("answer", SimpleNamespace(question="q"), {})
