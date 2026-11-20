# BUDGET_STOP_GROK — 2026-11-20

上一版因骨干模型下架、经用户同意改用 grok-4.7 做冒烟测试；外推费用约 290 元，超过上限而停止。这不是复现失败，也不是 MM-FOPD 的最终决定。

原文件名是 `final_decision.md`。方案 B 开始后改名为本文件。Grok 烟雾不参与判定。

## 当时的决定

**Grok 迁移停在预算门禁。** CLI 会话额度可以打通官方评分。满量没有跑。

1. **严格同模型复现**：关闭。模型是 `grok-4.7`，原文是 DeepSeek-V3.2。
2. **Grok 迁移信号**：预算停止。NO-MEM 烟雾 4/4、ACE 烟雾 8/8，官方 `run_batch_evaluate` 未改，api/runtime 失败为 0。这只说明管道在烟雾规模上能给出合法 per-sample。200×2 的标价外推是 289.85 元（汇率 6.6667），硬顶 150 元，所以满量没有启动。方向相对当时抄录的 −2.0 pp 不可判。
3. **教学任务迁移**：当时停止。
4. **12 对跨环境**：未做。

代码后来从 EvoMemBench 的 `codex/mmfopd-repro` 上移走：`5670db5` 与 `647bbef` 在分支 `grok-smoke`。工作分支回到 `3efc221fd8d5f4de7c2dc2022357e600d26325c7`。

烟雾汇总仍在 `artifacts/no_mem/` 与 `artifacts/ace/`。
