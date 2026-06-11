# Teacher Resource Protection

This package contains PB-C2-RAG copyright-aware retrieval:

- exposure budget accounting;
- copyright-aware ranking;
- controlled return modes;
- protected resource variants;
- source trace generation.

It reuses the cross-layer schemas and text utilities from `protection.common`.

Teacher resource fixtures live in `data/`. Reconstruction attacks and their
prompts live under `experiments/attacks/`.

Run its tests from the repository root:

```bash
pytest protection/teacher_resource/tests
```
