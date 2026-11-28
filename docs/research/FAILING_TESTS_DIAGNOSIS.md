# 三个已知失败测试的诊断

日期：2026-11-28。分支 `paper/eswa-evolving` 从 `origin/main`（`5827e4e`）拉出。只诊断，不改被测代码，也不改这些测试。

命令：

`python -m pytest cogniguard/tests core/tests protection/common protection/teacher_resource protection/student_profile -q`

本机的 `python` 是 3.9，工程要求 3.12 以上，实际用的是 `/usr/local/bin/python3.14`。为了让既有测试能被收集，用户目录里装了 pytest、PyYAML、langgraph、pymysql、numpy、Pillow。没有下载模型。

整套结果：`3 failed, 379 passed, 9 skipped`。失败正好是下面三个。当时工作区里已经有本轮新增的进化层测试，它们是通过的，没有把失败数推过 3。

## 1. `core/tests/test_paths.py::test_repository_has_named_image_modules_and_no_old_root_directories`

```
core/tests/test_paths.py:51: in test_repository_has_named_image_modules_and_no_old_root_directories
    assert (paths.EDITGUARD_DIR / "options/test_editguard.yml").is_file()
E   AssertionError: assert False
E    +  where False = is_file()
E    +    where is_file = (PosixPath('.../third_party/editguard') / 'options/test_editguard.yml').is_file
```

`core/paths.py` 把 `EDITGUARD_DIR` 定成 `third_party/editguard`。这个检出里没有 `third_party/editguard`，`git ls-files third_party` 是空的，也没有 `.gitmodules`。路径翻译逻辑没有被这条断言打到。失败是因为 main 里没有这个第三方目录，测试却把它当成仓库的一部分。

判断：测试相对当前 main 的内容过时，或者第三方树从未入库。被测的路径常量与测试写法一致，不是常量写错。

要修的话会动到：把 EditGuard 放进 `third_party/editguard/`，或者改 `core/tests/test_paths.py` 和 `core/paths.py` 里的期望。本轮不修。

## 2. `core/tests/test_supplychain.py::SupplyChainTests.test_clean_verifies_and_loads`

```
core/tests/test_supplychain.py:15: in test_clean_verifies_and_loads
    self.assertTrue(v["provenance_valid"])
E   AssertionError: False is not true
```

`pin` 再 `verify` 同一份实际指纹。不通过是因为有制品缺失，不是哈希算法算错。当前缺失项：

- `injecagent_dataset_cases`：`experiments/external_data/injecagent/f19c9f2c79a41046eb13c03c51a24c567a8ffa07/data/user_cases.jsonl` 不在检出里
- `injecagent_license`：同一修订下的 `LICENCE` 也不在
- `dep_torch`、`dep_transformers`、`dep_sklearn`：这个解释器里没有这三个包

`verify` 对 `missing` 判 provenance 无效，符合 `runner.py` 里的写法。

判断：测试假定数据集和重依赖已经在本机。代码按缺失拒绝，没有算错。不是被测逻辑坏了。

要修的话会动到：把 InjecAgent 那个修订下的数据放进 `experiments/external_data/`，并在运行测试的环境里安装 torch、transformers、scikit-learn。或者改 `experiments/focused/supplychain/inventory.py` 和 `core/tests/test_supplychain.py`，让干净场景不依赖这些缺失项。本轮不下载模型，也不改这些文件。

## 3. `core/tests/test_supplychain.py::SupplyChainTests.test_run_scenarios`

```
core/tests/test_supplychain.py:36: in test_run_scenarios
    self.assertTrue(summary["clean_loads"])
E   AssertionError: False is not true
```

`clean_loads` 来自同一次干净校验。数据集和三个依赖仍然缺失，所以干净场景不能加载。和上一则是同一个原因，不是另一处逻辑错误。

要修的文件与上一则相同。本轮不修。
