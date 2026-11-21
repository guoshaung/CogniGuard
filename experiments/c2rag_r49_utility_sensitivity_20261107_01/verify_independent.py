"""Independent full-tuple reward/rollout reference, not a policy under test."""
import random

import run_r49 as run


def main():
    run.assert_freeze()
    ref = run.reference_namespace()
    rng = random.Random(490490)
    checks = 0
    candidates_checked = 0

    def reference_options(st, who, q, s, cfg):
        out = []
        for j, bits, weight in ((0, 1 << q, 80), (1, 1 << ((q + 1) % s['r']), cfg['alt']),
                                (2, 0, cfg['degraded']), (3, 0, 0)):
            after = st[:who] + (st[who] | bits,) + st[who + 1:]
            if not ref['partition_unsafe'](after, s['k'], s['r']):
                reward = weight
                if bits and bits & st[who] == bits:
                    reward = weight * cfg['repeat'] // 80
                out.append((j, bits, reward, after))
        return out

    # Every reward configuration; r3/4/5 and empty/spread; artificial forecast
    # sample lists independent of actual future requests, identical for both implementations.
    for cfg in run.configs():
        for r, k in ((3, 2), (4, 2), (4, 3), (5, 3)):
            for initial in ('empty', 'spread'):
                s = dict(n=8, r=r, k=k, init=initial)
                state, counts, sig = run.init(s)
                for _ in range(5):
                    who, q = rng.randrange(8), rng.randrange(r)
                    st = tuple(state)
                    samples = [[(rng.randrange(8), rng.randrange(r)) for _ in range(3)] for __ in range(3)]
                    # select's normalization is fixed 8 samples; explicitly use 8 here.
                    samples += [samples[i % 3] for i in range(5)]
                    opts = reference_options(st, who, q, s, cfg)
                    opt_fast = run.candidates(state, counts, sig, who, q, k, r, cfg)
                    assert [(a[0], a[1], a[2]) for a in opts] == [a[:3] for a in opt_fast]
                    candidates_checked += len(opts)
                    ranked = []
                    for a in opts:
                        future_value = 0
                        for sample in samples:
                            sim = a[3]
                            for rec, qt in sample:
                                b = max(reference_options(sim, rec, qt, s, cfg), key=lambda x: x[2])
                                sim = b[3]
                                future_value += b[2]
                        ranked.append((8 * a[2] + future_value, a[2], a))
                    wanted = max(ranked, key=lambda x: x[:2])[2]
                    actual, _ = run.select(state, counts, sig, who, q, s, cfg, 'M2-trained', samples)
                    assert wanted[:3] == actual[:3]
                    checks += 1
                    run.commit(state, counts, who, actual[3])
                    sig = actual[4]
    run.dump('INDEPENDENT_ROLLOUT_VERIFICATION.json', dict(status='PASS',
        exact_full_tuple_reference=True, configurations=52, selection_checks=checks,
        candidate_checks=candidates_checked, max_reference_forecast_horizon=3,
        no_test_results_used_for_tuning=True))
    print('PASS:', checks, 'independent rollout selections;', candidates_checked, 'candidates')


if __name__ == '__main__':
    main()
