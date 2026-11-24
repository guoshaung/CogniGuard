# 组会记录：并行安全扫描（2026-11-25）

开发扫描，不是 30 种子的正式实验。父提交 `893c6b3fe5e50d1526f2704ca3ae5ed555c4c609`，分支 `dev/confidential-secrets`。历史 X1、X3 保持 STOP。`x1_diag` 与 `x3_diag` 是事后效用诊断，不改冻结协议，也不把 STOP 改成 PASS。本次没有改 `cogniguard/` 或 `protection/`。

冻结的开发扫描规则：安全增益 ≥ 0.10，效用下降 ≤ 0.10，开销比 < 10。标准锁、事务、幂等键、已有 `check_release` 不能 PASS。

## 1. 当前判定表

| 方向 | 判定 | 一句话 |
| --- | --- | --- |
| X1 任务级联合选择 | STOP | 已有门已经挡住 p2+p4；相对串行门的安全增益是 0 |
| X2 撤销与派生副本 | STOP | 最强基线 B2 已经是 0 次未授权交付/执行 |
| X3 水印相对元数据 | STOP | 未授权成功在失败关闭下已经是 0；水印没有堵住攻击 |
| X4 并发与重复提交 | ANALYZE | 普通 SQLite 事务仍会把同一事件写两次；补事件号是幂等键 |
| X5 决策字段侧信道 | ANALYZE | 漏的是 degradation 和 replanned；不展示即可 |
| E9/E10 | BLOCKED | 没有冻结协议。远程只有标明未冻结的草案 |

### X1 STOP

协调脚本的同时释放 p2+p4：B4 违规率 0.6667（4/6），已有 `check_release` 为 0。两边任务成功都是 1.0，假拒绝都是 0。延迟大约 0.00035 ms 对 0.00217 ms（摘要里是 0.000347 ms 对 0.002169 ms）。B4 看不见「每一份都允许、合在一起才补齐见证」的情况，现有门看得见。这不是新协调器。

后来的背书视图日程（4 个固定日程）：B4 确定性违规 8 次，率 0.1311。`serial_gate` 和 `joint_commit` 都是 0 次违规，良性成功都是 0.90。5 个开发种子：`joint_commit` 良性成功 0.9091（50/55），串行门 0.5455（30/55），两边违规都是 0。相对这道门的安全增益是 0。

`x1_diag` 复跑后的标签是 PLANNER，诊断判定 STOP。各方法用同一份任务、同一组候选和同一组 `candidate.utility`。每个任务的最高候选效用都是 1，所以效用优先排序实际是按任务名排序，把 `u_test` 放在最后，再交给串行门。开发种子上它的良性成功也是 0.9091，违规 0，与 `joint_commit` 相同。两步前瞻在开发种子上仍是 0.5455：下一步效用同样是 1，平局时保留当前这次安全放行。用 `Random(seed)` 打乱同一批任务后再走串行门，5 个种子都只少交 `u_test`，合计 50/55。收益来自执行顺序，普通重排加现有门已经补上。不继续做联合选择算法。

### X2 STOP

最强基线是 B2，依赖传播，并在缓存送达、未来读取、排队执行时复查。确定性未授权交付/执行 0/10，任务成功 12/12，假拒绝 0，开销比 1.0。候选与 B2 的决策相同。B3 是现有 `ReleaseGate` 的预留加提交复查：策略版本推进后，它取消 asset-a 的在途释放，但不取消一份登记成 derived-a、且不在提交比较列表里的派生缓存。已获得的知识不计为违规。

### X3 STOP

不要写成通过。失败关闭下，F7 和理想水印的未授权成功都是 0。协调脚本：F7 效用 0.7143，W0 效用 0.8571，合法翻转 1 次，开销大约 0.016 ms 对 0.017 ms（0.0159 对 0.0173）。翻转的是元数据缺失时收回的合法请求，不是拦住的攻击。

更全的工人目录按同一失败关闭规则重打分：120 个请求，未授权成功全是 0。分母是 oracle 允许的 70 次，拒绝 50 次。W0 为 50/70，F5 为 30/70，F7 为 25/70。假拒绝分别是 20/70、40/70、45/70。15.6 倍开销是失败打开规则下 W1 相对 F2，超过冻结上限 10，阈值没有改。

