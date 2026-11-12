# Expanded-observation phase, frozen before T5 watermarked outputs

The first T4-only N10 result is retained. After T5 insertion finishes, freeze the combined successful T4+T5 public-output pool. N=10/50/200 observations use the original fixed SHA256 ranking; targets and N are never chosen from attack scores. Repeat N10 on this expanded pool is a separately labelled observation-pool condition, not a retry of the historical N10 result.

Spoof targets stay the same200 frozen unmarked paragraphs. Scrubbing targets: up to200 distinct source outputs per method chosen by SHA256(2026111205|scrub_target|sourceID), independently of N. Training and scrubbing pools can overlap when material is limited. Report all targets, the observation-overlap subset and the strictly disjoint subset separately; no claim of200 independent unseen targets where unavailable. All N use the same scrubbing target pool to avoid sample composition confounding. Insufficient observation N => NOT_AVAILABLE, never silently replace N.

No new watermark generation beyond the frozen T5 sources and one CertInsert/RC embedding per source. No changes to private selection, attack prefix mining, insertion constraints or detector thresholds. Keep initial P1 archive and counts under historical_phase; final expanded counts have explicit phase label.
