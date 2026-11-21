# 失败案例

每条案例都能回到轮次、片段、联盟和账本哈希。完整字段在 `artifacts/failure_cases.jsonl`。
G1 是跨轨迹恢复成功。G2 是账本合规但高阶单元被恢复。G3 是教学方法片段以 NONE 加 IDENTITY 零代价放出。超支单独列出。

| 假设 | 臂 | 条数 |
| --- | --- | --- |
| G1 | cost_model_identity | 120 |
| G1 | nemo | 50 |
| G1 | none | 74 |
| G2 | cost_model_identity | 20 |
| G3 | ocelot_minus | 40 |

- G1 cost_model_identity congruence.seq3_a k=3 联盟 congruence.k3.s00-s01-s02 成员 congruence.s00,congruence.s01,congruence.s02
  - 轮次 congruence.s00.split.congruence-seq3_a-F1 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b4683a1b230266aabf87c399ca43be525b35f0ead22cd59e3904b43514ff037f
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s01.split.congruence-seq3_a-F2 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 83f4c75e4ca942d2553014795b0aa92399fac246ab266dfd6a9cbcbb46a40f85
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s02.split.congruence-seq3_a-F3 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f481528e9e9122e85021f8128ebee0f46fcb986e66cfa3f06cbec6abdb2a5abe
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 cost_model_identity congruence.seq3_a k=3 联盟 congruence.k3.s05-s06-s07 成员 congruence.s05,congruence.s06,congruence.s07
  - 轮次 congruence.s05.split.congruence-seq3_a-F1 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d30142b80bdd940588b0bf3e8cf2e51132415ed53b3a648d85ab81271a02899a
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s06.split.congruence-seq3_a-F2 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 396d0a1967f739c7f28d2f5eafa23e08fc2edcd4e2faac208aaed5435e01b1fc
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s07.split.congruence-seq3_a-F3 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 db8a713540e7071f76f216b1a4c5b1965a7fe9d9c9dba59b6ccf8f4c123be4da
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 cost_model_identity congruence.seq3_a k=3 联盟 congruence.k3.s10-s11-s12 成员 congruence.s10,congruence.s11,congruence.s12
  - 轮次 congruence.s10.split.congruence-seq3_a-F1 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 56ba89bc48acf6198a0a9fe3cd441243010fa2bdc8a6520a1b3d7403ef9f1c6d
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s11.split.congruence-seq3_a-F2 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 1cd34d0588871befe2eff14157b0283ae11fe0ffa3cba69d7f2e5104eecc0380
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s12.split.congruence-seq3_a-F3 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c8f5de7f7417f8ce1fadc5d11688e166d090b2f5a16818908408aac8fe0f571a
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 cost_model_identity congruence.seq3_a k=3 联盟 congruence.k3.s15-s16-s17 成员 congruence.s15,congruence.s16,congruence.s17
  - 轮次 congruence.s15.split.congruence-seq3_a-F1 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ea4bdc7853d8fe24cdb13ecb436455805b590610931eed1672650e99c12edd43
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s16.split.congruence-seq3_a-F2 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f5e6de5ce01c3b81515c42f9b67429446aa1eec3322f2f584c87c09bd2fc2955
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s17.split.congruence-seq3_a-F3 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 37e2f773a9e3ba11c370c9b3b5e1b0ad429e2662821410d49184f3949ee6b1d1
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 cost_model_identity congruence.seq3_b k=3 联盟 congruence.k3.s00-s01-s02 成员 congruence.s00,congruence.s01,congruence.s02
  - 轮次 congruence.s00.split.congruence-seq3_b-F1 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 666dab9cc41a8080b0bbcd80429d667a52fa5eaa4682f33166701e2a168eb436
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s01.split.congruence-seq3_b-F2 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bdc2f25312d9a082b811add343f55d09a0a8e4be2d020712db452b6148507e34
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s02.split.congruence-seq3_b-F3 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5bfa568eb6194a6e9fd14c66766027f5fc59631ce374e2f0d9736d8f9055a0c1
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 cost_model_identity congruence.seq3_b k=3 联盟 congruence.k3.s05-s06-s07 成员 congruence.s05,congruence.s06,congruence.s07
  - 轮次 congruence.s05.split.congruence-seq3_b-F1 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5e801661b0cd1e5036871db6c31d00a83eaa08a0b88b0c70f8a52eda4f459f70
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s06.split.congruence-seq3_b-F2 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 790c4d17176e52a16f9188517a014e2e45f1bcb7df68c79ca3f0d0a2b87f4a50
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s07.split.congruence-seq3_b-F3 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b89e0f442cc18776c3f30f711b560057a46aa517c6a44beb8b5e4994b428b823
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 cost_model_identity congruence.seq3_b k=3 联盟 congruence.k3.s10-s11-s12 成员 congruence.s10,congruence.s11,congruence.s12
  - 轮次 congruence.s10.split.congruence-seq3_b-F1 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 256cf1ae10474521aeeac374697f1e694d7650581ec250deb0740b3b13fb3894
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s11.split.congruence-seq3_b-F2 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 e9a680338c83545b4f2f81179eb41225705fe1df2259359a22253cdc3a749c16
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s12.split.congruence-seq3_b-F3 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 26fc4a04b3226349cb35bf03ae6204c49b814fa91f93a5f135b01885c6234021
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 cost_model_identity congruence.seq3_b k=3 联盟 congruence.k3.s15-s16-s17 成员 congruence.s15,congruence.s16,congruence.s17
  - 轮次 congruence.s15.split.congruence-seq3_b-F1 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 aa5997e9f6d8260dfbdfc41c9a38a62e42c4afea4ce49b4efffceee92b4fba42
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s16.split.congruence-seq3_b-F2 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 84e875e37394ef28e43e7c9449730f6ca93469bb698956c8431602bd39b9a075
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s17.split.congruence-seq3_b-F3 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f97f57951a7b0bc4646c3a548717d86d8944204e7c7b4885666afefbde7632f0
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 nemo congruence.diag_a k=3 联盟 congruence.k3.s00-s01-s02 成员 congruence.s00,congruence.s01,congruence.s02
  - 轮次 congruence.s00.split.congruence-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F1：错因是把夹角写成另外一个角。
  - 轮次 congruence.s01.split.congruence-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F2：干预是让学生用手指指出夹角，再落笔。
- G1 nemo congruence.diag_a k=3 联盟 congruence.k3.s05-s06-s07 成员 congruence.s05,congruence.s06,congruence.s07
  - 轮次 congruence.s05.split.congruence-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F1：错因是把夹角写成另外一个角。
  - 轮次 congruence.s06.split.congruence-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F2：干预是让学生用手指指出夹角，再落笔。
- G1 nemo congruence.diag_a k=3 联盟 congruence.k3.s10-s11-s12 成员 congruence.s10,congruence.s11,congruence.s12
  - 轮次 congruence.s10.split.congruence-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F1：错因是把夹角写成另外一个角。
  - 轮次 congruence.s11.split.congruence-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F2：干预是让学生用手指指出夹角，再落笔。
- G1 nemo congruence.diag_a k=3 联盟 congruence.k3.s15-s16-s17 成员 congruence.s15,congruence.s16,congruence.s17
  - 轮次 congruence.s15.split.congruence-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F1：错因是把夹角写成另外一个角。
  - 轮次 congruence.s16.split.congruence-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F2：干预是让学生用手指指出夹角，再落笔。
- G1 nemo congruence.diag_b k=3 联盟 congruence.k3.s00-s01-s02 成员 congruence.s00,congruence.s01,congruence.s02
  - 轮次 congruence.s00.split.congruence-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F1：错因是对应顶点写反，边的名称跟着错。
  - 轮次 congruence.s01.split.congruence-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F2：干预是先写对应顶点顺序，再写边。
- G1 nemo congruence.diag_b k=3 联盟 congruence.k3.s05-s06-s07 成员 congruence.s05,congruence.s06,congruence.s07
  - 轮次 congruence.s05.split.congruence-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F1：错因是对应顶点写反，边的名称跟着错。
  - 轮次 congruence.s06.split.congruence-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F2：干预是先写对应顶点顺序，再写边。
- G1 nemo congruence.diag_b k=3 联盟 congruence.k3.s10-s11-s12 成员 congruence.s10,congruence.s11,congruence.s12
  - 轮次 congruence.s10.split.congruence-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F1：错因是对应顶点写反，边的名称跟着错。
  - 轮次 congruence.s11.split.congruence-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F2：干预是先写对应顶点顺序，再写边。
- G1 nemo congruence.diag_b k=3 联盟 congruence.k3.s15-s16-s17 成员 congruence.s15,congruence.s16,congruence.s17
  - 轮次 congruence.s15.split.congruence-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F1：错因是对应顶点写反，边的名称跟着错。
  - 轮次 congruence.s16.split.congruence-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F2：干预是先写对应顶点顺序，再写边。
- G1 nemo congruence.seq3_a k=3 联盟 congruence.k3.s00-s01-s02 成员 congruence.s00,congruence.s01,congruence.s02
  - 轮次 congruence.s00.split.congruence-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s01.split.congruence-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s02.split.congruence-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 nemo congruence.seq3_a k=3 联盟 congruence.k3.s05-s06-s07 成员 congruence.s05,congruence.s06,congruence.s07
  - 轮次 congruence.s05.split.congruence-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s06.split.congruence-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s07.split.congruence-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 nemo congruence.seq3_a k=3 联盟 congruence.k3.s10-s11-s12 成员 congruence.s10,congruence.s11,congruence.s12
  - 轮次 congruence.s10.split.congruence-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s11.split.congruence-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s12.split.congruence-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 nemo congruence.seq3_a k=3 联盟 congruence.k3.s15-s16-s17 成员 congruence.s15,congruence.s16,congruence.s17
  - 轮次 congruence.s15.split.congruence-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s16.split.congruence-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s17.split.congruence-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 nemo congruence.seq3_b k=3 联盟 congruence.k3.s00-s01-s02 成员 congruence.s00,congruence.s01,congruence.s02
  - 轮次 congruence.s00.split.congruence-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s01.split.congruence-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s02.split.congruence-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 nemo congruence.seq3_b k=3 联盟 congruence.k3.s05-s06-s07 成员 congruence.s05,congruence.s06,congruence.s07
  - 轮次 congruence.s05.split.congruence-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s06.split.congruence-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s07.split.congruence-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 nemo congruence.seq3_b k=3 联盟 congruence.k3.s10-s11-s12 成员 congruence.s10,congruence.s11,congruence.s12
  - 轮次 congruence.s10.split.congruence-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s11.split.congruence-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s12.split.congruence-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 nemo congruence.seq3_b k=3 联盟 congruence.k3.s15-s16-s17 成员 congruence.s15,congruence.s16,congruence.s17
  - 轮次 congruence.s15.split.congruence-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s16.split.congruence-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s17.split.congruence-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 none congruence.diag_a k=3 联盟 congruence.k3.s00-s01-s02 成员 congruence.s00,congruence.s01,congruence.s02
  - 轮次 congruence.s00.split.congruence-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F1：错因是把夹角写成另外一个角。
  - 轮次 congruence.s01.split.congruence-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F2：干预是让学生用手指指出夹角，再落笔。
- G1 none congruence.diag_a k=3 联盟 congruence.k3.s05-s06-s07 成员 congruence.s05,congruence.s06,congruence.s07
  - 轮次 congruence.s05.split.congruence-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F1：错因是把夹角写成另外一个角。
  - 轮次 congruence.s06.split.congruence-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F2：干预是让学生用手指指出夹角，再落笔。
- G1 none congruence.diag_a k=3 联盟 congruence.k3.s10-s11-s12 成员 congruence.s10,congruence.s11,congruence.s12
  - 轮次 congruence.s10.split.congruence-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F1：错因是把夹角写成另外一个角。
  - 轮次 congruence.s11.split.congruence-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F2：干预是让学生用手指指出夹角，再落笔。
- G1 none congruence.diag_a k=3 联盟 congruence.k3.s15-s16-s17 成员 congruence.s15,congruence.s16,congruence.s17
  - 轮次 congruence.s15.split.congruence-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F1：错因是把夹角写成另外一个角。
  - 轮次 congruence.s16.split.congruence-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F2：干预是让学生用手指指出夹角，再落笔。
- G1 none congruence.diag_b k=3 联盟 congruence.k3.s00-s01-s02 成员 congruence.s00,congruence.s01,congruence.s02
  - 轮次 congruence.s00.split.congruence-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F1：错因是对应顶点写反，边的名称跟着错。
  - 轮次 congruence.s01.split.congruence-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F2：干预是先写对应顶点顺序，再写边。
- G1 none congruence.diag_b k=3 联盟 congruence.k3.s05-s06-s07 成员 congruence.s05,congruence.s06,congruence.s07
  - 轮次 congruence.s05.split.congruence-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F1：错因是对应顶点写反，边的名称跟着错。
  - 轮次 congruence.s06.split.congruence-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F2：干预是先写对应顶点顺序，再写边。
- G1 none congruence.diag_b k=3 联盟 congruence.k3.s10-s11-s12 成员 congruence.s10,congruence.s11,congruence.s12
  - 轮次 congruence.s10.split.congruence-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F1：错因是对应顶点写反，边的名称跟着错。
  - 轮次 congruence.s11.split.congruence-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F2：干预是先写对应顶点顺序，再写边。
- G1 none congruence.diag_b k=3 联盟 congruence.k3.s15-s16-s17 成员 congruence.s15,congruence.s16,congruence.s17
  - 轮次 congruence.s15.split.congruence-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F1：错因是对应顶点写反，边的名称跟着错。
  - 轮次 congruence.s16.split.congruence-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F2：干预是先写对应顶点顺序，再写边。
- G1 none congruence.seq3_a k=3 联盟 congruence.k3.s00-s01-s02 成员 congruence.s00,congruence.s01,congruence.s02
  - 轮次 congruence.s00.split.congruence-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s01.split.congruence-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s02.split.congruence-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 none congruence.seq3_a k=3 联盟 congruence.k3.s05-s06-s07 成员 congruence.s05,congruence.s06,congruence.s07
  - 轮次 congruence.s05.split.congruence-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s06.split.congruence-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s07.split.congruence-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 none congruence.seq3_a k=3 联盟 congruence.k3.s10-s11-s12 成员 congruence.s10,congruence.s11,congruence.s12
  - 轮次 congruence.s10.split.congruence-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s11.split.congruence-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s12.split.congruence-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 none congruence.seq3_a k=3 联盟 congruence.k3.s15-s16-s17 成员 congruence.s15,congruence.s16,congruence.s17
  - 轮次 congruence.s15.split.congruence-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s16.split.congruence-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s17.split.congruence-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 none congruence.seq3_b k=3 联盟 congruence.k3.s00-s01-s02 成员 congruence.s00,congruence.s01,congruence.s02
  - 轮次 congruence.s00.split.congruence-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s01.split.congruence-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s02.split.congruence-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 none congruence.seq3_b k=3 联盟 congruence.k3.s05-s06-s07 成员 congruence.s05,congruence.s06,congruence.s07
  - 轮次 congruence.s05.split.congruence-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s06.split.congruence-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s07.split.congruence-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 none congruence.seq3_b k=3 联盟 congruence.k3.s10-s11-s12 成员 congruence.s10,congruence.s11,congruence.s12
  - 轮次 congruence.s10.split.congruence-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s11.split.congruence-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s12.split.congruence-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 none congruence.seq3_b k=3 联盟 congruence.k3.s15-s16-s17 成员 congruence.s15,congruence.s16,congruence.s17
  - 轮次 congruence.s15.split.congruence-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s16.split.congruence-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s17.split.congruence-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 cost_model_identity congruence.seq3_a k=5 联盟 congruence.k5.s00-s01-s02-s03-s04 成员 congruence.s00,congruence.s01,congruence.s02,congruence.s03,congruence.s04
  - 轮次 congruence.s00.split.congruence-seq3_a-F1 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b4683a1b230266aabf87c399ca43be525b35f0ead22cd59e3904b43514ff037f
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s01.split.congruence-seq3_a-F2 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 83f4c75e4ca942d2553014795b0aa92399fac246ab266dfd6a9cbcbb46a40f85
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s02.split.congruence-seq3_a-F3 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f481528e9e9122e85021f8128ebee0f46fcb986e66cfa3f06cbec6abdb2a5abe
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 cost_model_identity congruence.seq3_a k=5 联盟 congruence.k5.s05-s06-s07-s08-s09 成员 congruence.s05,congruence.s06,congruence.s07,congruence.s08,congruence.s09
  - 轮次 congruence.s05.split.congruence-seq3_a-F1 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d30142b80bdd940588b0bf3e8cf2e51132415ed53b3a648d85ab81271a02899a
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s06.split.congruence-seq3_a-F2 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 396d0a1967f739c7f28d2f5eafa23e08fc2edcd4e2faac208aaed5435e01b1fc
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s07.split.congruence-seq3_a-F3 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 db8a713540e7071f76f216b1a4c5b1965a7fe9d9c9dba59b6ccf8f4c123be4da
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 cost_model_identity congruence.seq3_a k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-seq3_a-F1 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 56ba89bc48acf6198a0a9fe3cd441243010fa2bdc8a6520a1b3d7403ef9f1c6d
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s11.split.congruence-seq3_a-F2 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 1cd34d0588871befe2eff14157b0283ae11fe0ffa3cba69d7f2e5104eecc0380
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s12.split.congruence-seq3_a-F3 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c8f5de7f7417f8ce1fadc5d11688e166d090b2f5a16818908408aac8fe0f571a
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 cost_model_identity congruence.seq3_a k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-seq3_a-F1 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ea4bdc7853d8fe24cdb13ecb436455805b590610931eed1672650e99c12edd43
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s16.split.congruence-seq3_a-F2 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f5e6de5ce01c3b81515c42f9b67429446aa1eec3322f2f584c87c09bd2fc2955
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s17.split.congruence-seq3_a-F3 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 37e2f773a9e3ba11c370c9b3b5e1b0ad429e2662821410d49184f3949ee6b1d1
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 cost_model_identity congruence.seq3_b k=5 联盟 congruence.k5.s00-s01-s02-s03-s04 成员 congruence.s00,congruence.s01,congruence.s02,congruence.s03,congruence.s04
  - 轮次 congruence.s00.split.congruence-seq3_b-F1 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 666dab9cc41a8080b0bbcd80429d667a52fa5eaa4682f33166701e2a168eb436
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s01.split.congruence-seq3_b-F2 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bdc2f25312d9a082b811add343f55d09a0a8e4be2d020712db452b6148507e34
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s02.split.congruence-seq3_b-F3 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5bfa568eb6194a6e9fd14c66766027f5fc59631ce374e2f0d9736d8f9055a0c1
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 cost_model_identity congruence.seq3_b k=5 联盟 congruence.k5.s05-s06-s07-s08-s09 成员 congruence.s05,congruence.s06,congruence.s07,congruence.s08,congruence.s09
  - 轮次 congruence.s05.split.congruence-seq3_b-F1 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5e801661b0cd1e5036871db6c31d00a83eaa08a0b88b0c70f8a52eda4f459f70
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s06.split.congruence-seq3_b-F2 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 790c4d17176e52a16f9188517a014e2e45f1bcb7df68c79ca3f0d0a2b87f4a50
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s07.split.congruence-seq3_b-F3 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b89e0f442cc18776c3f30f711b560057a46aa517c6a44beb8b5e4994b428b823
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 cost_model_identity congruence.seq3_b k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-seq3_b-F1 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 256cf1ae10474521aeeac374697f1e694d7650581ec250deb0740b3b13fb3894
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s11.split.congruence-seq3_b-F2 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 e9a680338c83545b4f2f81179eb41225705fe1df2259359a22253cdc3a749c16
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s12.split.congruence-seq3_b-F3 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 26fc4a04b3226349cb35bf03ae6204c49b814fa91f93a5f135b01885c6234021
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 cost_model_identity congruence.seq3_b k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-seq3_b-F1 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 aa5997e9f6d8260dfbdfc41c9a38a62e42c4afea4ce49b4efffceee92b4fba42
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s16.split.congruence-seq3_b-F2 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 84e875e37394ef28e43e7c9449730f6ca93469bb698956c8431602bd39b9a075
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s17.split.congruence-seq3_b-F3 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f97f57951a7b0bc4646c3a548717d86d8944204e7c7b4885666afefbde7632f0
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 cost_model_identity congruence.seq4_a k=5 联盟 congruence.k5.s00-s01-s02-s03-s04 成员 congruence.s00,congruence.s01,congruence.s02,congruence.s03,congruence.s04
  - 轮次 congruence.s00.split.congruence-seq4_a-F1 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 80bac950f430885ff697840707a76e14db22717d43b1273717a50ae2e0fc44da
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F1：抄写已知，不添加辅助线。
  - 轮次 congruence.s01.split.congruence-seq4_a-F2 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2942e04202567017c6228ea94a0cb206e33ab65be9dff95c884ea6aeea2e7fd7
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F2：指出要证明的对应关系。
  - 轮次 congruence.s02.split.congruence-seq4_a-F3 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a4853644f2fcf9e888bc8e59f3d5564a405f557660ce4f51edf7321aaba93d2e
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F3：列出三组条件。
  - 轮次 congruence.s03.split.congruence-seq4_a-F4 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 dfa220f6011c3956de60a5a048ba2b9d65ddf1a2f92af57db875d98b18515eee
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F4：写出判定和对应顶点顺序。
- G1 cost_model_identity congruence.seq4_a k=5 联盟 congruence.k5.s05-s06-s07-s08-s09 成员 congruence.s05,congruence.s06,congruence.s07,congruence.s08,congruence.s09
  - 轮次 congruence.s05.split.congruence-seq4_a-F1 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4d55e59dd88a4360bf0ab6afbdadc937895608f0c8c298c4852355d205e4d3c0
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F1：抄写已知，不添加辅助线。
  - 轮次 congruence.s06.split.congruence-seq4_a-F2 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 84fafc67d380ddb98d2f9ecbf27ddadcd186558401d9a1453a045b1562c41102
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F2：指出要证明的对应关系。
  - 轮次 congruence.s07.split.congruence-seq4_a-F3 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0c17fcd182cdceb6d6f21a89adda01ab0e98a6c23c634b39b4cbaf420967c1a7
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F3：列出三组条件。
  - 轮次 congruence.s08.split.congruence-seq4_a-F4 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bb77f46024e81363255a27afee26a74140c60f03a16d57fea2411e272224c0a8
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F4：写出判定和对应顶点顺序。
- G1 cost_model_identity congruence.seq4_a k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-seq4_a-F1 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 45ee948e33c4e5267608a8c6f72ce4de038af586768857b05a51cb08afaca466
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F1：抄写已知，不添加辅助线。
  - 轮次 congruence.s11.split.congruence-seq4_a-F2 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b1498b89ed188b353dfb7b54f066de89891fcd9d4d627e9429918e5f0e6c333d
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F2：指出要证明的对应关系。
  - 轮次 congruence.s12.split.congruence-seq4_a-F3 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 853ef20ebcb1f4c1c5f1552edf39f26207cc62062b3e792cef709d0cccb1aac3
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F3：列出三组条件。
  - 轮次 congruence.s13.split.congruence-seq4_a-F4 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bcd5eb9abb28e71b05120724e9c99fe76c9ccf0ae070c9681a2013b7aa48041b
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F4：写出判定和对应顶点顺序。
- G1 cost_model_identity congruence.seq4_a k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-seq4_a-F1 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 50655a2f84dd5710d4dc7ff305c2537e5838a09d4e541e539b7ca06cec377719
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F1：抄写已知，不添加辅助线。
  - 轮次 congruence.s16.split.congruence-seq4_a-F2 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b06f6719d56d119f3484fdfdb5d9bf868f24aa0e4de391a3d2e8b40e556e44d8
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F2：指出要证明的对应关系。
  - 轮次 congruence.s17.split.congruence-seq4_a-F3 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 cbc47e4b54914b28085435e209d37ca1986b5211ff1e54f9a2a6fc9d5af6a661
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F3：列出三组条件。
  - 轮次 congruence.s18.split.congruence-seq4_a-F4 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 e3221e6430cdef2ce03a4359f5d77fe971e80d82eaaf68609574d6444628842d
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F4：写出判定和对应顶点顺序。
- G1 cost_model_identity congruence.seq4_b k=5 联盟 congruence.k5.s00-s01-s02-s03-s04 成员 congruence.s00,congruence.s01,congruence.s02,congruence.s03,congruence.s04
  - 轮次 congruence.s00.split.congruence-seq4_b-F1 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a1d37706444f85cf3ed5a314b65a6765fa02b83a7d1a949d1cb7825a2b3f2750
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F1：先让学生口头说判定名称。
  - 轮次 congruence.s01.split.congruence-seq4_b-F2 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5f6dccf7953c19219a27039a787f835ceb6217ae2f5ba7ba69d716c18d7fc9b4
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F2：再要求指出夹角。
  - 轮次 congruence.s02.split.congruence-seq4_b-F3 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 37205c561fc9e2439866642ec754bdb1df0dc3451503d83788e9e418b5d85c82
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F3：然后写对应边。
  - 轮次 congruence.s03.split.congruence-seq4_b-F4 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 02c4a5c4673c3d8f6f20d3a28de6de52405b7cd1f8e5cc4e7555fa1b3204f7d7
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F4：最后交换顶点顺序，检查是否仍然成立。
- G1 cost_model_identity congruence.seq4_b k=5 联盟 congruence.k5.s05-s06-s07-s08-s09 成员 congruence.s05,congruence.s06,congruence.s07,congruence.s08,congruence.s09
  - 轮次 congruence.s05.split.congruence-seq4_b-F1 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d6f6b9409dedf2046588d63162c9a7a7060d3b661bb31667b47baa5178212bea
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F1：先让学生口头说判定名称。
  - 轮次 congruence.s06.split.congruence-seq4_b-F2 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9b8298b510b415d7cf297ac51445734d20c2937d83b6d665ccd17d4b1b4d8ffb
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F2：再要求指出夹角。
  - 轮次 congruence.s07.split.congruence-seq4_b-F3 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ebaa20bd950d573654444bc366685014220edcbf3bff3571b786f1a3417e2f37
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F3：然后写对应边。
  - 轮次 congruence.s08.split.congruence-seq4_b-F4 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6b46ab794a5a40810f6a4755d9e7392e49766aeb51eaca96901e691643a86e70
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F4：最后交换顶点顺序，检查是否仍然成立。
- G1 cost_model_identity congruence.seq4_b k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-seq4_b-F1 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6a0209f5277ac433993f206fb57f5fee2c802d48be34f95d539b27a84e78bae2
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F1：先让学生口头说判定名称。
  - 轮次 congruence.s11.split.congruence-seq4_b-F2 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0dae25896ccb60c1f2ed2041c4ab82277529a35ca24db135a83377f30d760ba9
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F2：再要求指出夹角。
  - 轮次 congruence.s12.split.congruence-seq4_b-F3 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6309e7ac28881b604a8198edd80608fcd8eba0a485281be3ae1fac9e39890287
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F3：然后写对应边。
  - 轮次 congruence.s13.split.congruence-seq4_b-F4 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f02a9af266c9fa2d074158fccbf0fa9c30dd126b0a88658eee028814f9f1763f
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F4：最后交换顶点顺序，检查是否仍然成立。
- G1 cost_model_identity congruence.seq4_b k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-seq4_b-F1 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4889f91427a56922fca1edf11459e1208f1e136c6c3fa07cc1911bc666f27fd7
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F1：先让学生口头说判定名称。
  - 轮次 congruence.s16.split.congruence-seq4_b-F2 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 61664aacf0a5ddba7d7b1995cd9746426af441a0bb62290d52455cc57a2a782a
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F2：再要求指出夹角。
  - 轮次 congruence.s17.split.congruence-seq4_b-F3 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b4937f9e2faaef73a60cd5de9e6a088eef7f516f13f37f0706e7bd8448fa83a3
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F3：然后写对应边。
  - 轮次 congruence.s18.split.congruence-seq4_b-F4 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 535d8a3e8ffc5559a122bd0704d93c9a3f6497fcff1221b4977855ac399114fd
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F4：最后交换顶点顺序，检查是否仍然成立。
- G1 nemo congruence.diag_a k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F1：错因是把夹角写成另外一个角。
  - 轮次 congruence.s11.split.congruence-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F2：干预是让学生用手指指出夹角，再落笔。