`x3_diag` 把五个合法翻转单独抽出。五个案例的 oracle 与 W0 都允许，没有另一条已经登记的发行能授权同一主体、动作和目的。签名内嵌凭证 CRED 用与理想水印相同的发行号列表，在精确文本和轻改写上做 HMAC，释义文本上不带。CRED 对这五例全部允许，所以五例在公平基线下都不成立，没有写 `PILOT_HANDOFF.md`。其中 `s1-same-perm-meta` 的元数据里本来就有发行号，F5 和完整来源记录也能允许。另外四例的元数据和回执已被去掉，理想水印是原方法里唯一还带着真实发行号的通道；CRED 带着同一份名单，不靠水印。重测的 15.6 倍来自 W1 里的 simhash：simhash 0.572 ms，是 F2 的 14.6 倍；回执校验 0.0008 ms，理想标记查找 0.0002 ms。F1 MinHash 是 3.70 ms，约为 F2 的 94 倍。F3/F4 仍是 BLOCKED：本机没有 `torch` 或 sentence-transformers，没有本地权重。远程 `bge-small-en-v1.5` 的权重约 133MB，没有把正文下下来，也没有编造分数。X3 仍是 STOP。

### X4 ANALYZE

普通 SQLite 事务（L1，`BEGIN IMMEDIATE`）仍然双写 `duplicate_event` 和 `retry_after_commit`。`event_key` 相对 L1 的安全增益 0.2857（7 个确定性用例里 L1 错 2 个；RESULT.md 印成 0.286），效用变化 0，开销比大约 0.95（0.951）。它是标准幂等键，不是论文机制。进程内的门把见证竞争串行化了。MySQL `DisclosureStore` 没有启动。

### X5 ANALYZE

C1 攻击成功 1.0，因为 `degradation` 和 `replanned` 仍然随秘密比特变化。不展示这两项后，攻击成功降到 0.5，效用下降 0。这是展示选择。C1 相对 C0 的开销大约 1.57（110/70）。正文在所有格子里都是常数 `REDACTED`。

### E9/E10 BLOCKED

本检出、所列工作树的 HEAD、提交说明、文件名和 14 个 PR 里，都没有冻结的 E9/E10。PR #13（`docs/research-sync-20261124` @ `1de55a0`）有两份草案，文件头写「未冻结」，并写明冻结前不得跑网格。细节和命令在 `e9_e10_search.md`。水印 stage9/stage10 不是这个协议。

## 2. 图表数据

下列表可直接贴进幻灯片。标签：**dev-scan，不是 30 种子正式实验**。规则：安全增益 ≥ 0.10，效用下降 ≤ 0.10，开销比 < 10；标准机制不能 PASS。

### X1 四方法：固定日程与开发种子

固定日程，4 个会话。效用是良性任务里目标单元送达的比例。

| 方法 | 违规次数 | 违规率 | 良性成功 | 联合会话 |
| --- | ---: | ---: | ---: | ---: |
| B4 | 8 | 0.1311 | 1.0000 | 4/4 |
| joint_commit | 0 | 0.0000 | 0.9000 | 0/4 |
| serial_gate | 0 | 0.0000 | 0.9000 | 0/4 |
| snapshot_gate | 1 | 0.0164 | 0.9250 | 1/4 |

开发种子，5 个，轮次顺序打乱。两边违规都是 0 的方法，安全增益相对串行门为 0。

| 方法 | 违规次数 | 违规率 | 良性成功 | 联合种子 |
| --- | ---: | ---: | ---: | ---: |
| B4 | 9 | 0.1000 | 1.0000 | 5/5 |
| joint_commit | 0 | 0.0000 | 0.9091 | 0/5 |
| serial_gate | 0 | 0.0000 | 0.5455 | 0/5 |
| snapshot_gate | 0 | 0.0000 | 0.5455 | 0/5 |

早期同时释放表（不要和上表混用）：B4 违规率 0.6667，门为 0，任务成功都是 1.0，假拒绝都是 0。

### X3 失败关闭：效用与未授权率

协调脚本，未授权成功都是 0。

