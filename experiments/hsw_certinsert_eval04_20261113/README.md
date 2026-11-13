# HSW-CERTINSERT-EVAL-04 v3

Execute stage 0, A, B, C, D in order. Each completed stage must have code,
data and threshold SHA256 commitments committed before the next stage starts.
This directory and its own var/results directory are the only new write targets.
EVAL-01/EVAL-03 artifacts are read-only. Paid APIs are forbidden.

Stage 0/A may use only development data. Do not read or generate T6 contents
before stage B's pre-content freeze. Reserve chapter identifiers using metadata
only. No score-dependent T6 allocation. Preserve original EVAL-03 insertion,
anchor, certificate, grouping-use, sentence and stopping constraints except
the explicitly requested lexicon/null-source/multi-detector changes.

Stage 0 requires at least 2000 source documents and 300 once-generated teaching
documents from disjoint OpenStax chapters, using the exact T5 model. Corpus
split 80/20 at document level. Do not count the corpus as materialized until
source hashes, actual text deduplication and generation outputs are recorded.

Mandatory lexicon thresholds: prefix length 1–4 words before comma; build df
>=0.002*build documents; 100 NLI contexts per candidate; bidirectional
entailment >=.9 in >=95% pairs; reject anchor-bearing candidate; remove worst
30% by EVAL03 3B fluency change; calibration q<=.05; pair lift<=3 after conflict
removal. Nested sizes 10/20/40/80 or actual fewer. No EVAL02 null calibration.

The updated TASK_EVAL04.md resolves combined ranking, L* selection and entry
conditions. Rules 1–3 are copied verbatim into PREREG_RULES.md and committed
before any R scores. Require >=10 qualified candidates; stop if not achieved.
Automatic entries have no position conditions, as explicitly required by v3.
Candidate sentence sampling, NLI label mapping, q opportunity denominator and
group construction must also be explicit before scoring, never after results.

Stage 0 is NOT complete. A protocol/preflight commit does not satisfy its gate.
The first action is a metadata-only source/asset inventory. This does not read
T6 text, allocate T6 questions, generate answers, or evaluate any detector.
