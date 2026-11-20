# final_decision — 2026-11-20

## 决定

**Grok 迁移复刻线停在密钥。** 没有成功率，没有合法 per-sample。

1. **严格同模型复现**：关闭。模型已从 DeepSeek-V3.2 换成 Grok（D-001R）。
2. **Grok 迁移信号**：未判定。客户端已接上，评分脚本未改，但 `XAI_API_KEY` 不在 `mmfopd-repro/.env`，冒烟和 200×2 都没有跑。这不算方法失败，也不是成功或部分成功。
3. **原文方向（供下次对照）**：Table 6 四环境等权成功率 ACE 43.0 − DeepSeek-V3.2 45.0 = −2.0 pp。下次 Grok 的等权差若也 ≤ 0，方向与原文一致。
4. **教学任务迁移**：停止。Grok 线还没有可解释的 CrossEp-Tool 信号。
5. **12 对跨环境**：未做。

## 生效条件

- [x] `mmfopd-repro/EvoMemBench` 存在，commit `3efc221fd8d5f4de7c2dc2022357e600d26325c7` 已写入预注册
- [x] 适配层已挂上，`run_batch_evaluate.py` 未改
- [ ] 冒烟通过，且费用外推 ≤ 150 元
- [ ] 两组第一阶段跑完并归档 artifacts

## 下一步

把密钥和精确模型 id 放进 `mmfopd-repro/.env`，按 `R_RESULT.md` §6 先 ping、再冒烟、再决定满量。不要把 key 贴进对话。

## 签署

- `R_PREREG.md` / `DEVIATIONS.md` / `R_RESULT.md` / `RUNBOOK.md`
- 代码：`EvoMemBench/.../bfcl_eval/memory/ark_client.py`
