# Gate W0 偏离记录

1. （运行后发现）`run_attribution` 对每种变换都运行了一次 S4，而 S4 固定使用 fragment 变换，所以 `attribution.csv` 中有 3 组 S4 行。它们的区别只在于查询种子不同。三组都保留，没有删除任何结果，结论不受影响。