- G1 nemo congruence.diag_a k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F1：错因是把夹角写成另外一个角。
  - 轮次 congruence.s16.split.congruence-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F2：干预是让学生用手指指出夹角，再落笔。
- G1 nemo congruence.diag_b k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F1：错因是对应顶点写反，边的名称跟着错。
  - 轮次 congruence.s11.split.congruence-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F2：干预是先写对应顶点顺序，再写边。
- G1 nemo congruence.diag_b k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F1：错因是对应顶点写反，边的名称跟着错。
  - 轮次 congruence.s16.split.congruence-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F2：干预是先写对应顶点顺序，再写边。
- G1 nemo congruence.seq3_a k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s11.split.congruence-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s12.split.congruence-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 nemo congruence.seq3_a k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s16.split.congruence-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s17.split.congruence-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 nemo congruence.seq3_b k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s11.split.congruence-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s12.split.congruence-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 nemo congruence.seq3_b k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s16.split.congruence-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s17.split.congruence-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 nemo congruence.seq4_a k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-seq4_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F1：抄写已知，不添加辅助线。
  - 轮次 congruence.s11.split.congruence-seq4_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F2：指出要证明的对应关系。
  - 轮次 congruence.s12.split.congruence-seq4_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F3：列出三组条件。
  - 轮次 congruence.s13.split.congruence-seq4_a-F4 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F4：写出判定和对应顶点顺序。
- G1 nemo congruence.seq4_a k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-seq4_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F1：抄写已知，不添加辅助线。
  - 轮次 congruence.s16.split.congruence-seq4_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F2：指出要证明的对应关系。
  - 轮次 congruence.s17.split.congruence-seq4_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F3：列出三组条件。
  - 轮次 congruence.s18.split.congruence-seq4_a-F4 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F4：写出判定和对应顶点顺序。
- G1 nemo congruence.seq4_b k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-seq4_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F1：先让学生口头说判定名称。
  - 轮次 congruence.s11.split.congruence-seq4_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F2：再要求指出夹角。
  - 轮次 congruence.s12.split.congruence-seq4_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F3：然后写对应边。
  - 轮次 congruence.s13.split.congruence-seq4_b-F4 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F4：最后交换顶点顺序，检查是否仍然成立。
- G1 nemo congruence.seq4_b k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-seq4_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F1：先让学生口头说判定名称。
  - 轮次 congruence.s16.split.congruence-seq4_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F2：再要求指出夹角。
  - 轮次 congruence.s17.split.congruence-seq4_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F3：然后写对应边。
  - 轮次 congruence.s18.split.congruence-seq4_b-F4 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F4：最后交换顶点顺序，检查是否仍然成立。
- G1 none congruence.diag_a k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F1：错因是把夹角写成另外一个角。
  - 轮次 congruence.s11.split.congruence-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F2：干预是让学生用手指指出夹角，再落笔。
- G1 none congruence.diag_a k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F1：错因是把夹角写成另外一个角。
  - 轮次 congruence.s16.split.congruence-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_a-F2：干预是让学生用手指指出夹角，再落笔。
- G1 none congruence.diag_b k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F1：错因是对应顶点写反，边的名称跟着错。
  - 轮次 congruence.s11.split.congruence-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F2：干预是先写对应顶点顺序，再写边。
- G1 none congruence.diag_b k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F1：错因是对应顶点写反，边的名称跟着错。
  - 轮次 congruence.s16.split.congruence-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-diag_b-F2：干预是先写对应顶点顺序，再写边。
- G1 none congruence.seq3_a k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s11.split.congruence-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s12.split.congruence-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 none congruence.seq3_a k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s16.split.congruence-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s17.split.congruence-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G1 none congruence.seq3_b k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s11.split.congruence-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s12.split.congruence-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 none congruence.seq3_b k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s16.split.congruence-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s17.split.congruence-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G1 none congruence.seq4_a k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-seq4_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F1：抄写已知，不添加辅助线。
  - 轮次 congruence.s11.split.congruence-seq4_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F2：指出要证明的对应关系。
  - 轮次 congruence.s12.split.congruence-seq4_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F3：列出三组条件。
  - 轮次 congruence.s13.split.congruence-seq4_a-F4 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F4：写出判定和对应顶点顺序。
- G1 none congruence.seq4_a k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-seq4_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F1：抄写已知，不添加辅助线。
  - 轮次 congruence.s16.split.congruence-seq4_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F2：指出要证明的对应关系。
  - 轮次 congruence.s17.split.congruence-seq4_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F3：列出三组条件。
  - 轮次 congruence.s18.split.congruence-seq4_a-F4 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F4：写出判定和对应顶点顺序。
- G1 none congruence.seq4_b k=5 联盟 congruence.k5.s10-s11-s12-s13-s14 成员 congruence.s10,congruence.s11,congruence.s12,congruence.s13,congruence.s14
  - 轮次 congruence.s10.split.congruence-seq4_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F1：先让学生口头说判定名称。
  - 轮次 congruence.s11.split.congruence-seq4_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F2：再要求指出夹角。
  - 轮次 congruence.s12.split.congruence-seq4_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F3：然后写对应边。
  - 轮次 congruence.s13.split.congruence-seq4_b-F4 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F4：最后交换顶点顺序，检查是否仍然成立。
- G1 none congruence.seq4_b k=5 联盟 congruence.k5.s15-s16-s17-s18-s19 成员 congruence.s15,congruence.s16,congruence.s17,congruence.s18,congruence.s19
  - 轮次 congruence.s15.split.congruence-seq4_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F1：先让学生口头说判定名称。
  - 轮次 congruence.s16.split.congruence-seq4_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F2：再要求指出夹角。
  - 轮次 congruence.s17.split.congruence-seq4_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F3：然后写对应边。
  - 轮次 congruence.s18.split.congruence-seq4_b-F4 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F4：最后交换顶点顺序，检查是否仍然成立。
- G1 none linear_eq.diag_a k=2 联盟 linear_eq.k2.s00-s01 成员 linear_eq.s00,linear_eq.s01
  - 轮次 linear_eq.s00.split.linear_eq-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_a-F1：错因是移项时只搬家、不变号。
  - 轮次 linear_eq.s01.split.linear_eq-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_a-F2：干预是要求每移一项就在旁边写上相反数。
- G1 none linear_eq.diag_a k=2 联盟 linear_eq.k2.s05-s06 成员 linear_eq.s05,linear_eq.s06
  - 轮次 linear_eq.s05.split.linear_eq-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_a-F1：错因是移项时只搬家、不变号。
  - 轮次 linear_eq.s06.split.linear_eq-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_a-F2：干预是要求每移一项就在旁边写上相反数。
- G1 none linear_eq.diag_a k=2 联盟 linear_eq.k2.s10-s11 成员 linear_eq.s10,linear_eq.s11
  - 轮次 linear_eq.s10.split.linear_eq-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_a-F1：错因是移项时只搬家、不变号。
  - 轮次 linear_eq.s11.split.linear_eq-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_a-F2：干预是要求每移一项就在旁边写上相反数。
- G1 none linear_eq.diag_a k=2 联盟 linear_eq.k2.s15-s16 成员 linear_eq.s15,linear_eq.s16
  - 轮次 linear_eq.s15.split.linear_eq-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_a-F1：错因是移项时只搬家、不变号。
  - 轮次 linear_eq.s16.split.linear_eq-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_a-F2：干预是要求每移一项就在旁边写上相反数。
- G1 none linear_eq.diag_b k=2 联盟 linear_eq.k2.s00-s01 成员 linear_eq.s00,linear_eq.s01
  - 轮次 linear_eq.s00.split.linear_eq-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_b-F1：错因是系数化为 1 时把除法做成乘法。
  - 轮次 linear_eq.s01.split.linear_eq-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_b-F2：干预是先圈出未知数系数，再写除以这个系数。
- G1 none linear_eq.diag_b k=2 联盟 linear_eq.k2.s05-s06 成员 linear_eq.s05,linear_eq.s06
  - 轮次 linear_eq.s05.split.linear_eq-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_b-F1：错因是系数化为 1 时把除法做成乘法。
  - 轮次 linear_eq.s06.split.linear_eq-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_b-F2：干预是先圈出未知数系数，再写除以这个系数。
- G1 none linear_eq.diag_b k=2 联盟 linear_eq.k2.s10-s11 成员 linear_eq.s10,linear_eq.s11
  - 轮次 linear_eq.s10.split.linear_eq-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_b-F1：错因是系数化为 1 时把除法做成乘法。
  - 轮次 linear_eq.s11.split.linear_eq-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_b-F2：干预是先圈出未知数系数，再写除以这个系数。
- G1 none linear_eq.diag_b k=2 联盟 linear_eq.k2.s15-s16 成员 linear_eq.s15,linear_eq.s16
  - 轮次 linear_eq.s15.split.linear_eq-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_b-F1：错因是系数化为 1 时把除法做成乘法。
  - 轮次 linear_eq.s16.split.linear_eq-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 linear_eq-diag_b-F2：干预是先圈出未知数系数，再写除以这个系数。
