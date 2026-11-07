"""Freeze detailed public retrieval rules before any TEST generation or score."""
from bootstrap import E,R,save,digest
import json,math
assert not (R/'PUBLIC_EVALUATION_FREEZE.json').exists()
save(R/'PUBLIC_EVALUATION_FREEZE.json',{
 'status':'BEFORE_S3_TEST_GENERATION_AND_ALL_TEST_SCORES',
 'main_methods':['B0_EXACT_REGISTRY','MINHASH128_CHAR3','LEXICAL_CHAR3_COSINE','MINILM_EN_WINDOWS','HYBRID_EQUAL','B2_TOOLKIT_GREENLIST','B3_MPAC32'],
 'common_gallery':'all actual registered author-copy and C0/B2/B3 delivery instances; same issue universe; unstarted/calibration negatives excluded from issue register',
 'B0_exact':'all public byte SHA matches; unique=associated, multiple=AMBIGUOUS; known-record exact lookup does not prove who forwarded it',
 'MinHash':'reuse immutable R37N128char3 whitespace-removal implementation; no language weakening/no truncation',
 'lexical':'character3 frequency cosine on whitespace-removed text; unchanged from historical strong baseline',
 'semantic_model':'existing sentence-transformers/all-MiniLM-L6-v2 snapshot1110a243fdf4706b3f48f1d95db1a4f5529b4d41; languageen; CPU only',
 'semantic_window':{'max_content_subtokens':256,'stride':192,'pooling':'attention-mask mean then L2','max_length_with_specials':512,
   'score':'each querywindow max cosine over candidate windows, mean across querywindows; clip[0,1]','no_query_instruction':True},
 'hybrid':'.5 lexical char3 frequencycosine +.5 MiniLM English semantic; no test-selected coefficients',
 'candidate_pooling':'same issue may have several original/variant references; per-reference method score then max within issue; no separate raw-source shortcut unavailable to others',
 'unique_rank':'preserve exact score ties; top1 tie->AMBIGUOUS, never stable-index forced identity',
 'FP_nominal_diagnostic_margin':.03,
 'empirical_main_alpha':.01,'CAL_sources':['S03','S04'],
 'CAL_bundle':'original and one C0 rewrite if delivered; all metadata/format/full/fixed-window views per source; resource maximum across views and all candidate issues/epochs',
 'CAL_rank_rule':'ceil((N+1)*(1-.01)); rank>N implies infinity; no percentile interpolation/small-N relaxation',
 'expected_primary_certification':'INSUFFICIENT_CALIBRATION_N. Even 0/2 gives no1% bound; primary calibrated statistical reject rule remains explicit',
 'nominal_B2_only_reference':'.01/(29planned issuedkeys *13declared full/format/crop views); p-values nominal, no empirical validity guarantee',
 'B3_decoded_acceptance':'independently extract one top1 code for both E1/E2; map only to issued code for that scanned epoch. One candidate only under threshold; otherwiseREJECT/AMBIGUOUS; no nearest true code/list oracle',
 'B3_scores_limitation':'official z derived from decoded-max colors is not proven single-key normal under this sampling/application; do not claim exact likelihood/FPR',
 'B3_capacity_limitation':'32-bit chosen to run official full list decoder default without editing core, not minimum number of bits for this registry. Poor32bit recovery cannot rule out shorter public MPAC settings or strongerPRMB/DMW.',
 'format_transforms':['PUBLIC_BODY_ONLY','CRLF','COLLAPSE_WHITESPACE'],
 'metadata_stripping':'detect uses .txt body only; no filename/metadata issue labels passed; authoritative public decode must match realIDs byte-for-byte',
 'crop_request_lengths':[50,100,200],'crop_start_rule':'start0 / middlefloor((N-(L+2))/2) / endN-(L+2)',
 'crop_counting':'L+2 canonical public rawTokens requested for context2; actual T after public re-encode/dedup separately recorded. InsufficientN or invalidUTF8boundary->N/A; no moving start to repair.',
 'pressure':'null additional keys/codes only, no extra model text; fixed S01 unmarked FULL andSTART50; candidate counts1/8/32/128/512; retention over both epochs; not genuine512issuance',
 'detector_input_boundary':'opaque query ID + exact public bytes, separate registered complete gallery/historical method key materials; no truth manifest or generation trajectory/seed file',
 'fingerprint_forward_seconds_cap':300,'public_watermark_cpu_seconds_cap':1800,
 'knowledge':'lock each raw parent before public scoring, authorPROVISIONAL; inherited probe3 already locked before their public score; all future parents require separate locks',
 'statistics':'per chapter/source count; no individual seed/crop inferential independence; exact numerators, Wilson marginal descriptive, no smallcluster significance/bootstrap',
 'mutating_main_method_parameters':False,
 'initial_probe_quality_seen':True,'probe_only_score_seen':True,'TEST_scores_seen':False})
save(E/'BASELINE_CALIBRATION_PLAN.md','''# 整体误报与信息条件

所有候选身份和两个历史周期共同扫描，查询名改为opaque ID，私有真值只交评估器，不供检测函数。登记及历史key是允许保留的材料，原执行日志不是输入。C0/B2/B3全部实际版本供指纹同库索引；B0同内容多登记时歧义拒识。

主参考alpha=.01，但只有2个独立CAL章节。使用原文级跨视图/候选最大值，rank=ceil((N+1)*.99)>N时阈值为∞，不通过插值、换成5%或在TEST挑阈值制造可认证操作点。必须写1%目标未认证；“阈值∞全拒”不是成功检出或实际方法FPR为0。另报告精确字节登记查找（工程能力）、原始排名、固定.03拒识及未认证nominal水印参照，全部与主统计分开。

两个CAL的无标记改写和原稿同源，最多仍2个背景独立来源。4个TEST章节仅探索。多key、epoch、裁剪和格式归同查询/原稿家族，附加nullkeys不增加独立样本。不能将比特正确率、来源识别或单keyp等同完整issue关联。

MPAC32bit是固定的官方兼容配置，消息负荷比本批最小ID需求大。若短文完整消息恢复不足，不说明其他bit宽或USENIX/DMW都失败，更不能把该容量代价直接当创新点。
''')
print('PUBLIC_EVALUATION_RULES_FROZEN')
