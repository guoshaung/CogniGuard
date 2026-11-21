from types import SimpleNamespace

import pytest

from experiments.rag_real.scifact_train_calibration import (
    ALPHAS, blend_ranking, choose_alpha,
)


def test_alpha_zero_preserves_rrf_order_and_alpha_one_uses_cross_scores():
    rrf = [2, 0, 1]
    chunks = [SimpleNamespace(chunk_id=f"c{i}") for i in range(3)]
    scores = {2: .1, 0: .3, 1: .9}
    assert blend_ranking(rrf, scores, 0.0, chunks) == rrf
    assert blend_ranking(rrf, scores, 1.0, chunks) == [1, 0, 2]


def test_train_gate_falls_back_to_rrf_when_tradeoffs_fail():
    baseline = {"recall@10": .8, "mrr@100": .6, "ndcg@10": .65}
    dev = {alpha: {"recall@10": .79, "mrr@100": .7, "ndcg@10": .7}
           for alpha in ALPHAS}
    dev[0.0] = baseline
    assert choose_alpha(dev) == 0.0
    dev[.1] = {"recall@10": .81, "mrr@100": .61, "ndcg@10": .66}
    assert choose_alpha(dev) == .1
    with pytest.raises(ValueError):
        blend_ranking([0], {}, .5, [SimpleNamespace(chunk_id="c0")])
