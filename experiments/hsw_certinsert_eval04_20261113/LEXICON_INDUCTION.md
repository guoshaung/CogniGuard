# LEXICON_INDUCTION — EVAL-04 v3 阶段0停止报告

结论：**STOPPED_BEFORE_FLUENCY；最终L*未选出。** 双向NLI与锚点排除后只有6个合格候选，少于预注册要求的10个。没有放宽阈值、补手工词或进入阶段A。

## 语料与执行

- R共4461篇：4161篇教材正文/例题解答、300篇本地生成讲解。每个正文段落或完整解答为一个文档，不把它们称为独立章节。
- R_build 3568篇、R_calib 893篇；按冻结SHA256顺序划分。教材来源、章节、原始哈希与逐文档划分见RAG_CORPUS_MANIFEST.json。
- 生成沿用T5的Qwen2.5-7B Q4_K_M，每题一次：300个请求完成，284自然EOS、16达到长度上限，截断原样保留。
- T6正文读取0，付费API调用0；原EVAL-01/EVAL-03文件只读。跨章节划分按元数据，历史去重范围与无法证明的语义去重边界见manifest及DEVIATIONS.md。

## 候选数量漏斗

1. 挖掘句首1–4词、紧跟逗号的完整片段：**1592**。
2. 真实性df ≥ 3568×0.2%=7.136，即至少8篇文档：**47**。
3. 每词100句、双向蕴含概率均≥0.9的比例≥95%：**6**。
4. 候选本身的冻结知识锚点抽取为空：**6**（此步未再剔除）。
5. 3B流畅度最差30%筛除：**未运行**。
6. R_calib每句p≤0.05筛除及p的95%上界：**未运行**。
7. 文档共现lift>3去冲突：**未运行**。
8. 实词/句法分组、每组最多2项、F×E排序：**未运行**。
9. L10/20/40/80和C/P/Q模拟选L*：**未运行**。

停止理由：任务书0.2b明确要求“合格候选少于10个，停下并报告，由人决定”；因此后续数字写未运行而不是0。

## 当前通过的6项（不是最终词表）

- `for example`：df=242，双向通过98/100，无候选知识锚点。
- `for instance`：df=30，双向通过98/100，无候选知识锚点。
- `in fact`：df=44，双向通过98/100，无候选知识锚点。
- `in other words`：df=52，双向通过99/100，无候选知识锚点。
- `in this case`：df=28，双向通过97/100，无候选知识锚点。
- `that is`：df=33，双向通过99/100，无候选知识锚点。

这些只是固定NLI模型的通过项，不等于人工语义保证。`in fact`有强调/事实确认语用，`for example`与`for instance`有例示语用，`in other words`与`that is`有重述语用；按规则3没有手工删掉它们。尚未检验流畅度、频率、独立性，不能把6项当L*。

## 高频但被剔除的候选

- `thus`：df=214，NLI双向通过85/100，低于95/100。
- `however`：df=151，NLI双向通过23/100，低于95/100。
- `therefore`：df=93，NLI双向通过54/100，低于95/100。
- `so`：df=54，NLI双向通过92/100，低于95/100。
- `similarly`：df=43，NLI双向通过9/100，低于95/100。
- `first`：df=38，NLI双向通过7/100，低于95/100。
- `in addition`：df=37，NLI双向通过2/100，低于95/100。
- `as a result`：df=27，NLI双向通过75/100，低于95/100。
- `finally`：df=24，NLI双向通过0/100，低于95/100。
- `in this chapter`：df=23，NLI双向通过0/100，低于95/100。

## 与EVAL-03手工7词的对照

- `at this point`：真实性不通过：df=4，要求≥8。
- `here`：NLI通过84/100，不达95/100。
- `in this case`：NLI通过97/100，保留至当前停止点。
- `next`：NLI通过1/100，不达95/100。
- `now`：NLI通过42/100，不达95/100。
- `then`：NLI通过16/100，不达95/100。
- `to begin`：真实性不通过：df=1，要求≥8。

- 与手工词表重合的当前通过项：in this case。
- 算法新增且当前通过：for example, for instance, in fact, in other words, that is。

## 模型、阈值与理由

- CPU NLI：MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli，revision 6f5cf0a2b59cabb106aca4c287eed12e357e90eb。任务书允许如DeBERTa系列本地NLI，本轮选择base规模CPU可运行版本；不是large模型的等价实验。标签0为entailment；权重及分词器逐文件哈希见NLI_MODEL_FREEZE.json。
- 0.2% df、100句、双向0.9、95%通过、30%流畅度淘汰、每句频率0.05、lift3、k4、嵌入0.001/检测0.01全部来自任务书；未因结果改变。
- 未执行的排序和L*选择仍沿用PREREG_RULES.md：S=F×E，Q≤.01，最大化C−P，J差<.02选小词表。
- 用户补充的每句p加一平滑及q(y)=1−(1−p)^n(y)已冻结；本轮因前置门槛失败尚未估计p，不虚构q或置信上界。
- 实现细节见INDUCTION_DETAILS.md。环境修复及旧spaCy安装包来源未冻结的限制见DEVIATIONS.md。

## 结果与证据

- 最终L*：**null / 未选出**。
- lexicon_L10/20/40/80：**未产生**；不创建名称为L10但实际只有6项的伪交付。
- NLI完整证据：47词×100句×2方向，共9400个蕴含概率，见nli/逐词文件；相同候选100句全部保留。
- 输入/模型/规则：PREREG_RULES.md、NULL_MODEL_ADDENDUM.md、NLI_MODEL_FREEZE.json、CORPUS_MINING_FREEZE.json。
- 阶段0未完成；没有进入A/B/C/D。后续修改必须新版本预注册，不能在这批结果上改门槛再称独立验证。
