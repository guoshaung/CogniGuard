# Teacher Resource Protection

This package contains PB-C2-RAG copyright-aware retrieval:

- exposure budget accounting;
- copyright-aware ranking;
- controlled return modes;
- protected resource variants;
- resource-level provenance trace generation.

C2-RAG owns resource provenance fields such as `resource_id`, `chunk_id`,
`license_policy`, `return_mode`, exposure budget states, `policy_reason`,
`retrieval_trace`, `quote_span_hash`, `controlled_output_hash`, and
`resource_provenance_commitment`. Generation watermark embedding and watermark
detection remain in HSW-ST; C2-RAG only provides the upstream resource evidence
that HSW-ST can bind into its answer-level audit chain.

It reuses the cross-layer schemas and text utilities from `protection.common`.

Teacher resource fixtures live in `data/`. Reconstruction attacks and their
prompts live under `experiments/attacks/`.

Run its tests from the repository root:

```bash
pytest protection/teacher_resource/tests
```
