# CA-PD 与经典推断控制：同一状态下的对比

基准提交：`exp/cogniguard-nowm-phase1@2d8e9b8a88abaf847c7d20fd8137508f32c4dabf`。
授权、见证、请求流和效用定义与该提交的 Phase 1 相同。
每一格里，配额、全局并集代理和 CA-PD 读同一份知识；只有 writer 的放行会写入后续状态。
没有为了制造差异而改见证或威胁模型。

## 复现了哪一条规则

最接近 CA-PD 的可复现披露规则是 Woodruff–Staddon 2004 的共谋配额，不是 PIR 协议。

能读到的原文依据：ePrint 2004/130 的摘要和被检索索引到的正文写明，单用户定义不够实现共谋抵抗；做法是让每个用户在每条推断通道上拿到更少的对象，而且这个限制只依赖该用户已经做了多少次查询，不依赖查询内容。正文把共谋抵抗留到 Section 8。公开讲稿把同一规则概括为：c-共谋抵抗把长度为 m 的通道收成 (m−1)/c。用户审阅原文后的记录给出同一个上限 ⌊(|W|−1)/k⌋。ePrint 的 PDF 在本环境返回 HTTP 403，所以这里不引用 Section 8 的逐句原文。PIR/SPIR 不实现：它隐藏查询，不改变哪些交付满足配额。

Staddon 2003 只读到 ACM 摘要。摘要中的 c-共谋抵抗和 crowd control（很多人已经拿走过通道中除最后一个以外的对象时，谁也不能再拿最后一个）是性质，不是可执行的令牌分配。Sec. 3–4 的令牌构造没有全文，因此不实现令牌方案，也不把令牌方案说成与 CA-PD 等价。全局并集是 crowd control 的代理，保证强于 k-安全，单独报告。

Toland、Farkas、Eastman 2010（Computers & Security）的 Elsevier 全文没有打开。2005 年同一组作者的 D²Mon 性能论文可以读到 Algorithm 1：每个用户一份历史库，用 UpCon 丢掉过期元组，再用 DiIE 对 Horn 子句做闭合，然后由强制访问控制判断闭合结果是否非法。这是单个用户的查询历史加数据库依赖，不是人数不超过 k 的联盟覆盖一个见证。2010 年论文有一节题为推断合作预防，正文未读到，所以不实现一个猜测出来的合作规则。

## 主表（真实状态，writer = capd：后续状态只写入 CA-PD 在真实状态上允许的交付）

效用的分母是决策时刻真实状态上的安全请求。CA-PD 在这一层上就是该安全定义。

| 传播 | k | 授权请求 | 安全/危险 | 配额=CA-PD | 配额拒绝且 CA-PD 安全放行 | 配额安全放行且 CA-PD 拒绝 | 配额不安全放行 | 配额效用 | CA-PD 效用 | 配额危险率 | CA-PD 危险率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| low | 1 | 7401 | 6374/1027 | 7401 | 0 | 0 | 0 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| low | 2 | 7401 | 3490/3911 | 5805 | 1066 | 0 | 530 | 0.6946 | 1.0000 | 0.1355 | 0.0000 |
| low | 3 | 7401 | 2444/4957 | 5899 | 981 | 0 | 521 | 0.5986 | 1.0000 | 0.1051 | 0.0000 |
| high | 1 | 7432 | 5602/1830 | 7432 | 0 | 0 | 0 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| high | 2 | 7432 | 2914/4518 | 6338 | 768 | 0 | 326 | 0.7364 | 1.0000 | 0.0722 | 0.0000 |
| high | 3 | 7432 | 2214/5218 | 6325 | 821 | 0 | 286 | 0.6292 | 1.0000 | 0.0548 | 0.0000 |

## 五个问题

1. 在 k=1 上等价，在 k≥2 上不等价。真实状态、writer=capd 的不一致格子：low/k=2、low/k=3、high/k=2、high/k=3。CA-PD 与同一真实状态上的 Oracle 不一致 0 次。k=1 时配额上限是 |W|−1，和单人补全是同一条规则。

