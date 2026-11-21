"""Write sanitized, explicitly bounded audit conclusions. No algorithms executed."""
import csv
import io
import platform
import subprocess

from experiments.c2rag_r36_authorization_audit_20261029_01.common import (
    OUT, PROJECT_ROOT, frozen, read, sha, write,
)


def main():
    frozen()
    assert read('VERIFICATION.json')['status'] == 'PASS'
    joins = [
        ('episode -> resource/profile', 'teacher_resource_ref; student_profile_ref',
         'F03 -> F02/synthetic_profiles', 'design-time linkage exists; rotating synthetic episodes',
         'no real issuer-bound grants or source-approved recipient-specific candidate replies'),
        ('demo -> episode resource', 'DemoCase; DemoC2RAGService; return_mode',
         'F09 -> F03 -> F02', 'demo loader and adapter connect existing records',
         'default course_limited_license is generated metadata, not an independently authenticated authorization'),
        ('teacher team -> profile/resource views', 'view_fields: context_card/resource_text',
         'F08 + F09', 'internal trusted roles have configured input differences',
         'no source-backed mapping to distinct end-user recipients and no per-target coalition authorization'),
        ('OpenStax -> historical research simulation', 'public worked examples with multiple methods',
         'F06; prior R34/R35 context', 'real public teaching source supports problem and two approaches',
         'restricted targets and recipient grants in earlier work were researcher simulated, not textbook-issued'),
    ]
    buf = io.StringIO(newline='')
    w = csv.writer(buf)
    w.writerow(['join', 'join_fields', 'families', 'supported_link', 'remaining_missing_evidence'])
    w.writerows(joins)
    write('CROSS_SOURCE_JOINS.csv', buf.getvalue())
    write('STRUCTURE_AUDIT.md', '''# R36 角色授权与固定菜单结构审计

EXPLORATORY；审计日2026-10-29。结论：没有找到可进入真实任务结构核验的完整契约。不得将缺证据写成固定菜单最优证明。

## 所检验的命题

沿用R34/R35的失败认识：若对受限目标存在一个未授权联盟C*（人数≤3），其可见知识覆盖所有需要防护的联盟视图，某些原有静态候选设定就可能退化为全局并集约束。旧实验中固定菜单足够，不等于任何任务均如此。

本轮先核查能否从现有来源恢复真正的接收者、签发权限、实际候选答案和持续实例。对每个目标，覆盖应比较真实交付历史V_C：存在同样未授权C*且所有V_C⊆V_C*才叫覆盖。人数超过3、角色名称不同、输入字段不同均不足以推出不覆盖。授权联盟不能拿来作未授权覆盖见证。

即便发现不覆盖，也只是否定旧论证的一项充分条件，仍须独立展示强菜单不足。强菜单可以使用来源确定的题型、可信角色/权限类和公开条件；不能故意删掉这些键制造动态方法优势。

## 案例一：真实教材多解任务，缺限权契约

`experiments/c2rag_r10_20261020_01/local_sources/college-physics-2e__7-2-kinetic-energy-and-the-work-energy-theorem.html`：

- 第626行，段落`import-auto-id2521056`：同一包裹的净功问题要求两种求法，先用净力、再逐力计算并求和。
- 第740行，`import-auto-id1115429`：说明重力和支持力与位移垂直，不做功。
- 第903行，`import-auto-id1997856`：说明摩擦力与位移反向，摩擦功为负。

因此“存在两个真实正确求解途径”有教材依据。但原题/数值/题解在公开页可见，来源没有给不同学生签发不同答案权限，也没有受限实例目标。本轮不把它改成秘密、不重新分配接收者，不重跑T05—T08。状态：真实问题/多解SUPPORTED；角色答案可用性UNKNOWN；菜单反例NOT_EVALUATED。

## 案例二：六节点委员会，不能由节点数推出非覆盖

`configs/teacher-teams.yaml`第27—41行定义committee（精确节点行号见`static_input_field_covers.json`）。concept/visual/review/synthesize初始视图只有question、knowledge、difficulty；worked另有resource_mode、resource_text；diagnose另有context_card。

对初始字段名称做只读集合检查：worked+diagnose两个既有节点的字段并集覆盖整个团队；其余五种团队的最小字段覆盖均为1。独立bitmask穷举与集合枚举的六组结果全部一致。

这仅是STATIC_INPUT_FIELD_COVER_ONLY：没有计算实际知识、父节点消息、最终输出或未授权联盟。配置没有证明内部教师节点等同于不同恶意学生，也没有给出按资产签发的接收者授权。因此不能把这个“两节点字段覆盖”当安全证明，也不能把“六节点”当新结构证据。

## 跨来源连接复核

不能仅因为单一文件缺某字段就排除跨文件完整契约。`CROSS_SOURCE_JOINS.csv`保留四条已有连接：episode→资源/合成profile、demo→episode、team→profile/resource输入、OpenStax→既有模拟研究。它们支持数据路由或公开问题，却都未补齐真实签发授权与角色绑定的正确候选回复。既有demo代码会补默认license/source标签，不是独立授权来源。

## 严格分母与停止

194个冻结文件不是194个任务；10050个JSON顶层记录也不是10050份独立教学资产。识别到的完整真实任务契约0；可认证的非覆盖真实任务0；菜单不足证书0。后两项是“未找到的数量”，不是经过算法试验得到0风险或0差距。

由于没有合格契约，没有运行G、A2、B、菜单OPT、攻击器或任何防御。效用/最优差距为null/NOT_EVALUATED。没有修改身份、权限、题目或候选来补正例。此轮完成后停止。
''')
    write('RESULT.md', '''# R36 本地真实教学来源审计结果

**ANALYZE：当前本地证据不足以建立打破固定菜单等价性的真实教学任务，停止本轮，不开发新算法。**

这是有边界的负面来源审计，不是“现实中不存在复杂任务”或“Simple永远最优”的结论。先冻结来源/判据，再检查内容；协议SHA256：`c77ec9d1e77067fc4c02dcf68127163a7ce9461a6334dc803209061f3b23c19e`。接续research-sync版本`caedf0ca698473b61207782c3472b96a07230143`，不改写R34/R35。

## 实际范围

十类来源共194个唯一文件：教师资源、分层教学episode与profile、本地raw/processed记录、GSM8K/MATH副本、OpenStax缓存、KARC Pilot、教师团队配置、教育应用边界和测试日志。全部JSON字段扫描共10050个顶层记录；29546个相关字段定位、3355个文本标记定位、38个重复候选定位。扫描是定位工具，不是授权真值或语义审稿。38个是疑似相同字段/记录的定位，不是38份重复资产。

目录`data`、`assets/resources`、`assets/documents`、`assets/knowledge`中的PDF/DOCX/TXT元数据普查未找到文件；没有搜个人主目录或整个磁盘，不能说机器上没有其他材料。来源表按原目录关系去重；同一个manifest在两族出现，族计数不能直接相加。

## 发现

1. **教师资源标签不足以建立真实授权。** master资源30条，数字归一后只有1个占位内容模板；均自报teacher_original，缺具体作者/机构签发权限和实质标准答案。分层资源10条是短题意/教学提示，有copyright_level及return_mode，但没有可核验的角色授权/候选答案矩阵。总manifest的教师资源5、profile5与现存30、50不符，保留为过期元数据问题。
2. **教学记录的合成/演示性质必须保留。** episode10+generated50为预设编排，generated使用deterministic_stratified_rotation_v2；不是60次真实课堂交付。30 raw与30 processed是派生对，存在合成生成入口但本轮未证明其真实采集来源。KARC Pilot20资产全部明确AI辅助合成、权限模拟、单作者标注，不能当真实授权样本。
3. **真实教材支持多解，未支持受限角色差异。** 35份OpenStax缓存HTML对应32个检测到的页面URL，其中7份文件名为license。35/35缓存页含CC BY-NC-SA 4.0链接；这只报告本地缓存页脚，没有在线重验，也不是全部插图许可审计或排他访问许可。净功例题确有两种求解方法，但题目和答案公开，不能把它直接称作秘密。
4. **实际Agent视图差异并未给出所需非覆盖证据。** 六种团队中五种初始字段并集由一个节点覆盖，committee由worked+diagnose两个节点覆盖。输入字段覆盖不是实际知识覆盖。内部Agent教学职责、提示风格和服务器scope接口均不等于真实不同学生的资产授权；demo还会填入默认license标签，不能据此反推签发事实。
5. **跨来源拼接也未补齐授权链。** 已有episode/profile/resource/demo/team连接已保留，未发现真实签发者→持续接收者→具体资产→允许回复→联合权限的完整链。公开数学副本有8795个题答记录，但本轮没有重评分所有答案或补办缺失许可证，更没有把公开知识改成秘密。

## 判据与结果

冻结八项资格门：真实来源、持续接收者、签发授权、具体受限目标、正常题及正确候选、来源支持的答案可用性、联合权限、跨题实例绑定。逐族SUPPORTED/NOT_SUPPORTED/UNKNOWN/SYNTHETIC_ONLY见ROLE_AUTH_AUDIT.csv；它是来源库存判断，不是独立任务的成功率统计。人工判断由单一研究助手完成，没有独立人类双标。

完整真实契约0；可认证非覆盖任务0；固定菜单不足证书0。没有合格对象，故算法差距为**未评估/null**，没有将其填0。未运行防御、优化器、模型或攻击。六组字段覆盖独立bitmask核验一致，194个来源哈希前后不变，126处来源标记行核验通过；3项软件自检通过。独立计算不等于独立人类标注。

## 唯一下一步

获得一份**已有教学任务的完整、可脱敏授权证据包**：机构/资源负责人批准的持续接收者与资产权限、真实任务、允许的正确候选回复、跨轮实际交付及联合权限边界。先审计其是否非覆盖，再判断强固定菜单是否真有不足。不改变身份/权限来寻求结果；材料未到位前不开发新算法、不继续扩量。

同步只包含脱敏定位、统计、判断、代码及哈希，不上传原始教师材料、学生日志、题库正文、生产代码或密钥。原始扫描保留本地；发布版去除逐值/逐行内容哈希，独立标明脱敏变换，不能据发布包重建未公开语料。
''')
    write('GAPS.md', '''# 缺口、失败与不确定性

EXPLORATORY；全数保留，不选有利样本。

- 缺真实签发的角色/资产授权，不是缺一个更复杂的控制器。role、source、copyright、license默认值无法替代机构授权证据。
- 有公开教材多解，但没有同一任务、同等正常效用、由来源约束的角色答案可用性矩阵。Socratic提示与完整解答不能默认同分。
- 没有真实多接收者联合权限/观察语义；内部可信Agent和恶意学生联盟不能混同。当前输入字段检查不包含实际父消息或语义闭包。
- 缺实际持续接收者与跨题资产绑定日志。旧研究同包裹关系有教材依据，身份与授权仍是作者模拟，不能升级为真实制度约束。
- master资源30条是同模板占位内容；manifest计数过期。分层资源不是已认证教师私有题库，版权标签/来源名字均需核验。没有删除这些记录。
- KARC20是开发合成资产；raw/processed记录的真实来源未独立认证；GSM8K/MATH本地副本的许可证/版本链不足。没有将以上转成新独立真实样本。
- OpenStax缓存有许可链接，但未在线重验，不能延伸为每项附图/第三方材料均许可；未向接收者开放新的原文，也未下载任何资料。
- 字段定位/计数覆盖全部冻结文件，语义审查按来源与实际关联进行；没有逐题独立验证8795道公开题解。UNKNOWN不作为安全或算法成功。
- 没有独立人类标注；所有结论为作者研究审计。自动核验只验证哈希、定位、计数和集合计算。

工程检查记录：首次目录定位把education.py误作目录；一次PowerShell通配路径未展开；一次Python -c的HTML正则受引号影响失败。均为只读定位命令错误，未执行研究回放、未写入旧数据、未修改冻结契约。改用已冻结文件的明确路径和保存脚本/标准输入。主prepare、scan、review、verify与测试均成功，无失败结果被删。以上错误不算实验样本或研究负例。

没有合格任务时不运行算法，是冻结停止条件。Gap=null，不能声称强菜单零差距，也不能把“来源缺失”包装成新算法空间。
''')
    write('REPRODUCE.md', '''# 复核与证据分层

本地工程根目录D:/pycharm/CogniGuard，Python使用.venv-langgraph。生产/历史文件未改；项目原有未提交修改不纳入本次同步。定义目录experiments/c2rag_r36_authorization_audit_20261029_01；结果目录var/results/c2rag_r36_authorization_audit_20261029_01。

按顺序实际执行（输出写入采用exclusive-create，避免覆盖）：

```powershell
.venv-langgraph/Scripts/python.exe -m experiments.c2rag_r36_authorization_audit_20261029_01.prepare
.venv-langgraph/Scripts/python.exe -m experiments.c2rag_r36_authorization_audit_20261029_01.scan
.venv-langgraph/Scripts/python.exe -m experiments.c2rag_r36_authorization_audit_20261029_01.review
.\\run.cmd test experiments/c2rag_r36_authorization_audit_20261029_01/test_audit.py -q
.venv-langgraph/Scripts/python.exe -m experiments.c2rag_r36_authorization_audit_20261029_01.verify
.venv-langgraph/Scripts/python.exe -m experiments.c2rag_r36_authorization_audit_20261029_01.report
```

prepare会拒绝复写已存在结果目录；不要对原目录重跑。独立复现应使用工程副本并保留原结果，先核对194份source_sha256。source_selection是冻结文件清单，不是把原材料全部再分发。scan只导出定位。review包含明确作者判断，verifier不把它当独立人工真值。

发布包中scripts为独立审计定义，outputs为脱敏元数据和报告。原始源文件、生产代码、学生/教师正文不发布；故公开包能核验产物/判断定位，完整重扫需要获准访问相同本地来源。field_locators的value_sha256、text_marker_locators的line_sha256及duplicate_candidates的内容hash在发布副本移除；源文件哈希仍保留以便经授权本地核验。发布清单单独登记本地原字节与脱敏字节SHA256。

固定提交后回读报告/清单/脚本及归档分片验证；回读回执保留本地REMOTE_VERIFICATION.json，避免将自身提交号写回同一个提交造成循环。
''')
    write('RUN_RECORD.json', {
        'date': '2026-10-29', 'timezone': 'Asia/Shanghai', 'python': platform.python_version(),
        'code_git_head_context_only': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=PROJECT_ROOT, text=True).strip(),
        'workspace_preexisting_dirty': True, 'test_command': 'run.cmd test experiments/c2rag_r36_authorization_audit_20261029_01/test_audit.py -q',
        'tests': {'passed': 3, 'failed': 0, 'purpose': 'software fixtures, not real task evidence'},
        'source_changes_from_frozen_snapshot': 0,
        'model_calls': 0, 'gpu_calls': 0, 'paid_api_calls': 0, 'new_source_downloads': 0,
        'audit_definition_sha256': {p.name: sha(p.read_bytes()) for p in sorted((PROJECT_ROOT/'experiments/c2rag_r36_authorization_audit_20261029_01').glob('*.py'))},
        'main_research_run': 'one frozen metadata/source review; no algorithm performance experiment',
    })
    frozen()
    print('Wrote RESULT, STRUCTURE_AUDIT, GAPS, cross-source joins, reproducibility and run record.')


if __name__ == '__main__':
    main()
