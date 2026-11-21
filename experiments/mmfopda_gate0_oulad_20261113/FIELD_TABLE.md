# OULAD 字段审计（全发布表，非仅选中队列）

来源、许可见 README.md。缺失率为 pandas 默认 NA（含空单元格），不把 0 当缺失。
类型为整列实际可解析类型；整数语义但存在缺失时为 float64。
studentInfo 的三项标签仅在攻击拟合/评价时读取，不传入请求生成函数。
联结键不作为请求内容或攻击特征。其他画像列、最终结果和未来行为禁止用于生成。
courses 为额外的公开日历元数据表，仅用于全学期终点，非画像输入。

## studentInfo.csv — 32,593 行

| 字段 | 实测类型 | 缺失率 | 用途 |
|---|---|---:|---|
| code_module | object | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| code_presentation | object | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| id_student | int64 | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| gender | object | 0.000000% | 禁止使用 |
| region | object | 0.000000% | 禁止使用 |
| highest_education | object | 0.000000% | 禁止使用 |
| imd_band | object | 3.408707% | 敏感标签：0-10%、10-20=1；缺失排除本标签 |
| age_band | object | 0.000000% | 敏感标签：55<= =1 |
| num_of_prev_attempts | int64 | 0.000000% | 禁止使用 |
| studied_credits | int64 | 0.000000% | 禁止使用 |
| disability | object | 0.000000% | 敏感标签：Y=1 |
| final_result | object | 0.000000% | 禁止使用 |

## studentAssessment.csv — 173,912 行

| 字段 | 实测类型 | 缺失率 | 用途 |
|---|---|---:|---|
| id_assessment | int64 | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| id_student | int64 | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| date_submitted | int64 | 0.000000% | 请求：已发生提交；模拟分数可用时间 |
| is_banked | int64 | 0.000000% | 过滤：不使用结转成绩 |
| score | float64 | 0.099476% | 请求：模拟已公布分数 |

## assessments.csv — 206 行

| 字段 | 实测类型 | 缺失率 | 用途 |
|---|---|---:|---|
| code_module | object | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| code_presentation | object | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| id_assessment | int64 | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| assessment_type | object | 0.000000% | 过滤：仅 TMA/CMA |
| date | float64 | 5.339806% | 请求：截止日；无截止日不触发 |
| weight | float64 | 0.000000% | 禁止使用 |

## studentVle.csv — 10,655,280 行

| 字段 | 实测类型 | 缺失率 | 用途 |
|---|---|---:|---|
| code_module | object | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| code_presentation | object | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| id_student | int64 | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| id_site | int64 | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| date | int64 | 0.000000% | 请求：截至当周已发生点击 |
| sum_click | int64 | 0.000000% | 请求：资源占比 |

## vle.csv — 6,364 行

| 字段 | 实测类型 | 缺失率 | 用途 |
|---|---|---:|---|
| id_site | int64 | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| code_module | object | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| code_presentation | object | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| activity_type | object | 0.000000% | 请求：资源类型 |
| week_from | float64 | 82.385292% | 禁止使用 |
| week_to | float64 | 82.385292% | 禁止使用 |

## studentRegistration.csv — 32,593 行

| 字段 | 实测类型 | 缺失率 | 用途 |
|---|---|---:|---|
| code_module | object | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| code_presentation | object | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| id_student | int64 | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| date_registration | float64 | 0.138066% | 资格：截止时已注册 |
| date_unregistration | float64 | 69.097659% | 资格：截止时已退课则不发新请求 |

## courses.csv — 22 行

| 字段 | 实测类型 | 缺失率 | 用途 |
|---|---|---:|---|
| code_module | object | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| code_presentation | object | 0.000000% | 仅内部联结/队列/划分；禁止进入外发和攻击特征 |
| module_presentation_length | int64 | 0.000000% | 日历：全学期观察终点 |