2. 存在。配额拒绝而 CA-PD 安全放行共 3636 条（真实状态，writer=capd，两种传播、k=1..3 合计）。这些请求是 k-安全的。

3. 在真实状态上不存在：writer=capd 的合计是 0 条。全部层、全部 writer 上，只要决策前的知识还在配额不变量里，配额放行而 CA-PD 拒绝的次数是 0。配额在真实状态上另有 1663 条放行，CA-PD 拒绝且 Oracle 判为不安全。nli 层只有 high/k=2 出现配额放行、CA-PD 拒绝、真实状态却安全的判定：external 4 条，writer=capd 6 条，writer=quota 6 条。抽查 seed 4、high、k=2、q119：nli 把 math-01:f1 记在 S3 和 TA 上，真实持有里没有；CA-PD 因此看到联盟 (S1, S3) 并拒绝，配额不看 S3，所以放行。这不是配额在真实威胁模型上安全地放宽了 CA-PD，而是配额忽略了 nli 的误确认。全局并集没有出现“安全放行而 CA-PD 拒绝”。并集多出的拒绝是更强保证。

4. 安全标签用决策时刻真实状态上的 CA-PD(k)。在这个分母上，CA-PD 的效用是 1。配额效用如下，差就是过拒：low/k=1：配额效用 1.0000，危险率 0.0000；CA-PD 效用 1.0000，危险率 0.0000；low/k=2：配额效用 0.6946，危险率 0.1355；CA-PD 效用 1.0000，危险率 0.0000；low/k=3：配额效用 0.5986，危险率 0.1051；CA-PD 效用 1.0000，危险率 0.0000；high/k=1：配额效用 1.0000，危险率 0.0000；CA-PD 效用 1.0000，危险率 0.0000；high/k=2：配额效用 0.7364，危险率 0.0722；CA-PD 效用 1.0000，危险率 0.0000；high/k=3：配额效用 0.6292，危险率 0.0548；CA-PD 效用 1.0000，危险率 0.0000。k≥2 时配额的危险率大于 0，所以它没有达到 CA-PD 已经达到的安全水平：其他主体可以持有超过 ⌊(|W|−1)/k⌋ 的单元，配额不看这些持有。并集的危险率不高于 CA-PD，效用更低，那是更强保证下的损失。

5. 配额对每个被本次放行碰到的见证做一次交集，不随其他主体人数做组合，也不随 k 枚举联盟。CA-PD 对每个受影响见证在缺失单元上做集合覆盖，上界 O(|masks|·2^m)；m>20 才保守拒绝。本数据见证大小不超过 5，too_large 见上文。并集代理先求全体持有的并。实测 P50/P95 见上表。配额更快。这个速度差不构成 CA-PD 相对配额的效率优势。

## 延迟（全部共享轨迹上的判定时间，不含世界生成和证据回放）

| 规则 | 调用次数 | P50 (μs) | P95 (μs) |
|---|---:|---:|---:|
| WS04 配额 | 486000 | 1.7080 | 3.0840 |
| 全局并集代理 | 486000 | 3.1250 | 6.7080 |
| CA-PD | 486000 | 9.0840 | 20.7500 |

## 其余共享轨迹

external：不写入任何请求交付，只比较发行、未记录获得和（nli 层）已确认观察。
quota：只写入配额允许的交付。
并集列是更强的保证，不与 k-安全放在同一安全水平里。

