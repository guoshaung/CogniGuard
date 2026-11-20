# final_decision — 2026-11-20

## 决定

**Grok 迁移停在预算门禁。** CLI 会话额度可以打通官方评分。满量没有跑。

1. **严格同模型复现**：关闭。模型是 `grok-4.7`，原文是 DeepSeek-V3.2（D-001R）。
2. **Grok 迁移信号**：预算停止。NO-MEM 烟雾 4/4、ACE 烟雾 8/8，官方 `run_batch_evaluate` 未改，api/runtime 失败为 0。这只说明管道在烟雾规模上能给出合法 per-sample。200×2 的标价外推是 289.85 元（汇率 6.6667），硬顶 150 元，所以满量没有启动。方向相对原文 −2.0 pp **不可判**。不记为成功，不记为部分成功，也不记为方向相反的失败。
3. **原文方向（仍锁定）**：Table 6 四环境等权成功率 ACE 43.0 − DeepSeek-V3.2 45.0 = −2.0 pp。
4. **教学任务迁移**：停止。没有 200 条上的 Grok 信号。
5. **12 对跨环境**：未做。

## 生效条件

- [x] `mmfopd-repro/EvoMemBench` 存在，上游 commit `3efc221fd8d5f4de7c2dc2022357e600d26325c7` 已写入预注册
- [x] 适配层已挂上，`run_batch_evaluate.py` 未改。本地提交 `5670db5`、`647bbef`
- [x] 冒烟已跑，费用外推 **超过** 150 元，按红线停止
- [ ] 两组第一阶段 200 条跑完并归档。未做，因为外推超顶

## 下一步

维持 150 元硬顶时，到此结束。若要满量，需要明确把硬顶提高到至少覆盖约 290 元的不计缓存标价（固定 1152 token 缓存假设下约 241 元），再跑 `scripts/run_crossep_tool_phase1.sh full`。不要换模型，不要砍样本。

## 签署

- `R_PREREG.md` / `DEVIATIONS.md` / `R_RESULT.md` / `RUNBOOK.md`
- 代码：`EvoMemBench/.../bfcl_eval/memory/ark_client.py` @ `647bbef`
- 烟雾汇总：`artifacts/no_mem/`、`artifacts/ace/`
