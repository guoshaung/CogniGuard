# 影子来源状态：模型与伪代码

本文描述 `cogniguard/governance/source_state.py` 里已经跑起来的判定。它是实验用的影子模型，不替换 `ReleaseGate`，也不声称新的安全定理。联盟检查仍是现有的 `check_release`。

## 对象

一次请求是主体 \(p\)、资源集合 \(R\)、目的、组织、时刻，以及准备释放的单元 \(U\)。

每条发行记录 \(b\) 有资源、被授权人、目的集合、单元和撤销位。撤销只作用于这一条记录。

每条证据 \(e\) 有类型、候选发行号、匹配到的单元、置信度、核验状态、可信事件号和策略版本。类型只有五种：指纹、水印、内嵌签名凭证、可信日志、理想证据。

可信事件记为 \(T(e)\)。它为真仅当核验状态是 verified，类型是签名凭证、可信日志或理想证据，并且可信日志还带有事件号。指纹和水印即使置信度为 1 也不是 \(T(e)\)。

传播被确认，仅当 \(T(e)\) 且类型是可信日志或理想证据且事件号非空。签名凭证只证明发行身份。

## 知识

记系统已有的持有为 \(K\)。影子判定使用

\[
K' = K \cup \{\text{可信日志或理想证据写明的 (持有者, 单元)}\}.
\]

水印和指纹的匹配单元不进入 \(K'\)。因此它们不能把一次释放变成“更接近重构”，也不能据此扣减安全预算。本原型不写回执，`charged_budget` 恒为 false。

联盟判定是现有函数：

\[
\mathrm{safe}(p, U, K', k) = \mathtt{check\_release}(p, U, K', k).\mathrm{safe}.
\]

## 授权

一条可信发行号能用于本次请求，需同时满足：

- 绑定存在、未撤销、被授权人是 \(p\)、资源属于本次请求；
- 绑定写了目的时，请求目的在其中；
- 证据上的正策略版本等于该资源当前版本；
- 该证据若声明了持有，则匹配单元与绑定单元相交；
- `AccessRegistry.is_authorized` 对这个资源仍为真；
- 仅在 Ours 打开否决时，一条声明了持有的水印或指纹若与绑定单元不相交，则这条发行号被丢掉。否决不是授权。

请求被影子允许，当且仅当下面两条都成立，并且 \(\mathrm{safe}\) 为真：

1. 每个待释放资源都被一条可用发行覆盖；或者没有任何被接受的证据声称 \(p\) 自己的发行，并且注册表对每个资源授权（回退）。
2. 证据一旦声称了 \(p\) 的发行但没有一条可用，就不再回退到注册表。别人的发行记录不会取消 \(p\) 自己仍有效的授权。

冲突状态的凭证不能作为 \(T(e)\)。若它是该主体唯一的发行声明，判定拒绝。

## 伪代码

```
function shadow_decide(evidence, request, registry, bindings, K, k):
    trusted = [e in evidence if accepted(e) and T(e)]
    usable = []
    for issuance in issuance_ids(trusted):
        if not independent_grant(issuance, request, registry, bindings, evidence):
            drop issuance
        else:
            usable.append(issuance)
    K_prime = copy(K)
    for e in trusted if e is trusted_log or ideal and e.holder is set:
        K_prime[e.holder] |= e.units
    auth = covers(usable, request) or (silent(evidence, request) and registry_allows(request))
    if auth and not check_release(request.principal, request.units, K_prime, k).safe:
        return deny(reconstruction, charged_budget=false)
    return decision(auth, charged_budget=false, changes_production_path=false)
```

`independent_grant` 在同一资源上看到一条撤销记录和另一条仍有效记录时，保留后者。

## 对照臂如何取证据

各臂看到同一份传播结果上自己的通道，不把别的通道补进来。

| 臂 | 参与授权的证据 | 水印能否否决 |
|---|---|---|
| B0 | 无，只用注册表和 \(K\) | 否 |
| B1 | 同 B0；指纹只记录内容身份 | 否 |
| B2 | 签名凭证；通道沉默时回到 B0 | 否 |
| B3 | 可信日志；通道沉默时回到 B0 | 否 |
| B4 | 同 B0；水印不进入 \(K'\) | 否 |
| B5 | 同 B4；另报告标记与绑定是否不一致 | 否 |
| Ours | 凭证和日志；标记不一致时可否决对应发行 | 是 |
| Oracle | 理想证据，不回退 | 否 |

Oracle 的允许与否还用一份独立的真值复核：真实发行是否仍授权、释放单元是否仍留在文本里、以及真实持有上的 `check_release`。两套结果不一致时，以测试失败处理，不改真值。