| 方法 | 未授权成功 | 效用 | 毫秒 |
| --- | ---: | ---: | ---: |
| F7 | 0 | 0.7143 | 0.0159 |
| W0 | 0 | 0.8571 | 0.0173 |

重打分，120 个请求，未授权成功都是 0。

| 方法 | 未授权成功 | 效用 | 假拒绝 | 正确 |
| --- | ---: | ---: | ---: | ---: |
| F5 | 0 | 0.4286 | 0.5714 | 80/120 |
| F7 | 0 | 0.3571 | 0.6429 | 75/120 |
| W0 | 0 | 0.7143 | 0.2857 | 100/120 |
| W1 | 0 | 0.7857 | 0.2143 | 105/120 |

15.6 倍不在这张失败关闭表里。它是失败打开的 W1 对 F2。

### X4 仍失败的用例

L1 是一条 SQLite 事务。`event_key` 是这条事务加上唯一事件号。

| 用例 | L0 | L1 | L2 | event_key |
| --- | --- | --- | --- | --- |
| duplicate_event | 双写 | 双写 | 双写 | 1 行 |
| retry_after_commit | 双写 | 双写 | 双写 | 重放，1 行 |
| witness_race | 无 | 无 | 两次都交付 | 无 |

进程内的门在见证竞争上只交付一次。L1 的违规率 0.286（2/7），`event_key` 为 0，效用变化 0，开销比 0.951。

### X5 攻击成功

每个种子相同。秘密是平衡比特。攻击者看不到正文。

| 条件 | 攻击成功 | 效用 | 假拒绝 | 每种子步数 |
| --- | ---: | ---: | ---: | ---: |
| C0 只涂内容 | 1.0 | 0.5 | 0.0 | 70 |
| C1 固定 allow/工具、无冲突、查询记录不展示 | 1.0 | 0.5 | 0.0 | 110 |
| 草图：再去掉 degradation 和 replanned | 0.5 | 0.5 | 0.0 | 130 |

### X1 诊断：同一计划下的良性成功

违规都是 0。开发扫描 55 个良性任务。`exact_subset` 在 17 个任务的开发会话上没有跑，因为超过 16 的枚举上限。

| 方法 | 固定日程 40 个良性任务 | 开发种子 55 个良性任务 |
| --- | ---: | ---: |
| serial_gate | 36/40 | 30/55 |
| joint_commit | 36/40 | 50/55 |
| utility_greedy_reorder | 36/40 | 50/55 |
| lookahead_2 | 36/40 | 30/55 |
| exact_type_ban | 36/40 | 50/55 |
| 打乱顺序后的 serial_gate | — | 50/55 |

### X3 诊断：效用分子和五个案例

效用分母是 70 次 oracle 允许。未授权分母是 50 次 oracle 拒绝，分子都是 0。

| 方法 | 效用 | 五例上的允许 |
| --- | ---: | ---: |
| W0 | 50/70 | 25/25 |
| F5 | 30/70 | 5/25 |
| F7 | 25/70 | 0/25 |
| F6 | 15/70 | 0/25 |
| CRED | 50/70 | 25/25 |
| Oracle | 70/70 | 25/25 |

## 3. 架构变化

这次扫描没有改任何 `cogniguard/` 或 `protection/` 文件。父提交已经包含机密属性这条线上的工作，到 `893c6b3` 为止：学生属性走同一道放行门，`confidentiality_level` 是 `copyright_level` 的只读别名，计量失败发生在预算扣费之前。

| 已在父提交中 | 位置 | 这次扫描 |
| --- | --- | --- |
| `AccessRegistry.is_authorized` | `cogniguard/governance/access_policy.py` | 未改 |
| `ReleaseGate.evaluate_and_reserve` / `commit` | `cogniguard/runtime/release_gate.py` | 未改 |
| `check_release` | `cogniguard/governance/reconstruction.py` | 未改 |
| `LexicalMeter`（`lexical-v1`） | `cogniguard/runtime/meters.py` | 未改 |
| `attribute_target` | `protection/student_profile/src/fopd/secret_targets.py` | `893c6b3` 加入，本次未改 |
| `confidentiality_level` | `protection/common/schemas.py`，等于 `copyright_level` | `893c6b3` 加入，本次未改 |
| 计量失败则拒绝且不扣预算 | `test_meter_failure_refuses_before_budget_or_approval` | 父历史已有，本次未改 |

