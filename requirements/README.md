# 依赖清单

基础治理库使用 `python -m pip install -e .`；教育参考流程使用
`python -m pip install -e ".[runtime]"`。本目录存放研究环境的依赖清单。

- `runtime.txt`：现有 LangGraph 研究运行环境，根 `requirements.txt` 引用它。
- `runtime-lock.txt`：既有 Windows Python 3.12 环境的版本快照；不是 wheel 哈希锁。
- `benchmarks.txt`：运行环境加可选 Parquet 基准读取依赖。
- `research.txt`：历史模型和水印研究环境，引用相应领域模块的依赖。

从仓库根目录运行，例如：

```sh
python -m pip install -r requirements.txt
python -m pip install -r requirements/benchmarks.txt
```

`-r` 路径相对于包含它的清单解析。领域模块的独立依赖仍保存在各模块内；
具体实验的模型、资产和环境要求以模块文档为准。
