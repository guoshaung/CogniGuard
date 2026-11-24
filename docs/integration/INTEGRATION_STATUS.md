# 跨模块集成状态（X3-E2E 准备阶段）

> 更新：2026-11-24（X3-E2E 正式运行后），集成负责人（Mac 上的 Claude），分支 `integration/provenance-governance`。
> **本轮已完成最后一次跨模块联动；研究收束，不再开新的联动实验。** 结果：`experiments/x3_e2e_integration/RESULT.md`；论文结论：`RESEARCH_STATUS.md` 第 1 节。
> 研究整体状态仍以 `RESEARCH_STATUS.md` 为准；本文件只管模块、接口、联动实验。
> 本轮**未修改** Codex / Grok 的算法代码，未合并 main，未运行他们负责的实验。

## 1. 模块、分支与固定提交

| 模块 | 负责人 | 分支 | 固定提交 | 是否在 GitHub | 状态 |
|---|---|---|---|---|---|
| CA-PD 判定内核（`check_release`、`ReleaseGate`、`AccessRegistry`、`DisclosureStore`） | — | `main` | `5827e4e` | 是 | 已冻结使用，本轮不改 |
| 来源证据接口 pe-1.0 + 参考核验 / 状态 / 决策 + mock + 契约 | 集成 | `integration/provenance-governance` | 本文件所在提交 | 是 | **冻结** |
| X3-E2E 统一入口（回放 / 在线 / mock）与协议 | 集成 | 同上 | 冻结 `5d6ce72`；偏离 `eec96b6` | 是 | **教育场景正式运行完成**（21,120 次运行）；软件场景延期 |
| pe-0.1 → pe-1.0 兼容转换 | 集成 | 同上 | `eec96b6` | 是 | Codex 两份证据 7,440 + 910 条转换 0 失败，正式提供方契约通过 |
| KBPW 来源检测（M1 / M2 / M3 / M1+source）、内容基线、真实传播试点 | Codex | `codex/hsw-st` | `065bb82`（含 `d7239c4`） | 是 | 完成 |
| Gate W0-Real / KBPW 收尾 / 核验器对照 | Codex | `codex/gate-w0-real` | `fcf1374` | 是 | KBPW **STOP**（接受）；BGE + 原版 NLI 判定已交付，集成侧复现 99/137，并完成 X3-E2E NLI 网格（23,040 次运行） |
| 影子来源状态、X3 验证、动态安全状态适配器 | Grok | `dev/source-evidence` | `0e48995` | **否**（仅本机主检出；另有未跟踪的 `provenance_link.py`） | 只读探针：消费者契约仅 C5 失败（已核验内容持有不入状态）；未纳入正式运行；已在 Issue #16 请求推送 |

## 2. 依赖关系

```
Codex 检测器 ──(pe-1.0 Observation JSONL / SourceDetector)──► RuleVerifier ──► SecurityState ──► DisclosurePolicy ──► 决策
                                                                     ▲                 ▲                  │
                                    系统登记的事实表述（资产主人） ──┘                 │                  ▼
                                    DisclosureStore 回执 ──────────────────────────────┘        score.py（唯一读金标）
Grok 适配器 ──(实现 StateUpdater / DisclosurePolicy，过消费者契约)──► 作为额外治理模式接入
全部判定都落到 main 上的 check_release + AccessRegistry.is_authorized
```

## 3. 重复实现核对

| 重复点 | 位置 | 处理 |
|---|---|---|
| 证据记录类型 | 集成 pe-0.1 `provenance_evidence.py` | **已删除**，由 pe-1.0 取代 |
| 证据记录类型 | Grok `cogniguard/governance/source_evidence.py`（`SourceEvidence`） | 与 pe-1.0 重叠；对应表见 `PROVENANCE_INTERFACE.md` 第 9 节。建议 Grok 改为消费 `cogniguard.provenance.schema.Observation`，或写一个双向转换并过契约；**我没有改他的文件** |
| 证据 JSON Schema | Grok `experiments/x3_e2e_20261125/schema/*.json` | 与 `cogniguard/provenance/schemas/pe-1.0/` 重叠；正式联动只认 pe-1.0 |
| 端到端运行器 | Grok `experiments/x3_e2e_20261125/run.py`、`evaluate.py`（受控夹具，B0–B5 / Ours / Oracle） | 与统一入口重叠。他的 `shadow_decide` 作为一个 `DisclosurePolicy` 接入统一入口；他的夹具结果保持原样，不作为联动结果 |
| 状态更新语义 | Grok：只有可信日志 / 理想证据写入 K′；集成：已核验的内容单元也写入 confirmed，未核验的只进疑似层 | **需要 Grok 确认**。两种语义都能由消费者契约检查；作为治理模式并列报告 |
| 检测指标 | Codex 各 `evaluate.py`、`compare.py` | 检测层指标归 Codex，不重复；X3-E2E 只算决策层指标 |