`ReleaseGate.select_and_reserve` 也已经在同一文件里：只在授权且 `check_release` 通过的候选中，按效用减价格取一个再预留。它不是这次扫描新加的，也没有被记成 X1 的新贡献。`joint_commit`、水印、事件号、隐藏 degradation 都只活在 `experiments/parallel_x_20261124/` 的脚本里，没有进产品代码。不要把未建的协调器画成已实现。

## 4. 已实现算法与数学定义

只写仓库里有、并且这次扫描调用过的部分。

一次放行不安全，当且仅当某个见证能被一个包含接收方、规模至多 k 的联盟补齐。`check_release` 把接收方已持有的单元并上本次候选；见证已满则接收方单独违规；缺失单元不超过默认 20 时，帮手人数 ≤ k−1 即违规；缺失集更大则保守当成已经暴露。

X1 诊断里的效用，是良性任务中目标单元被送达的比例。早期协调表里的 task success 是另一列，两边都是 1.0，不要和良性成功 0.90 / 0.9091 混读。

`is_authorized(principal, resource, purpose, acting_org, now)`：所有者，或者目的和 `policy_version` 都与当前所有权一致、且未过期的授权。`now >= expires_at` 算过期。`acting_org` 必须是主体的组织之一，并且等于资源的组织。`org_of` 不是授权接口。

`evaluate_and_reserve` 先做计量；计量抛错则返回 `meter_error`，不预留、不扣预算。然后授权，再跑 `check_release`，通过才预留。`commit` 再查一次：策略版本变了或 `is_authorized` 失败，就取消全部回执并返回 false。

`LexicalMeter` 默认 n=4，覆盖阈值 0.5，最长公共子串比阈值 0.3。短单元做子串包含。库里没有正文的单元按已披露计。方法名 `lexical-v1`。

`attribute_target` 把每个信号组做成一个见证集，目标 id 是 `student_id/attribute`，`kind` 为 `student_attribute`。承诺由调用方传入；属性值和盐不进目标。学生属性和教学资产共用一个 `TargetRegistry` 和一道 `ReleaseGate`。

`joint_commit` 和水印都不是已采纳算法。

## 5. 失败原因与当前研究问题

X1 停，是因为洞已经被现有门补上。后补比较里 `joint_commit` 和串行门的违规都是 0，安全增益是 0。种子打乱后的效用差（50/55 对 30/55）是扣哪一块，不是少放了一次违规。`x1_diag` 说明普通重排加上这道门就能达到 50/55，诊断判定 STOP。

X2 停，是因为 B2 的确定性违规已经是 0，任务成功 1.0，假拒绝 0，开销比 1.0。B3 留下的洞是未列入提交比较的派生缓存，B2 的依赖传播已经盖住它。

X3 停，是因为失败关闭的未授权成功在 F7 和理想水印上都是 0。W0 的 50/70 对 F7 的 25/70 多出来的是合法请求。五个翻转在签名凭证下全部恢复，所以不交给真实水印试点。15.6 倍是 simhash，不是水印核验，并且仍然超过上限 10。F3/F4 仍因本机没有可运行的模型而 BLOCKED。

X4 停在 ANALYZE，是因为剩下的双写用唯一事件号就能消掉，而这是现有事务上的标准幂等键。见证竞争已经被进程内的门串行化。跨进程的 MySQL 存储这次没有启动。

X5 停在 ANALYZE，是因为 C1 仍确定性地漏出比特，所以不是 STOP；漏出的字段不展示就回到 0.5，效用下降 0，所以也不是新算法的 PASS。正文已经是常数 `REDACTED`。

不是新算法的两处扩展：不要把 degradation 和 replan 展示给调用方；在现有事务上放唯一事件号。留下的核心是现有的联合检查（`check_release`）加上提交复查。

这两个问题已经有诊断结果，历史 STOP 不变。X1 的效用差可以由执行顺序解释，效用优先重排在效用全部为 1 时退化为按任务名把测试结果放在最后。X3 的五次合法允许可以由签名里的发行号恢复，不需要水印。没有新的未决机制要在这次组会上展开。

### X1 与已有安全约束规划的重叠