- G1 cost_model_identity linear_eq.seq3_a k=3 联盟 linear_eq.k3.s00-s01-s02 成员 linear_eq.s00,linear_eq.s01,linear_eq.s02
  - 轮次 linear_eq.s00.split.linear_eq-seq3_a-F1 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8cebb4e13e45593770d895dba3844643fbcc24181f4def5744e4f019c0947315
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F1：先合并同类项，不先除系数。
  - 轮次 linear_eq.s01.split.linear_eq-seq3_a-F2 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 71b89126d1d5f644268703e4aeaec156e559be46b79ce83509e57e88e2280856
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F2：再把常数项移到另一边并变号。
  - 轮次 linear_eq.s02.split.linear_eq-seq3_a-F3 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 af5ebf7c87e3578f3000a9c48ee43cddc077d4f4fba8079252ca27b603475a23
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F3：最后把未知数系数化为 1。
- G1 cost_model_identity linear_eq.seq3_a k=3 联盟 linear_eq.k3.s05-s06-s07 成员 linear_eq.s05,linear_eq.s06,linear_eq.s07
  - 轮次 linear_eq.s05.split.linear_eq-seq3_a-F1 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 964df289a67af2190f263c76e15f2096fe7b43bbd5358a7b26d6217ac7f3f782
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F1：先合并同类项，不先除系数。
  - 轮次 linear_eq.s06.split.linear_eq-seq3_a-F2 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6dc35de59c6c830c5553ec79dc6a2f7d30cbf1d418f95ad616a61a8103342cdc
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F2：再把常数项移到另一边并变号。
  - 轮次 linear_eq.s07.split.linear_eq-seq3_a-F3 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 764b9ce1bcc13dda20899b1e4815d64b696059efcc685447c6ddd3ef609afe06
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F3：最后把未知数系数化为 1。
- G1 cost_model_identity linear_eq.seq3_a k=3 联盟 linear_eq.k3.s10-s11-s12 成员 linear_eq.s10,linear_eq.s11,linear_eq.s12
  - 轮次 linear_eq.s10.split.linear_eq-seq3_a-F1 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 41cd9506cdd44d83a0b97b7da765b38e04246eb9fd8af88653363441ab54b720
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F1：先合并同类项，不先除系数。
  - 轮次 linear_eq.s11.split.linear_eq-seq3_a-F2 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5e1b152655cbfb0ddbe6e5c69d2dc2a65748c74edfc870589c89c31a65ecedac
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F2：再把常数项移到另一边并变号。
  - 轮次 linear_eq.s12.split.linear_eq-seq3_a-F3 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5860cb76333a00d39f60b9346ad1b50900583dc64b61cf6fc4db5511a02d51ea
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F3：最后把未知数系数化为 1。
- G1 cost_model_identity linear_eq.seq3_a k=3 联盟 linear_eq.k3.s15-s16-s17 成员 linear_eq.s15,linear_eq.s16,linear_eq.s17
  - 轮次 linear_eq.s15.split.linear_eq-seq3_a-F1 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 736237716dafd4a9ffaad63abed6b41481cff5ff7f701c06acea4051ca9a7e1b
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F1：先合并同类项，不先除系数。
  - 轮次 linear_eq.s16.split.linear_eq-seq3_a-F2 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 634e6e93585566e605272fa1a20af967645b2daedf96bb9d1b14b664f89ee5a0
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F2：再把常数项移到另一边并变号。
  - 轮次 linear_eq.s17.split.linear_eq-seq3_a-F3 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 eb55e5c73bdced5955eb093737fc746a59faa2cf1405a3df070ff9f09536f597
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F3：最后把未知数系数化为 1。
- G1 cost_model_identity linear_eq.seq3_b k=3 联盟 linear_eq.k3.s00-s01-s02 成员 linear_eq.s00,linear_eq.s01,linear_eq.s02
  - 轮次 linear_eq.s00.split.linear_eq-seq3_b-F1 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 dd42b3430e79588d41e3a3d8c8c88e7f337a403b2ba39c9dbe6b2f9d7925627a
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F1：先去分母，写明同乘的数。
  - 轮次 linear_eq.s01.split.linear_eq-seq3_b-F2 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6e959950263f0d0601ad686d5a7e64b64672fba369e33ae1e0680b56ea45be54
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F2：再去括号，分配律逐项做。
  - 轮次 linear_eq.s02.split.linear_eq-seq3_b-F3 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f44ed54a9aa05a3a48f34a152ee0323430d463023c7d562a6615187eb6aa8565
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F3：最后才移项合并。
- G1 cost_model_identity linear_eq.seq3_b k=3 联盟 linear_eq.k3.s05-s06-s07 成员 linear_eq.s05,linear_eq.s06,linear_eq.s07
  - 轮次 linear_eq.s05.split.linear_eq-seq3_b-F1 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2dd459de6957a23166fc52596891be8d62268c4dde67ee8b69714d0ef7263a1a
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F1：先去分母，写明同乘的数。
  - 轮次 linear_eq.s06.split.linear_eq-seq3_b-F2 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 129858bca368d81ea74ccba5bf814333f93a55bdff376c4bbf60b3b292399a9c
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F2：再去括号，分配律逐项做。
  - 轮次 linear_eq.s07.split.linear_eq-seq3_b-F3 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a413ccec14590c246622cd378d6c8dec3ab31cbe47028f817ff44e471856a6f1
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F3：最后才移项合并。
- G1 cost_model_identity linear_eq.seq3_b k=3 联盟 linear_eq.k3.s10-s11-s12 成员 linear_eq.s10,linear_eq.s11,linear_eq.s12
  - 轮次 linear_eq.s10.split.linear_eq-seq3_b-F1 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 25f041361ded626d96640539f158f0cfef00286eb067ee1c389a456fc24a943c
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F1：先去分母，写明同乘的数。
  - 轮次 linear_eq.s11.split.linear_eq-seq3_b-F2 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5d0ba6374c8b8d1b9e247a356b0d62753aa4b3825f99f6493ebb3b546d7224fe
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F2：再去括号，分配律逐项做。
  - 轮次 linear_eq.s12.split.linear_eq-seq3_b-F3 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a2691fa71ac8245a82a9c7130516e748aa907f07e1d60227506aeba23014616a
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F3：最后才移项合并。
- G1 cost_model_identity linear_eq.seq3_b k=3 联盟 linear_eq.k3.s15-s16-s17 成员 linear_eq.s15,linear_eq.s16,linear_eq.s17
  - 轮次 linear_eq.s15.split.linear_eq-seq3_b-F1 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b744789a4e22f22d9c66c2be163817ef7a52a7d19d4e7b6157af71235b4d1d75
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F1：先去分母，写明同乘的数。
  - 轮次 linear_eq.s16.split.linear_eq-seq3_b-F2 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 81d25ec808fce51b92fd4752ec47cf8fb0c483d7e7d38b7f788cd3761f362bf6
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F2：再去括号，分配律逐项做。
  - 轮次 linear_eq.s17.split.linear_eq-seq3_b-F3 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5544b1b1b985075a3ea158fd0003655956bd851dea5c214208402a80e053b99f
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F3：最后才移项合并。
- G1 cost_model_identity linear_eq.seq3_a k=5 联盟 linear_eq.k5.s00-s01-s02-s03-s04 成员 linear_eq.s00,linear_eq.s01,linear_eq.s02,linear_eq.s03,linear_eq.s04
  - 轮次 linear_eq.s00.split.linear_eq-seq3_a-F1 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8cebb4e13e45593770d895dba3844643fbcc24181f4def5744e4f019c0947315
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F1：先合并同类项，不先除系数。
  - 轮次 linear_eq.s01.split.linear_eq-seq3_a-F2 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 71b89126d1d5f644268703e4aeaec156e559be46b79ce83509e57e88e2280856
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F2：再把常数项移到另一边并变号。
  - 轮次 linear_eq.s02.split.linear_eq-seq3_a-F3 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 af5ebf7c87e3578f3000a9c48ee43cddc077d4f4fba8079252ca27b603475a23
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F3：最后把未知数系数化为 1。
- G1 cost_model_identity linear_eq.seq3_a k=5 联盟 linear_eq.k5.s05-s06-s07-s08-s09 成员 linear_eq.s05,linear_eq.s06,linear_eq.s07,linear_eq.s08,linear_eq.s09
  - 轮次 linear_eq.s05.split.linear_eq-seq3_a-F1 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 964df289a67af2190f263c76e15f2096fe7b43bbd5358a7b26d6217ac7f3f782
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F1：先合并同类项，不先除系数。
  - 轮次 linear_eq.s06.split.linear_eq-seq3_a-F2 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6dc35de59c6c830c5553ec79dc6a2f7d30cbf1d418f95ad616a61a8103342cdc
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F2：再把常数项移到另一边并变号。
  - 轮次 linear_eq.s07.split.linear_eq-seq3_a-F3 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 764b9ce1bcc13dda20899b1e4815d64b696059efcc685447c6ddd3ef609afe06
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F3：最后把未知数系数化为 1。
- G1 cost_model_identity linear_eq.seq3_a k=5 联盟 linear_eq.k5.s10-s11-s12-s13-s14 成员 linear_eq.s10,linear_eq.s11,linear_eq.s12,linear_eq.s13,linear_eq.s14
  - 轮次 linear_eq.s10.split.linear_eq-seq3_a-F1 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 41cd9506cdd44d83a0b97b7da765b38e04246eb9fd8af88653363441ab54b720
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F1：先合并同类项，不先除系数。
  - 轮次 linear_eq.s11.split.linear_eq-seq3_a-F2 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5e1b152655cbfb0ddbe6e5c69d2dc2a65748c74edfc870589c89c31a65ecedac
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F2：再把常数项移到另一边并变号。
  - 轮次 linear_eq.s12.split.linear_eq-seq3_a-F3 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5860cb76333a00d39f60b9346ad1b50900583dc64b61cf6fc4db5511a02d51ea
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F3：最后把未知数系数化为 1。
- G1 cost_model_identity linear_eq.seq3_a k=5 联盟 linear_eq.k5.s15-s16-s17-s18-s19 成员 linear_eq.s15,linear_eq.s16,linear_eq.s17,linear_eq.s18,linear_eq.s19
  - 轮次 linear_eq.s15.split.linear_eq-seq3_a-F1 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 736237716dafd4a9ffaad63abed6b41481cff5ff7f701c06acea4051ca9a7e1b
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F1：先合并同类项，不先除系数。
  - 轮次 linear_eq.s16.split.linear_eq-seq3_a-F2 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 634e6e93585566e605272fa1a20af967645b2daedf96bb9d1b14b664f89ee5a0
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F2：再把常数项移到另一边并变号。
  - 轮次 linear_eq.s17.split.linear_eq-seq3_a-F3 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 eb55e5c73bdced5955eb093737fc746a59faa2cf1405a3df070ff9f09536f597
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F3：最后把未知数系数化为 1。
- G1 cost_model_identity linear_eq.seq3_b k=5 联盟 linear_eq.k5.s00-s01-s02-s03-s04 成员 linear_eq.s00,linear_eq.s01,linear_eq.s02,linear_eq.s03,linear_eq.s04
  - 轮次 linear_eq.s00.split.linear_eq-seq3_b-F1 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 dd42b3430e79588d41e3a3d8c8c88e7f337a403b2ba39c9dbe6b2f9d7925627a
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F1：先去分母，写明同乘的数。
  - 轮次 linear_eq.s01.split.linear_eq-seq3_b-F2 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6e959950263f0d0601ad686d5a7e64b64672fba369e33ae1e0680b56ea45be54
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F2：再去括号，分配律逐项做。
  - 轮次 linear_eq.s02.split.linear_eq-seq3_b-F3 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f44ed54a9aa05a3a48f34a152ee0323430d463023c7d562a6615187eb6aa8565
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F3：最后才移项合并。
- G1 cost_model_identity linear_eq.seq3_b k=5 联盟 linear_eq.k5.s05-s06-s07-s08-s09 成员 linear_eq.s05,linear_eq.s06,linear_eq.s07,linear_eq.s08,linear_eq.s09
  - 轮次 linear_eq.s05.split.linear_eq-seq3_b-F1 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2dd459de6957a23166fc52596891be8d62268c4dde67ee8b69714d0ef7263a1a
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F1：先去分母，写明同乘的数。
  - 轮次 linear_eq.s06.split.linear_eq-seq3_b-F2 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 129858bca368d81ea74ccba5bf814333f93a55bdff376c4bbf60b3b292399a9c
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F2：再去括号，分配律逐项做。
  - 轮次 linear_eq.s07.split.linear_eq-seq3_b-F3 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a413ccec14590c246622cd378d6c8dec3ab31cbe47028f817ff44e471856a6f1
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F3：最后才移项合并。
- G1 cost_model_identity linear_eq.seq3_b k=5 联盟 linear_eq.k5.s10-s11-s12-s13-s14 成员 linear_eq.s10,linear_eq.s11,linear_eq.s12,linear_eq.s13,linear_eq.s14
  - 轮次 linear_eq.s10.split.linear_eq-seq3_b-F1 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 25f041361ded626d96640539f158f0cfef00286eb067ee1c389a456fc24a943c
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F1：先去分母，写明同乘的数。
  - 轮次 linear_eq.s11.split.linear_eq-seq3_b-F2 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5d0ba6374c8b8d1b9e247a356b0d62753aa4b3825f99f6493ebb3b546d7224fe
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F2：再去括号，分配律逐项做。
  - 轮次 linear_eq.s12.split.linear_eq-seq3_b-F3 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a2691fa71ac8245a82a9c7130516e748aa907f07e1d60227506aeba23014616a
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F3：最后才移项合并。
- G1 cost_model_identity linear_eq.seq3_b k=5 联盟 linear_eq.k5.s15-s16-s17-s18-s19 成员 linear_eq.s15,linear_eq.s16,linear_eq.s17,linear_eq.s18,linear_eq.s19
  - 轮次 linear_eq.s15.split.linear_eq-seq3_b-F1 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b744789a4e22f22d9c66c2be163817ef7a52a7d19d4e7b6157af71235b4d1d75
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F1：先去分母，写明同乘的数。
  - 轮次 linear_eq.s16.split.linear_eq-seq3_b-F2 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 81d25ec808fce51b92fd4752ec47cf8fb0c483d7e7d38b7f788cd3761f362bf6
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F2：再去括号，分配律逐项做。
  - 轮次 linear_eq.s17.split.linear_eq-seq3_b-F3 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5544b1b1b985075a3ea158fd0003655956bd851dea5c214208402a80e053b99f
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F3：最后才移项合并。
- G1 cost_model_identity linear_eq.seq4_a k=5 联盟 linear_eq.k5.s00-s01-s02-s03-s04 成员 linear_eq.s00,linear_eq.s01,linear_eq.s02,linear_eq.s03,linear_eq.s04
  - 轮次 linear_eq.s00.split.linear_eq-seq4_a-F1 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 47acc924a52e2e881b3f234929219aefe596732ab90de70b3b05acea97935cdf
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F1：读题时先标出等号两边。
  - 轮次 linear_eq.s01.split.linear_eq-seq4_a-F2 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 e1b31d8c8030468481de0cb129eff940c6e627b5e642056474ac328541516c29
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F2：去分母后逐项检查有没有漏乘。
  - 轮次 linear_eq.s02.split.linear_eq-seq4_a-F3 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c2bd206d962554cb52b56e9c1b8d39889759d3bbe53a894c44f15f597e598cc0
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F3：移项时只动一项，并立刻变号。
  - 轮次 linear_eq.s03.split.linear_eq-seq4_a-F4 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bc79fa98626e429228993bf81fd91adde5b294d990e0b8494b20bf5465f59c78
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F4：写出解以后代回原方程检验。
- G1 cost_model_identity linear_eq.seq4_a k=5 联盟 linear_eq.k5.s05-s06-s07-s08-s09 成员 linear_eq.s05,linear_eq.s06,linear_eq.s07,linear_eq.s08,linear_eq.s09
  - 轮次 linear_eq.s05.split.linear_eq-seq4_a-F1 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c65d15b75d07147b244d1f2810b1e2ac52ee04ed9962840a3d4a6beb453269e9
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F1：读题时先标出等号两边。
  - 轮次 linear_eq.s06.split.linear_eq-seq4_a-F2 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bd2aa63558d05ed29ed0bad4c125cdc714fb393a1cc6ade2a61559746c910709
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F2：去分母后逐项检查有没有漏乘。
  - 轮次 linear_eq.s07.split.linear_eq-seq4_a-F3 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c6e061d3b3a764405f9c1c1f78e1b5d000d9d93b45a7e33723d0ae214ce6b6d8
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F3：移项时只动一项，并立刻变号。
  - 轮次 linear_eq.s08.split.linear_eq-seq4_a-F4 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 e4a10d7be8d84ee7de917fd2bebe7c3184b869dd10f94a839411f21b5d09db55
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F4：写出解以后代回原方程检验。
- G1 cost_model_identity linear_eq.seq4_a k=5 联盟 linear_eq.k5.s10-s11-s12-s13-s14 成员 linear_eq.s10,linear_eq.s11,linear_eq.s12,linear_eq.s13,linear_eq.s14
  - 轮次 linear_eq.s10.split.linear_eq-seq4_a-F1 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 448c43e05c2a8b541aa2e35532af1847760848ad1a485883aa6d8152984ade26
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F1：读题时先标出等号两边。
  - 轮次 linear_eq.s11.split.linear_eq-seq4_a-F2 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0261fcf57009134299c5d68b9988708c099d9634b2da5b9abcec853b9c2bccbb
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F2：去分母后逐项检查有没有漏乘。
  - 轮次 linear_eq.s12.split.linear_eq-seq4_a-F3 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 7c485e9c3d0e1773b274ec5ae37002e7b68703578d9bdbe10b67c5df1f8dc89a
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F3：移项时只动一项，并立刻变号。
  - 轮次 linear_eq.s13.split.linear_eq-seq4_a-F4 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 131abbe3bb9ac92d4565f64a05df7c0e6aff85caf6503e2b278b453af95415e8
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F4：写出解以后代回原方程检验。
- G1 cost_model_identity linear_eq.seq4_a k=5 联盟 linear_eq.k5.s15-s16-s17-s18-s19 成员 linear_eq.s15,linear_eq.s16,linear_eq.s17,linear_eq.s18,linear_eq.s19
  - 轮次 linear_eq.s15.split.linear_eq-seq4_a-F1 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 28a913c055e6d0d55347331df6239cff167fa1f628517d8f3753022115888331
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F1：读题时先标出等号两边。
  - 轮次 linear_eq.s16.split.linear_eq-seq4_a-F2 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ec6974afb61817c507333052a9dddd74679e5c6fd2b23378fb2810a8e33f8097
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F2：去分母后逐项检查有没有漏乘。
  - 轮次 linear_eq.s17.split.linear_eq-seq4_a-F3 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 812020d5db27bf3d38de5eedd38c1a0971600f6ce054f676279a2ef38c82860e
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F3：移项时只动一项，并立刻变号。
  - 轮次 linear_eq.s18.split.linear_eq-seq4_a-F4 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c1740d35c8a46feac583cc18d8ea4a37f10d4085233653d1ff13ea0c31736074
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F4：写出解以后代回原方程检验。
- G1 cost_model_identity linear_eq.seq4_b k=5 联盟 linear_eq.k5.s00-s01-s02-s03-s04 成员 linear_eq.s00,linear_eq.s01,linear_eq.s02,linear_eq.s03,linear_eq.s04
  - 轮次 linear_eq.s00.split.linear_eq-seq4_b-F1 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 85e03333839ec7503994c5be4f5964c45d82d2bbf7190040bfbe55f3fc3a6803
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F1：例题先讲整数系数。
  - 轮次 linear_eq.s01.split.linear_eq-seq4_b-F2 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 899a65ade2bd95ee86e88b1cb87e080595ab4ea59be039dae42b8c845cd0ced7
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F2：变式改成带分数。
  - 轮次 linear_eq.s02.split.linear_eq-seq4_b-F3 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bb8d106adc460451f83b3d8c692204d3daebf62815087e91ada37dbd39d11b8c
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F3：再改成含括号。
  - 轮次 linear_eq.s03.split.linear_eq-seq4_b-F4 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 563de82476547af9a5e8e4e4130132e613bfd987008f95dad4e7dd2361d64083
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F4：最后让学生自己出一道并写出检验。
- G1 cost_model_identity linear_eq.seq4_b k=5 联盟 linear_eq.k5.s05-s06-s07-s08-s09 成员 linear_eq.s05,linear_eq.s06,linear_eq.s07,linear_eq.s08,linear_eq.s09
  - 轮次 linear_eq.s05.split.linear_eq-seq4_b-F1 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8f26b8407d3266ee8f23ecfc5d57bbf87ee29234636cd670efe4b1e203d8577f
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F1：例题先讲整数系数。
  - 轮次 linear_eq.s06.split.linear_eq-seq4_b-F2 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0f621eb866009c464992d81aef840fe197e720ad5a987b2d0d129390658ee6d3
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F2：变式改成带分数。
  - 轮次 linear_eq.s07.split.linear_eq-seq4_b-F3 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 cb67d8bbb96d4c6c86045296a5642a166353aee709cde2e7dea59525f18d5bf0
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F3：再改成含括号。
  - 轮次 linear_eq.s08.split.linear_eq-seq4_b-F4 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b8f5244db1cb60bc93c963ca2de126d36cf0268d451fd9b82351c94f1974dcc5
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F4：最后让学生自己出一道并写出检验。
- G1 cost_model_identity linear_eq.seq4_b k=5 联盟 linear_eq.k5.s10-s11-s12-s13-s14 成员 linear_eq.s10,linear_eq.s11,linear_eq.s12,linear_eq.s13,linear_eq.s14
  - 轮次 linear_eq.s10.split.linear_eq-seq4_b-F1 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 67d31b524e8492839e2aa7f5612015dcd4cf5d97955c4ee9295ac4056b97570c
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F1：例题先讲整数系数。
  - 轮次 linear_eq.s11.split.linear_eq-seq4_b-F2 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0f4900fca3ed134830e1bebc9ae223ff0e8e1a8a09223bf0a7588522a561d0ed
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F2：变式改成带分数。
  - 轮次 linear_eq.s12.split.linear_eq-seq4_b-F3 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8210045ba658fc5247d7d0c072059903088aa5025affede74a9f578ccfb5c191
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F3：再改成含括号。
  - 轮次 linear_eq.s13.split.linear_eq-seq4_b-F4 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ccb3616a96d734bb295d0f618f08c9348aa5d0bc40ae708f265f246626e9fe28
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F4：最后让学生自己出一道并写出检验。
- G1 cost_model_identity linear_eq.seq4_b k=5 联盟 linear_eq.k5.s15-s16-s17-s18-s19 成员 linear_eq.s15,linear_eq.s16,linear_eq.s17,linear_eq.s18,linear_eq.s19
  - 轮次 linear_eq.s15.split.linear_eq-seq4_b-F1 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 776b32e3e0c6bb71654d9e57ab596967f3ae75d462128b9cdb17602150409f86
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F1：例题先讲整数系数。
  - 轮次 linear_eq.s16.split.linear_eq-seq4_b-F2 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 7826345ca9272e7383259133a721efd60a5fd74bf94137b0d5f20191434f2726
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F2：变式改成带分数。
  - 轮次 linear_eq.s17.split.linear_eq-seq4_b-F3 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f18fc2891ec975700abb68d7d126b85d972a2d9e4bc2948cebc08e3a03754434
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F3：再改成含括号。
  - 轮次 linear_eq.s18.split.linear_eq-seq4_b-F4 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6204205e5da13f220c91073af59446ea43815c0b2a7022592b9a4abc86e75703
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F4：最后让学生自己出一道并写出检验。
- G1 nemo prob_tree.diag_a k=2 联盟 prob_tree.k2.s00-s01 成员 prob_tree.s00,prob_tree.s01
  - 轮次 prob_tree.s00.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s01.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 nemo prob_tree.diag_a k=2 联盟 prob_tree.k2.s05-s06 成员 prob_tree.s05,prob_tree.s06
  - 轮次 prob_tree.s05.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s06.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 nemo prob_tree.diag_a k=2 联盟 prob_tree.k2.s10-s11 成员 prob_tree.s10,prob_tree.s11
  - 轮次 prob_tree.s10.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s11.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 nemo prob_tree.diag_a k=2 联盟 prob_tree.k2.s15-s16 成员 prob_tree.s15,prob_tree.s16
  - 轮次 prob_tree.s15.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s16.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 nemo prob_tree.diag_b k=2 联盟 prob_tree.k2.s00-s01 成员 prob_tree.s00,prob_tree.s01
  - 轮次 prob_tree.s00.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s01.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 nemo prob_tree.diag_b k=2 联盟 prob_tree.k2.s05-s06 成员 prob_tree.s05,prob_tree.s06
  - 轮次 prob_tree.s05.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s06.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 nemo prob_tree.diag_b k=2 联盟 prob_tree.k2.s10-s11 成员 prob_tree.s10,prob_tree.s11
  - 轮次 prob_tree.s10.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s11.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 nemo prob_tree.diag_b k=2 联盟 prob_tree.k2.s15-s16 成员 prob_tree.s15,prob_tree.s16
  - 轮次 prob_tree.s15.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s16.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 none prob_tree.diag_a k=2 联盟 prob_tree.k2.s00-s01 成员 prob_tree.s00,prob_tree.s01
  - 轮次 prob_tree.s00.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s01.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 none prob_tree.diag_a k=2 联盟 prob_tree.k2.s05-s06 成员 prob_tree.s05,prob_tree.s06
  - 轮次 prob_tree.s05.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s06.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 none prob_tree.diag_a k=2 联盟 prob_tree.k2.s10-s11 成员 prob_tree.s10,prob_tree.s11
  - 轮次 prob_tree.s10.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s11.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 none prob_tree.diag_a k=2 联盟 prob_tree.k2.s15-s16 成员 prob_tree.s15,prob_tree.s16
  - 轮次 prob_tree.s15.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s16.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 none prob_tree.diag_b k=2 联盟 prob_tree.k2.s00-s01 成员 prob_tree.s00,prob_tree.s01
  - 轮次 prob_tree.s00.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s01.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 none prob_tree.diag_b k=2 联盟 prob_tree.k2.s05-s06 成员 prob_tree.s05,prob_tree.s06
  - 轮次 prob_tree.s05.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s06.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 none prob_tree.diag_b k=2 联盟 prob_tree.k2.s10-s11 成员 prob_tree.s10,prob_tree.s11
  - 轮次 prob_tree.s10.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s11.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 none prob_tree.diag_b k=2 联盟 prob_tree.k2.s15-s16 成员 prob_tree.s15,prob_tree.s16
  - 轮次 prob_tree.s15.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s16.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 cost_model_identity prob_tree.seq3_a k=3 联盟 prob_tree.k3.s00-s01-s02 成员 prob_tree.s00,prob_tree.s01,prob_tree.s02
  - 轮次 prob_tree.s00.split.prob_tree-seq3_a-F1 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 1939a5af15601843ad4742f60a166e04d6465ebf47c73d57e327c9e77fc95b31
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s01.split.prob_tree-seq3_a-F2 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f5cd0ca6cba658745ce450fcd31c16e0fc290f7fb7b0e2cd7b3084be15a4ba0a
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s02.split.prob_tree-seq3_a-F3 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 91abbbbc2627f7a4e0df1c2ddc8c27954b2d4c281921240c09a6b40026cb04c4
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 cost_model_identity prob_tree.seq3_a k=3 联盟 prob_tree.k3.s05-s06-s07 成员 prob_tree.s05,prob_tree.s06,prob_tree.s07
  - 轮次 prob_tree.s05.split.prob_tree-seq3_a-F1 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 e76cd3ed40afd9c13f00508425da631621e5bc75e2e0595e5b439dc3cf55e3a8
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s06.split.prob_tree-seq3_a-F2 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d0200bc39d603662f8ebc55a720c12d254370082c6bfb765b150b58400d9fa5d
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s07.split.prob_tree-seq3_a-F3 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9d5404d38396e3ee4083910596c3b5035678b8d008aec9ae6702d3719e153d0b
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 cost_model_identity prob_tree.seq3_a k=3 联盟 prob_tree.k3.s10-s11-s12 成员 prob_tree.s10,prob_tree.s11,prob_tree.s12
  - 轮次 prob_tree.s10.split.prob_tree-seq3_a-F1 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9a71b547ba82b569d50028e4ce2e7b3097247de8f172eb62c03b32aba432b05c
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s11.split.prob_tree-seq3_a-F2 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f48d0dc39d79e93e215a0743424987673e77331dee0c04dcc36e87e7cb9e38a0
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s12.split.prob_tree-seq3_a-F3 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 415d272ed16c75a972fd9a5966231208d221f032d7db9a3692bafcecaed2d8a1
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 cost_model_identity prob_tree.seq3_a k=3 联盟 prob_tree.k3.s15-s16-s17 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17
  - 轮次 prob_tree.s15.split.prob_tree-seq3_a-F1 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 36782d87950704e87889ed6b8d44dde2404f289a31a7065cebe8756f53e3ae4e
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s16.split.prob_tree-seq3_a-F2 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 00b261d8b2243c18f3b321f6ddf97d8c961d601436da9a45f8fdcba8b84b6371
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s17.split.prob_tree-seq3_a-F3 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 3a3b2cb78b67ec569f11bc87aa9b5010e5913ebd6fb08e5207c562fee5cee88d
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 cost_model_identity prob_tree.seq3_b k=3 联盟 prob_tree.k3.s00-s01-s02 成员 prob_tree.s00,prob_tree.s01,prob_tree.s02
  - 轮次 prob_tree.s00.split.prob_tree-seq3_b-F1 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5e792723d578712e83977ba7965e4b8790c82ab597a3fba62cbb40f0e5a32a7a
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s01.split.prob_tree-seq3_b-F2 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8c782ce7ca598b9951a9fba956ac5b6153f954bdadfb76033170c0ba2f48d069
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s02.split.prob_tree-seq3_b-F3 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 1ad089e59bc5785acce7cee0bd0f495ac6c8aee22e4cdc0988f1f61ac95a04dd
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 cost_model_identity prob_tree.seq3_b k=3 联盟 prob_tree.k3.s05-s06-s07 成员 prob_tree.s05,prob_tree.s06,prob_tree.s07
  - 轮次 prob_tree.s05.split.prob_tree-seq3_b-F1 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 040d7588f69959ff303535fd0e9b066a7775bbc55051f8ddc1e5cfa0bc3c2ade
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s06.split.prob_tree-seq3_b-F2 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 3d6a6dd045e9639fafcc81eb703578f88716dce643fad4c4392b0385e6101a49
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s07.split.prob_tree-seq3_b-F3 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 88431968f343d3465cb03fa225b49600d1452415f77d712d6ee2aaea922b3d2e
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 cost_model_identity prob_tree.seq3_b k=3 联盟 prob_tree.k3.s10-s11-s12 成员 prob_tree.s10,prob_tree.s11,prob_tree.s12
  - 轮次 prob_tree.s10.split.prob_tree-seq3_b-F1 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b41edd79ab0b44137f0e70133c38454f584964ba785ee81e34fc63d60024f2cb
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s11.split.prob_tree-seq3_b-F2 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9ed6f0c3b9774c9581020bec6e9b7f9e38ef4e920113b7e2ccba1fd5f72ab258
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s12.split.prob_tree-seq3_b-F3 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d64fa6fb75391c60c67b17d1f58bb642bde89923bdaec8d5f9e6f6fb3add6ded
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 cost_model_identity prob_tree.seq3_b k=3 联盟 prob_tree.k3.s15-s16-s17 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17
  - 轮次 prob_tree.s15.split.prob_tree-seq3_b-F1 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 426adfa1019200a0abb74db295ac4bc371ef64d5e9539382b90a4708e65e82e0
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s16.split.prob_tree-seq3_b-F2 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6882e7a2309315dc425aef8088491ed075a6fa57a08778485e2ee94aab7e59f1
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s17.split.prob_tree-seq3_b-F3 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 74d028d9d64e6c06d6d05474f3795ddebb6ea4f04ea3fd3d8d05055b11a2d20b
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 none prob_tree.diag_a k=3 联盟 prob_tree.k3.s00-s01-s02 成员 prob_tree.s00,prob_tree.s01,prob_tree.s02
  - 轮次 prob_tree.s00.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s01.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 none prob_tree.diag_a k=3 联盟 prob_tree.k3.s05-s06-s07 成员 prob_tree.s05,prob_tree.s06,prob_tree.s07
  - 轮次 prob_tree.s05.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s06.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 none prob_tree.diag_a k=3 联盟 prob_tree.k3.s10-s11-s12 成员 prob_tree.s10,prob_tree.s11,prob_tree.s12
  - 轮次 prob_tree.s10.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s11.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 none prob_tree.diag_a k=3 联盟 prob_tree.k3.s15-s16-s17 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17
  - 轮次 prob_tree.s15.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s16.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 none prob_tree.diag_b k=3 联盟 prob_tree.k3.s00-s01-s02 成员 prob_tree.s00,prob_tree.s01,prob_tree.s02
  - 轮次 prob_tree.s00.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s01.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 none prob_tree.diag_b k=3 联盟 prob_tree.k3.s05-s06-s07 成员 prob_tree.s05,prob_tree.s06,prob_tree.s07
  - 轮次 prob_tree.s05.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s06.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 none prob_tree.diag_b k=3 联盟 prob_tree.k3.s10-s11-s12 成员 prob_tree.s10,prob_tree.s11,prob_tree.s12
  - 轮次 prob_tree.s10.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s11.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 none prob_tree.diag_b k=3 联盟 prob_tree.k3.s15-s16-s17 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17
  - 轮次 prob_tree.s15.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s16.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 none prob_tree.seq3_a k=3 联盟 prob_tree.k3.s00-s01-s02 成员 prob_tree.s00,prob_tree.s01,prob_tree.s02
  - 轮次 prob_tree.s00.split.prob_tree-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s01.split.prob_tree-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s02.split.prob_tree-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 none prob_tree.seq3_a k=3 联盟 prob_tree.k3.s05-s06-s07 成员 prob_tree.s05,prob_tree.s06,prob_tree.s07
  - 轮次 prob_tree.s05.split.prob_tree-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s06.split.prob_tree-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s07.split.prob_tree-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 none prob_tree.seq3_a k=3 联盟 prob_tree.k3.s10-s11-s12 成员 prob_tree.s10,prob_tree.s11,prob_tree.s12
  - 轮次 prob_tree.s10.split.prob_tree-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s11.split.prob_tree-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s12.split.prob_tree-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 none prob_tree.seq3_a k=3 联盟 prob_tree.k3.s15-s16-s17 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17
  - 轮次 prob_tree.s15.split.prob_tree-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s16.split.prob_tree-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s17.split.prob_tree-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 none prob_tree.seq3_b k=3 联盟 prob_tree.k3.s00-s01-s02 成员 prob_tree.s00,prob_tree.s01,prob_tree.s02
  - 轮次 prob_tree.s00.split.prob_tree-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s01.split.prob_tree-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s02.split.prob_tree-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 none prob_tree.seq3_b k=3 联盟 prob_tree.k3.s05-s06-s07 成员 prob_tree.s05,prob_tree.s06,prob_tree.s07
  - 轮次 prob_tree.s05.split.prob_tree-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s06.split.prob_tree-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s07.split.prob_tree-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 none prob_tree.seq3_b k=3 联盟 prob_tree.k3.s10-s11-s12 成员 prob_tree.s10,prob_tree.s11,prob_tree.s12
  - 轮次 prob_tree.s10.split.prob_tree-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s11.split.prob_tree-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s12.split.prob_tree-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 none prob_tree.seq3_b k=3 联盟 prob_tree.k3.s15-s16-s17 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17
  - 轮次 prob_tree.s15.split.prob_tree-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s16.split.prob_tree-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s17.split.prob_tree-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 cost_model_identity prob_tree.seq3_a k=5 联盟 prob_tree.k5.s00-s01-s02-s03-s04 成员 prob_tree.s00,prob_tree.s01,prob_tree.s02,prob_tree.s03,prob_tree.s04
  - 轮次 prob_tree.s00.split.prob_tree-seq3_a-F1 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 1939a5af15601843ad4742f60a166e04d6465ebf47c73d57e327c9e77fc95b31
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s01.split.prob_tree-seq3_a-F2 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f5cd0ca6cba658745ce450fcd31c16e0fc290f7fb7b0e2cd7b3084be15a4ba0a
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s02.split.prob_tree-seq3_a-F3 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 91abbbbc2627f7a4e0df1c2ddc8c27954b2d4c281921240c09a6b40026cb04c4
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 cost_model_identity prob_tree.seq3_a k=5 联盟 prob_tree.k5.s05-s06-s07-s08-s09 成员 prob_tree.s05,prob_tree.s06,prob_tree.s07,prob_tree.s08,prob_tree.s09
  - 轮次 prob_tree.s05.split.prob_tree-seq3_a-F1 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 e76cd3ed40afd9c13f00508425da631621e5bc75e2e0595e5b439dc3cf55e3a8
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s06.split.prob_tree-seq3_a-F2 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d0200bc39d603662f8ebc55a720c12d254370082c6bfb765b150b58400d9fa5d
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s07.split.prob_tree-seq3_a-F3 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9d5404d38396e3ee4083910596c3b5035678b8d008aec9ae6702d3719e153d0b
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 cost_model_identity prob_tree.seq3_a k=5 联盟 prob_tree.k5.s10-s11-s12-s13-s14 成员 prob_tree.s10,prob_tree.s11,prob_tree.s12,prob_tree.s13,prob_tree.s14
  - 轮次 prob_tree.s10.split.prob_tree-seq3_a-F1 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9a71b547ba82b569d50028e4ce2e7b3097247de8f172eb62c03b32aba432b05c
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s11.split.prob_tree-seq3_a-F2 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f48d0dc39d79e93e215a0743424987673e77331dee0c04dcc36e87e7cb9e38a0
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s12.split.prob_tree-seq3_a-F3 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 415d272ed16c75a972fd9a5966231208d221f032d7db9a3692bafcecaed2d8a1
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 cost_model_identity prob_tree.seq3_a k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-seq3_a-F1 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 36782d87950704e87889ed6b8d44dde2404f289a31a7065cebe8756f53e3ae4e
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s16.split.prob_tree-seq3_a-F2 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 00b261d8b2243c18f3b321f6ddf97d8c961d601436da9a45f8fdcba8b84b6371
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s17.split.prob_tree-seq3_a-F3 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 3a3b2cb78b67ec569f11bc87aa9b5010e5913ebd6fb08e5207c562fee5cee88d
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 cost_model_identity prob_tree.seq3_b k=5 联盟 prob_tree.k5.s00-s01-s02-s03-s04 成员 prob_tree.s00,prob_tree.s01,prob_tree.s02,prob_tree.s03,prob_tree.s04
  - 轮次 prob_tree.s00.split.prob_tree-seq3_b-F1 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5e792723d578712e83977ba7965e4b8790c82ab597a3fba62cbb40f0e5a32a7a
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s01.split.prob_tree-seq3_b-F2 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8c782ce7ca598b9951a9fba956ac5b6153f954bdadfb76033170c0ba2f48d069
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s02.split.prob_tree-seq3_b-F3 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 1ad089e59bc5785acce7cee0bd0f495ac6c8aee22e4cdc0988f1f61ac95a04dd
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 cost_model_identity prob_tree.seq3_b k=5 联盟 prob_tree.k5.s05-s06-s07-s08-s09 成员 prob_tree.s05,prob_tree.s06,prob_tree.s07,prob_tree.s08,prob_tree.s09
  - 轮次 prob_tree.s05.split.prob_tree-seq3_b-F1 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 040d7588f69959ff303535fd0e9b066a7775bbc55051f8ddc1e5cfa0bc3c2ade
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s06.split.prob_tree-seq3_b-F2 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 3d6a6dd045e9639fafcc81eb703578f88716dce643fad4c4392b0385e6101a49
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s07.split.prob_tree-seq3_b-F3 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 88431968f343d3465cb03fa225b49600d1452415f77d712d6ee2aaea922b3d2e
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 cost_model_identity prob_tree.seq3_b k=5 联盟 prob_tree.k5.s10-s11-s12-s13-s14 成员 prob_tree.s10,prob_tree.s11,prob_tree.s12,prob_tree.s13,prob_tree.s14
  - 轮次 prob_tree.s10.split.prob_tree-seq3_b-F1 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b41edd79ab0b44137f0e70133c38454f584964ba785ee81e34fc63d60024f2cb
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s11.split.prob_tree-seq3_b-F2 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9ed6f0c3b9774c9581020bec6e9b7f9e38ef4e920113b7e2ccba1fd5f72ab258
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s12.split.prob_tree-seq3_b-F3 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d64fa6fb75391c60c67b17d1f58bb642bde89923bdaec8d5f9e6f6fb3add6ded
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 cost_model_identity prob_tree.seq3_b k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-seq3_b-F1 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 426adfa1019200a0abb74db295ac4bc371ef64d5e9539382b90a4708e65e82e0
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s16.split.prob_tree-seq3_b-F2 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6882e7a2309315dc425aef8088491ed075a6fa57a08778485e2ee94aab7e59f1
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s17.split.prob_tree-seq3_b-F3 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 74d028d9d64e6c06d6d05474f3795ddebb6ea4f04ea3fd3d8d05055b11a2d20b
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 cost_model_identity prob_tree.seq4_a k=5 联盟 prob_tree.k5.s00-s01-s02-s03-s04 成员 prob_tree.s00,prob_tree.s01,prob_tree.s02,prob_tree.s03,prob_tree.s04
  - 轮次 prob_tree.s00.split.prob_tree-seq4_a-F1 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 709f42cce88dae098b80a5f0c5ba383d4c2c024623b48cfb2b6b1033ad72ce14
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F1：读出第一步有几种结果。
  - 轮次 prob_tree.s01.split.prob_tree-seq4_a-F2 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 77223ae337ff1dc7c9e038b7005f166f91eaad593b7cb89bf332bd561ee20d1a
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F2：读出第二步是否受第一步影响。
  - 轮次 prob_tree.s02.split.prob_tree-seq4_a-F3 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 cdf1d173c73d97f099a620ed7dcd549399adafbf4519b8be32f7a0527b6157fa
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F3：写出一条路径的乘法。
  - 轮次 prob_tree.s03.split.prob_tree-seq4_a-F4 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 719db0f400fda3ab7bdbed111d4316f1ad369509f5572927e9c87145c860207d
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F4：把目标路径加总并写成最简分数。
- G1 cost_model_identity prob_tree.seq4_a k=5 联盟 prob_tree.k5.s05-s06-s07-s08-s09 成员 prob_tree.s05,prob_tree.s06,prob_tree.s07,prob_tree.s08,prob_tree.s09
  - 轮次 prob_tree.s05.split.prob_tree-seq4_a-F1 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 85c4d00fc88da3339e6256c01e13d2ac88aa2701bc30efbcc7fefab5f23490bd
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F1：读出第一步有几种结果。
  - 轮次 prob_tree.s06.split.prob_tree-seq4_a-F2 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 77c62e465cf7849a4a21e62106f97f40895d079e8b8d4e739570c392160c15a7
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F2：读出第二步是否受第一步影响。
  - 轮次 prob_tree.s07.split.prob_tree-seq4_a-F3 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a8da106f55e22613fa0e74672b28e20d5773eb9f5ce9d6636d73a661fe05b2a2
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F3：写出一条路径的乘法。
  - 轮次 prob_tree.s08.split.prob_tree-seq4_a-F4 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c6e2edc686e36dd44e9d3ec392e6c2e9b44dcf99b6a9b06f3f57b457d47913c3
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F4：把目标路径加总并写成最简分数。
- G1 cost_model_identity prob_tree.seq4_a k=5 联盟 prob_tree.k5.s10-s11-s12-s13-s14 成员 prob_tree.s10,prob_tree.s11,prob_tree.s12,prob_tree.s13,prob_tree.s14
  - 轮次 prob_tree.s10.split.prob_tree-seq4_a-F1 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6281760eaa5e15fda0552dfebde780cb9d533b87564c4f1424c54ce18ceb024a
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F1：读出第一步有几种结果。
  - 轮次 prob_tree.s11.split.prob_tree-seq4_a-F2 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5249dd44ffd1cf923ffa6e9478ccd5cac6fda9d819ae3783fe878486a9bce695
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F2：读出第二步是否受第一步影响。
  - 轮次 prob_tree.s12.split.prob_tree-seq4_a-F3 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d70d536abae0f788d0e077505a9261a72d93f59d0b6eb62ed63b4a9ac9caa264
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F3：写出一条路径的乘法。
  - 轮次 prob_tree.s13.split.prob_tree-seq4_a-F4 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b0cdf4a176019b6d527ba01cc78665d1243cd899b23752ed1b3611f18a8db867
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F4：把目标路径加总并写成最简分数。
- G1 cost_model_identity prob_tree.seq4_a k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-seq4_a-F1 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 3c644f0dfc162ad78a301c983090c2ecfb9fd65c3a6e724dbce9508c8eb4ef02
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F1：读出第一步有几种结果。
  - 轮次 prob_tree.s16.split.prob_tree-seq4_a-F2 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 065a5feb5df3998f97c9e65785a5f71a0927abddc0873375ee152b1d5ac4bede
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F2：读出第二步是否受第一步影响。
  - 轮次 prob_tree.s17.split.prob_tree-seq4_a-F3 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f180bc6f51e47cf99ac78050102fba5f1981f22415a0992aebdf0720f234bdc0
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F3：写出一条路径的乘法。
  - 轮次 prob_tree.s18.split.prob_tree-seq4_a-F4 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d96f29cf974b49c58e28a0157caf319107c92d38da11b244cc6a1e261506405c
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F4：把目标路径加总并写成最简分数。
- G1 cost_model_identity prob_tree.seq4_b k=5 联盟 prob_tree.k5.s00-s01-s02-s03-s04 成员 prob_tree.s00,prob_tree.s01,prob_tree.s02,prob_tree.s03,prob_tree.s04
  - 轮次 prob_tree.s00.split.prob_tree-seq4_b-F1 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 7ebf21d88151933d8f1c67f5f7e90c4e061f6d3e574e79b984a88799606250d0
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F1：先做有放回的例子。
  - 轮次 prob_tree.s01.split.prob_tree-seq4_b-F2 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 24b9f8a6e4789797e966ef6da82f151b4161b1549c59e4da453c630f2988ae62
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F2：再做不放回，让学生改第二层概率。
  - 轮次 prob_tree.s02.split.prob_tree-seq4_b-F3 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 592803565e7fe7ca654152f2056c4148372003285bb31953b7ba75cc3d40f8b3
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F3：然后比较两个答案。
  - 轮次 prob_tree.s03.split.prob_tree-seq4_b-F4 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 11c4554ba483fddb95794409419e531666882dd94d4c3df2932163aa1c14180e
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F4：最后让学生说出第二层为什么变了。
- G1 cost_model_identity prob_tree.seq4_b k=5 联盟 prob_tree.k5.s05-s06-s07-s08-s09 成员 prob_tree.s05,prob_tree.s06,prob_tree.s07,prob_tree.s08,prob_tree.s09
  - 轮次 prob_tree.s05.split.prob_tree-seq4_b-F1 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 12d40331e8656f64b5a57d994387b71d0a738d8d82e78a2dfbdcc538b37c5159
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F1：先做有放回的例子。
  - 轮次 prob_tree.s06.split.prob_tree-seq4_b-F2 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c0e0f89963bbb932d226f37a1158e409c767012b14c20bb38cb53f870531596a
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F2：再做不放回，让学生改第二层概率。
  - 轮次 prob_tree.s07.split.prob_tree-seq4_b-F3 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2de367664b7a024eaadd1e89d552255f379f383d8813132276d0b29614d11d18
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F3：然后比较两个答案。
  - 轮次 prob_tree.s08.split.prob_tree-seq4_b-F4 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c4a8667171f9eb72211195cb06ef1e14b7b741abbf8553407cc44d25fda239ff
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F4：最后让学生说出第二层为什么变了。
- G1 cost_model_identity prob_tree.seq4_b k=5 联盟 prob_tree.k5.s10-s11-s12-s13-s14 成员 prob_tree.s10,prob_tree.s11,prob_tree.s12,prob_tree.s13,prob_tree.s14
  - 轮次 prob_tree.s10.split.prob_tree-seq4_b-F1 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f2f469263209c5937e58db96048f03748ca7eafe75026cea1fd613da278cc4b2
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F1：先做有放回的例子。
  - 轮次 prob_tree.s11.split.prob_tree-seq4_b-F2 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6a782cad3da7149eed7c80613723d2a92b9cab8e5326d3a3f93f4e781f8bbfe8
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F2：再做不放回，让学生改第二层概率。
  - 轮次 prob_tree.s12.split.prob_tree-seq4_b-F3 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 560fbbfb7c566263eed985c1995d39d86a1419d71d1bff5b276547fa836fd03d
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F3：然后比较两个答案。
  - 轮次 prob_tree.s13.split.prob_tree-seq4_b-F4 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 cb87f0bb94ca7a9147183045c35056fbb9b7de0b717e844049b59ce7f01ff881
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F4：最后让学生说出第二层为什么变了。
- G1 cost_model_identity prob_tree.seq4_b k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-seq4_b-F1 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 24ed92d312402b504d30da21545c76cb1aaad1697aaf162fb4cd5da98449b5a0
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F1：先做有放回的例子。
  - 轮次 prob_tree.s16.split.prob_tree-seq4_b-F2 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ce1936090f1ec5c51f931292fe0ceb12b1fdfffd31f25c85785f7deea97becab
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F2：再做不放回，让学生改第二层概率。
  - 轮次 prob_tree.s17.split.prob_tree-seq4_b-F3 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 87a1a002776212c5ca7ba1b79a04ed4f83eecdf564deac7f3348c9e9d0e615e6
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F3：然后比较两个答案。
  - 轮次 prob_tree.s18.split.prob_tree-seq4_b-F4 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 392d59ac67f23040a0e61114c75fb303c6e6969375530950495b288a434db291
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F4：最后让学生说出第二层为什么变了。
- G1 nemo prob_tree.diag_a k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s16.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 nemo prob_tree.diag_b k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s16.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 nemo prob_tree.seq3_a k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s16.split.prob_tree-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s17.split.prob_tree-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 nemo prob_tree.seq3_b k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s16.split.prob_tree-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s17.split.prob_tree-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 nemo prob_tree.seq4_a k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-seq4_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F1：读出第一步有几种结果。
  - 轮次 prob_tree.s16.split.prob_tree-seq4_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F2：读出第二步是否受第一步影响。
  - 轮次 prob_tree.s17.split.prob_tree-seq4_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F3：写出一条路径的乘法。
  - 轮次 prob_tree.s18.split.prob_tree-seq4_a-F4 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F4：把目标路径加总并写成最简分数。
