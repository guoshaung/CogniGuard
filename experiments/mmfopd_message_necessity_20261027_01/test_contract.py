"""Small interface tests: no data access, model fitting or paid calls."""
from pathlib import Path
import importlib.util
import pytest
spec=importlib.util.spec_from_file_location('message_necessity_contract',Path(__file__).with_name('run.py'))
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
def student():
    return {'values':{k:1.25 for k in core.SAFE},'module':'BBB','cutoff':42,'target_due':55,'student':123,'target_score':94,'gender_F':0,'disability_Y':1}
def test_forbidden_fields_never_reach_wire():
    a=student();b={**a,'student':999,'target_score':4,'gender_F':1,'disability_Y':0}
    assert core.raw_pairs(a,core.ALL)==core.raw_pairs(b,core.ALL)
    for key in ['student','target_score','gender_F','disability_Y']:
        with pytest.raises(ValueError):core.parse(key+'=1')
def test_missing_and_absent_are_distinguishable():
    views=core.encode([core.parse('latest_score=NA'),{}],{'latest_score':70.})
    assert views[0]['missing:latest_score']==1 and views[0]['present:latest_score']==1
    assert 'present:latest_score' not in views[1]
    assert core.parse('latest_score=0')['latest_score']==0.
def test_summary_contains_categories_not_raw_values():
    row=student();row['values']['latest_score']=85.
    assert core.summary_pairs(row,['latest_score'],{'latest_score':[30.,60.]})==[('latest_score_bin','high')]
    row['values']['latest_score']=None
    assert core.summary_pairs(row,['latest_score'],{'latest_score':[30.,60.]})==[('latest_score_bin','NA')]
def test_authorized_forecast_duplicate_adds_no_view_feature():
    auth=[core.parse('predicted_score=71.2')]
    assert core.union(auth,auth)==core.union(auth,[{}])
