# 最小使用示例

两个示例均使用内存合成数据，不读取本地研究数据、不下载权重、不调用模型。

- `quickstart.py`：框架核心。可信调用方配置 capability，将领域证据交给
  `LifecycleGuard`，得到可预测的 `allow`、`refuse`、`quarantine` 决策。
  该示例只需要 Python 标准库和 CogniGuard 核心包。证据由示例构造，
  决策返回不会自动执行检测、认证或回滚操作。
- `education.py`：可选的教育集成。展示画像最小化、资源受控摘要与离线规则解题，
  输出 `summary` 和 `x=2`。需要项目的 LangGraph 运行依赖。
  本例未配置可选生命周期治理和水印 hook。

## 安装与运行

在仓库根目录安装核心包，使用 Python 3.12 或以上版本：

```powershell
python -m pip install -e .
python examples/quickstart.py
```

教育集成需要额外的运行依赖：

```powershell
python -m pip install -e ".[runtime]"
python examples/education.py
```

使用已有研究环境时，可以复用已装依赖：

```powershell
.\.venv-langgraph\Scripts\python.exe -m pip install --no-deps -e .
.\.venv-langgraph\Scripts\python.exe examples/quickstart.py
.\.venv-langgraph\Scripts\python.exe examples/education.py
```

`--no-deps` 使用环境中已有依赖；完整研究环境的依赖入口是
[`requirements.txt`](../requirements.txt)。核心治理示例自身不需要
LangGraph、Torch 或模型 SDK。editable 安装后，也可以从其他工作目录用
Python 执行这两个脚本的实际路径，无需修改 `sys.path` 或依赖当前目录。

教育集成的 `AccessScope` 必须由可信调用方创建，在线应用应从已验证的会话取得。
每个学生会话使用独立的 pipeline，保留该会话的累计预算。
`ProtectionResult.to_dict()` 包含内部诊断，不能整体发送给模型；未来模型适配器
只接收 `TeachingInput` 文本视图，并继续将其中的文本作为不可信输入处理。
