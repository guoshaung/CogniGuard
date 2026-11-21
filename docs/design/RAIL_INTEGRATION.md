# Rails 与三层保护的接入约定

## 两个维度

Input、retrieval、dialog、execution、output 描述在系统生命周期的什么位置介入。
MM-FOPD、C²-RAG、HSW-ST 描述保护什么对象、用什么机制产生结果和证据。
三层机制可以接入多个位置；CGC 负责跨层协调。它们没有一对一的层级对应关系。

这与 [NVIDIA 对 rails 的定义](https://docs.nvidia.com/nemo/guardrails/latest/about-nemo-guardrails-library/rail-types)
一致。复用介入机制和接口时，领域策略继续由 CogniGuard 实现。

## 接入职责

- **Input**：校验外部输入和上下文边界；需要画像时调用 MM-FOPD 构建获准的最小上下文。
  用户请求检查不能替代可信会话授权，也不能据原始画像构造模型提示。
- **Retrieval**：调用 C²-RAG 完成版权感知检索、受控返回和累计暴露预算，
  输出被批准的片段、摘要或拒绝结果；检索内容的指令隔离属于可组合的辅助检查。
- **Dialog**：由现有 LangGraph 与 CGC 协调会话状态、跨轮预算和回退。
  接入第三方 dialog rails 时，不再引入一套独立的业务状态机覆盖这些决策。
- **Execution**：在 Agent 消息、工具调用与画像写回边界落实 CGC 的能力授权和领域约束。
  工具返回值仍是待检查数据，不能因调用成功取得额外权限。
- **Output**：复核画像与资源释放边界，调用 HSW-ST 完成水印和来源绑定。
  内容清理或改写应在最终水印/审计绑定前完成；若绑定后必须改变内容，应重新绑定并验证。

## 策略所有权与冲突

以下规则来自仓库维护者的明确要求：**重合或冲突的领域策略使用 CogniGuard 自己的实现。**

1. MM-FOPD 决定画像选择和释放，C²-RAG 决定资源授权、返回模式和领域预算，
   HSW-ST 决定水印与来源绑定；第三方通用规则不重复计算或覆盖相同职责。
2. 对同一职责，停用或替换对应的第三方内置 flow/action，接入本地机制的结果与证据。
   不采用两套竞争策略分别改写同一数据，也不为同一释放重复扣账。
3. 本地领域拒绝、预算耗尽、来源或完整性失败不能被第三方 `allow` 恢复为允许。
   本地某一领域的 `allow` 也不表示其他独立检查自动通过。
4. 同一职责之外的通用检查可以保留，例如输入格式和额外的提示注入检查。
   策略作用域与启用由可信应用配置确定，用户消息和检索文本不能请求覆盖。

## 当前代码覆盖

- 可通过可信环境设置 `COGNIGUARD_NEMO_NATIVE=on`，在网关使用原生 NeMo 0.24.1
  IORails 的基础输入/输出检查；依赖或配置失败时停止。默认关闭以保留原有安装契约。
  当前配置仅为明确列出的本地正则规则，不启用模型、Colang dialog、NeMo retrieval 或工具流，
  不能说已经完成所有 NeMo 安全能力。领域保护与最终交付检查仍然强制执行。
- 可另启用本地模型驱动的 NeMo 自检变体，检查语义越狱与内容安全；默认关闭且服务
  不可用时停止。已有模拟服务接线测试与少量真实本地模型冒烟，尚未系统评估检测能力。
- `COGNIGUARD_NEMO_COLANG=on` 在原生基础护栏开启时，另启用 `LLMRails` 的固定
  Colang dialog 流、retrieval flow 与执行前 action 检查。它们仅执行少量正则，
  执行前检查覆盖 CGController 的 Agent dispatch 和教学图片提示，未覆盖全部工具；不提供
  多轮语义意图理解。领域授权与最终交付仍由原有机制负责。

- `cogniguard/protection/cg/nemo_guardrails_adapter.py` 是本地确定性检查，
  暴露 input、retrieval、execution、output 四类接口；没有创建 `LLMRails`，
  也不执行 `config.yml`/Colang 中列出的 flow。
- `run_free_chat()`、`run_classroom_turn()` 与 `run_demo()` 的公共执行入口统一经过
  `cogniguard/runtime/gateway.py`。HTTP/直接 Python 调用共用同一最终交付边界；
  `enable_nemo=false` 只影响可选适配，不会关闭服务端会话、领域预算和最终校验。
- 公开教育接入使用 `cogniguard.integrations.education.run_protected_education()`，由可信
  服务端提供 pipeline、profile 与 `AccessScope`，同样经过 gateway 并将会话绑定到单一
  获准学生。原 `ProtectionPipeline.run()` 保留为离线研究与受信应用的底层组合点，
  单独调用不自动获得这条会话、最终校验和强制水印链路。
- **Input**：gateway 执行确定性通用输入检查；画像节点注册真实私值与实际获准的最小上下文。
  画像/资源请求类关键词不替代后续 MM-FOPD/C²-RAG 领域决策。
- **Retrieval**：`protection/retrieval.py` 在领域释放之前隔离候选指令；领域实现随后决定
  受控内容、成本与哈希。已绑定释放若还需要改写则被隔离，不能改正文后沿用旧哈希。
  `CopyrightAwareResourceAgent` 注册原始受保护资源、实际获准片段和来源 ID，并记录领域成本。
  当前课堂演示通过 `DemoC2RAGService` 接入该契约；它是演示领域适配器，不等同于正式检索基准。
- **Dialog**：SQLite 匿名会话保存服务器 history、课堂状态、请求幂等结果与跨轮预算；
  客户端 history、session_state、已生成图片数、消融开关不能覆盖可信状态或重置额度。
- **Execution**：每个请求原子预留请求数；图像生成在副作用之前预留服务端图片额度。
  privacy/copyright 成本来自实际 CGC/MM-FOPD/C²-RAG 证据，不接受客户端计费值。
  课堂当前最小上下文披露使用既有 CGC `RiskScorer.score`，不是固定扣除演示常量。
- CGController 完成本地授权、合规、领域变换和预算检查后，调用适配器的
  `check_authorized_message()`：跳过重复的画像/版权请求关键词判断，保留独立注入与原始字段检查。
  普通 `check_message()` 不接受消息中的授权标记作为依据；第三方适配器应显式实现该可信接点。
- **Output**：交付前检测私值、未经批准的原文重现及伪造来源；同样清理嵌套消息、模型日志与
  诊断字段。校验通过的最终文本进入 HSW-ST 语义水印与 HMAC 来源绑定，再次校验水印后的
  文本并验证最终签名。若水印改写引入违规内容，则拒绝原答案并重新绑定安全替代文本。
- `check_retrieved_chunks()` 已接入候选检查；业务对话状态仍由本地会话与 LangGraph 管理。
- `protection/supporting/cg_guardrails/` 保留 NeMo 风格配置与 actions。配置里有 flow 不等于业务已经执行它。
- `nemo_runtime_available` 表示包是否可导入；`guardrail_backend` 表示当前实际使用的适配器。

上面的职责划分是集成约定，不能据此宣称已经原生运行五类 NeMo rails。

## 水印和部署范围

当前默认文本保护是可检测的本地语义标记，加上对最终文本、获准来源和审计记录的 HMAC
绑定。它没有自动启用 logits 采样或 KGW 统计水印，语义标记鲁棒性也不等于统计显著性。
`statistical` 模式需要可信应用显式提供可嵌入且可检测的后端；必需后端不可用时停止交付。

匿名 session token 表示持有某个会话，不证明用户身份。新 token 会创建新配额；部署仍需
实现账号级/全局额度及入口限流。SQLite 与会话文件锁支持同一主机上的线程和进程，
不承诺跨主机共享文件系统的分布式事务。运行库和 HTTP 契约分别见
[runtime](../../cogniguard/runtime/README.md)、[API](../../cogniguard/api/README.md)。
