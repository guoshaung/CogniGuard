# 提示词注入边界与测试

## 当前模型能读取什么

默认 `ProtectionPipeline` 不调用 LLM。后端读取完整 `StudentProfile` 和教师资源，
选择画像记录、构建上下文卡片，再按资源策略生成受控文本。
本地敏感字段不直接写入卡片；资源正文中的指令不会自动变成 Python 权限。
这些性质不等于真实 LLM 的注入防御能力。

内部 `ProtectionResult.selected` 保留画像记录，`controlled.resource` 保留原始资源。
未来模型适配器不能直接序列化整个结果对象，也不能把调试用 `to_dict()` 全量作为模型上下文。

## 已接入默认流程的访问策略

默认 `ProtectionPipeline.run` 现在必须显式传入 `AccessScope`。
它在检索与预算提交前检查学生范围和资源读取权限；不提供范围会拒绝调用。
`AccessScope.resource_ids` 可进一步限定资源编号集合，先过滤再排名；空集合拒绝资源请求，
`None` 表示可信调用方授予当前资源库的读取范围，仍逐次执行版权与暴露策略。
`ProfileReadPolicy` 在相关性算法之前排除非白名单类型和超敏感度记录，
只允许 mastery、error_pattern、preference，且 mastery 必须是 0 到 1 的有限数值。
`configs/focused.yaml` 中 `access.max_profile_sensitivity` 是独立硬门限。

教学生成改为只接收不可变的 `TeachingInput`，字段限于 question、knowledge、difficulty、
context_card、resource_mode、resource_text。原始画像、资源、权限对象和诊断轨迹不会传入。
本地敏感字段的顶层值会在教学文本入口做精确匹配脱敏；不代表能识别转述、编码或嵌套秘密。

```python
from core.access import AccessScope

# 离线示例；在线必须来自已验证的登录会话，不能照抄请求的 student_id。
scope = AccessScope(student_id="stu_001", allow_resources=True)
result = pipeline.run(profile, question, access=scope)
model_data = result.teaching_input.to_dict()
```

范围对象只约束通过此默认流程的访问。它不是操作系统沙箱，也不保护绕过流程直接读取数据库的代码。
本轮没有迁移旧 backend、frontend、CG 或真实模型适配器；它们尚未受到此新接口保护。
未来模型必须通过该文本入口接入，并保持可信指令与不可信文本分隔。

| 数据 | 模型可见范围 | 后端控制点 |
|---|---|---|
| 学生身份与归属 | 通常无需发送真实身份 | 从登录会话确定学生归属；不能信任请求自报 student_id |
| 本地敏感字段 | 禁止发送 | 不向模型暴露读取完整画像的工具 |
| 学习画像 | 本轮选出的掌握状态、错误类别、学习偏好 | 后端筛选并构建卡片，模型无权扩大字段范围 |
| 教师资源 | 受控文本及必要来源编号 | 每次读取强制执行可信策略与会话预算 |
| 资源正文与工具返回 | 不可信资料 | 与系统指令分隔；正文不得修改权限或预算 |
| 画像写入 | 不能仅凭模型文字直接执行 | 单独的写入授权、字段校验及评估证据 |

当前范围与画像 ID 检查不能代替登录鉴权；CLI 与评估是可信本地调用方。
资源策略应来自受信存储；不得允许上传资料自行声明版权权限。

## 已添加的离线对抗测试

运行：

```bash
python -m unittest discover -s core/tests -v
```

`core/tests/test_injection_boundaries.py` 检查：

- 用户问题中的越权指令不会释放本地秘密或写入画像。
- 强制检索到的恶意正文不会改变后端 summary-only 策略。
- 重复攻击请求不会绕过禁止返回资源的策略或倒退预算状态。
- 文本中的管理员声明不能绕过任务与画像 ID 一致性检查。
- 正向对照：允许短引用时，恶意文字可以进入回答。版权控制不是注入净化器。

`core/tests/test_access.py` 另外检查强制范围、拒绝时不执行检索或提交隐私预算、
无资源权限时仍可进行无需资源的教学、资源编号白名单、字段白名单和硬门限、教学输入字段集及本地已知值脱敏。

上述用例是自建边界测试，没有导入 InjecAgent 数据。它们不统计真实模型攻击成功率。
摘要模式不回显恶意正文，只能说明当前模板摘要没有使用该正文，不能外推到 LLM 摘要。
引号、角色标签和提示词约束本身也不能保证安全。

真实模型先导实验现已提供 `python -m cogniguard redteam`，
保存攻击入口、实际模型输入、工具调用轨迹与最终输出。
它使用合成学生和本地只读画像工具，对比无保护、仅访问控制、仅独立模型检测和联合保护。
实验实现与局限见 [redteam/README.md](../../experiments/focused/redteam/README.md)。
伪造工具结果以资料正文形式注入；真实跨 Agent 传播尚未覆盖。
