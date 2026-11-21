# AFK阶段0快速预判

结论：快速预判未达到7比特，按预注册停止，不进入第3节和阶段1。

## 有效容量

{"min": 0.0, "p25": 0.0, "median": 1.0, "p75": 2.146240625180289, "max": 13.509775004326936}

容量来自300篇R生成讲解；30篇压缩预判按固定哈希选择，不按容量挑选。

## 压缩后的有效证据

- C1：中位容量1.000 × 写法保留率0.6405 + 插入带来的存活新比特中位数0.000 = 0.641比特；要求≥7。
- C2：中位容量1.000 × 写法保留率0.7908 + 插入带来的存活新比特中位数0.000 = 0.791比特；要求≥7。

## 各类存活计数

{
  "C1": {
    "variant": {
      "retained": 98,
      "n": 153,
      "eligible_documents": 19,
      "not_applicable_documents": 0,
      "rate": 0.6405228758169934
    },
    "connective": {
      "retained": 4,
      "n": 55,
      "eligible_documents": 29,
      "not_applicable_documents": 1,
      "rate": 0.07272727272727272
    },
    "equivalent_parenthesis": {
      "retained": 1,
      "n": 2,
      "eligible_documents": 2,
      "not_applicable_documents": 28,
      "rate": 0.5
    },
    "intermediate_arithmetic": {
      "retained": 0,
      "n": 2,
      "eligible_documents": 1,
      "not_applicable_documents": 29,
      "rate": 0.0
    },
    "unit_substitution": {
      "retained": 0,
      "n": 0,
      "eligible_documents": 0,
      "not_applicable_documents": 30,
      "rate": null
    },
    "dimension_check": {
      "retained": 0,
      "n": 0,
      "eligible_documents": 0,
      "not_applicable_documents": 30,
      "rate": null
    }
  },
  "C2": {
    "variant": {
      "retained": 121,
      "n": 153,
      "eligible_documents": 19,
      "not_applicable_documents": 0,
      "rate": 0.7908496732026143
    },
    "connective": {
      "retained": 0,
      "n": 55,
      "eligible_documents": 29,
      "not_applicable_documents": 1,
      "rate": 0.0
    },
    "equivalent_parenthesis": {
      "retained": 0,
      "n": 2,
      "eligible_documents": 2,
      "not_applicable_documents": 28,
      "rate": 0.0
    },
    "intermediate_arithmetic": {
      "retained": 0,
      "n": 2,
      "eligible_documents": 1,
      "not_applicable_documents": 29,
      "rate": 0.0
    },
    "unit_substitution": {
      "retained": 0,
      "n": 0,
      "eligible_documents": 0,
      "not_applicable_documents": 30,
      "rate": null
    },
    "dimension_check": {
      "retained": 0,
      "n": 0,
      "eligible_documents": 0,
      "not_applicable_documents": 30,
      "rate": null
    }
  }
}

## 边界

- Parser/validation coverage documented in VARIANT_TABLE and CPU_CAPACITY.
- Literal insertion survival is distinguished from equivalently rewritten content.
- No applicable source-backed unit-substitution or dimension-check insertion was constructed in the fixed 30-source sample; these cells are unavailable, not a measured 0% survival.
- Groups newly appearing in separate insertion arms can overlap; summing their bits is an optimistic diagnostic bound, not simultaneous independent capacity.

50项自然度表保持空白，不能宣称A0通过。第3节的300篇×多密钥测量、3B评分与微基准未启动，未运行数字不填0。
H2额外留出调用0、付费调用0。