问题是：在安全候选里挑选、以保住任务效用，是不是已经有的约束选择。重叠高就表示这是普通约束选择，不是新的 CogniGuard 机制。直接打开页面时，`web_fetch` 对下面四个地址都因 SSRF 失败（解析到 198.18.0.0/15）：`https://arxiv.org/abs/2602.11416`、`https://arxiv.org/abs/2611.24839`、`https://xinyi-yu.github.io/papers/2022CEP.pdf`、`https://www.cs.purdue.edu/homes/ninghui/readings/AccessControl/brewer_nash_89.pdf`。下面四条用的是检索工具返回的页面摘录，没有另造论文。

| 文献 | 年 | URL | 是否已在安全候选中为任务效用做选择 |
| --- | --- | --- | --- |
| Brewer, Nash. The Chinese Wall security policy. IEEE S&P | 1989 | https://doi.org/10.1109/SECPRI.1989.36295 | 否。SciSpace 摘要：允许的访问由以往访问历史约束，分析师只能接触不与已有任务冲突的公司。这是历史约束下的允许集，没有在剩余安全对象上最大化任务效用 |
| Yu, Yin, Li, Li. Security-preserving multi-agent coordination for complex temporal logic tasks. Control Engineering Practice 123, 105130 | 2022 | https://xinyi-yu.github.io/papers/2022CEP.pdf | 是。摘录中的问题 3.1：计划必须满足 LTL、满足两类信息流安全，并且代价不差于任何其他满足这两条的计划 |
| Optimizing Agent Planning for Security and Autonomy（Prudentia）. arXiv:2602.11416 | 2026 | https://arxiv.org/abs/2602.11416 | 是。摘录：把策略遵守和任务进展一起规划，在需要展开变量时于「请求背书」和「不背书、从而污染上下文」之间选择，以减少人工批准。作者名本次摘录里没有，不补 |
| Mallick, Rose, Laws, Oprea, Nita-Rotaru. Kaer: Security-Aware Replanning for Multi-Agent Systems. arXiv:2611.24839 | 2026 | https://arxiv.org/abs/2611.24839 | 是。修订限制在确定的修复算子上，改过的计划必须满足预设策略；摘要模板会在部分任务上压低效用。这是策略内的重规划，不是联盟见证 |

仓库里的 `select_and_reserve` 已经在通过 `check_release` 的候选上按效用减价格取最大者。X1 扫描里相对串行门的安全增益是 0。把「联合提交以便少扣良性任务」说成新机制，和上述规划论文以及这段现有代码都是同一类约束选择。

`x5_behavior/results/literature.json` 里已记录、本次没有重新打开全文的两条只说明组合，不说明效用选择：Goguen 与 Meseguer 1982 把策略写成无干扰断言；Sabelfeld 与 Myers 2003 写安全类型在外部签名一致时可组合。X5 的 RESULT 称这两页当时打开过。Purdue 上的 PDF 本次 `web_fetch` 失败。

## 6. 复现

- 父提交：`893c6b3fe5e50d1526f2704ca3ae5ed555c4c609`。
- 新提交与本文是同一次提交，正文不能写入该提交自己的哈希，否则哈希会变。提交后执行 `git rev-parse HEAD`。本次只在本地，没有推送。
- 验收：`PATH="/tmp/cg-pytest/bin:$PATH" python -m pytest experiments/parallel_x_20261124/acceptance/test_score.py -q`。2026-11-25 重跑为 **33 passed**（0.03 s）。这是打分器夹具，不是 X1–X5 的通过。
- 路径都在 `experiments/parallel_x_20261124/`：`CONTRACT.md`、`ROUND1.md`、`RECONCILE.md`、本文、`e9_e10_search.md`、`acceptance/`、`x1_policy/`、`x2_auth/`、`x3_issuance/`、`x4_consistency/`、`x5_behavior/`、`x1_diag/`、`x3_diag/`。诊断脚本可再跑：`PATH="/tmp/cg-pytest/bin:$PATH" python experiments/parallel_x_20261124/x1_diag/run.py`。X1 这次复跑仍是 PLANNER / STOP，安全增益 0。
- 正式阈值没有按这次测量重拟合。没有付费 API，没有下载 BGE，没有启动 MySQL。