- G1 nemo prob_tree.seq4_b k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-seq4_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F1：先做有放回的例子。
  - 轮次 prob_tree.s16.split.prob_tree-seq4_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F2：再做不放回，让学生改第二层概率。
  - 轮次 prob_tree.s17.split.prob_tree-seq4_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F3：然后比较两个答案。
  - 轮次 prob_tree.s18.split.prob_tree-seq4_b-F4 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F4：最后让学生说出第二层为什么变了。
- G1 none prob_tree.diag_a k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F1：错因是把同一路径上的分支概率相加。
  - 轮次 prob_tree.s16.split.prob_tree-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_a-F2：干预是在每条边上写乘号，在路径终点才允许相加。
- G1 none prob_tree.diag_b k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F1：错因是漏掉一条目标路径，只算了其中一条。
  - 轮次 prob_tree.s16.split.prob_tree-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-diag_b-F2：干预是先用颜色把所有目标终点圈出，再计算。
- G1 none prob_tree.seq3_a k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-seq3_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s16.split.prob_tree-seq3_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s17.split.prob_tree-seq3_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G1 none prob_tree.seq3_b k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-seq3_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s16.split.prob_tree-seq3_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s17.split.prob_tree-seq3_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G1 none prob_tree.seq4_a k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-seq4_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F1：读出第一步有几种结果。
  - 轮次 prob_tree.s16.split.prob_tree-seq4_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F2：读出第二步是否受第一步影响。
  - 轮次 prob_tree.s17.split.prob_tree-seq4_a-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F3：写出一条路径的乘法。
  - 轮次 prob_tree.s18.split.prob_tree-seq4_a-F4 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F4：把目标路径加总并写成最简分数。
- G1 none prob_tree.seq4_b k=5 联盟 prob_tree.k5.s15-s16-s17-s18-s19 成员 prob_tree.s15,prob_tree.s16,prob_tree.s17,prob_tree.s18,prob_tree.s19
  - 轮次 prob_tree.s15.split.prob_tree-seq4_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F1：先做有放回的例子。
  - 轮次 prob_tree.s16.split.prob_tree-seq4_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F2：再做不放回，让学生改第二层概率。
  - 轮次 prob_tree.s17.split.prob_tree-seq4_b-F3 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F3：然后比较两个答案。
  - 轮次 prob_tree.s18.split.prob_tree-seq4_b-F4 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F4：最后让学生说出第二层为什么变了。
