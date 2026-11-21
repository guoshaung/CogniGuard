from experiments.formal_v2_llm.graph import LLMFrame, LLM_GRAPH, run_llm_graph


class FakeTokenizer:
    vocab_size = 100


def test_llm_method_graph_preserves_hidden_label_boundary_without_loading_model():
    prompts = []
    chosen = [{
        "visible": {"case_id": "one", "question": "求 2+2", "student_id": "s", "resource_id": "r"},
        "hidden": {"is_attack": True, "attack_family": "HIDDEN_SENTINEL"},
        "profile": {"local_only_fields": {"key": "PRIVATE"}},
        "resource": {"knowledge": "math", "content": "teacher text"},
    }]

    def generate(model, tokenizer, prompt, seed, max_new_tokens):
        prompts.append(prompt)
        return "PRIVATE 2+2", 1.0

    rows = run_llm_graph(LLMFrame(
        chosen=chosen, methods=["FullProfile", "Full Output Protection"],
        model=object(), tokenizer=FakeTokenizer(), max_new_tokens=8,
        model_dir="fake", watermark_key="test", cuda_available=False,
        generate_fn=generate,
        rewrite_fn=lambda text, *args, **kwargs: {"watermarked_answer": text + "-wm"},
        detect_fn=lambda *args: {"is_watermarked": True},
        profile_text_fn=lambda profile, full: "student profile" if full else "minimum card",
        controlled_resource_fn=lambda resource: "controlled text",
        visible_prompt_fn=lambda question, student, teacher: f"{question}|{student}|{teacher}",
        privacy_leak_fn=lambda text, profile: "PRIVATE" in text,
        copyright_leak_fn=lambda text, resource: False,
    ))
    assert len(rows) == 2
    assert all("HIDDEN_SENTINEL" not in prompt for prompt in prompts)
    assert all(row["hidden_label_access"] is False for row in rows)
    assert all(row["evaluator_pending"] is False for row in rows)
    assert all(row["attack_success"] == 1 for row in rows)
    assert rows[1]["watermark_detection"] == {"is_watermarked": True}
    assert {"prepare_visible_input", "generate_answer", "protect_answer",
            "record_visible_result", "evaluate_posthoc"} <= set(LLM_GRAPH.get_graph().nodes)
