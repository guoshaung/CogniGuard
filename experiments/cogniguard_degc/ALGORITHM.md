# DEGC 算法与复杂度

实现：`cogniguard/governance/degc.py`。接入实际执行路径：`experiments/cogniguard_degc/gate.py`。

```
输入: 接收方 r, 回答 x, 信念 B (可信单元 + 不确定观测), 注册表 𝒲, 联盟上界 k,
      δ, 每请求核验上限 c, 总预算 Bv, 校准器 Cal_det / Cal_ver, 核验器 V
1  对每张表 u: f ← features(x, u)            # 归一化匹配, BGE+NLI, 余弦, 是否桥接表
              (q, q_lo, q_hi) ← Cal_det(f)     # 经校准的 P(u ∈ U_x)，带 Beta 区间
              pend ← pend ∪ {Obs(r, u, q, q_lo, q_hi)}
2  R⁰ ← Risk(B, ∅)                             # 历史上已可重构的概率
3  (R, R_lo, R_hi) ← Risk(B, pend) 在 p / lo / hi 下分别计算
4  while R_lo ≤ R⁰+δ < R_hi  且  本请求已核验 < c  且  已用 < Bv:
5      pool ← { 未核验, 0<p<1, 单元属于某个见证 的观测 }   # 含已放行的历史回答
6      o* ← argmax_{o∈pool}  h(R) − [ p_o·h(R|o=1) + (1−p_o)·h(R|o=0) ]
7      (p, lo, hi)_{o*} ← Cal_ver(V(o*))         # 核验结果仍是概率观测
8      重新计算 (R, R_lo, R_hi)
9  if R ≤ R⁰+δ:  放行；B ← B ∪ pend
10 else:          拒绝（返回拒答文本）

Risk(B, pend):
   m ← { (i, u) : u 属于某个见证, 0 < P_i(u) < 1 }   # k = 1 时只考虑 i = r
   若 |m| ≤ 12:  精确枚举 2^|m| 种取值，每种取值调用 CA-PD 核判断是否可重构
   否则:        蒙特卡洛采样（默认 1,024 次，仿真中 256 次）
   P_i(u) = 1，若 u 是 i 的可信单元；否则为 i 对 u 所有观测的 noisy-OR（或 max）
```

| 步骤 | 复杂度 |
|---|---|
| Risk | O(2^m · T_CAPD)；T_CAPD 为 CA-PD 的位掩码动态规划。Sum Leaks 中 k = 1、m ≤ 5，即最多 32 次核调用 |
| 一轮核验选择 | O(\|pool\| · 2 · Risk)；pool 只含见证相关观测 |
| 每请求 | O(c · \|pool\| · Risk)，外加最多 c 次核验器调用 |
| 实测（Sum Leaks，M1 CPU） | 决策计算 P50 约 0.2 ms、P95 约 0.6 ms（不含检测器与核验器），见 RESULT.md |

**消融开关**（`DegcConfig`）：

| 开关 | 效果 | 对应组 |
|---|---|---|
| `use_epistemic=False` | 不触发核验，只用机会约束 | B2 |
| `use_leakage=False` | 按单元熵 h(p) 核验，再对 MAP 状态调用确定性核 | B3 |
| `selector="ec2"` | 用 R(1−R) 选择核验对象 | EC2 |
| `trigger="entropy"` | 用 h(R) ≥ η 触发核验，与 δ 无关 | HZ |

预算相关参数：`per_request_cap`、`budget`。误拒成本仅在 B7 中显式出现（λ = δ，核验成本 `vcost`）。
