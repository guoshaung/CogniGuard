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

## Offline field audits

Run `python3 -m experiments.datasets.eedi_exam.audit` or
`python3 -m experiments.datasets.sumleaks.audit` from this checkout.
Inputs are `eedi/` and `sumleaks/` under `COGNIGUARD_RAW_DIR` (default
`../cogniguard_raw/`). Each writes AUDIT.json and a SHA-256 MANIFEST.json
under `COGNIGUARD_DATA_DIR/audits/` (default `../cogniguard_data/audits/`).

The Eedi audit counts distinct misconception IDs per question. Numeric
answers include exact integers, decimals and fractions, including simple
LaTeX fractions. Stem counts use occurrences of signed decimal tokens.
The pilot uses seed 2026 and samples 30 annotated question IDs without
replacement independently for each K. It covers the rarest clues first
with a random suitable neighbor, reuses covered clues, then samples remaining
questions from the target subject. All target clues must have a neighbor.
The leakage check uses at most 12 retained clues and up to 50 redraws after
the initial draw. Trial groups exist only in memory.

For Sum Leaks, a full defense match means every name in the final recognized
list matches a table. Free prose with exact table-name mentions is partial.
The audit lists same-name columns and cross-name Jaccard overlap on distinct
non-null values. Suffixes and within-table uniqueness flag candidates for
manual review. Each scenario records its column names and row counts.

## Eedi "which question will be set" (revision 2.1)

Run `python3 -m experiments.datasets.eedi_exam.generate` after the field audit.
Questions are real Eedi questions; which one is set is a sampled construct.
Two rules were added after the audit and approved by the project owner:
a unit whose value is held by only one question in the whole bank is a direct
identifier and is left out of the universe (counted per secret in the
manifest), and candidates are filled from the same subject, then from questions
sharing a retained unit, then from the whole bank (counts per tier in the
manifest). Targets per K are 300; shortfalls are reported, not filled. The
set-gain variant (three questions, K=16) is not generated yet.
