# X5: observable control decisions

Dev scan only (10 synthetic subjects, seeds 0–4). No model calls. `formal` is false. Base SHA `893c6b3fe5e50d1526f2704ca3ae5ed555c4c609`.

`docs/literature_baseline_matrix.md` lists RAGFort, CanaryRAG, the RAG extraction benchmark, RAG-Thief, and IKEA as content-extraction references, all `NOT_RUN` as numeric baselines. Those URLs were not re-opened here. They are low overlap with X5: they target retrieved text, not allow/deny, tool choice, or planner signals.

## Citations

Pages below were opened. The 1988 IEEE S&P composability record and the 2025 HOST Termite record did not return body text, so they are not cited. No opened source compares a content watermark with a metadata label; X3 stays low for that reason.

1. Kenthapadi, Mishra, and Nissim. "Denials leak information: Simulatable auditing." *Journal of Computer and System Sciences* 79 (2013) 1322–1340. https://cs.stanford.edu/people/kngk/papers/denialsLeakInformation-JCSS2013.pdf
   Query denials that depend on the secret answer leak. A simulatable auditor decides from the attacker's history alone, so the allow/deny bit adds nothing.
2. Cretu, Houssiau, Cully, and de Montjoye. "QuerySnout: Automating the Discovery of Attribute Inference Attacks against Query-Based Systems." ACM CCS 2022. https://arxiv.org/abs/2211.05249
   The evaluated attack infers a sensitive attribute from query answers. The opened paper treats an error string as a possible extension, and it assumes bucket suppression returns 0 rather than an error. It does not itself show allow/deny leakage.
3. Debenedetti, Severi, Carlini, Choquette-Choo, Jagielski, Nasr, Wallace, and Tramèr. "Privacy Side Channels in Machine Learning Systems." USENIX Security 2024. https://arxiv.org/abs/2309.05610
   Output filters and query filters turn block/allow into membership signals. Composing differential privacy with deduplication can make privacy worse.
4. Goguen and Meseguer. "Security Policies and Security Models." IEEE Symposium on Security and Privacy, 1982. https://cs.purdue.edu/homes/ninghui/readings/AccessControl/goguen_meseguer_82.pdf
   The opened text layer mangles the title line; authors, year, and the noninterference definition are legible. A policy is a set of noninterference assertions: one group's commands must not change what another group sees.
5. Sabelfeld and Myers. "Language-Based Information-Flow Security." *IEEE JSAC* 21(1), 2003. https://www.cs.cornell.edu/andru/papers/jsac/sm-jsac03.pdf
   End-to-end noninterference, covert channels, and the claim that security-type checking composes when external signatures agree. Access control does not control propagation after a read.
6. Hicks, Tse, Hicks, and Zdancewic. "Dynamic Updating of Information-Flow Policies." Foundations of Computer Security (FCS), 2005. http://www.cis.upenn.edu/~stevez/papers/HTHZ05.pdf
   Year and venue from the author's bibliography page https://www.cs.umd.edu/~mwh/papers/hicks05secupdate.html, which was opened. Hierarchy edges can be revoked. The guarantee is noninterference between updates, which forgets flow history rather than tracking derived copies.
7. Lee. "Logs and side channels." Ph.D. thesis, University of Illinois Urbana-Champaign, 2023. https://www.ideals.illinois.edu/items/128641
   Introduces Termite attacks: audit logs support membership inference and a concurrency timing channel through implicit content, after explicit secrets are the thing one would redact. The 2025 HOST version of Termite was not opened.
8. Attiya, Fernández Anta, Milani, Rapetti, and Travers. "Auditing without Leaks Despite Curiosity." PODC 2025. https://arxiv.org/abs/2505.00665
   A wait-free register logs an effective read in the same atomic step and keeps that log unreadable to other readers (one-time pad). A max register can reveal prior values that were not explicitly read.
9. Shahriar, Rahman, Ahmed, Sadeque, and Parvez. "AgentTell: Behavioural Side-Channel Leakage in Browser-Use Agents." arXiv:2609.32915, 2026. https://arxiv.org/abs/2609.32915
   Choosing a secret-specific action instead of a general one leaks a bit even when the agent was told not to disclose it and even when its own note says it will not.
10. El Yagoubi, Badu-Marfo, and Al Mallah. "AgentLeak: A Benchmark for Internal-Channel Privacy Leakage in Multi-Agent LLM Systems." arXiv:2602.11510, 2026. https://arxiv.org/abs/2602.11510
    In the opened abstract, final-output leakage is 27.2% while inter-agent messages are 68.8% (1,000 scenarios, 4,979 traces). Output-only checks miss internal channels. Tool arguments are named as a pathway; the reported aggregate is C1, C2, and C5, not a separate tool-choice attack.

## Overlap with X1–X5

