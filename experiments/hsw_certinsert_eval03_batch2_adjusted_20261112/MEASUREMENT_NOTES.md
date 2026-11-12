# Additional reporting clarifications (no method changes)

T5 generated originals are evaluated by the unchanged detector as unwatermarked controls before interpreting conditional watermarked detection. The existing public evaluation already saves the original's p value in its Fingerprint row; its `detected` field remains source retrieval, not watermark detection. Report the p<.01 original rate separately, never confuse these metrics.

Report zero-insertion PREDICTED_TARGET_REACHED outputs separately. If an unmarked original already has enough natural hits, the frozen algorithm can stop without inserting. This is not new embedded signal; do not describe it as successful watermark modification. Preserve the original algorithm's status and overall source denominator rather than silently changing its stopping rule.

All source generation failures/truncations, planning errors, low capacity, scoring errors and public parser errors stay in separate ledgers. Conditional successful-embedding rates do not replace full200-source coverage. Source knowledge quality is format-only/PROVISIONAL, not human gold.

P4 reviewer labels remain missing until actual independent submissions. No model or author fills either reviewer's ratings. No Cohen kappa can be reported before both submit.
