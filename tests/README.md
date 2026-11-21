# 公共契约检查

```bat
run.cmd test tests -q
```

- `test_public_api.py`：公共治理类型、历史导入兼容性及无第三方依赖导入。
- `test_examples.py`：合成数据示例、跨工作目录执行与模型依赖隔离。

旧模块的专用检查保留在 `cogniguard/tests/`、`core/tests/`、
`core/langgraph_runtime/tests/` 和相应领域模块内。上述命令是公共入口检查，
不代表完整的模型推理、训练或所有历史研究实验已被验证。