| Experiment | Overlap | Closest prior mechanism |
|---|---|---|
| X1 policy composition | partial, high only for typed IFC | Sabelfeld and Myers: security-type composition when signatures agree. Debenedetti shows a negative composition (DP plus dedup). |
| X2 revocation and derived data | partial | Hicks et al.: noninterference between updates under hierarchy revocation. It does not revoke derived copies. Simulatable auditing is about prior answers, not revocation. |
| X3 watermark versus metadata | low | None. No opened paper separates a watermark from metadata. |
| X4 concurrency and transactions | partial, high for one audit object | Attiya et al.: atomic auditable register. Lee: concurrent ordering of audit-log events. Neither is a protected transaction over derived data. |
| X5 observable decision signals | high | Simulatable auditing (allow/deny). Debenedetti query/output filters (block as membership). AgentTell (secret-specific action versus a general action). |

`literature_overlap`: X5 high (simulatable auditing; filter allow/block; AgentTell action choice); X1 partial-to-high (security-type composition; filter composition side effects); X2 partial (noninterference between updates, not derived-copy revocation); X3 low (no watermark-versus-metadata source opened); X4 partial (auditable concurrent registers; Termite log ordering).

## Simulation

Secret: one synthetic bit, `secret = (subject + seed) mod 2`. Ten subjects, so each seed is balanced 5/5. The attacker does not see content. Content is the constant string `REDACTED` for both bit values.

Attacker view under C0 and C1: `decision`, `degradation`, `tool`, `replanned`, `conflict`.

- C0, content defense only. The payload is redacted, but the bit still sets the five signals. Secret 1: refuse, degradation 2, tool `redacted_template`, replanned, conflict `policy_conflict:sensitive_attribute`. Secret 0: allow, degradation 0, tool `tutor_retrieve`, no replan, empty conflict.
- C1, traditional mitigations as specified. Decision is the constant `allow`. Tool is the constant `tutor_retrieve`. Conflict is empty. A query record, including the bit, is appended server-side with `shown=false` and is not part of the attacker view. Degradation and `replanned` are not in that specification, so they still follow C0.

Attack success is 1 when the two worlds differ (the observation determines the bit) and 0.5 when they match (chance on a balanced bit). Utility is the fraction of enforced decisions that are allow, on `tutor_retrieve`, at degradation 0. Hiding a label does not change utility. False reject is the fraction of secret-0 subjects that are refused. Overhead is C1 metered steps divided by C0 metered steps (content redaction, the control branch, field emits, C1's three overrides, and the server-side write).

Frozen caps, not used to change the run: safety gain at least 0.10, utility drop at most 0.10, overhead at most 10. STOP would require C1 attack success 0.5. PASS is withheld when the remaining leak is a field a deployer would simply not display.

## Numbers

Same on every seed.

| Condition | Attack success | Utility | False reject | Steps per seed |
|---|---:|---:|---:|---:|
| C0 content defense | 1.0 | 0.5 | 0.0 | 70 |
| C1 constant allow/tool, no conflict, hidden query record | 1.0 | 0.5 | 0.0 | 110 |
| Sketch: also omit degradation and replanned | 0.5 | 0.5 | 0.0 | 130 |

- `safety_gain` (C0 attack success minus C1) = 0.0
- `utility_change` (C1 utility minus C0) = 0.0
- `false_reject_rate` under C1 = 0.0
- `compute_overhead` = 110/70 = 1.5714285714285714
- Hide sketch versus C0 = 130/70 = 1.8571428571428572
- Hide sketch versus C1: attack success falls from 1.0 to 0.5 (gain 0.5), utility drop 0.0

C1 does not stop the leak.

## Counterexample

Gap label: `GAP_OPTIONAL_DISPLAY_DEGRADATION_AND_REPLAN`.

Seed 0, subject 0, secret 0. Attacker sees `{decision: allow, degradation: 0, tool: tutor_retrieve, replanned: false, conflict: ""}`.

Seed 0, subject 1, secret 1. Attacker sees `{decision: allow, degradation: 2, tool: tutor_retrieve, replanned: true, conflict: ""}`.

Allow/deny, tool, and the conflict string match. The bit is recovered from `degradation` or from `replanned`. The server record for subject 1 holds the secret and `shown=false`; it is not in the attacker view. Under C0 the same subject also differs on decision, tool, and the conflict string, so content redaction alone leaks on every listed signal.

## Verdict

ANALYZE. C1 leaves a deterministic leak, so this is not STOP. The leak is only `degradation` and `replanned`. In this model the body is already the constant `REDACTED`, so the numeric degradation field is not required for the caller to use the answer, and the replan flag is planner telemetry. A deployer would simply not display either field. That is why the result is ANALYZE rather than PASS, even though omitting them drops attack success to chance with utility drop 0 and overhead about 1.86, inside the frozen caps.

Smallest mitigation, not a new algorithm and not built as a system: project the client response to `decision`, `tool`, and `conflict` only. Keep degradation, the replan bit, and the query record on the server. Do not choose the constant decision or tool from the secret. This does not address a timing channel or a deployment in which degradation changes visible content; those are outside the observation model used here.