- G1 cost_model_identity quad_vertex.seq3_a k=3 联盟 quad_vertex.k3.s00-s01-s02 成员 quad_vertex.s00,quad_vertex.s01,quad_vertex.s02
  - 轮次 quad_vertex.s00.split.quad_vertex-seq3_a-F1 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 32d742939e409f6d6c93a19df3b900997b5b84fa99f3b18fd46d7056b02044ab
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F1：先由 y=x^2 向右平移两个单位。
  - 轮次 quad_vertex.s01.split.quad_vertex-seq3_a-F2 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9acfef09db636db281f3722d0080a4c735905fa4d1f1cd1c968536b2126b986c
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F2：再向下平移三个单位，点出顶点 (2,-3)。
  - 轮次 quad_vertex.s02.split.quad_vertex-seq3_a-F3 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6db48fffb55279f371601de025e6627a97e6bee50a02533eb0ba58f9513de6c8
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F3：最后用对称轴 x=2 让学生判断一个点的对称点
- G1 cost_model_identity quad_vertex.seq3_a k=3 联盟 quad_vertex.k3.s05-s06-s07 成员 quad_vertex.s05,quad_vertex.s06,quad_vertex.s07
  - 轮次 quad_vertex.s05.split.quad_vertex-seq3_a-F1 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6bfa7b3a980347e8050b01d27f27728bae26ba78026479fba73828eeeeb4ee4b
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F1：先由 y=x^2 向右平移两个单位。
  - 轮次 quad_vertex.s06.split.quad_vertex-seq3_a-F2 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4076d6d4b9e354dbf41964c901dbdac9d51675aced371cb9215533451cf46ce7
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F2：再向下平移三个单位，点出顶点 (2,-3)。
  - 轮次 quad_vertex.s07.split.quad_vertex-seq3_a-F3 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4e951abf0d7f9d2081beca4dc3db806f371a2846b0345afbc0c9cab68ffbea41
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F3：最后用对称轴 x=2 让学生判断一个点的对称点
- G1 cost_model_identity quad_vertex.seq3_a k=3 联盟 quad_vertex.k3.s10-s11-s12 成员 quad_vertex.s10,quad_vertex.s11,quad_vertex.s12
  - 轮次 quad_vertex.s10.split.quad_vertex-seq3_a-F1 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2eb67d3d844052e683d9fad20b08309aedd297219d6e2d7395333fc74f034f7d
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F1：先由 y=x^2 向右平移两个单位。
  - 轮次 quad_vertex.s11.split.quad_vertex-seq3_a-F2 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 db308d25fcfc06a72e8f110a967e6cada1285db043933bab37b587c765b38c0e
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F2：再向下平移三个单位，点出顶点 (2,-3)。
  - 轮次 quad_vertex.s12.split.quad_vertex-seq3_a-F3 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a055c7bfc7b40889e0ff254e1200cd6fb00d15a6bb397f6f5d66f562cc93158d
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F3：最后用对称轴 x=2 让学生判断一个点的对称点
- G1 cost_model_identity quad_vertex.seq3_a k=3 联盟 quad_vertex.k3.s15-s16-s17 成员 quad_vertex.s15,quad_vertex.s16,quad_vertex.s17
  - 轮次 quad_vertex.s15.split.quad_vertex-seq3_a-F1 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 e11ae040e72a607b37c8a0972af04f5f4ca4fb132c84ee49b289b5a90631b002
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F1：先由 y=x^2 向右平移两个单位。
  - 轮次 quad_vertex.s16.split.quad_vertex-seq3_a-F2 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 91d6645828e76f82700aaad990348d62445df7f9a8b77688310caaf01ff3983b
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F2：再向下平移三个单位，点出顶点 (2,-3)。
  - 轮次 quad_vertex.s17.split.quad_vertex-seq3_a-F3 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bfe45dae76a0b7ba38bd14aa5727056c1c12e25c4ecbf2c2c9919e2618ed3eb9
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F3：最后用对称轴 x=2 让学生判断一个点的对称点
- G1 cost_model_identity quad_vertex.seq3_b k=3 联盟 quad_vertex.k3.s00-s01-s02 成员 quad_vertex.s00,quad_vertex.s01,quad_vertex.s02
  - 轮次 quad_vertex.s00.split.quad_vertex-seq3_b-F1 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bddf880ecab461508112ea8afabd16dae3f79e31523d6fe0814ed3e88c7d82a8
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F1：先问开口由 a 决定，先不急着求顶点。
  - 轮次 quad_vertex.s01.split.quad_vertex-seq3_b-F2 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 51654cf45105e30d7d13932dcd903e93e026b73cc38a128ca4ea9e295d9abd71
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F2：再完成配方，把一般式改写成顶点式。
  - 轮次 quad_vertex.s02.split.quad_vertex-seq3_b-F3 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f24730e1be736a09ceddd141a4139d9767272ce9358b5dcd20eb524d35559e65
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F3：最后只改一个系数，让学生说顶点怎么动。
- G1 cost_model_identity quad_vertex.seq3_b k=3 联盟 quad_vertex.k3.s05-s06-s07 成员 quad_vertex.s05,quad_vertex.s06,quad_vertex.s07
  - 轮次 quad_vertex.s05.split.quad_vertex-seq3_b-F1 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ef1289f380e71c20e0724d81a53a93ce3f19550f3a6302beb03712638b89e487
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F1：先问开口由 a 决定，先不急着求顶点。
  - 轮次 quad_vertex.s06.split.quad_vertex-seq3_b-F2 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 92b124361688012ef25ac6091a8f098dde433e1fb3900a78578453eee234c262
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F2：再完成配方，把一般式改写成顶点式。
  - 轮次 quad_vertex.s07.split.quad_vertex-seq3_b-F3 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 300a02757153bf08a263fe564df8998956756f4c1bfc5d9374cb758afc39fff9
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F3：最后只改一个系数，让学生说顶点怎么动。
- G1 cost_model_identity quad_vertex.seq3_b k=3 联盟 quad_vertex.k3.s10-s11-s12 成员 quad_vertex.s10,quad_vertex.s11,quad_vertex.s12
  - 轮次 quad_vertex.s10.split.quad_vertex-seq3_b-F1 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 769ce8468c7ea38f8cee277f3266012bb6bb2c2f7835ad0fc1dea45a2aaff9fd
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F1：先问开口由 a 决定，先不急着求顶点。
  - 轮次 quad_vertex.s11.split.quad_vertex-seq3_b-F2 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c44bf72229eb013e1990aa5f942028aa674ae479cd9969be4c6b9098fbd2d28b
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F2：再完成配方，把一般式改写成顶点式。
  - 轮次 quad_vertex.s12.split.quad_vertex-seq3_b-F3 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c4d81d368333d62fd7a452fd9ae64dd09d0655da8ed1926db70194c97f9a2c5d
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F3：最后只改一个系数，让学生说顶点怎么动。
- G1 cost_model_identity quad_vertex.seq3_b k=3 联盟 quad_vertex.k3.s15-s16-s17 成员 quad_vertex.s15,quad_vertex.s16,quad_vertex.s17
  - 轮次 quad_vertex.s15.split.quad_vertex-seq3_b-F1 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 41b87b88381c1f6b7bc11a7aaec95f944d9d56ec833d0cbe95a7abb5a35c9d06
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F1：先问开口由 a 决定，先不急着求顶点。
  - 轮次 quad_vertex.s16.split.quad_vertex-seq3_b-F2 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 38bb5f4985bb282fc10245474531bb726134f674f65b354ac2b1d4af07a4f988
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F2：再完成配方，把一般式改写成顶点式。
  - 轮次 quad_vertex.s17.split.quad_vertex-seq3_b-F3 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a4244657d92fa13b7b62c2de65746124ac930859e7f983ff7a8c9005544ad7e0
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F3：最后只改一个系数，让学生说顶点怎么动。
- G1 cost_model_identity quad_vertex.seq3_a k=5 联盟 quad_vertex.k5.s00-s01-s02-s03-s04 成员 quad_vertex.s00,quad_vertex.s01,quad_vertex.s02,quad_vertex.s03,quad_vertex.s04
  - 轮次 quad_vertex.s00.split.quad_vertex-seq3_a-F1 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 32d742939e409f6d6c93a19df3b900997b5b84fa99f3b18fd46d7056b02044ab
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F1：先由 y=x^2 向右平移两个单位。
  - 轮次 quad_vertex.s01.split.quad_vertex-seq3_a-F2 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9acfef09db636db281f3722d0080a4c735905fa4d1f1cd1c968536b2126b986c
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F2：再向下平移三个单位，点出顶点 (2,-3)。
  - 轮次 quad_vertex.s02.split.quad_vertex-seq3_a-F3 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6db48fffb55279f371601de025e6627a97e6bee50a02533eb0ba58f9513de6c8
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F3：最后用对称轴 x=2 让学生判断一个点的对称点
- G1 cost_model_identity quad_vertex.seq3_a k=5 联盟 quad_vertex.k5.s05-s06-s07-s08-s09 成员 quad_vertex.s05,quad_vertex.s06,quad_vertex.s07,quad_vertex.s08,quad_vertex.s09
  - 轮次 quad_vertex.s05.split.quad_vertex-seq3_a-F1 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6bfa7b3a980347e8050b01d27f27728bae26ba78026479fba73828eeeeb4ee4b
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F1：先由 y=x^2 向右平移两个单位。
  - 轮次 quad_vertex.s06.split.quad_vertex-seq3_a-F2 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4076d6d4b9e354dbf41964c901dbdac9d51675aced371cb9215533451cf46ce7
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F2：再向下平移三个单位，点出顶点 (2,-3)。
  - 轮次 quad_vertex.s07.split.quad_vertex-seq3_a-F3 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4e951abf0d7f9d2081beca4dc3db806f371a2846b0345afbc0c9cab68ffbea41
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F3：最后用对称轴 x=2 让学生判断一个点的对称点
- G1 cost_model_identity quad_vertex.seq3_a k=5 联盟 quad_vertex.k5.s10-s11-s12-s13-s14 成员 quad_vertex.s10,quad_vertex.s11,quad_vertex.s12,quad_vertex.s13,quad_vertex.s14
  - 轮次 quad_vertex.s10.split.quad_vertex-seq3_a-F1 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2eb67d3d844052e683d9fad20b08309aedd297219d6e2d7395333fc74f034f7d
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F1：先由 y=x^2 向右平移两个单位。
  - 轮次 quad_vertex.s11.split.quad_vertex-seq3_a-F2 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 db308d25fcfc06a72e8f110a967e6cada1285db043933bab37b587c765b38c0e
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F2：再向下平移三个单位，点出顶点 (2,-3)。
  - 轮次 quad_vertex.s12.split.quad_vertex-seq3_a-F3 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a055c7bfc7b40889e0ff254e1200cd6fb00d15a6bb397f6f5d66f562cc93158d
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F3：最后用对称轴 x=2 让学生判断一个点的对称点
- G1 cost_model_identity quad_vertex.seq3_a k=5 联盟 quad_vertex.k5.s15-s16-s17-s18-s19 成员 quad_vertex.s15,quad_vertex.s16,quad_vertex.s17,quad_vertex.s18,quad_vertex.s19
  - 轮次 quad_vertex.s15.split.quad_vertex-seq3_a-F1 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 e11ae040e72a607b37c8a0972af04f5f4ca4fb132c84ee49b289b5a90631b002
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F1：先由 y=x^2 向右平移两个单位。
  - 轮次 quad_vertex.s16.split.quad_vertex-seq3_a-F2 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 91d6645828e76f82700aaad990348d62445df7f9a8b77688310caaf01ff3983b
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F2：再向下平移三个单位，点出顶点 (2,-3)。
  - 轮次 quad_vertex.s17.split.quad_vertex-seq3_a-F3 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bfe45dae76a0b7ba38bd14aa5727056c1c12e25c4ecbf2c2c9919e2618ed3eb9
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F3：最后用对称轴 x=2 让学生判断一个点的对称点
- G1 cost_model_identity quad_vertex.seq3_b k=5 联盟 quad_vertex.k5.s00-s01-s02-s03-s04 成员 quad_vertex.s00,quad_vertex.s01,quad_vertex.s02,quad_vertex.s03,quad_vertex.s04
  - 轮次 quad_vertex.s00.split.quad_vertex-seq3_b-F1 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bddf880ecab461508112ea8afabd16dae3f79e31523d6fe0814ed3e88c7d82a8
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F1：先问开口由 a 决定，先不急着求顶点。
  - 轮次 quad_vertex.s01.split.quad_vertex-seq3_b-F2 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 51654cf45105e30d7d13932dcd903e93e026b73cc38a128ca4ea9e295d9abd71
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F2：再完成配方，把一般式改写成顶点式。
  - 轮次 quad_vertex.s02.split.quad_vertex-seq3_b-F3 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f24730e1be736a09ceddd141a4139d9767272ce9358b5dcd20eb524d35559e65
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F3：最后只改一个系数，让学生说顶点怎么动。
- G1 cost_model_identity quad_vertex.seq3_b k=5 联盟 quad_vertex.k5.s05-s06-s07-s08-s09 成员 quad_vertex.s05,quad_vertex.s06,quad_vertex.s07,quad_vertex.s08,quad_vertex.s09
  - 轮次 quad_vertex.s05.split.quad_vertex-seq3_b-F1 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ef1289f380e71c20e0724d81a53a93ce3f19550f3a6302beb03712638b89e487
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F1：先问开口由 a 决定，先不急着求顶点。
  - 轮次 quad_vertex.s06.split.quad_vertex-seq3_b-F2 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 92b124361688012ef25ac6091a8f098dde433e1fb3900a78578453eee234c262
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F2：再完成配方，把一般式改写成顶点式。
  - 轮次 quad_vertex.s07.split.quad_vertex-seq3_b-F3 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 300a02757153bf08a263fe564df8998956756f4c1bfc5d9374cb758afc39fff9
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F3：最后只改一个系数，让学生说顶点怎么动。
- G1 cost_model_identity quad_vertex.seq3_b k=5 联盟 quad_vertex.k5.s10-s11-s12-s13-s14 成员 quad_vertex.s10,quad_vertex.s11,quad_vertex.s12,quad_vertex.s13,quad_vertex.s14
  - 轮次 quad_vertex.s10.split.quad_vertex-seq3_b-F1 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 769ce8468c7ea38f8cee277f3266012bb6bb2c2f7835ad0fc1dea45a2aaff9fd
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F1：先问开口由 a 决定，先不急着求顶点。
  - 轮次 quad_vertex.s11.split.quad_vertex-seq3_b-F2 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c44bf72229eb013e1990aa5f942028aa674ae479cd9969be4c6b9098fbd2d28b
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F2：再完成配方，把一般式改写成顶点式。
  - 轮次 quad_vertex.s12.split.quad_vertex-seq3_b-F3 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c4d81d368333d62fd7a452fd9ae64dd09d0655da8ed1926db70194c97f9a2c5d
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F3：最后只改一个系数，让学生说顶点怎么动。
- G1 cost_model_identity quad_vertex.seq3_b k=5 联盟 quad_vertex.k5.s15-s16-s17-s18-s19 成员 quad_vertex.s15,quad_vertex.s16,quad_vertex.s17,quad_vertex.s18,quad_vertex.s19
  - 轮次 quad_vertex.s15.split.quad_vertex-seq3_b-F1 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 41b87b88381c1f6b7bc11a7aaec95f944d9d56ec833d0cbe95a7abb5a35c9d06
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F1：先问开口由 a 决定，先不急着求顶点。
  - 轮次 quad_vertex.s16.split.quad_vertex-seq3_b-F2 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 38bb5f4985bb282fc10245474531bb726134f674f65b354ac2b1d4af07a4f988
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F2：再完成配方，把一般式改写成顶点式。
  - 轮次 quad_vertex.s17.split.quad_vertex-seq3_b-F3 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a4244657d92fa13b7b62c2de65746124ac930859e7f983ff7a8c9005544ad7e0
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F3：最后只改一个系数，让学生说顶点怎么动。
- G1 cost_model_identity quad_vertex.seq4_a k=5 联盟 quad_vertex.k5.s00-s01-s02-s03-s04 成员 quad_vertex.s00,quad_vertex.s01,quad_vertex.s02,quad_vertex.s03,quad_vertex.s04
  - 轮次 quad_vertex.s00.split.quad_vertex-seq4_a-F1 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 af6e66c5c5c0daacf465a8aa402f6d8785f6f9de8fc18de661902365164ef149
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F1：第 1 问只辨认 h 和 k。
  - 轮次 quad_vertex.s01.split.quad_vertex-seq4_a-F2 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9ffe055afeb6dfabbc3de421e950c8f8e457eea71a3275cec871ce64f9f183a6
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F2：第 2 问画出对称轴。
  - 轮次 quad_vertex.s02.split.quad_vertex-seq4_a-F3 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8f55692920d9c10d51fb3a8746234461613b2482bc478de33e72f7d5ec5df3f2
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F3：第 3 问说出平移顺序，先左右后上下。
  - 轮次 quad_vertex.s03.split.quad_vertex-seq4_a-F4 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ffe1dfc560284cd7f8a38f846468faeeb869ba118d209d713038381898c6ba79
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F4：第 4 问交换平移顺序，说明结果是否相同。
- G1 cost_model_identity quad_vertex.seq4_a k=5 联盟 quad_vertex.k5.s05-s06-s07-s08-s09 成员 quad_vertex.s05,quad_vertex.s06,quad_vertex.s07,quad_vertex.s08,quad_vertex.s09
  - 轮次 quad_vertex.s05.split.quad_vertex-seq4_a-F1 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 cf08b9f1fdd46f358cdb99573b864b3d9ac3b100fbeb17722fc45dbc6d48171a
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F1：第 1 问只辨认 h 和 k。
  - 轮次 quad_vertex.s06.split.quad_vertex-seq4_a-F2 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 696dfbb73e535b532be35aa4ef4452ff2404833f6db8332745d9461d736c7418
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F2：第 2 问画出对称轴。
  - 轮次 quad_vertex.s07.split.quad_vertex-seq4_a-F3 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 7b4ae1c4af09f3468a00396261658ad550df4ac48217eec17501b55943b1fd0f
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F3：第 3 问说出平移顺序，先左右后上下。
  - 轮次 quad_vertex.s08.split.quad_vertex-seq4_a-F4 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a4dd141220676ea8e59437b820b993998008a3472a64dfd31016b3980b8df618
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F4：第 4 问交换平移顺序，说明结果是否相同。
- G1 cost_model_identity quad_vertex.seq4_a k=5 联盟 quad_vertex.k5.s10-s11-s12-s13-s14 成员 quad_vertex.s10,quad_vertex.s11,quad_vertex.s12,quad_vertex.s13,quad_vertex.s14
  - 轮次 quad_vertex.s10.split.quad_vertex-seq4_a-F1 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 63df782ee81ff49b58cf493b739d9158e8368c399879c5801f2dbe276e0edf6e
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F1：第 1 问只辨认 h 和 k。
  - 轮次 quad_vertex.s11.split.quad_vertex-seq4_a-F2 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 dbf0e7caad971618f03fcb4731e9b3b217d2cffbd869a9b231ce011a67d424b1
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F2：第 2 问画出对称轴。
  - 轮次 quad_vertex.s12.split.quad_vertex-seq4_a-F3 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 60fd6a1aad81c09abca4373ec2ba23585f6a9e564f5d1583f0b85908e232538b
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F3：第 3 问说出平移顺序，先左右后上下。
  - 轮次 quad_vertex.s13.split.quad_vertex-seq4_a-F4 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 58fb10e6cc5421aeaf8b10686a8bab950d7c907e19f7bc14b71790e9cd8aa4d4
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F4：第 4 问交换平移顺序，说明结果是否相同。
- G1 cost_model_identity quad_vertex.seq4_a k=5 联盟 quad_vertex.k5.s15-s16-s17-s18-s19 成员 quad_vertex.s15,quad_vertex.s16,quad_vertex.s17,quad_vertex.s18,quad_vertex.s19
  - 轮次 quad_vertex.s15.split.quad_vertex-seq4_a-F1 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 40cfa9e9ac039105dd0fcb42db78e1c83e164b980ab7f144b46825bf9c4572fb
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F1：第 1 问只辨认 h 和 k。
  - 轮次 quad_vertex.s16.split.quad_vertex-seq4_a-F2 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 05c2a7f03381ef6773a76c4e2ad9660b024900e2990612e1305bc549f6d1b430
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F2：第 2 问画出对称轴。
  - 轮次 quad_vertex.s17.split.quad_vertex-seq4_a-F3 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 dd6ac4442a4d93ea956ccd528f8fe2e85a7a70868fe65fc6bdbc7f073373add1
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F3：第 3 问说出平移顺序，先左右后上下。
  - 轮次 quad_vertex.s18.split.quad_vertex-seq4_a-F4 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0f0d3a4e7ce49629bca90c00ffd6741d5af353872d764c40e84f57fed44afd3b
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F4：第 4 问交换平移顺序，说明结果是否相同。
- G1 cost_model_identity quad_vertex.seq4_b k=5 联盟 quad_vertex.k5.s00-s01-s02-s03-s04 成员 quad_vertex.s00,quad_vertex.s01,quad_vertex.s02,quad_vertex.s03,quad_vertex.s04
  - 轮次 quad_vertex.s00.split.quad_vertex-seq4_b-F1 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8ff3d5b27005e133c68299b6702c74abc9c5a0a9c17cd878237a74c7f77aa909
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F1：板书先写顶点，不写一般式。
  - 轮次 quad_vertex.s01.split.quad_vertex-seq4_b-F2 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 65db198dc6647c5e45ddb6cdd07da648560e82e8932e2194dcbe0d922488751c
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F2：再在顶点两侧各取一个等距点。
  - 轮次 quad_vertex.s02.split.quad_vertex-seq4_b-F3 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 59aa961b0e5d28d29f9e2e592cef956bcd9d4d60c7bf5af27d05888e8eebc228
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F3：然后让学生填对称点的纵坐标。
  - 轮次 quad_vertex.s03.split.quad_vertex-seq4_b-F4 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5518c0f5e9c2dd9f0027ffb5680b50dd5f3d21da5750cbf2f45108fe44517db1
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F4：最后才回到一般式，要求自己配方。
- G1 cost_model_identity quad_vertex.seq4_b k=5 联盟 quad_vertex.k5.s05-s06-s07-s08-s09 成员 quad_vertex.s05,quad_vertex.s06,quad_vertex.s07,quad_vertex.s08,quad_vertex.s09
  - 轮次 quad_vertex.s05.split.quad_vertex-seq4_b-F1 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 71e50f2d94b824736eed83481568acce191ecac922236f4439f1a57ece848a3f
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F1：板书先写顶点，不写一般式。
  - 轮次 quad_vertex.s06.split.quad_vertex-seq4_b-F2 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 beca7f0e33719492f41af929df40a02230c107c9f5beab8bd9c6b19d43096726
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F2：再在顶点两侧各取一个等距点。
  - 轮次 quad_vertex.s07.split.quad_vertex-seq4_b-F3 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 cff304b9ed0e03c10699b7ae7776deb5e4fe156e6577373f4b39a477f18aeab1
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F3：然后让学生填对称点的纵坐标。
  - 轮次 quad_vertex.s08.split.quad_vertex-seq4_b-F4 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 89f8ef5e9f9a0749c7dfd4d11d5dee53faf03e2d8b20ad940ba2bd0842a55fa7
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F4：最后才回到一般式，要求自己配方。
- G1 cost_model_identity quad_vertex.seq4_b k=5 联盟 quad_vertex.k5.s10-s11-s12-s13-s14 成员 quad_vertex.s10,quad_vertex.s11,quad_vertex.s12,quad_vertex.s13,quad_vertex.s14
  - 轮次 quad_vertex.s10.split.quad_vertex-seq4_b-F1 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c5b7834d98647a45432a57374f049d23c36940d6c438db8008853cd522797240
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F1：板书先写顶点，不写一般式。
  - 轮次 quad_vertex.s11.split.quad_vertex-seq4_b-F2 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 384a067dce8a15d8903477c490e79e7ef40502b5ec3d37dfb12c73d9c21e2c55
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F2：再在顶点两侧各取一个等距点。
  - 轮次 quad_vertex.s12.split.quad_vertex-seq4_b-F3 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 136f469595cc2b64e63de229f470da910deb84af560af76c53bc6404e9505aae
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F3：然后让学生填对称点的纵坐标。
  - 轮次 quad_vertex.s13.split.quad_vertex-seq4_b-F4 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 da66971b0e3fa36ebbd90a077411a1eb23a13e60b7580ce12f24e1ba19fadb26
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F4：最后才回到一般式，要求自己配方。
- G1 cost_model_identity quad_vertex.seq4_b k=5 联盟 quad_vertex.k5.s15-s16-s17-s18-s19 成员 quad_vertex.s15,quad_vertex.s16,quad_vertex.s17,quad_vertex.s18,quad_vertex.s19
  - 轮次 quad_vertex.s15.split.quad_vertex-seq4_b-F1 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b8daf2db9a96101b8f34e76565f63ac83f38c7547a184509039a801d4c20c596
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F1：板书先写顶点，不写一般式。
  - 轮次 quad_vertex.s16.split.quad_vertex-seq4_b-F2 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 af49fa655641c887b75b80f12271db41947bbd8d4972402cc347490a41e353ed
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F2：再在顶点两侧各取一个等距点。
  - 轮次 quad_vertex.s17.split.quad_vertex-seq4_b-F3 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6b8f975ee3ea0733ef611201d0334a05851ee9a79414af92ee4ba42999a8fef6
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F3：然后让学生填对称点的纵坐标。
  - 轮次 quad_vertex.s18.split.quad_vertex-seq4_b-F4 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 df0237da563660e1fd91e416144902187236d321ee37b5169b3a34a289d017e1
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F4：最后才回到一般式，要求自己配方。
- G1 nemo recursion.diag_a k=2 联盟 recursion.k2.s00-s01 成员 recursion.s00,recursion.s01
  - 轮次 recursion.s00.split.recursion-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F1：错因是看见加 1 就把它当成等差数列。
  - 轮次 recursion.s01.split.recursion-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F2：干预是先计算前四项，强迫学生看到差不相等。
