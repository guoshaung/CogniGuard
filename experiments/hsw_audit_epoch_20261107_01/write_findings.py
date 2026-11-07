"""Final answers from locked results. No score/quality changes or new models."""
import argparse,csv,json,statistics
from collections import Counter,defaultdict
from bootstrap import R,save
ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);a=ap.parse_args();D=R/('analysis_'+a.round);V=R/('delivery_'+a.round)
quality=list(csv.DictReader((V/'RESULTS.csv').open(encoding='utf-8-sig')))
summary=list(csv.DictReader((D/'PRIMARY_SUMMARY.csv').open(encoding='utf-8-sig')))
own=list(csv.DictReader((D/'OWN_KEY_DIAGNOSTICS.csv').open(encoding='utf-8-sig')))
lines=[]
for arm in ['C0','B2','B3']:
 q=[x for x in quality if x['method']==arm and x['stage']!='CAL']
 fp=[x for x in summary if x['generating_arm']==arm and x['association_method']=='MINHASH128_CHAR3' and x['rule']=='UNCERTIFIED_CAL_MAX_MARGIN_0.03']
 c=Counter(x['overall_quality'] for x in q)
 lines.append(f'|{arm}|{len(q)}|{sum(x["EOS"]=="True" for x in q)}|{c["PASS"]}|{c["FAIL"]}|{c["UNKNOWN"]}|{sum(int(x["complete_correct_identity_count"]) for x in fp)}|{sum(int(x["knowledge_complete_identity_joint_count"]) for x in fp)}|')
table='\n'.join(lines)
b2=[x for x in own if x['variant']=='FULL' and x['method']=='B2'];b3=[x for x in own if x['variant']=='FULL' and x['method']=='B3']
top=sum(x['top1_message_correct']=='True' for x in b3);lst=sum(x['official_list_contains_true_code']=='True' for x in b3)
life=json.loads((D/'REAL_TEXT_LIFECYCLE.json').read_text(encoding='utf-8'))
epochs={}
for epoch in ['E1','E2']:
 ls=[x for x in life if not x['parent_id'].startswith('B0_') and x['expected_epoch']==epoch]
 epochs[epoch]={'records_retained':len(ls),'exact_status':dict(Counter(x['asof150_exact_association']['status'] for x in ls))}
