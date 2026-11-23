# Synthetic discrete secrets

From the checkout root run `python3 experiments/datasets/synthetic/generate.py`.
The generator writes seven files under `../cogniguard_data/synthetic/`. Set
`COGNIGUARD_DATA_DIR` to a fresh directory for another run. The default is
resolved relative to the checkout, independently of the working directory.
This stage has no raw inputs. The generator uses the Python standard library.

Defaults are seed 2026, six ternary features, and 200 slots per candidate
count (8, 16, 32). Each attempt draws independent candidate vectors and
selects a uniform candidate index. Candidate IDs are distinct even when
vectors coincide. Each slot gets an initial draw and at most 50 redraws.
The manifest counts failed attempts (a only, b only, both) separately from
slots that exhaust the limit. Each target is a synthetic teaching asset.
The reproducible seed and evaluation labels are trusted evaluator inputs.
The assumed observer sees only the selected disclosure, with a uniform
reference prior over candidate IDs. The construction measures structural
leakage conditional on that model.

A witness crosses the strict threshold log2(K/2). With uniform identity gain,
two consistent candidates are on the safe boundary and one crosses it.
All subsets of the retained universe are evaluated. The leakage file stores
the empty set, subsets of size at most four, and all witnesses. When there are more than 12 units, the generator keeps the 12 with
the smallest supports, breaking ties by unit ID. Only the retained universe is guaranteed.
Three templates express attribute predicates. Each decoy uses a feature where
its selected candidate differs from the true candidate.

The compact fixture contains five K=8 targets as six files totaling at most 50 KB, excluding
the private file. Fresh runs draw new 128-bit salts. Verify HMAC on fresh
output, and compare deterministic fixture fields after removing commitments.
The full output directory is private experiment material.

Run `python3 -m pytest experiments/datasets -q` for the exhaustive structural,
text-label, commitment, reproducibility, and fixture checks.
