上一轮使用了自建的合成单元，G1、G2 是按构造成立的，不用于判定。

这是阶段 1b。旧目录 `experiments/ocelot_edu_20261121/` 保持原样。分支仍是 `codex/ocelot-repro`。

资产包在仓库外：`../C2RAG_5_Pedagogical_Assets_Pilot_v1/`。运行前先确认：

```text
python3 -I ../C2RAG_5_Pedagogical_Assets_Pilot_v1/validate_assets.py ../C2RAG_5_Pedagogical_Assets_Pilot_v1
```

输出必须以 `PASS` 开头。单元原文不进入本目录。这里只放代码、哈希和统计。

预注册见 `EXPERIMENT_PROTOCOL.md`。判定见 `RESULT.md`。
