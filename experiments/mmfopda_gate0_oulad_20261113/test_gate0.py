"""Use the project launcher; scientific checks run in the existing research venv."""
import ast
import subprocess
from pathlib import Path

E = Path(__file__).resolve().parent
ROOT = E.parents[1]


def test_request_generator_does_not_read_sensitive_table():
    tree = ast.parse((E / 'run_gate0.py').read_text(encoding='utf-8'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'build_requests')
    literals = {n.value for n in ast.walk(function)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not literals.intersection({'studentInfo', 'disability', 'imd_band', 'age_band'})


def test_bootstrap_auc_ties_and_student_multiplicity():
    code = '''
import importlib.util
import numpy as np
from sklearn.metrics import roc_auc_score, balanced_accuracy_score
s = importlib.util.spec_from_file_location('gate', 'experiments/mmfopda_gate0_oulad_20261113/run_gate0.py')
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
y = np.array([0, 1, 0, 1, 1, 0])
p = np.array([.1, .5, .5, .8, .5, .2])
w = np.array([[1, 1, 1, 1, 1, 1], [2, 1, 0, 2, 1, 0]], float)
a, b = m.bootstrap_scores(y, p, w)
for i in range(len(w)):
    idx = np.repeat(np.arange(len(y)), w[i].astype(int))
    assert np.isclose(a[i], roc_auc_score(y[idx], p[idx]))
    assert np.isclose(b[i], balanced_accuracy_score(y[idx], p[idx] >= .5))
'''
    result = subprocess.run([str(ROOT / '.venv/Scripts/python.exe'), '-B', '-c', code],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_request_time_boundary_and_withdrawal():
    code = '''
import importlib.util, tempfile, zipfile, json
from pathlib import Path
import pandas as pd
s = importlib.util.spec_from_file_location('gate', 'experiments/mmfopda_gate0_oulad_20261113/run_gate0.py')
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    m.R = Path(tmp); m.ARCHIVE = m.R / 'fixture.zip'
    split = pd.DataFrame({'id_student':[1,2], 'code_module':['BBB']*2,
      'code_presentation':['2014J']*2, 'student_key':['a','b'], 'split':['train','test']})
    split.to_csv(m.R / 'split_LOCAL.csv', index=False)
    frames = {
      'courses':pd.DataFrame([['BBB','2014J',28]], columns=['code_module','code_presentation','module_presentation_length']),
      'studentRegistration':pd.DataFrame([['BBB','2014J',1,-10,None],['BBB','2014J',2,-10,14]],
        columns=['code_module','code_presentation','id_student','date_registration','date_unregistration']),
      'vle':pd.DataFrame([[10,'BBB','2014J','resource'],[11,'BBB','2014J','quiz']],
        columns=['id_site','code_module','code_presentation','activity_type']),
      'assessments':pd.DataFrame([[1,'BBB','2014J','TMA',0],[2,'BBB','2014J','TMA',7],[3,'BBB','2014J','TMA',14]],
        columns=['id_assessment','code_module','code_presentation','assessment_type','date']),
      'studentAssessment':pd.DataFrame([[1,1,0,0,90],[2,1,7,0,60],[3,1,14,0,30],[2,2,11,0,20]],
        columns=['id_assessment','id_student','date_submitted','is_banked','score'])}
    clicks = pd.DataFrame([['BBB','2014J',1,10,0,10],['BBB','2014J',2,11,0,10],
                          ['BBB','2014J',2,11,21,1000]],
      columns=['code_module','code_presentation','id_student','id_site','date','sum_click'])
    with zipfile.ZipFile(m.ARCHIVE,'w') as z: z.writestr('studentVle.csv', clicks.to_csv(index=False))
    m.read = lambda name, **kwargs: frames[name].copy()
    _, requests, raw = m.build_requests()
    assert requests[0,:3,0].sum() == 0, 'Future low score leaked'
    assert requests[0,3,0] == requests[0,3,1] == 1, 'Available low/decreasing score not seen'
    assert requests[1,1,2] == 1, 'Late submission request missing'
    assert requests[1,2:].sum() == 0, 'Requests after withdrawal'
    assert raw[1,-1,0] == 10, 'Post-withdrawal future clicks included'
    for line in (m.R / 'requests_LOCAL.jsonl').read_text().splitlines():
        assert set(json.loads(line)['message']) == {'request'}
'''
    result = subprocess.run([str(ROOT / '.venv/Scripts/python.exe'), '-B', '-c', code],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
