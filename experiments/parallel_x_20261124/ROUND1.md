# Round 1 dev scan (not a formal experiment)

Base SHA `893c6b3fe5e50d1526f2704ca3ae5ed555c4c609`. These scripts are uncommitted. Frozen rule: safety gain at least 0.10, utility drop at most 0.10, overhead ratio below 10. A standard lock, transaction, deny-overrides, or the existing `check_release` gate is not a new mechanism. No paid API. BGE was not downloaded. E9/E10: no frozen protocol in this checkout.

Acceptance scorer: `python -m pytest experiments/parallel_x_20261124/acceptance/test_score.py -q` → 33 passed.

Worker B's later X1 PASS and Worker C's X3 ANALYZE were re-scored in `RECONCILE.md`. Neither becomes PASS. No new upper-layer mechanism was added to `cogniguard/`.

Kept core: the existing release-gate coalition check plus commit recheck. Extensions, without a new algorithm: do not display degradation and replan; put a unique event id on the existing transaction. Watermark work stays stopped.
