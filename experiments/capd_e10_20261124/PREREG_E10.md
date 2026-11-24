# E10：相同有界共谋约束下的可用性比较（冻结版）

> 冻结方式：本文件与 `PREREG_E10.sha256` 放在同一个提交中推送。之后的任何修改都记入 `DEVIATIONS.md`。
> 草案：`docs/research/prereg_drafts/PREREG_E10_UNION_BUDGET_DRAFT.md`（修订 2）。相关理论：`docs/research/PRIOR_ART_AUDIT_20261124.md`（第 E 节局部命题与反例）、`docs/research/THEORY_PROPAGATION_EVIDENCE_20261124.md`（命题 4）。
> 只通过导入复用 E5 冻结的 `workload`、`GateArm`、`NoDefense`，以及 E7 的加载器。不修改 E5–E7 的任何文件。

## 0. 冻结前对草案的修改（均在看到结果之前确定）

1. **Eedi 数据**：本环境只能拿到 Kaggle 数据的 GitHub 镜像副本，重新生成后，MANIFEST 的 sha256 为 `35ebd79c…`，**与 E6 的 `d4401ef4…` 不同**。合成数据（`91854349…`）和 Sum Leaks（`7c53e01b…`）与 E5、E7 完全一致。所以 Eedi 部分的结果不能与 E6 逐字节对应，本机可以用官方数据补跑。
2. **H2 改为只描述**：按理论命题 4，当 k ≥ max|W| 时（E5 中 k = 4、w ≤ 4），ours(k) 与 union_view(0) 的判定基本一致。草案原来设定的"ours(4) 对 union_view(0)"不能检验任何东西。改为对每个 k 都报告 UR 的差值，不作判定。
3. **按见证大小分层**：每个普通请求，按"包含该单元的最小见证的大小" w_min 分成 w2 和 w3plus 两层，分别报告 UR。草案中"只含 w ≥ 3 见证的单元格"无法直接构造，所以用这种方式替代。

## 1. 对照组

| 组 | 参数 | 规则 |
|---|---|---|
| no_defense | — | 一律放行 |
| ours | k ∈ {2, 3, 4} | E5 的 `GateArm`（现行 `ReleaseGate`，λ = 0） |
| ws04_quota | k ∈ {2, 3, 4} | 每个用户对每个见证 W，最多持有 ⌊(\|W\| − 1)/k⌋ 个单元（Woodruff & Staddon, CCS 2004, Sec. 8 的分配规则，不含隐私检索协议） |
| union_view | δ ∈ {0, 0.5, 1, 2} | 全体接收者的持有 ∪ 本次候选，必须满足 L\* ≤ τ + δ |

Staddon 2003 的令牌方案：没有读到原文，**不纳入**。

## 2. 数据与请求流

- 合成数据 K ∈ {8, 16, 32}，Eedi K ∈ {8, 16, 32}，Sum Leaks 混合池，共 7 个数据单元格；
- c ∈ {0, 0.2}；种子 0–9；
- 请求流与 E5 相同（N = 60，小组人数 g = 2、2、3、3、4、4）。

## 3. 指标

- VR_all；
- UR_normal、DR_normal、CR_complete；
- 每用户 UR 的基尼系数；
- UR_w2 和 UR_w3plus（分层效用）。

## 4. 判定

- **H0（实现核对）**：ws04_quota(k) 在 g ≤ k 的小组上 VR = 0。
- **H1（实现核对）**：union_view(0) 在全部小组上 VR = 0。
- **H-Q（主假设，相同安全约束）**：对每个（数据单元格, c, k），计算 UR_normal 的差值（ours(k) − ws04_quota(k)），做种子间配对 bootstrap（5000 次，随机种子 20261124）。下界 > 0 时，该单元格判"支持"。
  - **全部 42 个单元格都支持**，才判 H-Q 支持；
  - 同时报告分层 UR、CR_complete、DR_normal 和基尼系数的差值。
  - **预先说明**：当 w = 2、k ≥ 2 时，配额 ⌊1/k⌋ = 0，所以 w2 层的差值由构造决定。论文的主要证据是 **E5 的 w3plus 层**；
  - 不得仅凭 UR 的差值就声称"全局可用性更高"。
- **H2（只描述）**：每个 k 下，ours(k) 与 union_view(0) 的 UR 差。
- **H3（只描述）**：union_view(δ > 0) 的 VR 和 UR。

冻结前用种子 99 空跑：14 个单元格；H0 有 168 个小组可核对；H1 有 84 个；w2、w3plus 两层都不为空。

## 5. 产出

- `results/raw.csv`；
- `results/groups.csv`；
- `results/judgments.json`；
- `RESULT.md`。