| 轨迹 | 配额=CA-PD | 配额过拒（安全） | 配额安全放行而 CA-PD 拒绝 | 其中配额不变量成立 | 配额不安全放行 | 并集过拒 | 并集安全放行而 CA-PD 拒绝 |
|---|---:|---:|---:|---:|---:|---:|---:|
| receipts/external | 40596 | 1464 | 0 | 0 | 958 | 12261 | 0 |
| receipts/capd | 38282 | 3320 | 0 | 0 | 682 | 10112 | 0 |
| receipts/quota | 37536 | 3603 | 0 | 0 | 567 | 10459 | 0 |
| nli/external | 40502 | 1766 | 4 | 0 | 2024 | 12200 | 0 |
| nli/capd | 38918 | 3543 | 6 | 0 | 1708 | 10629 | 0 |
| nli/quota | 38963 | 3820 | 6 | 0 | 1419 | 10874 | 0 |
| true/external | 40661 | 1822 | 0 | 0 | 2016 | 12361 | 0 |
| true/capd | 39200 | 3636 | 0 | 0 | 1663 | 10908 | 0 |
| true/quota | 39251 | 3865 | 0 | 0 | 1383 | 11149 | 0 |

真实状态上 CA-PD 与 Oracle 不一致的授权请求：0。
配额不变量成立时，配额放行但 CA-PD 拒绝的次数：0。
保守拒绝（too_large）：0。
决策前知识已经超出配额的授权请求：42405 / 44499。
初始发行已经超出配额的世界数：{"low|k=2": 30, "low|k=3": 30, "high|k=2": 30, "high|k=3": 30}。

## 例子

- `q2_union` seed 0 `low|k=1|true|capd` q0 S6 ['math-08', 'math-08:f2']：oracle_safe=True，quota=True，union=False，capd=True，配额不变量=True
- `q2_union` seed 0 `low|k=2|true|capd` q1 TA ['math-09', 'math-09:f3']：oracle_safe=True，quota=True，union=False，capd=True，配额不变量=False
- `quota_unsafe` seed 0 `low|k=2|true|capd` q12 S5 ['statistics-02', 'statistics-02:f2']：oracle_safe=False，quota=True，union=False，capd=False，配额不变量=False
- `q2_quota` seed 0 `low|k=2|true|capd` q32 S4 ['physics-01', 'physics-01:f1']：oracle_safe=True，quota=False，union=False，capd=True，配额不变量=False
- `q2_union` seed 0 `low|k=3|true|capd` q1 TA ['math-09', 'math-09:f3']：oracle_safe=True，quota=True，union=False，capd=True，配额不变量=False
- `quota_unsafe` seed 0 `low|k=3|true|capd` q16 S4 ['physics-05', 'physics-05:f1']：oracle_safe=False，quota=True，union=False，capd=False，配额不变量=False
- `q2_quota` seed 0 `low|k=3|true|capd` q30 COUNSELOR ['profile:S2', 'sig0']：oracle_safe=True，quota=False，union=True，capd=True，配额不变量=False
- `q2_union` seed 0 `high|k=1|true|capd` q3 S2 ['math-09', 'math-09:f2']：oracle_safe=True，quota=True，union=False，capd=True，配额不变量=True
- `q2_union` seed 0 `high|k=2|true|capd` q3 S2 ['math-09', 'math-09:f2']：oracle_safe=True，quota=True，union=False，capd=True，配额不变量=False
- `q2_quota` seed 0 `high|k=2|true|capd` q23 TA ['statistics-08', 'statistics-08:f2']：oracle_safe=True，quota=False，union=False，capd=True，配额不变量=False
- `quota_unsafe` seed 0 `high|k=2|true|capd` q48 S3 ['physics-01', 'physics-01:f3']：oracle_safe=False，quota=True，union=False，capd=False，配额不变量=False
- `q2_quota` seed 0 `high|k=3|true|capd` q4 COUNSELOR ['profile:S5', 'sig2']：oracle_safe=True，quota=False，union=True，capd=True，配额不变量=False
- `q2_union` seed 0 `high|k=3|true|capd` q10 TA ['statistics-04', 'statistics-04:f3']：oracle_safe=True，quota=True，union=False，capd=True，配额不变量=False
- `quota_unsafe` seed 0 `high|k=3|true|capd` q25 S3 ['physics-05', 'physics-05:f2']：oracle_safe=False，quota=True，union=False，capd=False，配额不变量=False
- `q3_quota` seed 4 `high|k=2|nli|capd` q119 S1 ['math-05', 'math-05:f1']：oracle_safe=True，quota=True，union=False，capd=False，配额不变量=False

