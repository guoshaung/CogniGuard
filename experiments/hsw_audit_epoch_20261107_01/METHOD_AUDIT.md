# 方法实施审查（运行前层）

核心算法文件没有修改。MPAC五个原文件及Apache2.0许可在vendor/mpac，逐文件SHA/SOURCE_PIN固定；TextSeal从旧核验clone只读导入，不复制环境。数据集与模型不得由这些官方demo自动下载。

B0为无标记相同作者正文＋签名登记。SQLite最小登记只保留身份、SHA/码及签名；内容索引为审计方允许保留的独立材料。多身份同字节必须AMBIGUOUS，不强选Top1。许可查询asof与水印关联分开，签名是自声明模拟时钟，不是可信时间戳。

B1从全部已登记原文/发行正文建索引；字符3gram MinHash128、英语all-MiniLM-L6-v2窗口meanpool/L2，以及等权词面—语义混合。现有中文BGE不冒称强英语基线；本轮语言en单列，不以英语成功覆盖中文问题。

B2调用未改官方Greenlist采样器：gamma.25/delta2/ngram2、after_topp=False、temperature.8/top_p.95、CPU、v2fresh去重。它在logits层实时施加偏置。所有候选发行key都扫描，不偷看epoch/source。理论单keyp仅作未认证nominal辅助，不宣称匹配1%总体错误率。

B3调用未改MPAC WatermarkLogitsProcessor，32bit、radix4、h2 additivePRF、独立positionPRF、CPU RNG、no feedback。原始152064输出头用于生成与检测，HF base151643/可解码151665另记。若选中无法解码paddingID则保留失败，不静默mask或替换。32bit为官方完整候选解码默认所需的16个radix4位置，非为了提高成绩而选择消息长度。

MPAC官方高层detect要求gold message/position来生成研究评分；不允许作为本轮公开输入。适配器只调用其低层独立提取，固定dummy32个0仅供无用BER计算，删除所有gold指标，仅保留真实提取top1码、T/G/z。UNIT_FIXTURE中0和1两dummy得到完全相同提取及分数。没有按“最接近真码”的list项选择成功。多个epoch皆在候选集，未登记码拒绝；最高颜色计数所导出的z含选择效应，不能照搬普通KGW空分布保证。

Native Qwen7B Q4_K_M真实前向在独立进程，Torch官方处理器在控制进程，经每次SHA核对的共享内存接收完整F32原始logits；不伪造HF forward。模型上下文与真实选择ID一次推进，进程与所有日志在新工作树。metadata-only对象仅向采样器提供参数，其forward故意报错，不能当真实模型替身。

已完成准入：18项生命周期软件测试；MPAC实际Torch bias＋不依赖dummy真值的提取＋DPAPI往返组件测试。它们是UNIT_FIXTURE，不是实际生成、知识保真或水印检出率。后续真实结果单独追加，不回改准备时点的状态。
