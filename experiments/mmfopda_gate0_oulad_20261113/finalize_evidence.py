"""Post-run consistency checks and plain-language interpretation; never fits models."""
import json

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

from run_gate0 import E, R, check_freeze, dump, sha

check_freeze()
split = pd.read_csv(R / 'split_LOCAL.csv')
assert split.id_student.is_unique and split.student_key.is_unique
train_keys = set(split.loc[split['split'] == 'train', 'student_key'])
test_keys = set(split.loc[split['split'] == 'test', 'student_key'])
assert train_keys.isdisjoint(test_keys)
features = np.load(R / 'features_LOCAL.npz')
reconstructed = np.zeros_like(features['requests'])
names = json.loads((R / 'feature_schema.json').read_text())['request_names']
name_index = {n: i for i, n in enumerate(names)}
student_index = {key: i for i, key in enumerate(split.student_key)}
request_count = 0
with (R / 'requests_LOCAL.jsonl').open() as f:
    for line in f:
        row = json.loads(line)
        assert set(row) == {'student_key', 'week', 'agent', 'message'}
        assert set(row['message']) == {'request'}
        j = name_index[row['message']['request']]
        assert row['agent'] == ('tutor' if j < 2 else 'admin' if j == 2 else 'resource')
        reconstructed[student_index[row['student_key']], row['week']-1, j] += 1
        request_count += 1
assert np.array_equal(reconstructed, features['requests'])
assert (features['raw'] >= 0).all()
predictions = pd.read_csv(R / 'per_student.csv', dtype={'week': str})
assert set(predictions.student_key) == test_keys
assert not set(predictions.student_key).intersection(train_keys)
config = ['label', 'observer', 'week', 'model', 'control']
assert not predictions.duplicated(['student_key'] + config).any()
metrics = pd.read_csv(E / 'metrics.csv', dtype={'week': str}).set_index(config)
assert len(metrics) == 384
for key, group in predictions.groupby(config):
    result = metrics.loc[key]
    assert len(group) == result.test_n
    assert np.isclose(roc_auc_score(group.evaluation_target, group.probability), result.auc)
    assert np.isclose(balanced_accuracy_score(group.evaluation_target, group.prediction),
                      result.balanced_accuracy)
assert predictions.control.eq('actual').sum() == predictions.control.eq('shuffled').sum()
validation = {
    'frozen_source_rules_split_and_archive_hashes_match': True,
    'students_disjoint_and_unique': True,
    'request_payloads_contain_only_request_name': True,
    'serialized_requests_reconstruct_feature_tensor_exactly': True,
    'request_count': request_count,
    'prediction_rows': len(predictions),
    'prediction_configs': len(metrics),
    'all_prediction_aucs_and_balanced_accuracies_recomputed': True,
    'project_launcher_tests_passed': 3,
    'ruff': 'Unavailable in both existing venvs; no packages installed.',
    'individual_output_path': str(R / 'per_student.csv'),
    'individual_output_sha256': sha(R / 'per_student.csv'),
}
dump(E / 'VALIDATION.json', validation)
interpretation = '''
## 关键数字与决定理由

按事前门槛判 **PARTIAL（部分通过）**，不是三方合谋 PASS，也不是把部分通过改成失败。

- 唯一满足单方点估计 AUC≥0.65 的配置：age55plus / resource / 全学期 / LR，
  AUC **0.6816 [0.5053, 0.8362]**，BA **0.7029 [0.5703, 0.8256]**。
  训练正例17/3911、测试正例15/2538；AUC下界仅略高于0.5，不能称为稳定确立的单方风险。
  部分通过门槛本身没有规定区间下界，故严格保留 PARTIAL。
- 同标签全学期 LR 三方 AUC **0.6586 [0.5008, 0.8224]**，
  相对最佳单方差 **−0.0229 [−0.1728, 0.0654]**，没有累积增益证据。
- 全学期 age55plus / Tree3 三方 AUC **0.6646 [0.5198, 0.8061]**，
  点差 **+0.0355 [−0.1697, 0.1128]**；尽管点估计与增量达标，
  三方AUC区间下界未超过0.55，所以不通过。
- disability 最佳三方 AUC **0.5645**（第12周 Tree3）；
  imd_low20 最佳三方 AUC **0.5816**（全学期 LR）；均不满足0.65门槛。
- 标签置乱AUC范围：disability 0.4769–0.5227；imd_low20 0.4873–0.5242；
  age55plus 0.4040–0.6120。年龄样本稀少时随机下界也明显波动，不能只挑点估计解释。
- 原始行为对照的 age55plus 第8周 LR AUC **0.7448 [0.6211, 0.8622]**；
  信息更丰富的行为记录可能有年龄信号，但该结果不满足“仅凭请求且有三方增量”的闸门。

**行动：不进入 Gate 1，不开发多Agent合谋防御。** 按部分通过条款仅保留单接收方线索；
如后续开展，应先取得更多55+独立测试样本验证，不能把当前稀少正例结果当作新防御算法准入。
本轮不追加样本、不改课程、不改规则、不更换标签、不运行新配置。

来源为真实公开行为，140,976次服务请求为规则模拟；无真实教学Agent或真实支持干预。
成绩可用时间是冻结假设，课程混合、多重比较及稀少正例限制均保留。
per_student.csv仅存于本机 var/results/mmfopda_gate0_oulad_20261113，不进入Git。
'''
for name in ['RESULT.md', 'final_decision.md']:
    content = (E / name).read_text(encoding='utf-8')
    if '## 关键数字与决定理由' not in content:
        (E / name).write_text(content + '\n' + interpretation, encoding='utf-8')
dump(E / 'OUTPUT_SHA256.json', {p.name: sha(p) for p in E.iterdir()
                               if p.is_file() and p.name != 'OUTPUT_SHA256.json'})
print(json.dumps(validation, indent=2))
