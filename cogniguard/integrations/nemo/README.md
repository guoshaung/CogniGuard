# NeMo 原生基础护栏与 Colang 接口

`NativeNeMoGuard` 使用 NeMo Guardrails 0.24.1 的原生 `Guardrails`/`IORails`
执行输入与输出检查，应用网关可通过可信服务端配置显式开启。启用后配置或执行错误会
停止请求，不会静默降级。内置配置仅包含少量本地正则规则，不调用模型，也不代表完整的
内容安全或语义越狱防护。该 IORails 后端本身不执行 Colang 对话、检索和工具动作。

```powershell
python -m pip install -e '.[runtime,nemo]'
$env:COGNIGUARD_NEMO_NATIVE='on'
python -m cogniguard.api
```

本机验证环境也可用 `.venv-nemo/Scripts/python.exe` 代替 `python`。NeMo 检查先于业务
操作，并在交付时检查输出；MM-FOPD、C²-RAG、HSW-ST 和 CGC 的领域决策、预算与最终
来源绑定仍各自生效。NeMo 放行不能覆盖领域拒绝。自定义配置只能由可信部署方提供，
并应自行审查其是否调用外部模型及传出何种数据。

## 可选 Colang 边界检查

NeMo 原生 `LLMRails`/Colang 1.0 可另外接到三个实际边界，默认关闭：

```powershell
$env:COGNIGUARD_NEMO_NATIVE='on'
$env:COGNIGUARD_NEMO_COLANG='on'
.\.venv-nemo\Scripts\python.exe -m cogniguard.api
```

- Dialog：网关业务调用前运行固定的 Colang 对话流和本地正则检查。
- Retrieval：C²-RAG 领域释放前，NeMo retrieval flow 检查每个候选文本字段；命中则隔离整批候选。
- Execution：CGC 对 Agent 消息授权后、`receiver.generate` 前运行 Colang action 检查；
  教学图片生成前也检查图片提示词；命中则停止调用。

实际内容只传给本地检查回调，Colang 事件只包含固定标签与布尔结果，不包含请求或资源正文。
检查失败停止请求。此处使用少量固定正则，不推断对话意图、不建模多轮对话，
不是 NeMo 内置 tool-call validation，未覆盖全部工具或直接调用底层接口的路径。
Agent 实际执行仍由 CGC 调度，不在 NeMo action 中运行。候选预算与权限仍由领域组件决定；
额外正则可能误拦截引用攻击文本的合法教学内容。若服务已运行，需要重新启动才会加载新配置。
不要把开启配置或接线测试当成安全覆盖率证明。

## 本地语义自检（需单独启用）

`configs/nemo/semantic/config.yml` 通过真正的 NeMo `self check` 输入/输出栏杆，
分别检查语义越狱意图、有害请求与有害回答；模型结果使用 NeMo 内置 JSON 解析器，
无法解析、服务错误或超时均不放行。它是**普通语言模型自检**，不是已经验证的
NeMoGuard、Llama Guard 专用分类器，也不能保证检测全部攻击或危险内容。

需先由部署者准备已运行的本地 OpenAI 兼容模型服务和其中实际存在的模型名称；
项目不会自动启动服务、下载权重或导入本地 GGUF。配置示例：

```powershell
$env:COGNIGUARD_NEMO_NATIVE='on'
$env:COGNIGUARD_NEMO_SEMANTIC='on'
$env:COGNIGUARD_NEMO_SEMANTIC_URL='http://127.0.0.1:11434/v1'
$env:COGNIGUARD_NEMO_SEMANTIC_MODEL='<已在本地服务注册的模型名>'
.\.venv-nemo\Scripts\python.exe -m cogniguard.api
```

只接受 `http://127.0.0.1:<端口>/v1`，本地地址还必须绕过代理；本地服务本身如何
处理收到的内容由部署者负责。系统不会将 OpenAI 默认 API key 发给该服务。一次正常
请求会执行两次输入自检和一次输出自检，可能明显增加延迟；输出自检检查经领域清理和
水印绑定后的完整交付 JSON。若网关已经拒绝输入、业务操作未执行，则语义自检只审查
服务端固定拒答正文（含水印），避免将可信审计元数据误判为有害内容。
输出被拒绝时先生成并重新绑定安全替代回答，替代回答也要再次通过语义检查；服务
不可用或替代回答未通过时停止请求。已发生的预算副作用不会自动撤销。
语义检查默认关闭；开启后不允许静默退回正则。`protection` 中记录的是实际执行阶段，
运行模式中的 `nemo_semantic_configured` 只表示配置，不能证明模型可用或检测有效。

本机已有 Qwen GGUF 只是通用模型，尚未通过系统安全评估。除模拟服务接线测试外，
已有少量真实本地模型冒烟，见 `var/results/nemo_semantic_setup_20261105_01/RESULT.md`。
不能据此宣称语义检测质量、误拦截率或多语言可靠性已经验证。

`ColangInterface` 仍是独立的只读元数据接口：

此接口用于查看保留配置的位置、action 名称和五个介入位置的策略归属。
它不导入 `nemoguardrails`，不创建 `LLMRails`，不解析运行配置、不注册 action，
也不调用模型。`prepare()` 只列出文件与准备元数据，不能证明配置经过原生版本校验。

```python
from cogniguard.integrations.nemo import ColangInterface

bridge = ColangInterface()
print(bridge.describe())
print(bridge.prepare())
```

原始配置保留在 [`protection/supporting/cg_guardrails/`](../../../protection/supporting/cg_guardrails/)。
`actions` 中的符号是配置库存元数据，不是已挂载的可执行函数。
指定其他 `config_path` 只改变待查看目录。

`enabled=True`、`execute()`、`generate()` 均抛出 `ColangExecutionDisabled`。
不能通过一个开关把本次保留的接口变成原生执行器。

五个位置继续由 CogniGuard 自有实现管理：input 连接 MM-FOPD 与 CGC，
retrieval 连接 C²-RAG，dialog 由 LangGraph 与 CGC 调度，execution 执行
CGC capability、参数与预算检查，output 连接内容校验、HSW-ST 水印和来源绑定。
配置中重合的第三方策略不能覆盖本地领域决定。

上面的 `NativeColangGates` 是独立的原生桥接，与此元数据接口不是同一组件。
职责与冲突处理见 [接入约定](../../../docs/design/RAIL_INTEGRATION.md)。
