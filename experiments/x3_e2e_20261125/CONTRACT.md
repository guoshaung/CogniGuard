# 来源证据交接

Codex 写传播束。Grok 读传播束并调用影子判定。两边不改同一个核心文件。

证据对象的必填字段：

- `evidence_id`
- `evidence_type`：`fingerprint`、`watermark`、`signed_credential`、`trusted_log`、`ideal`
- `artifact_id`
- `candidate_issuance_ids`
- `matched_knowledge_units`：`[resource_id, unit_id]` 对
- `confidence`：0 到 1。水印和指纹的这个数不能变成可信事件
- `verification_status`：`verified`、`unverified`、`conflict`、`absent`
- `trusted_event_id`：没有事件时为 null
- `policy_version`

可选：

- `holdings_asserted`：为真时，空的匹配单元表示检查过且没有剩下这些单元
- `holder_principal_id`：这条持有属于谁。只有可信日志和理想证据会把它写入联盟检查用的知识

内容身份看指纹候选。发行身份看可信凭证或日志里的发行号。实际传播只看带事件号的可信日志或理想证据。当前持有只看声明了持有者的可信单元。这四件事不能互相代替。

传播束见 `schema/propagation_bundle.schema.json`。某个通道缺席，就是这个方法没有观察到它。不要用另一个通道的行填上。

已有试点目录如果后来出现，路径是 `experiments/hsw_provenance/` 下的 `PILOT_RESULTS.md`、`evaluation.json`、`evaluation_38.json` 和 `watermark/orphan_stress.json`。形状对得上传播束才进入计分；对不上就记为未映射，不编造成 616/2052。
