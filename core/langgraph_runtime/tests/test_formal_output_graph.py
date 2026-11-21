from experiments.formal_v2_output.graph import (
    ATTACKS, OUTPUT_GRAPH, OutputFrame, run_output_graph,
)


class FakeTokenizer:
    vocab_size = 100


def test_hsw_output_graph_covers_protected_attacks_and_clean_controls_without_model():
    seeds = []
    test = [
        {"episode": {"episode_id": f"case-{index}", "resource_id": "r",
                     "user_request": "求 2+2"},
         "resource": {"content": "teacher", "knowledge": "math",
                      "chunk_id": "c", "resource_family_id": "family"}}
        for index in range(2)
    ]

    def generate(model, tokenizer, question, resource, seed):
        seeds.append(seed)
        return "draft 2+2", 1.0

    def detect(text, *args):
        found = "watermark" in text
        return {"is_watermarked": found, "z_score": 4.0 if found else 0.0}

    frame = run_output_graph(OutputFrame(
        test=test, model=object(), tokenizer=FakeTokenizer(),
        model_dir="fake", model_revision="revision", device="cpu",
        watermark={"key_id": "test", "key": "fake", "gamma": 0.25,
                   "window_size": 4, "z_threshold": 2.85},
        generate_fn=generate,
        extract_fn=lambda sample, _: (["math"], [], ["2"]),
        rewrite_fn=lambda text, *args, **kwargs: {"watermarked_answer": text + " math watermark"},
        detect_fn=detect,
        attack_fn=lambda text, attack: text + " " + attack,
        similarity_fn=lambda a, b: 0.5,
        digest_fn=lambda value: "trace-hash",
    ))
    assert len(frame.rows) == 2
    assert len(frame.attack_rows) == 2 * len(ATTACKS)
    assert frame.clean_flags == [False, False]
    assert seeds == [20260826, 20260827, 20260926, 20260927]
    assert {"generate_draft", "protect_and_detect", "attack_and_detect",
            "clean_control"} <= set(OUTPUT_GRAPH.get_graph().nodes)