- G1 nemo recursion.diag_a k=2 联盟 recursion.k2.s05-s06 成员 recursion.s05,recursion.s06
  - 轮次 recursion.s05.split.recursion-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F1：错因是看见加 1 就把它当成等差数列。
  - 轮次 recursion.s06.split.recursion-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F2：干预是先计算前四项，强迫学生看到差不相等。
- G1 nemo recursion.diag_a k=2 联盟 recursion.k2.s10-s11 成员 recursion.s10,recursion.s11
  - 轮次 recursion.s10.split.recursion-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F1：错因是看见加 1 就把它当成等差数列。
  - 轮次 recursion.s11.split.recursion-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F2：干预是先计算前四项，强迫学生看到差不相等。
- G1 nemo recursion.diag_a k=2 联盟 recursion.k2.s15-s16 成员 recursion.s15,recursion.s16
  - 轮次 recursion.s15.split.recursion-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F1：错因是看见加 1 就把它当成等差数列。
  - 轮次 recursion.s16.split.recursion-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F2：干预是先计算前四项，强迫学生看到差不相等。
- G1 nemo recursion.diag_b k=2 联盟 recursion.k2.s00-s01 成员 recursion.s00,recursion.s01
  - 轮次 recursion.s00.split.recursion-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F1：错因是构造新数列时把常数项符号取反。
  - 轮次 recursion.s01.split.recursion-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F2：干预是用 n=1 代入，检查 b_2 是否等于
- G1 nemo recursion.diag_b k=2 联盟 recursion.k2.s05-s06 成员 recursion.s05,recursion.s06
  - 轮次 recursion.s05.split.recursion-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F1：错因是构造新数列时把常数项符号取反。
  - 轮次 recursion.s06.split.recursion-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F2：干预是用 n=1 代入，检查 b_2 是否等于
- G1 nemo recursion.diag_b k=2 联盟 recursion.k2.s10-s11 成员 recursion.s10,recursion.s11
  - 轮次 recursion.s10.split.recursion-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F1：错因是构造新数列时把常数项符号取反。
  - 轮次 recursion.s11.split.recursion-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F2：干预是用 n=1 代入，检查 b_2 是否等于
- G1 nemo recursion.diag_b k=2 联盟 recursion.k2.s15-s16 成员 recursion.s15,recursion.s16
  - 轮次 recursion.s15.split.recursion-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F1：错因是构造新数列时把常数项符号取反。
  - 轮次 recursion.s16.split.recursion-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F2：干预是用 n=1 代入，检查 b_2 是否等于
- G1 none recursion.diag_a k=2 联盟 recursion.k2.s00-s01 成员 recursion.s00,recursion.s01
  - 轮次 recursion.s00.split.recursion-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F1：错因是看见加 1 就把它当成等差数列。
  - 轮次 recursion.s01.split.recursion-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F2：干预是先计算前四项，强迫学生看到差不相等。
- G1 none recursion.diag_a k=2 联盟 recursion.k2.s05-s06 成员 recursion.s05,recursion.s06
  - 轮次 recursion.s05.split.recursion-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F1：错因是看见加 1 就把它当成等差数列。
  - 轮次 recursion.s06.split.recursion-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F2：干预是先计算前四项，强迫学生看到差不相等。
- G1 none recursion.diag_a k=2 联盟 recursion.k2.s10-s11 成员 recursion.s10,recursion.s11
  - 轮次 recursion.s10.split.recursion-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F1：错因是看见加 1 就把它当成等差数列。
  - 轮次 recursion.s11.split.recursion-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F2：干预是先计算前四项，强迫学生看到差不相等。
- G1 none recursion.diag_a k=2 联盟 recursion.k2.s15-s16 成员 recursion.s15,recursion.s16
  - 轮次 recursion.s15.split.recursion-diag_a-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F1：错因是看见加 1 就把它当成等差数列。
  - 轮次 recursion.s16.split.recursion-diag_a-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_a-F2：干预是先计算前四项，强迫学生看到差不相等。
- G1 none recursion.diag_b k=2 联盟 recursion.k2.s00-s01 成员 recursion.s00,recursion.s01
  - 轮次 recursion.s00.split.recursion-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F1：错因是构造新数列时把常数项符号取反。
  - 轮次 recursion.s01.split.recursion-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F2：干预是用 n=1 代入，检查 b_2 是否等于
- G1 none recursion.diag_b k=2 联盟 recursion.k2.s05-s06 成员 recursion.s05,recursion.s06
  - 轮次 recursion.s05.split.recursion-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F1：错因是构造新数列时把常数项符号取反。
  - 轮次 recursion.s06.split.recursion-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F2：干预是用 n=1 代入，检查 b_2 是否等于
- G1 none recursion.diag_b k=2 联盟 recursion.k2.s10-s11 成员 recursion.s10,recursion.s11
  - 轮次 recursion.s10.split.recursion-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F1：错因是构造新数列时把常数项符号取反。
  - 轮次 recursion.s11.split.recursion-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F2：干预是用 n=1 代入，检查 b_2 是否等于
- G1 none recursion.diag_b k=2 联盟 recursion.k2.s15-s16 成员 recursion.s15,recursion.s16
  - 轮次 recursion.s15.split.recursion-diag_b-F1 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F1：错因是构造新数列时把常数项符号取反。
  - 轮次 recursion.s16.split.recursion-diag_b-F2 字段 None 算子 None 基础代价 None 收费 None 累计 None 哈希 None
    片段：不引用讲义编号。讲义步 recursion-diag_b-F2：干预是用 n=1 代入，检查 b_2 是否等于
- G1 cost_model_identity recursion.seq3_a k=3 联盟 recursion.k3.s00-s01-s02 成员 recursion.s00,recursion.s01,recursion.s02
  - 轮次 recursion.s00.split.recursion-seq3_a-F1 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b794adbe794ea327cb6ae020caa9d18f0b3c225a3eb32b769944197ef10d3304
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F1：先写递推，不猜通项。
  - 轮次 recursion.s01.split.recursion-seq3_a-F2 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bea290a9ae2fc3544b11411c9f1a376850cb79c67a6fb4ddcd40b20ec48b47e9
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F2：再计算前四项找差和比。
  - 轮次 recursion.s02.split.recursion-seq3_a-F3 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 54d8725a77fe4823152213462b2d5bbfd409045db1ec850744d4534e9fc17a3d
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F3：最后提出 b_n=a_n+1 并说明为什么。
- G1 cost_model_identity recursion.seq3_a k=3 联盟 recursion.k3.s05-s06-s07 成员 recursion.s05,recursion.s06,recursion.s07
  - 轮次 recursion.s05.split.recursion-seq3_a-F1 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b32644e5b0dc0e947307dbe11be6ddee4f2bbae5ae4802e4e71e42d2ecf94c1e
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F1：先写递推，不猜通项。
  - 轮次 recursion.s06.split.recursion-seq3_a-F2 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 340d14e2a6735659492d917000e280430254227155ca2486fdda8df93014dea0
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F2：再计算前四项找差和比。
  - 轮次 recursion.s07.split.recursion-seq3_a-F3 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 63f8b77b895e7fb1af64a1f8a90d92f7f02367fd5bc15771965db2aafae6212d
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F3：最后提出 b_n=a_n+1 并说明为什么。
- G1 cost_model_identity recursion.seq3_a k=3 联盟 recursion.k3.s10-s11-s12 成员 recursion.s10,recursion.s11,recursion.s12
  - 轮次 recursion.s10.split.recursion-seq3_a-F1 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2991ab2483508f0be2fb0d714a728f1d9cbcd9d6acf26cf9e540d72e106ecf0e
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F1：先写递推，不猜通项。
  - 轮次 recursion.s11.split.recursion-seq3_a-F2 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ca265bb1e0afe15eb0c9690fa721d28c0868d7707bc91dd4f20f524680063559
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F2：再计算前四项找差和比。
  - 轮次 recursion.s12.split.recursion-seq3_a-F3 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f58bf742e3da363a3da84a285aa771225cc2d8c99e8e72bb1591d9ec1795a1ae
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F3：最后提出 b_n=a_n+1 并说明为什么。
- G1 cost_model_identity recursion.seq3_a k=3 联盟 recursion.k3.s15-s16-s17 成员 recursion.s15,recursion.s16,recursion.s17
  - 轮次 recursion.s15.split.recursion-seq3_a-F1 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 31e18711d5b333f3f79d0cb63f4507f29ef2fe75a6577bf447a34412e939f4c3
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F1：先写递推，不猜通项。
  - 轮次 recursion.s16.split.recursion-seq3_a-F2 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0d60c1089b3a94437bdb7905164b226cb4003816a084eee8a127b1aaa21316a9
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F2：再计算前四项找差和比。
  - 轮次 recursion.s17.split.recursion-seq3_a-F3 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 59bb1a90242df2285f965214763e0fbc318c1c07dc1036b6b5847906ed7ea0c3
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F3：最后提出 b_n=a_n+1 并说明为什么。
- G1 cost_model_identity recursion.seq3_b k=3 联盟 recursion.k3.s00-s01-s02 成员 recursion.s00,recursion.s01,recursion.s02
  - 轮次 recursion.s00.split.recursion-seq3_b-F1 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ded4dbc2bf652f553ab0db67958a459076840b2ee29ac50c6cd911872a6d9b91
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F1：先把递推改写成 b_{n+1}=2 b_n。
  - 轮次 recursion.s01.split.recursion-seq3_b-F2 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c897229573ef740e34fc1cf9a49d345aee8589f15c837c704432a764d67f741b
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F2：再写出 b_n 的等比通项。
  - 轮次 recursion.s02.split.recursion-seq3_b-F3 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c95b42c7d6efd26a58c7103155495cccd688918bda16a13766687b928058676e
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F3：最后还原 a_n=b_n-1。
- G1 cost_model_identity recursion.seq3_b k=3 联盟 recursion.k3.s05-s06-s07 成员 recursion.s05,recursion.s06,recursion.s07
  - 轮次 recursion.s05.split.recursion-seq3_b-F1 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 80de4fac9d08172dfcf68c4f50428d1e3d7564a579f16b4850a010f4a1683f32
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F1：先把递推改写成 b_{n+1}=2 b_n。
  - 轮次 recursion.s06.split.recursion-seq3_b-F2 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0ad81b5d708c6eb8a6735c74b94ea5165df0e7c04f94b440980009cd4d0676cc
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F2：再写出 b_n 的等比通项。
  - 轮次 recursion.s07.split.recursion-seq3_b-F3 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9e4d2a6cea9b6c80171ebd92a2f36f1b03e111930a45037ada2053b5b7feb243
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F3：最后还原 a_n=b_n-1。
- G1 cost_model_identity recursion.seq3_b k=3 联盟 recursion.k3.s10-s11-s12 成员 recursion.s10,recursion.s11,recursion.s12
  - 轮次 recursion.s10.split.recursion-seq3_b-F1 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 44e06054ec3a0f87bd0d63db4200e45759f61a4bde90ecf2578977df241a154a
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F1：先把递推改写成 b_{n+1}=2 b_n。
  - 轮次 recursion.s11.split.recursion-seq3_b-F2 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 745be95bce7441cfc731a241fdb87bbfe10fe097fba2fbc4f5d2e7ee2fdecbd6
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F2：再写出 b_n 的等比通项。
  - 轮次 recursion.s12.split.recursion-seq3_b-F3 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4204def967f81feff440ad45b6db50aae07bc73714bdff1493a10e708f4c88ac
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F3：最后还原 a_n=b_n-1。
- G1 cost_model_identity recursion.seq3_b k=3 联盟 recursion.k3.s15-s16-s17 成员 recursion.s15,recursion.s16,recursion.s17
  - 轮次 recursion.s15.split.recursion-seq3_b-F1 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 818fc95124baf1ca1486b0693f8c402edc29112728166c9793b092fd7b97fc86
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F1：先把递推改写成 b_{n+1}=2 b_n。
  - 轮次 recursion.s16.split.recursion-seq3_b-F2 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0b64a4bb1fe4009f3dae5ddb47ca298c43076bda76b01acc22046eadcc6cd5eb
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F2：再写出 b_n 的等比通项。
  - 轮次 recursion.s17.split.recursion-seq3_b-F3 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 1eb0926186c1423d16cb5f21073d68acf3666c0daa994dc301575fea7f3c6703
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F3：最后还原 a_n=b_n-1。
- G1 cost_model_identity recursion.seq3_a k=5 联盟 recursion.k5.s00-s01-s02-s03-s04 成员 recursion.s00,recursion.s01,recursion.s02,recursion.s03,recursion.s04
  - 轮次 recursion.s00.split.recursion-seq3_a-F1 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b794adbe794ea327cb6ae020caa9d18f0b3c225a3eb32b769944197ef10d3304
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F1：先写递推，不猜通项。
  - 轮次 recursion.s01.split.recursion-seq3_a-F2 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bea290a9ae2fc3544b11411c9f1a376850cb79c67a6fb4ddcd40b20ec48b47e9
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F2：再计算前四项找差和比。
  - 轮次 recursion.s02.split.recursion-seq3_a-F3 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 54d8725a77fe4823152213462b2d5bbfd409045db1ec850744d4534e9fc17a3d
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F3：最后提出 b_n=a_n+1 并说明为什么。
- G1 cost_model_identity recursion.seq3_a k=5 联盟 recursion.k5.s05-s06-s07-s08-s09 成员 recursion.s05,recursion.s06,recursion.s07,recursion.s08,recursion.s09
  - 轮次 recursion.s05.split.recursion-seq3_a-F1 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b32644e5b0dc0e947307dbe11be6ddee4f2bbae5ae4802e4e71e42d2ecf94c1e
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F1：先写递推，不猜通项。
  - 轮次 recursion.s06.split.recursion-seq3_a-F2 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 340d14e2a6735659492d917000e280430254227155ca2486fdda8df93014dea0
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F2：再计算前四项找差和比。
  - 轮次 recursion.s07.split.recursion-seq3_a-F3 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 63f8b77b895e7fb1af64a1f8a90d92f7f02367fd5bc15771965db2aafae6212d
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F3：最后提出 b_n=a_n+1 并说明为什么。
- G1 cost_model_identity recursion.seq3_a k=5 联盟 recursion.k5.s10-s11-s12-s13-s14 成员 recursion.s10,recursion.s11,recursion.s12,recursion.s13,recursion.s14
  - 轮次 recursion.s10.split.recursion-seq3_a-F1 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2991ab2483508f0be2fb0d714a728f1d9cbcd9d6acf26cf9e540d72e106ecf0e
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F1：先写递推，不猜通项。
  - 轮次 recursion.s11.split.recursion-seq3_a-F2 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ca265bb1e0afe15eb0c9690fa721d28c0868d7707bc91dd4f20f524680063559
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F2：再计算前四项找差和比。
  - 轮次 recursion.s12.split.recursion-seq3_a-F3 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f58bf742e3da363a3da84a285aa771225cc2d8c99e8e72bb1591d9ec1795a1ae
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F3：最后提出 b_n=a_n+1 并说明为什么。
- G1 cost_model_identity recursion.seq3_a k=5 联盟 recursion.k5.s15-s16-s17-s18-s19 成员 recursion.s15,recursion.s16,recursion.s17,recursion.s18,recursion.s19
  - 轮次 recursion.s15.split.recursion-seq3_a-F1 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 31e18711d5b333f3f79d0cb63f4507f29ef2fe75a6577bf447a34412e939f4c3
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F1：先写递推，不猜通项。
  - 轮次 recursion.s16.split.recursion-seq3_a-F2 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0d60c1089b3a94437bdb7905164b226cb4003816a084eee8a127b1aaa21316a9
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F2：再计算前四项找差和比。
  - 轮次 recursion.s17.split.recursion-seq3_a-F3 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 59bb1a90242df2285f965214763e0fbc318c1c07dc1036b6b5847906ed7ea0c3
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F3：最后提出 b_n=a_n+1 并说明为什么。
- G1 cost_model_identity recursion.seq3_b k=5 联盟 recursion.k5.s00-s01-s02-s03-s04 成员 recursion.s00,recursion.s01,recursion.s02,recursion.s03,recursion.s04
  - 轮次 recursion.s00.split.recursion-seq3_b-F1 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ded4dbc2bf652f553ab0db67958a459076840b2ee29ac50c6cd911872a6d9b91
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F1：先把递推改写成 b_{n+1}=2 b_n。
  - 轮次 recursion.s01.split.recursion-seq3_b-F2 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c897229573ef740e34fc1cf9a49d345aee8589f15c837c704432a764d67f741b
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F2：再写出 b_n 的等比通项。
  - 轮次 recursion.s02.split.recursion-seq3_b-F3 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c95b42c7d6efd26a58c7103155495cccd688918bda16a13766687b928058676e
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F3：最后还原 a_n=b_n-1。
- G1 cost_model_identity recursion.seq3_b k=5 联盟 recursion.k5.s05-s06-s07-s08-s09 成员 recursion.s05,recursion.s06,recursion.s07,recursion.s08,recursion.s09
  - 轮次 recursion.s05.split.recursion-seq3_b-F1 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 80de4fac9d08172dfcf68c4f50428d1e3d7564a579f16b4850a010f4a1683f32
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F1：先把递推改写成 b_{n+1}=2 b_n。
  - 轮次 recursion.s06.split.recursion-seq3_b-F2 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0ad81b5d708c6eb8a6735c74b94ea5165df0e7c04f94b440980009cd4d0676cc
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F2：再写出 b_n 的等比通项。
  - 轮次 recursion.s07.split.recursion-seq3_b-F3 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9e4d2a6cea9b6c80171ebd92a2f36f1b03e111930a45037ada2053b5b7feb243
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F3：最后还原 a_n=b_n-1。
- G1 cost_model_identity recursion.seq3_b k=5 联盟 recursion.k5.s10-s11-s12-s13-s14 成员 recursion.s10,recursion.s11,recursion.s12,recursion.s13,recursion.s14
  - 轮次 recursion.s10.split.recursion-seq3_b-F1 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 44e06054ec3a0f87bd0d63db4200e45759f61a4bde90ecf2578977df241a154a
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F1：先把递推改写成 b_{n+1}=2 b_n。
  - 轮次 recursion.s11.split.recursion-seq3_b-F2 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 745be95bce7441cfc731a241fdb87bbfe10fe097fba2fbc4f5d2e7ee2fdecbd6
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F2：再写出 b_n 的等比通项。
  - 轮次 recursion.s12.split.recursion-seq3_b-F3 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4204def967f81feff440ad45b6db50aae07bc73714bdff1493a10e708f4c88ac
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F3：最后还原 a_n=b_n-1。
- G1 cost_model_identity recursion.seq3_b k=5 联盟 recursion.k5.s15-s16-s17-s18-s19 成员 recursion.s15,recursion.s16,recursion.s17,recursion.s18,recursion.s19
  - 轮次 recursion.s15.split.recursion-seq3_b-F1 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 818fc95124baf1ca1486b0693f8c402edc29112728166c9793b092fd7b97fc86
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F1：先把递推改写成 b_{n+1}=2 b_n。
  - 轮次 recursion.s16.split.recursion-seq3_b-F2 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0b64a4bb1fe4009f3dae5ddb47ca298c43076bda76b01acc22046eadcc6cd5eb
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F2：再写出 b_n 的等比通项。
  - 轮次 recursion.s17.split.recursion-seq3_b-F3 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 1eb0926186c1423d16cb5f21073d68acf3666c0daa994dc301575fea7f3c6703
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F3：最后还原 a_n=b_n-1。
- G1 cost_model_identity recursion.seq4_a k=5 联盟 recursion.k5.s00-s01-s02-s03-s04 成员 recursion.s00,recursion.s01,recursion.s02,recursion.s03,recursion.s04
  - 轮次 recursion.s00.split.recursion-seq4_a-F1 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a0df0beb2a658c26dada5e0136b29e0013502a4319f20f3625d3d7734abd3f42
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F1：问学生差是否恒定。
  - 轮次 recursion.s01.split.recursion-seq4_a-F2 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 7ad577d8d7b59f75a244cabf7e4831710bf57da9db6636a4272cf4fb5f0fcfe9
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F2：问学生相邻项的比是否恒定。
  - 轮次 recursion.s02.split.recursion-seq4_a-F3 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 3a85b5f054b8b05ae6225907436660e37c19e6b3bf1f1bbe82d03bdb33045a35
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F3：给出构造 b_n 的动机。
  - 轮次 recursion.s03.split.recursion-seq4_a-F4 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a638c55c1bd10cd183711356f4d58e55816be72749c28f2807a6f41f656b137d
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F4：要求独立把 a_n 写回去。
- G1 cost_model_identity recursion.seq4_a k=5 联盟 recursion.k5.s05-s06-s07-s08-s09 成员 recursion.s05,recursion.s06,recursion.s07,recursion.s08,recursion.s09
  - 轮次 recursion.s05.split.recursion-seq4_a-F1 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4af48e139122913a41d2e5770e24ac8c6439a9539e6ac06f2c3692a0bc0847a7
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F1：问学生差是否恒定。
  - 轮次 recursion.s06.split.recursion-seq4_a-F2 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4800f5f0631b7b518954916c4e69e641272d79479908dfbe37c5070ad2c866fb
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F2：问学生相邻项的比是否恒定。
  - 轮次 recursion.s07.split.recursion-seq4_a-F3 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 e152dadc9a89926cd5849a0867ca3b48a2cd4add3231acc9c9df25ed156aa1f3
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F3：给出构造 b_n 的动机。
  - 轮次 recursion.s08.split.recursion-seq4_a-F4 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 bb7c440c2c20ce37ddf1f60dcfeb51ba10ca962827b51daaa29ace01290fe2d5
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F4：要求独立把 a_n 写回去。
- G1 cost_model_identity recursion.seq4_a k=5 联盟 recursion.k5.s10-s11-s12-s13-s14 成员 recursion.s10,recursion.s11,recursion.s12,recursion.s13,recursion.s14
  - 轮次 recursion.s10.split.recursion-seq4_a-F1 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 603e904b59dbc470c550842549e0eacd15b37d34e5605ae48fd9c7e054e06a82
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F1：问学生差是否恒定。
  - 轮次 recursion.s11.split.recursion-seq4_a-F2 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c91a5159f758cb1e3564743c73e4c395c7ca60f6788f8fc9b78324ebc55c7b50
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F2：问学生相邻项的比是否恒定。
  - 轮次 recursion.s12.split.recursion-seq4_a-F3 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 99102d12180d86e3e037b9e7c42ffaa2ea4921406e58924a7947dbc850476fa7
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F3：给出构造 b_n 的动机。
  - 轮次 recursion.s13.split.recursion-seq4_a-F4 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 711b70a2ceecb443f62ddd022f2997f3f6349ec006e97f4aebeb0a86cbd68795
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F4：要求独立把 a_n 写回去。
- G1 cost_model_identity recursion.seq4_a k=5 联盟 recursion.k5.s15-s16-s17-s18-s19 成员 recursion.s15,recursion.s16,recursion.s17,recursion.s18,recursion.s19
  - 轮次 recursion.s15.split.recursion-seq4_a-F1 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5643f81cdc2bf82a2c67d0ce6583270b1b2bb87d7f34f5dc33960beba426467d
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F1：问学生差是否恒定。
  - 轮次 recursion.s16.split.recursion-seq4_a-F2 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ac3a27f0bdd5b67ce3169f363c506b004cc152ac6a00418584f9a6c5ff3f3fdb
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F2：问学生相邻项的比是否恒定。
  - 轮次 recursion.s17.split.recursion-seq4_a-F3 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 984cf9422372a6a0a0bd04e8c7145d866d21b0c1fecebdaf256a68f11370181a
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F3：给出构造 b_n 的动机。
  - 轮次 recursion.s18.split.recursion-seq4_a-F4 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 be7a4bfb69d1469e6e6dc31e6ff662b122de6ec73c8b0edf52169b5557b32432
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F4：要求独立把 a_n 写回去。
- G1 cost_model_identity recursion.seq4_b k=5 联盟 recursion.k5.s00-s01-s02-s03-s04 成员 recursion.s00,recursion.s01,recursion.s02,recursion.s03,recursion.s04
  - 轮次 recursion.s00.split.recursion-seq4_b-F1 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8dd12d23de9fa99110f7c26e1a9610690d24a79666010b34e6dbb266d8a9c3f1
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F1：先用具体首项 a_1=1 算。
  - 轮次 recursion.s01.split.recursion-seq4_b-F2 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c38a0dc8bff4a343f6ccb78a865c3c3b7272192990823d00b19037b75f988e65
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F2：再换成 a_1=3，看构造是否还在。
  - 轮次 recursion.s02.split.recursion-seq4_b-F3 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5b0059fdb487eabf358c563ccbd6ac9e5836e348f64170d1b0a6528f23a41bab
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F3：然后抽象首项。
  - 轮次 recursion.s03.split.recursion-seq4_b-F4 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 233922a9f11cd4700426c6a270ab32e616b73047197f7bbc83951047d040e6ae
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F4：最后才写求和或简单应用。
- G1 cost_model_identity recursion.seq4_b k=5 联盟 recursion.k5.s05-s06-s07-s08-s09 成员 recursion.s05,recursion.s06,recursion.s07,recursion.s08,recursion.s09
  - 轮次 recursion.s05.split.recursion-seq4_b-F1 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 82023e00c376d646c8ea2018514d4f0354307e7478c9a0fad7ab668abb308331
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F1：先用具体首项 a_1=1 算。
  - 轮次 recursion.s06.split.recursion-seq4_b-F2 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 83a1297b8bd6042a11eeb9283b905c8a14fb0f015fb02f18ee2a1a96dad6fe7c
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F2：再换成 a_1=3，看构造是否还在。
  - 轮次 recursion.s07.split.recursion-seq4_b-F3 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 443ac87e5d8db4d3caf47cd76452bca6ba763070a30d1f1c6f6b01e0179e8e2f
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F3：然后抽象首项。
  - 轮次 recursion.s08.split.recursion-seq4_b-F4 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 100a4395606eb122962c71a2b2a193075543618395d564df6609172b7f799198
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F4：最后才写求和或简单应用。
- G1 cost_model_identity recursion.seq4_b k=5 联盟 recursion.k5.s10-s11-s12-s13-s14 成员 recursion.s10,recursion.s11,recursion.s12,recursion.s13,recursion.s14
  - 轮次 recursion.s10.split.recursion-seq4_b-F1 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4b57e0ab655e3c9fc5e85663a2101073c6c1a359b016da20b7f500246ef16dac
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F1：先用具体首项 a_1=1 算。
  - 轮次 recursion.s11.split.recursion-seq4_b-F2 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 e906e312a2861f662599856dfe71430dd36dcfe0c1a8f07ae4683b073d4a47f0
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F2：再换成 a_1=3，看构造是否还在。
  - 轮次 recursion.s12.split.recursion-seq4_b-F3 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ac50a15ed6a08411a2ccd1c5a966ecad262e2105f58dd61b3ed8215935c331db
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F3：然后抽象首项。
  - 轮次 recursion.s13.split.recursion-seq4_b-F4 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c01211c1d6a715f58070332166377dd5cdd8b1ac7cc80ccdbb6d14c7ccf91f7c
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F4：最后才写求和或简单应用。
- G1 cost_model_identity recursion.seq4_b k=5 联盟 recursion.k5.s15-s16-s17-s18-s19 成员 recursion.s15,recursion.s16,recursion.s17,recursion.s18,recursion.s19
  - 轮次 recursion.s15.split.recursion-seq4_b-F1 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 294f678dfbbca029c6cb6312299cdb7ea9d9cfc3a7b3fa135c6d2cd4783862b0
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F1：先用具体首项 a_1=1 算。
  - 轮次 recursion.s16.split.recursion-seq4_b-F2 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 edd39814e7a1bf9c7df1501fa612886eb75fd863c65e66ef4dcd866e196d4fbe
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F2：再换成 a_1=3，看构造是否还在。
  - 轮次 recursion.s17.split.recursion-seq4_b-F3 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 24389f6c8343864629699fc3e48a13c77ed01a6b931be5bb0a7320451233abe3
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F3：然后抽象首项。
  - 轮次 recursion.s18.split.recursion-seq4_b-F4 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 295470d0182affac069208bc3e9b1af4dff124b45946c6d9ea41ba9360e8fa8e
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F4：最后才写求和或简单应用。
- G2 cost_model_identity congruence.seq3_a k=1 联盟 congruence.g2.s14 成员 congruence.s14
  - 轮次 congruence.s14.collector.congruence-seq3_a-F1 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 454a63754f2345cf8c92a2cfc6164764458d434ae5a2526bcb8de0b81a05194e
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F1：先标出已知的两边。
  - 轮次 congruence.s14.collector.congruence-seq3_a-F2 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0999a4a14134b1ce07921c668ce1816c84864c0fba82235fb9ec8817d2464549
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F2：再标出这两边的夹角。
  - 轮次 congruence.s14.collector.congruence-seq3_a-F3 字段 congruence.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 0c3e7ccf669295f1fe3e1d847602afa67b264cabe7da613ff33d794336823fd7
    片段：不引用讲义编号。讲义步 congruence-seq3_a-F3：最后按 SAS 写出对应顶点。
