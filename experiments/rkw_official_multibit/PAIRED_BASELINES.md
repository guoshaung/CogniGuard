# KGW 与 TextSeal 配对教师预检

在 RTX 5090 上用固定 Qwen2.5-0.5B-Instruct、BF16、seed 61126、batch 4、48 个新 token、temperature 0.8 和 top-p 0.95。三臂均读取同一批 12 条训练提示。使用上游 TextSeal v2.0.0 的生成循环，KGW 调用 CogniGuard 已有 LogitsProcessor。保留三臂原始生成文本以及两组共用的重新生成 clean 对照。评估文件未上传到服务器的此次运行目录。 [预先锁定](PAIRED_BASELINES_LOCK.json) · [运行协议](baseline_results/protocol.json) · [原始输出与打分](baseline_results/predictions.jsonl)

- 无标记 12/12 输出，576 token，生成 2.562 秒。KGW 检出 0/12，TextSeal 检出 0/12。知识核查合格 1/12。
- KGW 12/12 输出，576 token，生成 3.046 秒。以 z > 3 检出 4/12。知识核查合格 0/12。
- TextSeal 12/12 输出，576 token，生成 4.776 秒。以 unweighted p < 0.01 检出 6/12。知识核查合格 0/12。首批包含首次调用开销。
- 重新分词均达到 48 token。本次生成接口返回文本，不直接返回 EOS 状态，源文件保留全部结果。内容复核逐条检查要求的解释、数值及单位。电阻题中错误包括将目标 2 A 写为 0.15 A 或 1 A，另有一条给出 2 A 但随后误述比例常数。 [逐条判据](baseline_results/teacher_qualification.jsonl) · [汇总](baseline_results/summary.json)

教师配对未通过知识保真验收，两组新生成目标仅作诊断，本批学生训练为 0。检出率按固定检测器分别计算，12 条 clean 样本不足以校准同一实际误报率。这两个基线在此次运行各使用一个固定密钥，没有按来源扫描不同密钥，故来源识别结果不适用。 [KGW 教师候选](baseline_results/train_kgw.jsonl) · [TextSeal 教师候选](baseline_results/train_textseal.jsonl)
