# CGC5 frozen protocol (written before any run)

- A1 is used exactly as frozen in CGC4 (a_engine.Policy("A1", gamma=0.3), the CGC4 dev choice). Not re-tuned.
- Development seeds 0-39 per condition: only to choose the free parameters of the NEW baselines (OCELOT-proxy
  budget, PrivacyFlow-proxy risk threshold, dynCQE-proxy censor sample size, optimized-MPC depth). Choices are
  written to results/dev_choices.json before the test run.
- Test seeds: the CGC4 test seeds (100000+), same conditions, same task sequences (common random numbers).
  Real-data-derived sequences: odd ids (test), as in CGC4.
- All methods run in the same process pool on the same machine, sequentially per instance.
