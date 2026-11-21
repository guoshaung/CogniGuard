"""Additional independent score check, including the information-relaxation counterexample."""
from fractions import Fraction as F
import itertools
from experiments.c2rag_r35_20261029_01.common import *
from experiments.c2rag_r35_20261029_01.verify import Reference

def main():
    frozen();refs={b['id']:Reference(b) for b in read('banks.json')};packets={(p['asset'],p['law'],p['error'],tuple(p['prefix'])):p for p in read('forecast_packets.json')}
    checked=0;decisions=0;counterexample=[]
    for config in read('policy_index.json'):
        if config['method'] not in ['B-Expectation','Causal-DP']:continue
        r=refs[config['asset']]
        for node in read(config['path']):
            prefix=tuple(node['prefix']);p=tuple(map(F,packets[config['asset'],config['law'],config['error'],prefix]['probability']));remaining=H-len(prefix)
            known=0
            for v in node['known_before'][:3]:known|=r.from_engine(v)
            scores={};candidates=[]
            for a in r.options(prefix[-1]):
                after=known|r.bits[a]
                if r.table[after]['recover']:continue
                value=F(a!='EMPTY')
                if config['method']=='Causal-DP':value+=r.causal(after,remaining,p)
                else:
                    for suffix in itertools.product(range(len(p)),repeat=remaining):
                        probability=F(1)
                        for qt in suffix:probability*=p[qt]
                        value+=probability*r.opt(after,suffix)[0]
                scores[a]=str(value);candidates.append(((-value,-int(a!='EMPTY'),r.cost[a],a),a));checked+=1
            assert scores=={x['id']:x['score_fraction'] for x in node['detail']['scores']}
            assert min(candidates)[1]==node['answer_id'];decisions+=1
            if config['asset']=='L4' and config['law']=='uniform' and config['error']=='0' and prefix==(1,):
                counterexample.append({'method':config['method'],'prefix':[1],'known_observations':[],
                    'independent_scores':scores,'selected_action':node['answer_id']})
    # Independently recompute the exact information-relaxation bound, not merely
    # check inequalities around the primary number.
    for bound in read('verified_information_bounds.json'):
        r=refs[bound['asset']];p=tuple(map(F,r.bank['evaluation_true_probabilities'][bound['law']]));value=F(0)
        for q,pq in enumerate(p):
            actions=[]
            for a in r.options(q):
                after=r.bits[a]
                if r.table[after]['recover']:continue
                score=F(a!='EMPTY')
                for suffix in itertools.product(range(len(p)),repeat=H-1):
                    probability=F(1)
                    for qt in suffix:probability*=p[qt]
                    score+=probability*r.opt(after,suffix)[0]
                actions.append(score)
            value+=pq*max(actions)
        assert value==F(bound['B_exact_root_information_relaxation'])
    write('independent_distribution_score_check.json',{'complete':True,'candidate_scores':checked,'decisions':decisions,
        'all_scores_and_choices_match':True,'all_10_information_bound_values_recomputed':True,'counterexample':counterexample,
        'experiment_or_truth_changed':False})
    write('FINAL_MANIFEST.sha256.json',{p.relative_to(OUT).as_posix():sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    print('Independently certified full-distribution/causal scores:',checked,'decisions:',decisions)

if __name__=='__main__':main()
