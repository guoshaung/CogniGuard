from fractions import Fraction as F
import itertools
from experiments.c2rag_r35_20261029_01.common import read, module
from experiments.c2rag_r35_20261029_01.core import Backend

def test_milp_and_menu_small_future():
    b=read('banks.json')[1];x=Backend(b,module('engines'),module('old_planner'))
    for r in [1,2,3]:
        for seq in itertools.product(range(2),repeat=r):assert x.exact(0,seq)==x.menu(0,seq)

def test_distribution_not_future_oracle():
    b=read('banks.json')[1];x=Backend(b,module('engines'),module('old_planner'))
    assert x.dp(0,1,(F(1,2),F(1,2)))==1
    assert x.dp(0,2,(F(1,2),F(1,2)))==F(3,2)

def test_shared_persistent_union_and_risk():
    b=read('banks.json')[2];x=Backend(b,module('engines'),module('old_planner'));a=x.ids(0)[0];c=x.ids(1)[0]
    state,bad=x.g.trial((0,0,0,0),0,a);assert not bad
    _,bad=x.g.trial(state,0,c);assert bad
    _,bad=x.g.trial(state,1,c);assert bad

def test_forecast_inputs_contain_no_future_leaf():
    for p in read('forecast_packets.json'):
        assert 'actual_future' not in p and 'sequence' not in p
        assert all(len(s)==4-len(p['prefix']) for s in p['scenarios'])