- G2 cost_model_identity congruence.seq3_b k=1 联盟 congruence.g2.s14 成员 congruence.s14
  - 轮次 congruence.s14.collector.congruence-seq3_b-F1 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4f2551706cb18d98aea1bb40d0467a84b0653337f6608bf14067be42bc5d8dc4
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F1：先从图形里找公共边。
  - 轮次 congruence.s14.collector.congruence-seq3_b-F2 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 880ef870b7cd478fd58a320377a66eb0be4600976042784bfe4d6d548b1f239e
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F2：再找对顶角或公共角。
  - 轮次 congruence.s14.collector.congruence-seq3_b-F3 字段 congruence.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 554df2fcc8416b14667bacb57604421d7593ee7bdc2037862572330504a6976c
    片段：不引用讲义编号。讲义步 congruence-seq3_b-F3：最后选择 SAS 或 ASA，并说明为什么不是
- G2 cost_model_identity congruence.seq4_a k=1 联盟 congruence.g2.s19 成员 congruence.s19
  - 轮次 congruence.s19.collector.congruence-seq4_a-F1 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 424b305bedc5d146419f1d42dcf4f5636079891faa1b3908e66ffc115d5c4cc5
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F1：抄写已知，不添加辅助线。
  - 轮次 congruence.s19.collector.congruence-seq4_a-F2 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9425b590a171099a77257d59edb5806e4ea5fae990b5590370d2385a88d10a0c
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F2：指出要证明的对应关系。
  - 轮次 congruence.s19.collector.congruence-seq4_a-F3 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 3cde6adc1f944c7c7c9d0cc307c5d41e1424a17bd514f1dcb65b56edb1f36ff2
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F3：列出三组条件。
  - 轮次 congruence.s19.collector.congruence-seq4_a-F4 字段 congruence.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 727bc4e9465a393073215a886a550152380accd9d7667cc3e912553e39a47afc
    片段：不引用讲义编号。讲义步 congruence-seq4_a-F4：写出判定和对应顶点顺序。
- G2 cost_model_identity congruence.seq4_b k=1 联盟 congruence.g2.s19 成员 congruence.s19
  - 轮次 congruence.s19.collector.congruence-seq4_b-F1 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ce2658bcf36aa0e3f6f837f1cc5a312f414a33e00c6611755efa999ae090cd18
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F1：先让学生口头说判定名称。
  - 轮次 congruence.s19.collector.congruence-seq4_b-F2 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 20d9ec2ea8e11c9b80610975c454de6a494e389a3b1129bd3dbb136327f22eec
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F2：再要求指出夹角。
  - 轮次 congruence.s19.collector.congruence-seq4_b-F3 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 50a5d09c89f82ce176649a21c01630633a49377aae797b914eab87d12b75bd9b
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F3：然后写对应边。
  - 轮次 congruence.s19.collector.congruence-seq4_b-F4 字段 congruence.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f39dbf4731b1d829ec7de375ce2a7184e6aef675b1b34058b9ca464db2da77e0
    片段：不引用讲义编号。讲义步 congruence-seq4_b-F4：最后交换顶点顺序，检查是否仍然成立。
- G2 cost_model_identity linear_eq.seq3_a k=1 联盟 linear_eq.g2.s14 成员 linear_eq.s14
  - 轮次 linear_eq.s14.collector.linear_eq-seq3_a-F1 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2fa8ee15d4169cb5e952ffae3fbb61bc0a806fcce412d5df90b515eecce92935
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F1：先合并同类项，不先除系数。
  - 轮次 linear_eq.s14.collector.linear_eq-seq3_a-F2 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 7110a2a7e6914e903aef16f25c8aa6171c91c37ac5c9bb5fdd91c47f447e9769
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F2：再把常数项移到另一边并变号。
  - 轮次 linear_eq.s14.collector.linear_eq-seq3_a-F3 字段 linear_eq.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 becf3e3166b13f0bcf82618afdf2a4f7480805a09d17359cf9e46c650fd377fd
    片段：不引用讲义编号。讲义步 linear_eq-seq3_a-F3：最后把未知数系数化为 1。
- G2 cost_model_identity linear_eq.seq3_b k=1 联盟 linear_eq.g2.s14 成员 linear_eq.s14
  - 轮次 linear_eq.s14.collector.linear_eq-seq3_b-F1 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 70236f9e0ac7b63fb565b2c400720b0ac2223f02bec03d4f2e1e820f94488d2d
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F1：先去分母，写明同乘的数。
  - 轮次 linear_eq.s14.collector.linear_eq-seq3_b-F2 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 cd8617c757a442cd55456ebc0055cfacb6b451b7a0878e121336de5b12398556
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F2：再去括号，分配律逐项做。
  - 轮次 linear_eq.s14.collector.linear_eq-seq3_b-F3 字段 linear_eq.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 aeb26ba190617ed6abf8b16b71c3e6fa46e2f9d91d7555a7b640d36b491a7bab
    片段：不引用讲义编号。讲义步 linear_eq-seq3_b-F3：最后才移项合并。
- G2 cost_model_identity linear_eq.seq4_a k=1 联盟 linear_eq.g2.s19 成员 linear_eq.s19
  - 轮次 linear_eq.s19.collector.linear_eq-seq4_a-F1 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b7ecc21850e975cfbb5fa69b2bbd60def0c8df18d79cbf76b6a46630d5ddf33c
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F1：读题时先标出等号两边。
  - 轮次 linear_eq.s19.collector.linear_eq-seq4_a-F2 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 47ed3316ded688c69cd0414648d28b46ee09de2ce4701db878f4a4e1e5a6b068
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F2：去分母后逐项检查有没有漏乘。
  - 轮次 linear_eq.s19.collector.linear_eq-seq4_a-F3 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8f296ed74e9f858a43e81518e1c02f3d4dab56dc7dddb170e54dee517651d1dd
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F3：移项时只动一项，并立刻变号。
  - 轮次 linear_eq.s19.collector.linear_eq-seq4_a-F4 字段 linear_eq.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4751e2e163edcfeda5c5e801dce6989af34f1a6174d921ae353d56c4e11ca1f3
    片段：不引用讲义编号。讲义步 linear_eq-seq4_a-F4：写出解以后代回原方程检验。
- G2 cost_model_identity linear_eq.seq4_b k=1 联盟 linear_eq.g2.s19 成员 linear_eq.s19
  - 轮次 linear_eq.s19.collector.linear_eq-seq4_b-F1 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4b0358b435985a6f265743d790b7034d867e834a5eb4f239488bd3fe03e72d85
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F1：例题先讲整数系数。
  - 轮次 linear_eq.s19.collector.linear_eq-seq4_b-F2 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c9677e46bfdf19e1e0fb3c587c5ab6f473896d4637db3b9b776efdc86d7a9e13
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F2：变式改成带分数。
  - 轮次 linear_eq.s19.collector.linear_eq-seq4_b-F3 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 697919fb530f076f46a67f0829e343391d196db3e041796e04b5bd4007060a43
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F3：再改成含括号。
  - 轮次 linear_eq.s19.collector.linear_eq-seq4_b-F4 字段 linear_eq.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 45afb478759bab82b5addeb86291cfd8054123a13edec29d943503069f05d1fe
    片段：不引用讲义编号。讲义步 linear_eq-seq4_b-F4：最后让学生自己出一道并写出检验。
- G2 cost_model_identity prob_tree.seq3_a k=1 联盟 prob_tree.g2.s14 成员 prob_tree.s14
  - 轮次 prob_tree.s14.collector.prob_tree-seq3_a-F1 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a947dc87a5258e089ff457b32650f16683e3b025724180166281290452f61b4e
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F1：先画第一层分支，并在边上写概率。
  - 轮次 prob_tree.s14.collector.prob_tree-seq3_a-F2 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 715d954c2ee4468620b95e218caff636a08c28e112e5b9f375d5da2be8a76576
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F2：再画第二层，检查每一层的概率和是否为 1。
  - 轮次 prob_tree.s14.collector.prob_tree-seq3_a-F3 字段 prob_tree.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c2f46d0c158219f9e920dfb2fe86057b2ac7cd6ccc3c1b59cf33821b99d7f152
    片段：不引用讲义编号。讲义步 prob_tree-seq3_a-F3：最后沿路径相乘，合并目标路径。
- G2 cost_model_identity prob_tree.seq3_b k=1 联盟 prob_tree.g2.s14 成员 prob_tree.s14
  - 轮次 prob_tree.s14.collector.prob_tree-seq3_b-F1 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5f8c6e900387e537e2ab2c26bec8c9db35128cd8c28796b3fa4b2a95a25b0d33
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F1：先用文字列出两步试验。
  - 轮次 prob_tree.s14.collector.prob_tree-seq3_b-F2 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d7fca1165904301fecbfed6844cf11d521bee9d387ae32fe26c4594b3d0da312
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F2：再把文字翻译成树。
  - 轮次 prob_tree.s14.collector.prob_tree-seq3_b-F3 字段 prob_tree.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 20d5de59ea00c4cab552585de5b7ac027524a79b3e40c8367e1ef397213a5c41
    片段：不引用讲义编号。讲义步 prob_tree-seq3_b-F3：最后只计算题目要的终点，不计算全部终点。
- G2 cost_model_identity prob_tree.seq4_a k=1 联盟 prob_tree.g2.s19 成员 prob_tree.s19
  - 轮次 prob_tree.s19.collector.prob_tree-seq4_a-F1 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9ee121d390a9e4b715cef3ca5736558eab218c538c252112fb1817b2fa835d99
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F1：读出第一步有几种结果。
  - 轮次 prob_tree.s19.collector.prob_tree-seq4_a-F2 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 42f8cefcc556089c295229d524a90fc878563bb44a20d1c40b7a9ec7d5ceac0c
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F2：读出第二步是否受第一步影响。
  - 轮次 prob_tree.s19.collector.prob_tree-seq4_a-F3 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 723ea77731a063452908a364bd648f8cd4126621087642530a07ab5c7716aa23
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F3：写出一条路径的乘法。
  - 轮次 prob_tree.s19.collector.prob_tree-seq4_a-F4 字段 prob_tree.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 92be55af8781a0ea924df2f8ed6638ada7db9d1430e837852315985b0ad4e1b6
    片段：不引用讲义编号。讲义步 prob_tree-seq4_a-F4：把目标路径加总并写成最简分数。
- G2 cost_model_identity prob_tree.seq4_b k=1 联盟 prob_tree.g2.s19 成员 prob_tree.s19
  - 轮次 prob_tree.s19.collector.prob_tree-seq4_b-F1 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a2b14fa65d0d42f4f5a38a61980498f0c47c99e6986ea3ab2410971a05e0bbb0
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F1：先做有放回的例子。
  - 轮次 prob_tree.s19.collector.prob_tree-seq4_b-F2 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c80b7e3f1991036dee7c2b618ff251c2f40c7f6ec0cb1a3f8bf189ee06a5accb
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F2：再做不放回，让学生改第二层概率。
  - 轮次 prob_tree.s19.collector.prob_tree-seq4_b-F3 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 923d1543018d6f873fd66d9b4ea3f68a311d5b9b89135068096c66ed75ce2f9e
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F3：然后比较两个答案。
  - 轮次 prob_tree.s19.collector.prob_tree-seq4_b-F4 字段 prob_tree.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9ea25d0a9b1ad960aaa23421ffe6534f59929d874c9f122555e72a4c5846a40c
    片段：不引用讲义编号。讲义步 prob_tree-seq4_b-F4：最后让学生说出第二层为什么变了。
- G2 cost_model_identity quad_vertex.seq3_a k=1 联盟 quad_vertex.g2.s14 成员 quad_vertex.s14
  - 轮次 quad_vertex.s14.collector.quad_vertex-seq3_a-F1 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 57925b3597c394dc16250cb25c547756d14fa209c11c111a2446882bbda41729
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F1：先由 y=x^2 向右平移两个单位。
  - 轮次 quad_vertex.s14.collector.quad_vertex-seq3_a-F2 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2db78444eb33d9f900682f4730cc2971d00cf36dc307fb28d45480990049ce02
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F2：再向下平移三个单位，点出顶点 (2,-3)。
  - 轮次 quad_vertex.s14.collector.quad_vertex-seq3_a-F3 字段 quad_vertex.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 ed5e2032847d9089f6ce7fca532aa507d298b25096cad26b66cad00185346278
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_a-F3：最后用对称轴 x=2 让学生判断一个点的对称点
- G2 cost_model_identity quad_vertex.seq3_b k=1 联盟 quad_vertex.g2.s14 成员 quad_vertex.s14
  - 轮次 quad_vertex.s14.collector.quad_vertex-seq3_b-F1 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 1ce5642ecc8f138f4422caffac98ea7e41216814102723530556f341daf61729
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F1：先问开口由 a 决定，先不急着求顶点。
  - 轮次 quad_vertex.s14.collector.quad_vertex-seq3_b-F2 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9e7c60244cd9b5d61b09f9398ae294f7934fb02fc3ed55bbdf9ff3e546c76ae9
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F2：再完成配方，把一般式改写成顶点式。
  - 轮次 quad_vertex.s14.collector.quad_vertex-seq3_b-F3 字段 quad_vertex.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2d00c70dacdd2caecd4afda31d87b8712a8d864a904bb8b85bfbdbc366307688
    片段：不引用讲义编号。讲义步 quad_vertex-seq3_b-F3：最后只改一个系数，让学生说顶点怎么动。