未发现两处同时修改同一核心文件。

## 4. 正式联动前提的最终状态

| # | 条件 | 状态 |
|---|---|---|
| 1 | Codex 真实检测输出可映射并通过 `provider --formal` | **满足**：`065bb82` 试点输出（四个变体）和 `40213d3` 的两份证据都通过 |
| 2 | 数据提交号 | 沿用 `065bb82`（`40213d3` 没有新增试点终点输出），记入偏离第 2 条 |
| 3 | Grok 推送并通过消费者契约 | **未满足**：未推送；`0e48995` C5 失败。按预注册第 7 节不纳入 |
| 4 | 软件场景真实检测输出 | **未满足**：按偏离第 1 条延期 |
| 5 | 统一入口与接口测试 | 25 / 25 通过 |

## 5. 已知风险

1. **数据规模小**：真实试点只有 15 条链、45 个终点 / 变体；簇 bootstrap 只有 15 簇，置信区间宽。
2. **场景是叠加构造**：传播文本和事实保留是真实的；持有者分配和考题秘密是构造的，论文中必须写明。
3. **日志是模拟**：LOG 臂的签名日志由构造产生，覆盖率 0.5；不是任何真实系统的测量。
4. **预算条件不成立**：每条链 5 次未登记传播，k + (f − d) 在本场景没有保证；A-credits 只描述。
5. **CRED 无真实通道**：Codex 只在受控网格上测了签名凭证；真实试点没有，所以 CRED 臂等同 R0，如实报告。

## 6. 下一步命令

**Codex（GPU 服务器，在自己分支上）**：校验输出格式。

```bash
python -m cogniguard.provenance.contract provider path/to/observations.jsonl --formal
```

**Grok（Mac，在自己分支上）**：契约自检。

```bash
python -c "from cogniguard.provenance.contract import check_consumer; from my_adapter import make_state, make_policy; print(check_consumer(make_state, make_policy))"
```

**集成：空跑（已执行，可复现）**

```bash
python -m experiments.x3_e2e_integration.grid --repo ../CogniGuard --codex-ref 065bb82 --data ../cogniguard_data/x3e2e_dev --dry-run
```

**集成：正式运行**。前提条件满足后执行；SHA 先记入 `DEVIATIONS.md`。

```bash
python -m experiments.x3_e2e_integration.grid --repo ../CogniGuard --codex-ref <Codex 新 SHA> --data ../cogniguard_data/x3e2e --seeds 0-29
```

**单次运行**

回放：

```bash
python -m experiments.x3_e2e_integration.run --scenario S/scenario.json --observations S/observations_codex.jsonl --keys S/keys.json --arm CONTENT_ALL_WM --mode dyn_knowledge --formal --out runs
```

评分：

```bash
python -m experiments.x3_e2e_integration.score --run runs/<scenario_id>/CONTENT_ALL_WM__dyn_knowledge --scenario S/scenario.json --gold S/gold/gold.json
```

在线：把 `--observations` 换成 `--detector pkg.module:DetectorClass`。

## 7. 接口版本变更表

| 版本 | 日期 | 内容 |
|---|---|---|
| pe-0.1 | 2026-11-24 | 初版（集成分支），已删除 |
| pe-1.0 | 2026-11-24 | 冻结：五种身份分离；Observation / VerifiedEvidence / Decision；三层状态；四接口；金标禁入；契约 C1–C6 |
| pe-1.0（契约修正） | 2026-11-24 | `contract.py` 的 C4 实现与冻结文本对齐（"只计一次或不计"），接口与 schema 不变；新增 `compat.py`（pe-0.1 → pe-1.0） |