errors=json.loads((D/'SUBSTRING_POSTSCORE_ERROR_REVIEW.json').read_text(encoding='utf-8'))
elig=json.loads((D/'ELIGIBLE_INDEX_POSTSCORE_RESULTS.json').read_text(encoding='utf-8'))['rows']
old=errors['rows'];partial='ISSUE_S01_R02_E1_B2'
newwrong=[x for x in elig if x['status']=='WRONG' and not x['query_of_incomplete_unissued_snapshot']]
save(V/'METHOD_RESULTS.md',f'''# 同文本、同完整索引的对照

以下主分母每臂29个预定发行槽，含DEV/TEST/再发行，不能视为29个独立文档。只有6个发行来源章节（DEV2、TEST4）。CAL另外2章、2次无水印改写不混入臂间比较。

|生成臂|计划/已启动|EOS|知识PASS|FAIL|UNKNOWN|MinHash完整身份且EOS|MinHash知识+完整身份联合|
|---|---:|---:|---:|---:|---:|---:|---:|
{table}

MinHash列为冻结有限CAL-max+margin .03的**未认证诊断**，包含见到字节碰撞后附加的保守解释，非TPR@1%FPR。对同一批B2/B3正文同时扫描指纹与水印，没有只给指纹原文。全部方法的1%主阈值因N_CAL=2而为∞、拒识；不能把全拒识当成功。

B2对自己的29份全文，公开名义z范围{min(float(x['nominal_z']) for x in b2):.6f}—{max(float(x['nominal_z']) for x in b2):.6f}，最小官方单keyp={min(float(x['nominal_p']) for x in b2):.9g}；在冻结 .01/(29×13) 名义家族规则下全部拒识。B3公开Top1正确{top}/{len(b3)}，官方列表含真码{lst}/{len(b3)}，即使优化颜色统计量较高也不是发行码成功。

TEST裁剪的真实分母/错归因/拒识见COHORT_VARIANT_COMPARISON.csv。长度不足和不合法UTF8边界记NOT_APPLICABLE；请求50/100/200不等于最终去重计分T。正文质量字段是完整父文本判定，不代表每个片段独立完成教学任务。

## 不能隐藏的指纹与候选库混杂

原始主表保留全部116个签名**尝试快照**（含一份不完整前缀），不是116个实际合格发行。在各有限诊断规则/窗口中出现{len(old)}个错归因方法×查询行，涉及{errors['distinct_wrong_queries']}个相关查询、{len({x['source_id'] for x in old})}个来源章节，不能当独立错误样本。
其中{sum(x['predicted_issue']==partial for x in old)}行选中了那份未完整的63 Token快照；所有{sum(x['source_only_correct']=='True' for x in old)}行仍找到同一材料，错在交付身份。TEST内有6行错误（5 MinHash、1 MiniLM），并非已证明指纹完全解决所有短片段。

看到这些错误之后，另冻结并执行零模型的普通工程敏感性检查：只排除非EOS候选，保留所有知识FAIL候选，115个候选统一供所有方法，沿用原CAL最大值和margin，不降低阈值。原表不覆盖；模糊指纹错归因行从149变为{len(newwrong)}。该结果不是事前注册验证，也不是独立校准收益。

另做全1236查询的精确字节子串诊断：原149个错归因行中115行已有唯一且正确的已登记子串，34行属于多个版本的相同子串而应拒绝唯一认定。此处同样是**post-hoc**，说明普通索引/拒识就能解释不少问题，不能据此发明水印新机制；没有认证未知背景整体误报。

## 实现证据与限制

58份标记输出的事后颜色/MPAC位置对齐均无差异，公开分数未被私有轨迹替代。B2零模型平坦logit夹具验证同一官方配置的偏置支持集{{0,2}}和binary路径；它不是新生成样本，也不揭示真实模型每一步的logit间隔。未保存全词表实际logits，因而弱信号的具体敏感性机制仍不能定论。
''')
save(V/'RESEARCH_QUESTIONS.md',f'''# A—E结论

A. 在只给可疑文本、审计者保留全部登记版本的条件下，精确查回/指纹能关联部分具体交付。完整原样正文85/87个尝试快照可唯一查回，去掉不完整EOS资格后为84/87；同字节不同身份的2份必须歧义。29个同内容B0登记全部歧义。它不是无映射恢复真人身份。

B. E1/E2实际改写记录的模拟生命周期结果：{json.dumps(epochs,ensure_ascii=False)}。历史记录/材料保留没有改写旧身份；有1份E1和1份E2正文相同，无法唯一确定周期，不能声称全数旧版本都可识别。asof150许可独立显示；没有外部可信时间戳、抗发行者伪造或真实授权法效证明。

C. 同一版本索引下，全文MinHash诊断优于本轮逐密钥Greenlist/MPAC32的发行码恢复。但没有匹配且认证的1%整体误报工作点，没有更强英文BGE和其他多比特/失真优化方法的完整复现，因此不能推广成普遍方法优势。

D. 主89次尝试质量58P/26F/5U，88自然EOS；26个整体FAIL均由冻结覆盖义务未满足，事实判定82P/7U/0明确FAIL。普通改写也遗漏条件；不能把所有差异归因为水印。原生模型前向18136次，生成18135 Token，CPU阶段7126.036秒，峰值原生RSS约4.40GiB；另计指纹前向和公开检测。修改距离逐例保留且受数学排版影响，不是语义强度指标。

E. 工程PARTIAL，研究INSUFFICIENT_EVIDENCE。保留可集成的登记、历史检测材料和明确拒识能力；不能把ID/换钥/签名组合当创新。需要先修正发行准入与完整版本检索工程，并在独立背景充分校准的相同条件下检验增量价值；不授权现在开发算法。
''')
save(V/'ATTACK_STATUS.md','''# 强改写攻击分支

NOT_RUN_RESOURCE。原89主槽优先、均已执行；模型阶段7126.036秒，7200秒原上限剩73.964秒，小于预冻结80秒新攻击准入。3B只核验已有模型身份、许可、Tokenizer并准备隔离代码，模型加载0、新攻击生成0；不是用3B替代7B，不报告新有效强攻击0/若干次或强改写鲁棒性。旧版权移交有效强攻击0的负面证据单列历史，未重包装。
''')
save(V/'REPRODUCE_FINAL.md',f'''# 复现最新结果

公开数据完整性/签名/MinHash：`python -X utf8 -B code/public_archive_check.py <发布目录> --round {a.round}`。本轮实际校验116签名、1352文本、143376 MinHash配对；这不是安全强度或水印效果样本数。

按公开版本固定TextSeal与MPAC源码、相同Tokenizer、已有英语MiniLM可重算对应软件输出。真实水印分数完全复算需受控取得历史检测材料；公开只有key_id/承诺，实际水印密钥、Ed25519私钥和采样seed不发布。不能仅凭哈希声称公众逐字生成可复现。

GENERATION_CODE_FREEZE锁定首个forward前12个生成文件；freeze.json还保留早期准备版源码SHA。后续报告、公开匹配与资源守卫辅助代码变更单列，不修改12个生成文件。模型权重两分片及Tokenizer生成后再算SHA均一致。

MODEL_CALL_ACCOUNTING记录89次回答尝试、18136真实原生前向，HTTP生成0。源码和旧依赖只读，模型/venv/私钥不随发布物分发。本轮有界执行关闭，不要直接再运行生成入口复采STARTED槽；新试验需另行授权和冻结。

原round01/02、原评分批处理错误及修复、GBK读取失败、重复未提交审核卡的SUPERSEDED记录、内存中断均保留。最新post-hoc子串/非EOS索引诊断不覆盖主表，不能当独立确认。
''')
save(V/'FINAL_DECISION_FINAL.md','''# 最终决策

工程：PARTIAL。研究：INSUFFICIENT_EVIDENCE。

已完成原冻结89次主槽尝试，88自然EOS；完成公开检测、生命周期和完整版本指纹对照，不是停在审计。保留1个内存前缀失败且不重跑；强改写因预算未启动，1%全局误报目标未认证。

可以保留现有发行登记、历史周期保留、独立许可查询和拒识能力。当前证据不支持新算法必要性或水印相对合理强指纹的稳定增量价值。特别是裁剪误归因受不完整尝试快照进入候选库、缺少普通精确子串检索影响；不能据此宣称算法缺口。

下一步唯一研究问题：在完成发行准入、保真与独立背景校准后，水印是否对同一完整版本索引提供增量关联价值。

详细分母、失败、代价和A—E见METHOD_RESULTS.md、RESEARCH_QUESTIONS.md、RESULT.md及原始CSV。当前助手作者PROVISIONAL，不是独立真人金标。停止自有Worker，不自动扩量或开发新算法。
''')
print('FINAL_METHOD_RESULTS_RQ_AND_REPRO_WRITTEN')