- G2 cost_model_identity quad_vertex.seq4_a k=1 联盟 quad_vertex.g2.s19 成员 quad_vertex.s19
  - 轮次 quad_vertex.s19.collector.quad_vertex-seq4_a-F1 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 6e20cfdb580a40f3de47899717623a029ab131472ea8ef519f137b90fb003ee3
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F1：第 1 问只辨认 h 和 k。
  - 轮次 quad_vertex.s19.collector.quad_vertex-seq4_a-F2 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 010cf5341da127cff5e37bea8a80fcbca5bff2eb55662c3eeb5f1182da1d4ca9
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F2：第 2 问画出对称轴。
  - 轮次 quad_vertex.s19.collector.quad_vertex-seq4_a-F3 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8a82957055149581ec1888ab4d6fb7ba19a01acf1f33280e1ce3a20a1a78ab00
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F3：第 3 问说出平移顺序，先左右后上下。
  - 轮次 quad_vertex.s19.collector.quad_vertex-seq4_a-F4 字段 quad_vertex.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 7366e0b4c547d109da73d71aac1453ba3052cbfd081d226c5f01d535116b32e5
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_a-F4：第 4 问交换平移顺序，说明结果是否相同。
- G2 cost_model_identity quad_vertex.seq4_b k=1 联盟 quad_vertex.g2.s19 成员 quad_vertex.s19
  - 轮次 quad_vertex.s19.collector.quad_vertex-seq4_b-F1 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b87df4036cd856bddee0aea9bc235e11b840f61ffaf6238bb26228b2e124df53
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F1：板书先写顶点，不写一般式。
  - 轮次 quad_vertex.s19.collector.quad_vertex-seq4_b-F2 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8c9be86c32a09cc6362d3d805afa82ca12b0007df1eb1f4ad642acb8965537dd
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F2：再在顶点两侧各取一个等距点。
  - 轮次 quad_vertex.s19.collector.quad_vertex-seq4_b-F3 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 20c3cacf4548be3aba809816ee24b9b6d8a0d868fa70acf74b3e435d531394ab
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F3：然后让学生填对称点的纵坐标。
  - 轮次 quad_vertex.s19.collector.quad_vertex-seq4_b-F4 字段 quad_vertex.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 002893ad0a291b8fcf88eb3b513c3f292f612c2b3afa495092b690d54a8abe18
    片段：不引用讲义编号。讲义步 quad_vertex-seq4_b-F4：最后才回到一般式，要求自己配方。
- G2 cost_model_identity recursion.seq3_a k=1 联盟 recursion.g2.s14 成员 recursion.s14
  - 轮次 recursion.s14.collector.recursion-seq3_a-F1 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 85a143981b2855ec4205c1c9106a858d280956dea3b5c886260698ed4b421d53
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F1：先写递推，不猜通项。
  - 轮次 recursion.s14.collector.recursion-seq3_a-F2 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 304a6c916dc4bcc79cb355d0b64f7a654258977e9ecd959653bb927d5f422881
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F2：再计算前四项找差和比。
  - 轮次 recursion.s14.collector.recursion-seq3_a-F3 字段 recursion.seq3_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 939ce66b0630a056be6394c54814ba397c16f1b12e69265a08188d021ee22ca3
    片段：不引用讲义编号。讲义步 recursion-seq3_a-F3：最后提出 b_n=a_n+1 并说明为什么。
- G2 cost_model_identity recursion.seq3_b k=1 联盟 recursion.g2.s14 成员 recursion.s14
  - 轮次 recursion.s14.collector.recursion-seq3_b-F1 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a40fa552878ffa6589d24cf2dcf9da34c481b5aba68eee1ea431f9030283374f
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F1：先把递推改写成 b_{n+1}=2 b_n。
  - 轮次 recursion.s14.collector.recursion-seq3_b-F2 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 e917769b4e93ed852cdd1bc81217fce12a4b3f9d492fe4c757130db70a2e2627
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F2：再写出 b_n 的等比通项。
  - 轮次 recursion.s14.collector.recursion-seq3_b-F3 字段 recursion.seq3_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 7bd7d587b222a9717a99629c542b3c4f3cf85c568772ee72ee8363d3232c6acb
    片段：不引用讲义编号。讲义步 recursion-seq3_b-F3：最后还原 a_n=b_n-1。
- G2 cost_model_identity recursion.seq4_a k=1 联盟 recursion.g2.s19 成员 recursion.s19
  - 轮次 recursion.s19.collector.recursion-seq4_a-F1 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c95e54eed607587db323cdec58792db7c1359dc86014bcf7f718c95a9e5a3da7
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F1：问学生差是否恒定。
  - 轮次 recursion.s19.collector.recursion-seq4_a-F2 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5fde1db245e365520ae0410a93b57da482e51900da62d4f534b603e365ce74ac
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F2：问学生相邻项的比是否恒定。
  - 轮次 recursion.s19.collector.recursion-seq4_a-F3 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 365e7f9982277577d8afa41c1d84beff65fa586d71cfc8d60ee75b60e75d435d
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F3：给出构造 b_n 的动机。
  - 轮次 recursion.s19.collector.recursion-seq4_a-F4 字段 recursion.seq4_a 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d1031f6a9b5eb4eff48f37076515dbdfb517f284c97da1005de8de4341518051
    片段：不引用讲义编号。讲义步 recursion-seq4_a-F4：要求独立把 a_n 写回去。
- G2 cost_model_identity recursion.seq4_b k=1 联盟 recursion.g2.s19 成员 recursion.s19
  - 轮次 recursion.s19.collector.recursion-seq4_b-F1 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8b756560fabb17637bb79cd937bdff627c9051f6f093845017a0d43f410aadd7
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F1：先用具体首项 a_1=1 算。
  - 轮次 recursion.s19.collector.recursion-seq4_b-F2 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 1dbf2d0d0546413722ef208f5f04b70386ec75f4e430be7c1cf5388eeec41ee3
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F2：再换成 a_1=3，看构造是否还在。
  - 轮次 recursion.s19.collector.recursion-seq4_b-F3 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 c045dd5a0fec60bf55bbcdfbddb31c426d4608b24453868c4c63f1320b33b7d7
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F3：然后抽象首项。
  - 轮次 recursion.s19.collector.recursion-seq4_b-F4 字段 recursion.seq4_b 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8267554563210591953123efee27b9c142bdc75dafe7be89d2d9e3acd4abfa45
    片段：不引用讲义编号。讲义步 recursion-seq4_b-F4：最后才写求和或简单应用。
- G3 ocelot_minus quad_vertex.ped_a k=1 联盟 None 成员 quad_vertex.s00
  - 轮次 quad_vertex.s00.split.quad_vertex-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 8265bdcc83007d66ba07e4df67f3e40f4654520a5db742d702103ac724b91fcd
    片段：不引用讲义编号。讲义步 quad_vertex-ped_a-F1：教学方法是先盖住解析式，只让学生看平移箭头，再
- G3 ocelot_minus quad_vertex.ped_b k=1 联盟 None 成员 quad_vertex.s00
  - 轮次 quad_vertex.s00.split.quad_vertex-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f39c56a20911808df4242a17deb59c35696a5b326e6ca110b6a8f1efef455cb8
    片段：不引用讲义编号。讲义步 quad_vertex-ped_b-F1：教学方法是把左右平移和上下平移分成两张卡片，禁
- G3 ocelot_minus quad_vertex.ped_a k=1 联盟 None 成员 quad_vertex.s05
  - 轮次 quad_vertex.s05.split.quad_vertex-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4b85a71ee61e5a1c80c7db52455ae3ba082a49db29fc535f541368310679ce29
    片段：不引用讲义编号。讲义步 quad_vertex-ped_a-F1：教学方法是先盖住解析式，只让学生看平移箭头，再
- G3 ocelot_minus quad_vertex.ped_b k=1 联盟 None 成员 quad_vertex.s05
  - 轮次 quad_vertex.s05.split.quad_vertex-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9ca15a60ee668b47e17ed86ede5a91e02bd4762c0a451b5d88e8663d58a5ceeb
    片段：不引用讲义编号。讲义步 quad_vertex-ped_b-F1：教学方法是把左右平移和上下平移分成两张卡片，禁
- G3 ocelot_minus quad_vertex.ped_a k=1 联盟 None 成员 quad_vertex.s10
  - 轮次 quad_vertex.s10.split.quad_vertex-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 029127e07d5111a5c5c68de781f72cb5de3b8d501e1589bef4bf3a472ed9ff65
    片段：不引用讲义编号。讲义步 quad_vertex-ped_a-F1：教学方法是先盖住解析式，只让学生看平移箭头，再
- G3 ocelot_minus quad_vertex.ped_b k=1 联盟 None 成员 quad_vertex.s10
  - 轮次 quad_vertex.s10.split.quad_vertex-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2f6895c4fcd2a3ce6a06ca168a907635510087d1e72b691442da671c675ec136
    片段：不引用讲义编号。讲义步 quad_vertex-ped_b-F1：教学方法是把左右平移和上下平移分成两张卡片，禁
- G3 ocelot_minus quad_vertex.ped_a k=1 联盟 None 成员 quad_vertex.s15
  - 轮次 quad_vertex.s15.split.quad_vertex-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 20b11f39a56e1b0b2a10bed42b86fff77ed596bbfe77c354175859c1f892ec3f
    片段：不引用讲义编号。讲义步 quad_vertex-ped_a-F1：教学方法是先盖住解析式，只让学生看平移箭头，再
- G3 ocelot_minus quad_vertex.ped_b k=1 联盟 None 成员 quad_vertex.s15
  - 轮次 quad_vertex.s15.split.quad_vertex-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 fd14e51fb784563eaa8c7a4b67274ae5f5ddacf0cb5d438e93b34266c521779b
    片段：不引用讲义编号。讲义步 quad_vertex-ped_b-F1：教学方法是把左右平移和上下平移分成两张卡片，禁
- G3 ocelot_minus linear_eq.ped_a k=1 联盟 None 成员 linear_eq.s00
  - 轮次 linear_eq.s00.split.linear_eq-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 2b6bf1d426a684a92ce5798f41310dbe88cc51dfc32d9cca5b0d1428f14a024f
    片段：不引用讲义编号。讲义步 linear_eq-ped_a-F1：教学方法是让学生用两种颜色分别标未知数项和常数
- G3 ocelot_minus linear_eq.ped_b k=1 联盟 None 成员 linear_eq.s00
  - 轮次 linear_eq.s00.split.linear_eq-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 96bd63ca32055fce819117b083bf81d156203a3a7856bc323610bd04f2db7dc1
    片段：不引用讲义编号。讲义步 linear_eq-ped_b-F1：教学方法是先口头说下一步要做什么，写对了才允许
- G3 ocelot_minus linear_eq.ped_a k=1 联盟 None 成员 linear_eq.s05
  - 轮次 linear_eq.s05.split.linear_eq-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 08a66be043b3698bbfcd949feb8a6547871347ba211bdb84449e307b38dba028
    片段：不引用讲义编号。讲义步 linear_eq-ped_a-F1：教学方法是让学生用两种颜色分别标未知数项和常数
- G3 ocelot_minus linear_eq.ped_b k=1 联盟 None 成员 linear_eq.s05
  - 轮次 linear_eq.s05.split.linear_eq-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f96c184ef2dca90587a377cdf0b26e07a7fc97446b0e8ce508100ac5b4b3eee1
    片段：不引用讲义编号。讲义步 linear_eq-ped_b-F1：教学方法是先口头说下一步要做什么，写对了才允许
- G3 ocelot_minus linear_eq.ped_a k=1 联盟 None 成员 linear_eq.s10
  - 轮次 linear_eq.s10.split.linear_eq-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 b5d164a1ab23538a70f36d1dabd262ac6f430290ec46964dd1a39cdccaac9f6f
    片段：不引用讲义编号。讲义步 linear_eq-ped_a-F1：教学方法是让学生用两种颜色分别标未知数项和常数
- G3 ocelot_minus linear_eq.ped_b k=1 联盟 None 成员 linear_eq.s10
  - 轮次 linear_eq.s10.split.linear_eq-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a0ea9d47709ec6bf94108e3d0e5c12399555cf5bc7878bb62a4f7d76bc97843f
    片段：不引用讲义编号。讲义步 linear_eq-ped_b-F1：教学方法是先口头说下一步要做什么，写对了才允许
- G3 ocelot_minus linear_eq.ped_a k=1 联盟 None 成员 linear_eq.s15
  - 轮次 linear_eq.s15.split.linear_eq-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 7f9b1766e68e09bf048c481513cb8b76ef0d35f18c123c5372e83083776eb5c4
    片段：不引用讲义编号。讲义步 linear_eq-ped_a-F1：教学方法是让学生用两种颜色分别标未知数项和常数
- G3 ocelot_minus linear_eq.ped_b k=1 联盟 None 成员 linear_eq.s15
  - 轮次 linear_eq.s15.split.linear_eq-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f572e82b2de7068468f2b6a5a7f2d1e92e81b03217f775a175171bb68347311c
    片段：不引用讲义编号。讲义步 linear_eq-ped_b-F1：教学方法是先口头说下一步要做什么，写对了才允许
- G3 ocelot_minus recursion.ped_a k=1 联盟 None 成员 recursion.s00
  - 轮次 recursion.s00.split.recursion-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 3a631b33ba653d27793f0f24aa3139a58b00f1bd3fefb2a1ea78eecceef59947
    片段：不引用讲义编号。讲义步 recursion-ped_a-F1：教学方法是禁止直接给通项，学生必须先交前四项的
- G3 ocelot_minus recursion.ped_b k=1 联盟 None 成员 recursion.s00
  - 轮次 recursion.s00.split.recursion-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 acdfb552a0ae6da04a3cd44da0f9416da1242fcb51fdf5201e82b571c269f222
    片段：不引用讲义编号。讲义步 recursion-ped_b-F1：教学方法是把构造失败的例子留在板书右侧，用来对
- G3 ocelot_minus recursion.ped_a k=1 联盟 None 成员 recursion.s05
  - 轮次 recursion.s05.split.recursion-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4aa4c99c8a2e9e779588a5e6712659e0212559d5d89750a73c02ad834a19c7b1
    片段：不引用讲义编号。讲义步 recursion-ped_a-F1：教学方法是禁止直接给通项，学生必须先交前四项的
- G3 ocelot_minus recursion.ped_b k=1 联盟 None 成员 recursion.s05
  - 轮次 recursion.s05.split.recursion-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 4cf0848991e53cc64662d6897d5bc98d22328805e1ed728e6dc9c25892cb6841
    片段：不引用讲义编号。讲义步 recursion-ped_b-F1：教学方法是把构造失败的例子留在板书右侧，用来对
- G3 ocelot_minus recursion.ped_a k=1 联盟 None 成员 recursion.s10
  - 轮次 recursion.s10.split.recursion-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a0ec4fd0c8474d7b577100daf77ccfa5090152a5e8505cf8740e8cc0ce5bbab6
    片段：不引用讲义编号。讲义步 recursion-ped_a-F1：教学方法是禁止直接给通项，学生必须先交前四项的
- G3 ocelot_minus recursion.ped_b k=1 联盟 None 成员 recursion.s10
  - 轮次 recursion.s10.split.recursion-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 926d2b4b0df40718dcec46b3bf541e1f34cad188db9505bab0f63836084e10e4
    片段：不引用讲义编号。讲义步 recursion-ped_b-F1：教学方法是把构造失败的例子留在板书右侧，用来对
- G3 ocelot_minus recursion.ped_a k=1 联盟 None 成员 recursion.s15
  - 轮次 recursion.s15.split.recursion-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 7f45f0f7bcbc2384796d0ac53455c2b7da689fd5e6a8221c39d9d659d77f72e4
    片段：不引用讲义编号。讲义步 recursion-ped_a-F1：教学方法是禁止直接给通项，学生必须先交前四项的
- G3 ocelot_minus recursion.ped_b k=1 联盟 None 成员 recursion.s15
  - 轮次 recursion.s15.split.recursion-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 3593dd9d3a2d871a8608691845b39d4e5eee4fda3d77076835ead43cafc68881
    片段：不引用讲义编号。讲义步 recursion-ped_b-F1：教学方法是把构造失败的例子留在板书右侧，用来对
- G3 ocelot_minus congruence.ped_a k=1 联盟 None 成员 congruence.s00
  - 轮次 congruence.s00.split.congruence-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d59eeb3cc37680a03b0056039e678892d0eda80c84bf36c95f4ef6e82e5bbb11
    片段：不引用讲义编号。讲义步 congruence-ped_a-F1：教学方法是证明不从条件堆开始，而从要证的对应顶
- G3 ocelot_minus congruence.ped_b k=1 联盟 None 成员 congruence.s00
  - 轮次 congruence.s00.split.congruence-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 987ccaac28310c8359b9a6a9687003110923552ae0682abf1d75d1ae2d741ab7
    片段：不引用讲义编号。讲义步 congruence-ped_b-F1：教学方法是用一张只画标记、不写字母的图，先说关
- G3 ocelot_minus congruence.ped_a k=1 联盟 None 成员 congruence.s05
  - 轮次 congruence.s05.split.congruence-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 9502544342fc3eea8db4e7e4e896bc674b668f6406db63e0a70fa7c2b2f73fa0
    片段：不引用讲义编号。讲义步 congruence-ped_a-F1：教学方法是证明不从条件堆开始，而从要证的对应顶
- G3 ocelot_minus congruence.ped_b k=1 联盟 None 成员 congruence.s05
  - 轮次 congruence.s05.split.congruence-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 dbe3ed3f36cde3ff17aae36eca8e833304d17cd98ef9005b5fa6d5d1b9163f02
    片段：不引用讲义编号。讲义步 congruence-ped_b-F1：教学方法是用一张只画标记、不写字母的图，先说关
- G3 ocelot_minus congruence.ped_a k=1 联盟 None 成员 congruence.s10
  - 轮次 congruence.s10.split.congruence-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 d6db9625c46f3aeb8e6f0dcb76f106bcb50f6de17a4e4b84b72a8176d7c4f92f
    片段：不引用讲义编号。讲义步 congruence-ped_a-F1：教学方法是证明不从条件堆开始，而从要证的对应顶
- G3 ocelot_minus congruence.ped_b k=1 联盟 None 成员 congruence.s10
  - 轮次 congruence.s10.split.congruence-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 53743447cb2bdda2004f7cc6cf8602fdbe3014b834b79675e573b03e158577c2
    片段：不引用讲义编号。讲义步 congruence-ped_b-F1：教学方法是用一张只画标记、不写字母的图，先说关
- G3 ocelot_minus congruence.ped_a k=1 联盟 None 成员 congruence.s15
  - 轮次 congruence.s15.split.congruence-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 f81824625135fd9bdb67cf1ede720155b8693d55c151a5a6acce7e0ad4317ffc
    片段：不引用讲义编号。讲义步 congruence-ped_a-F1：教学方法是证明不从条件堆开始，而从要证的对应顶
- G3 ocelot_minus congruence.ped_b k=1 联盟 None 成员 congruence.s15
  - 轮次 congruence.s15.split.congruence-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 56c8d595d736f994f85481f7319fb85875fd64b0d0f45c51b506f1b03cd606f3
    片段：不引用讲义编号。讲义步 congruence-ped_b-F1：教学方法是用一张只画标记、不写字母的图，先说关
- G3 ocelot_minus prob_tree.ped_a k=1 联盟 None 成员 prob_tree.s00
  - 轮次 prob_tree.s00.split.prob_tree-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 15913884456c2c5fd2f47c735a6bc9b92468b22848c7b16032fd4477eb45e90e
    片段：不引用讲义编号。讲义步 prob_tree-ped_a-F1：教学方法是学生先用硬币实物走一遍路径，再把路径
- G3 ocelot_minus prob_tree.ped_b k=1 联盟 None 成员 prob_tree.s00
  - 轮次 prob_tree.s00.split.prob_tree-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 39d520802281f744859423681f7bddc70894610dfc406a62aabe7f12aa9d6497
    片段：不引用讲义编号。讲义步 prob_tree-ped_b-F1：教学方法是相加和相乘用两种颜色的笔，写错颜色就
- G3 ocelot_minus prob_tree.ped_a k=1 联盟 None 成员 prob_tree.s05
  - 轮次 prob_tree.s05.split.prob_tree-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 aa8e09c0dcb056e9804deb657badf6c5886251309444940d3402cf19b290faa5
    片段：不引用讲义编号。讲义步 prob_tree-ped_a-F1：教学方法是学生先用硬币实物走一遍路径，再把路径
- G3 ocelot_minus prob_tree.ped_b k=1 联盟 None 成员 prob_tree.s05
  - 轮次 prob_tree.s05.split.prob_tree-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 74f2b135f77dae20eea06271b63aac51cde3b19ba2fc08540b78256219bfb8d8
    片段：不引用讲义编号。讲义步 prob_tree-ped_b-F1：教学方法是相加和相乘用两种颜色的笔，写错颜色就
- G3 ocelot_minus prob_tree.ped_a k=1 联盟 None 成员 prob_tree.s10
  - 轮次 prob_tree.s10.split.prob_tree-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 7e783b089e72f6d9723b86d4cd8be2c82ad51e01ba63f02bbf362f8d65b025ec
    片段：不引用讲义编号。讲义步 prob_tree-ped_a-F1：教学方法是学生先用硬币实物走一遍路径，再把路径
- G3 ocelot_minus prob_tree.ped_b k=1 联盟 None 成员 prob_tree.s10
  - 轮次 prob_tree.s10.split.prob_tree-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 5f3293e774afcbaa33ff9e699c7bd06bc090fc5122de3141071b40c90c27ad31
    片段：不引用讲义编号。讲义步 prob_tree-ped_b-F1：教学方法是相加和相乘用两种颜色的笔，写错颜色就
- G3 ocelot_minus prob_tree.ped_a k=1 联盟 None 成员 prob_tree.s15
  - 轮次 prob_tree.s15.split.prob_tree-ped_a-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 a7002b90b0184563e93b02e1e09db8201050d8ee38326261d4f587712b4bd8e1
    片段：不引用讲义编号。讲义步 prob_tree-ped_a-F1：教学方法是学生先用硬币实物走一遍路径，再把路径
- G3 ocelot_minus prob_tree.ped_b k=1 联盟 None 成员 prob_tree.s15
  - 轮次 prob_tree.s15.split.prob_tree-ped_b-F1 字段 NONE 算子 identity 基础代价 0.0 收费 0.0 累计 0.0 哈希 931f80c937bb6fc2761e1c2e354ee77fb285e1c017b1751b9be68dde61c10e59
    片段：不引用讲义编号。讲义步 prob_tree-ped_b-F1：教学方法是相加和相乘用两种颜色的笔，写错颜色就