## Phase 1 已发表的在线轨迹

下面的数来自 `2d8e9b8` 的 `results/formal/runs.jsonl.gz`。
每条规则写入自己的交付，第一次分歧之后知识状态不再相同。这里只作对照，不代替上表。

| 传播 | k | 层 | 规则 | 危险放行率均值 | 效用均值 | P50 μs 均值 |
|---|---:|---|---|---:|---:|---:|
| high | 1 | nli | B2 | 0.1181 | 0.9926 | 1.3152 |
| high | 1 | nli | B4 | 0.0000 | 0.3427 | 4.1694 |
| high | 1 | nli | CAPD(k=1) | 0.1181 | 0.9926 | 8.3348 |
| high | 1 | true | B2 | 0.0000 | 1.0000 | 1.2417 |
| high | 1 | true | B4 | 0.0000 | 0.3264 | 4.8500 |
| high | 1 | true | CAPD(k=1) | 0.0000 | 1.0000 | 7.7568 |
| high | 2 | nli | B2 | 0.0923 | 0.7466 | 1.2986 |
| high | 2 | nli | B4 | 0.0212 | 0.6501 | 4.2111 |
| high | 2 | nli | CAPD(k=2) | 0.0409 | 0.9947 | 9.4000 |
| high | 2 | true | B2 | 0.0721 | 0.7433 | 1.2153 |
| high | 2 | true | B4 | 0.0000 | 0.6419 | 4.9389 |
| high | 2 | true | CAPD(k=2) | 0.0000 | 1.0000 | 8.8819 |
| high | 3 | nli | B2 | 0.0528 | 0.6108 | 1.2779 |
| high | 3 | nli | B4 | 0.0259 | 0.8782 | 4.1597 |
| high | 3 | nli | CAPD(k=3) | 0.0294 | 0.9990 | 9.2680 |
| high | 3 | true | B2 | 0.0455 | 0.6093 | 1.1931 |
| high | 3 | true | B4 | 0.0000 | 0.8792 | 4.9362 |
| high | 3 | true | CAPD(k=3) | 0.0000 | 1.0000 | 8.8708 |
| low | 1 | nli | B2 | 0.0412 | 1.0000 | 1.2250 |
| low | 1 | nli | B4 | 0.0000 | 0.3115 | 3.1098 |
| low | 1 | nli | CAPD(k=1) | 0.0412 | 1.0000 | 9.1487 |
| low | 1 | true | B2 | 0.0000 | 1.0000 | 1.2124 |
| low | 1 | true | B4 | 0.0000 | 0.3115 | 3.3528 |
| low | 1 | true | CAPD(k=1) | 0.0000 | 1.0000 | 8.6946 |
| low | 2 | nli | B2 | 0.1403 | 0.7220 | 1.2500 |
| low | 2 | nli | B4 | 0.0000 | 0.5356 | 3.1029 |
| low | 2 | nli | CAPD(k=2) | 0.0318 | 1.0000 | 9.4237 |
| low | 2 | true | B2 | 0.1267 | 0.7185 | 1.1348 |
| low | 2 | true | B4 | 0.0000 | 0.5356 | 3.3236 |
| low | 2 | true | CAPD(k=2) | 0.0000 | 1.0000 | 8.9084 |
| low | 3 | nli | B2 | 0.0840 | 0.5907 | 1.1529 |
| low | 3 | nli | B4 | 0.0000 | 0.8432 | 3.1431 |
| low | 3 | nli | CAPD(k=3) | 0.0035 | 1.0000 | 9.0750 |
| low | 3 | true | B2 | 0.0785 | 0.5900 | 1.0929 |
| low | 3 | true | B4 | 0.0000 | 0.8432 | 3.3652 |
| low | 3 | true | CAPD(k=3) | 0.0000 | 1.0000 | 8.7958 |

