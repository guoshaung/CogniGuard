# CGC4 frozen seed protocol (written before any run)

- Development seeds: 0-199. Used only to choose free parameters (gamma of A1, DRO radius, beam width/depth,
  MPC depth, SAA scenarios/horizon, B pruning threshold). Choices are recorded in results/dev_choices.json.
- Test seeds: 100000-100999. Every reported number comes from test seeds with the dev-chosen parameters.
- Episode (task-sequence) seeds are derived as hash((instance_seed, episode_index)) and are common to all
  policies in a comparison (common random numbers).
- Real-data-derived sequences (Sum Leaks, Eedi): scenarios/targets split by id parity: even = dev, odd = test.
- No seed, split or threshold is changed after test results are seen; any deviation goes to DEVIATIONS.md.
