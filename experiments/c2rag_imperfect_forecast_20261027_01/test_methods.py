import pytest
from experiments.c2rag_imperfect_forecast_20261027_01.common import read,module
from experiments.c2rag_imperfect_forecast_20261027_01.forecast import packet,posterior
from experiments.c2rag_imperfect_forecast_20261027_01.planner import Gate,choose


def visible(condition):return {'stream_id':'test','structure':'kinetic','family':'uniform','condition':condition,
    'hint':0 if condition!='prior' else None,'prefix':[1,0] if condition!='prior' else [],
    'step':1,'length':8,'types':2,'scenario_seed':123}


def test_known_uniform_hints_do_not_create_information():
    packets=[packet(visible(c)) for c in ['prior','none','weak','strong','misleading']]
    assert all(p['scenarios']==packets[0]['scenarios'] for p in packets)
    assert all(p['next_type_probabilities']==[0.5,0.5] for p in packets)
    bad=visible('strong')|{'true_suffix':[1]}
    with pytest.raises(AssertionError):posterior(bad)


def test_two_fact_simple_is_counting_and_simulation_does_not_commit():
    bank=read('public/banks.json')['kinetic'];gate=Gate(bank,module('engines'));state=(0,)*8
    scenes=[[1]*7 for _ in range(32)]
    for method in ['Simple','A2']:
        action,child,_=choose(gate,state,0,0,method,scenes)
        assert action=='EMPTY' and child==state
    assert state==(0,)*8


def test_T06_repeated_questions_can_mix_two_answer_methods():
    bank=read('public/banks.json')['T06'];gate=Gate(bank,module('engines'));state=(0,)*8
    s,bad=gate.trial(state,0,'T06-A1a');assert not bad
    _,bad=gate.trial(s,1,'T06-A1a');assert not bad
    _,bad=gate.trial(s,1,'T06-A1b');assert bad
    _,bad=gate.trial(s,1,'T06-A3a');assert bad
