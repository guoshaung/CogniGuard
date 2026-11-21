# 四个主体

实现在这一层。每个角色只构造请求。

| 文件 | 角色 |
|---|---|
| `diagnosis.py` | 画像诊断 |
| `materials.py` | 教师材料 |
| `teaching.py` | 讲解 |
| `learner.py` | 学生侧学习 |
| `assessment.py` | 评估 |
| `base.py` | 共同约束 |

`cogniguard/agents/` 下同名旧文件只做兼容导入。协调在 `protected_orchestrator.py`，守门仍走 CGC。
