# X3-E2E 来源证据影子闭环

本目录是一次可运行的接入实验。它不是新的定理，也不把工程集成写成科研贡献。
历史 X1–X5 的 STOP / ANALYZE 与冻结协议没有改写。X3 的五个合法翻转仍然不是水印试点。

## 试点数据

- 状态：`ABSENT`
- `git cat-file -t d7239c4`：exit 128: fatal: Not a valid object name d7239c4
- `origin/codex/hsw-st`：exit 0: 9be4d7301c139361664c25f47e75f6ef988efe77
- The cited server pilot was not measured here. 38 sources, 1288 endpoints, and 616/2052 are unverified user-side claims.
- 下表的水印行全部是受控夹具，标签为 `controlled_fixture`。理想证据列是 Oracle 臂。

## 对照

| 臂 | 未授权成功率 | 正常任务成功率 | 误拒率 | 放行中的联盟违规 | 错误归因授权次数 | 相对 B0 新增正确决策 | 传播确认次数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| B0 | 0.429 (3/7) | 1.000 | 0.000 | 0.045 | 0 | 0 | 0 |
| B1 | 0.429 (3/7) | 1.000 | 0.000 | 0.045 | 0 | 0 | 0 |
| B2 | 0.286 (2/7) | 1.000 | 0.000 | 0.048 | 0 | 1 | 0 |
| B3 | 0.286 (2/7) | 1.000 | 0.000 | 0.000 | 0 | 1 | 7 |
| B4 | 0.429 (3/7) | 1.000 | 0.000 | 0.045 | 0 | 0 | 0 |
| B5 | 0.429 (3/7) | 1.000 | 0.000 | 0.045 | 0 | 0 | 0 |
| Ours | 0.000 (0/7) | 0.947 | 0.053 | 0.000 | 0 | 3 | 7 |
| Oracle | 0.000 (0/7) | 1.000 | 0.000 | 0.000 | 0 | 3 | 26 |

## 延迟

中位值为单次影子决策的毫秒数，重复 5 轮。没有调用 MySQL，也没有调用水印服务器。

- B0: 0.0094 ms，相对 B0 1.00 倍
- B1: 0.0077 ms，相对 B0 0.81 倍
- B2: 0.0080 ms，相对 B0 0.85 倍
- B3: 0.0077 ms，相对 B0 0.82 倍
- B4: 0.0077 ms，相对 B0 0.82 倍
- B5: 0.0074 ms，相对 B0 0.79 倍
- Ours: 0.0091 ms，相对 B0 0.97 倍
- Oracle: 0.0111 ms，相对 B0 1.18 倍

## 分场景

- `s1-same-perm-meta` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。meta keeps an issuance id; that id is not trusted
- `s2-other-grantee` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。metadata and receipt stripped
- `s4-teach-read` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。metadata and receipt stripped
- `s3-live-copy` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。revoked sibling iss-a4-old is not this copy
- `s6-external-copy` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。boundary drops metadata; registry has no redistribution field
- `same-text-two-issuances` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。one body, education and research issuances; the credential names teaching
- `research-on-teaching-copy` oracle=N B0=Y B1=Y B2=N B3=Y B4=Y B5=Y Ours=N Oracle=N。wrong mark says research; the true copy is the teaching issuance
- `rounds-1` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。controlled mark confidence 0.9 after 1 hops; the log does not decay
- `rounds-3` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。controlled mark confidence 0.5 after 3 hops; the log does not decay
- `rounds-5` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。controlled mark confidence 0.2 after 5 hops; the log does not decay
- `summary-credential-kept` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。summary keeps the embedded credential
- `paraphrase-credential-lost` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。paraphrase drops the credential; a weak mark remains
- `fusion-two-sources` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。derived text keeps both source logs
- `metadata-missing` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。no source metadata channel exists on this artifact
- `residual-mark-knowledge-gone` oracle=N B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=N Oracle=N。credential and mark remain; the knowledge check asserts no units
- `detector-false-empty` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=N Oracle=Y。units are still present; the controlled mark falsely asserts they are gone
- `copied-mark-wrong-grantee` oracle=N B0=N B1=N B2=N B3=N B4=N B5=N Ours=N Oracle=N。outsider has no grant; the copied mark names u2
- `independent-generation` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。same units generated independently; fingerprint collides with A1 and is not a hop
- `grant-expired` oracle=N B0=N B1=N B2=N B3=N B4=N B5=N Ours=N Oracle=N。the grant's expires_at equals now, so the registry denies
- `policy-version-bump` oracle=N B0=N B1=N B2=N B3=N B4=N B5=N Ours=N Oracle=N。ownership policy is 2; the grant and the credential stay at version 1
- `readme-stays-authorized` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。the key policy bump does not revoke the readme grant
- `unrecorded-share` oracle=N B0=Y B1=Y B2=Y B3=N B4=Y B5=Y Ours=N Oracle=N。partner already holds unit b; only a trusted log may enter that holding
- `edu-one-unit` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。one witness member; k=2 does not finish the target
- `sibling-revoked-live-grant` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。iss-a4-old is revoked; iss-a4-new still authorizes
- `edu-completing-unit` oracle=N B0=N B1=N B2=N B3=N B4=N B5=N Ours=N Oracle=N。s1 holds unit a; releasing b to s2 finishes the witness
- `attribute-one-signal` oracle=Y B0=Y B1=Y B2=Y B3=Y B4=Y B5=Y Ours=Y Oracle=Y。one attribute signal; the other signal is not held

## 真实 ReleaseGate

教育探针走现有 `ReleaseGate`：学生 s1 取得教材的一个单元并提交回执；
s2 再取互补单元的原因是 `reconstruction`；
无授权陌生人的原因是 `unauthorized`；
学生属性一个信号允许=True，
互补信号的原因是 `reconstruction`。
属性目标种类是 `student_attribute`。

软件探针同样走 `ReleaseGate` 和 `RegistryHolder`。
runbook 预留=True；策略版本升到 2 之后提交成功=False；
再次申请密钥的原因是 `unauthorized`；
readme 仍允许=True。
影子模块没有调用 `evaluate_and_reserve`。

## 接口回归

五个历史翻转在去掉注册表回退时：普通水印不允许，内嵌签名凭证允许。
这只说明适配器没有把水印置信度当成授权。它不推翻 X3 的 STOP。

- `s1-same-perm-meta` watermark_only=False credential=True production_change=False
- `s2-other-grantee` watermark_only=False credential=True production_change=False
- `s4-teach-read` watermark_only=False credential=True production_change=False
- `s3-live-copy` watermark_only=False credential=True production_change=False
- `s6-external-copy` watermark_only=False credential=True production_change=False

## 怎么读这些数

B4 与 B0 的授权应当一致：普通水印不授予、不确认传播、不把单元写入知识。
B3 只在可信日志写明持有者时补上未记录传播，从而拦下 B0 会放行的联盟完成。
Ours 在残留标记且知识检查为空时，会否决仍有效的签名凭证。
检测器把仍在的单元报成空时，Ours 会误拒，B2 不会。两种结果都保留。
全部决策的 `charged_budget` 都是 false。
