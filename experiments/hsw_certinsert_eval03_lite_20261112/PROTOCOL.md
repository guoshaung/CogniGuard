# EVAL03-LITE pre-execution protocol

## Authority and version
User task TASK_EVAL03_LITE.md dated current execution 2026-11-12.
Revision09 parameters, EVAL02 structural adapter, and EVAL02 domain frequencies
are frozen by hash. This explicitly adopts the new frequencies for this new
evaluation; EVAL02 actually generated with the original frequencies. Its domain
holdout was incomplete (49 scorable, 1 unknown), not a certified PASS. Both facts
must be visible in the report. No threshold is changed after evaluation.

## Sets and disjointness
Target T4=400 complete worked examples; T5=200 distinct problem-only inputs;
in-domain unmarked control=1000 worked-example explanation paragraphs. A single
example's multiple paragraphs are NOT independent source samples and are grouped
in the bootstrap. Old general holdout=300 is explicitly reused.

Use only pinned CC BY4.0 OpenStax sources; physics/chemistry/biology, no fabricated
biology examples. Existing full-example rendering and missing-reference,
unsupported-formula/flattened-exponent checks are retained; no repairs. Record
all exclusions and material shortfalls. Do not silently reduce target denominators.

Exclude old T1/T2/T3, calibration, development and vocabulary-study source
chapters. Chapter means the nearest collection subcollection enclosing module
references, not an entire volume/part; full hierarchy is retained. Sampling and
partitioning use SHA256(2026111203|purpose|id) ordering. Use source groups, exact
normalized hashes and near-duplicate diagnostics; do not promise semantic
independence merely from different IDs. Freeze exact T4/T5/control IDs and the
100-example T4 costly subset before any model call. No output-based reselection.

## Systems and attacks
CertInsert uses fixed 3B scoring model, revision09 rules and domain frequency file.
KGW/Unigram/T5 source generation use the existing7B Q4_K_M settings. Fingerprint
uses the same frozen knowledge anchors/MinHash and a shared full source index.

RC uses the same seven-entry vocabulary and p-value detector, global-key-only
k=4 selection (no semantic anchor), random eligible positions, no title/question
structural protection; formula/number/unit token integrity is retained. Same
per-sentence, group, spacing and6% ceiling and predicted p<.001 stop. RC's public
detector reconstructs its own global list; do not score it using CertInsert's list.
All randomness fixed by frozen seeds/key commitments. Private keys stay local.

CPU attacks: unchanged, frozen PaddleOCR rendering, first/middle100words.
One70%-target compression per system on the same100T4 sources, fixed original
prompt and generation settings. If resources constrain attacks, retain baseline
100-source attempts first; never replace failures or claim all successful.
No failed-generation retries. EOS/truncation/error/NOT_RUN stay separate.

## Calibration and denominators
No null refit: use EVAL02 frequencies, strict p<.01. Evaluate1000in-domain and
300reused general controls separately.1000 independent random diagnostic keys
are detection-only; calculate alarms at .001/.01/.05, and report key-averaged and
per-document results separately. A million text-key pairs are NOT a million
independent texts. Cluster intervals by source example/chapter as appropriate.

Every cell reports planned/available/eligible/scorable, conditional and planned-
denominator rates; unavailable slots are not successful. Paired analysis includes
only explicitly shared output sources and also reports exclusions. Knowledge
anchors are mechanical checks, not semantic gold. No human review or PostMark.

## Resources and checkpoints
Zero paidAPI. No model download. Maximum48 cumulativeGPU hours as a conservative
upper bound within the task's1–2day estimate; lower machine safety limits apply.
Check RAM/GPU and other tasks before launch, never terminate unrelated processes.
No GPU generation before exact data freeze and end-to-end admission.
Atomic per-slot files, append-only request ledger, uniqueIDs and persistent state.
No automatic background promise across platform interruption.

## Delivery
Independent EVAL03 directory; full tables/counts/failures and source manifests.
figure_counts.json must match the actual paper make_figures.py schema; missing
paper script is an explicit integration dependency, not grounds to invent arrays.
Isolated research-sync branch, fixedcommit, independent hash readback.
