# 历史证据核对

- HSW R35 实际根据当前前缀的知识修改风险调节 KGW 偏置。12 份 M3 的知识审核为 10 PASS、1 FAIL、1 UNKNOWN，公开检出 3/12，联合 3/12。冻结线要求检出 10/12 且联合不低于历史 4/12，未达标。风险针对知识被改坏，原程序没有 CA-PD 联盟见证或未来请求反事实。历史报告 SHA-256 为 `3e20df6ee78a02cd6c4f673690496174234f34f5a133914aaaad8d5a3da65292`。
- HSW R39 已真实做过资源级水印。逐资源密钥 KGW 实测 30 个资源，全文按各自预分配密钥检出 30/30。起始 50 Token 的唯一正确来源定位为 2/30，MinHash 为 24/30，两者留出无标记背景的任意候选误报均为 3/117。保持信号 B 的 STOP。原实验 `f45144c1`，恢复报告 SHA-256 为 `342226eb27d5a137791958665b8be5fabd6fb2172248fa6154dcd817e1bf1e15`。恢复的逐资源偏置代码逐行分配互异 key。
- 初代 HSW 前缀 Pilot 按发行人写前缀、按内容检索来源。KBPW 后续 M1 用发行 ID，M2/M3 用发行与事实组合作键。真实摘要、强改写无原载体被检测到。Gate W0 末五词中带标的 382 次观察均裁掉句首码字。保留历史 STOP。 [结构审计](../gate_w0_real/closeout/STRUCTURAL_AUDIT.md)
- `fcf1374` 的 BGE+NLI 固定见证回放为 99/137、F1=0.825、过拒 4/835。独立提交已送达 Issue #16。`integration/provenance-governance@3ec09c0` 记录接收与运行计划，此次远端可查版本仍无该正式网格结果。之前的接入检查使用 1,254 个候选键。 [NLI 交接](../gate_w0_real/unit_checker/HANDOFF.md)
- 联盟风险使用既有 pe-1.0 判定内核。联合风险和知识状态规则的查新边界参考 `b23c42c` 中的 `docs/research/PRIOR_ART_AUDIT_20261124.md`。在远端 `3ec09c0` 的可见目录中暂未发现另行命名的 Claude RKW 历史审计。
