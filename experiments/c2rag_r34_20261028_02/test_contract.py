import itertools
from experiments.c2rag_r34_20261028_02.common import read, module
from experiments.c2rag_r34_20261028_02.planner import Gate, choose

def test_menu_universal_compatibility_against_all_schedules():
    bank=read('public/banks.json')[0];gate=Gate(bank,module('engines'))
    for schedule in [[0,1],[0,0],[0,3],[1,2,0]]:
        for menu in gate.menus:
            safe=True
            for types in itertools.product(range(len(menu)),repeat=len(schedule)):
                state=(0,0,0,0)
                for who,q in zip(schedule,types):
                    action=menu[q]
                    if who==3:action=bank['queries'][q]['answers'][0]['id']
                    state,_=gate.trial(state,who,action)
                safe=safe and not gate.risk(state)
            assert safe==gate.menu_safe((0,0,0,0),menu,schedule)

def test_heterogeneous_permission_and_accumulation():
    bank=read('public/banks.json')[0];gate=Gate(bank,module('engines'));a=bank['queries'][0]['answers'][0]['id'];b=bank['queries'][1]['answers'][0]['id']
    s,bad=gate.trial((0,0,0,0),3,a);s,bad=gate.trial(s,3,b);assert not bad
    s,bad=gate.trial((0,0,0,0),0,a);s,bad=gate.trial(s,0,b);assert bad
    s,bad=gate.trial((0,0,0,0),0,a);s,bad=gate.trial(s,1,b);assert bad

def test_incomparable_correct_work_answers():
    bank=read('public/banks.json')[1];gate=Gate(bank,module('engines'))
    a,b=bank['queries'][0]['answers'];A=gate.close(gate.bits[a['id']]);B=gate.close(gate.bits[b['id']])
    assert A&~B and B&~A
    for answer in [a,b]:assert not gate.trial((0,0,0,0),0,answer['id'])[1]

def test_future_not_required_for_greedy_and_ties_stable():
    bank=read('public/banks.json')[2];gate=Gate(bank,module('engines'));state=(0,0,0,0)
    a,s,_=choose(gate,state,0,0,'G',[],[])
    assert state==(0,0,0,0) and a!='EMPTY' and not gate.risk(s)
